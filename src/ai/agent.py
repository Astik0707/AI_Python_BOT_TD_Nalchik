from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import json
from decimal import Decimal
from openai import AsyncOpenAI
import re

from src.db.sql import execute_sql
from src.db.pool import fetch_one
from src.utils.logger import get_logger
from src.utils.memory import get_history, append_message, clear_history
import pickle
from src.utils.formatter import build_html_from_rows
# Справочники/обогащение отключены — агент распознаёт сущности самостоятельно
import datetime
 

logger = get_logger("ai.agent")


SYSTEM_PROMPT = """Ты — интеллектуальный, точный и надёжный агент-аналитик в Telegram-боте. Работаешь с PostgreSQL-базой milk (версия 16.9), схема public.

ОПИСАНИЕ И ЦЕЛЬ
Мы — аналитический бот для Telegram. Источник данных — PostgreSQL milk.public. Задача: по естественным запросам строить корректный SQL, извлекать данные и возвращать текстовый HTML‑отчёт. Мы убрали графики и полностью исключили выдумывание чисел — только SQL и реальные строки. Основные проблемы, которые решены/учтены: путаница сущностей (менеджер/клиент/бренд/регион), забытый JOIN products/clients, отсутствие фильтра периода, забытый фильтр marker='Бонус', неверный выбор поля для фильтра по менеджеру. Ниже — строгие правила.

ЖЁСТКИЕ ПРАВИЛА
1) Для любых запросов, подразумевающих данные, ВСЕГДА формируй корректный sql_query (SELECT/WITH) к milk.public и получай данные только из БД.
2) НИКОГДА не выдумывай значения и не используй память вместо БД. Даже если вопрос похож на предыдущий — формируй новый SQL заново.
3) Если формулировка неоднозначна — задай 1–2 коротких уточняющих вопроса и только потом формируй SQL.
4) Текущая дата не передаётся. При каждом новом запросе сначала выполни:
   SELECT CURRENT_DATE AS current_date, NOW() AS current_datetime;
   Используй её для интерпретации «сегодня/вчера/эта неделя/этот месяц/последние N дней» и т.п. Не запоминай дату между запросами.
5) В запросах к profit/orders/debt/stock/managers_plan и при связке с clients ВСЕГДА исключай клиентов с marker='Бонус'.
6) Всегда добавляй ограничение по периоду (дате). Для managers_plan период — месяц в виде полуинтервала: period >= 'YYYY-MM-01' AND period < 'YYYY-MM+1-01'.
7) Если не указан год или месяц — используй текущие значения. Если указан только месяц — используй текущий год.
8) Перед построением SQL используй справочники (менеджеры/клиенты/бренды/категории/каналы/регионы). Если обнаружена неоднозначность (одно и то же слово совпало в нескольких типах), задай 1 короткий уточняющий вопрос и только после ответа формируй SQL.

Структура БД (основные):
clients(
  client_code,     -- уникальный код клиента (PK)
  client_name,     -- юридическое название клиента
  public_name,     -- торговое / отображаемое название
  region,          -- регион клиента
  manager,         -- закреплённый менеджер из справочника клиентов
  marker           -- признак (например, 'Бонус'), для фильтрации
)

products(
  product_code,      -- уникальный код товара (PK)
  product_name,      -- полное название товара
  print_name,        -- печатное / короткое название
  unit,              -- единица измерения (шт, кг и т.д.)
  type,              -- тип товара (например, молочная продукция)
  brand,             -- бренд (Чабан, Новая Деревня и др.)
  weight,            -- вес единицы товара в кг
  client_code,       -- код клиента (для private-label товаров)
  category_1,        -- категория верхнего уровня
  category_group_1,  -- укрупнённая группа категорий
  product_group      -- внутренняя товарная группа
)

orders(
  order_number,      -- номер заказа
  client_code,       -- код клиента (FK → clients)
  product_code,      -- код товара (FK → products)
  order_date,        -- дата создания заказа
  shipment_date,     -- дата отгрузки
  planned_quantity,  -- заказанное количество
  weight_kg,         -- заказанный вес в кг
  warehouse          -- склад отгрузки
)

profit(
  order_number,      -- номер заказа (связь с orders)
  client_code,       -- код клиента (FK → clients)
  product_code,      -- код товара (FK → products)
  order_date,        -- дата заказа
  profit_date,       -- дата отражения продажи / возврата
  quantity,          -- количество (шт)
  weight_kg,         -- вес (кг)
  revenue,           -- выручка (₽, отрицательная для возвратов)
  manager,           -- менеджер, оформивший продажу
  channel,           -- канал сбыта (розница, ОПТ, HoReCa и т.п.)
  warehouse          -- склад
)

debt(
  client_code,       -- код клиента (FK → clients)
  contractor,        -- юр. лицо контрагента
  payment_term,      -- срок оплаты
  manager,           -- менеджер по дебиторке
  total_debt,        -- общая задолженность
  overdue_debt,      -- просроченная задолженность
  not_overdue_debt,  -- непосроченная задолженность
  debt_date          -- дата состояния задолженности
)

stock(
  product_code,      -- код товара (FK → products)
  warehouse,         -- склад
  stock_date,        -- дата учёта остатков
  income,            -- приход
  outcome,           -- расход
  initial_quantity,  -- начальный остаток
  final_quantity     -- конечный остаток
)

purchase_prices(
  product_code,      -- код товара (FK → products)
  order_date,        -- дата заказа
  order_number,      -- номер заказа
  quantity,          -- количество закупки
  client_code,       -- код клиента (если закупка под private-label)
  price_per_unit,    -- закупочная цена за единицу
  var_rate,          -- ставка НДС (% или 'Без НДС')
  warehouse,         -- склад
  contract_type      -- тип контракта
)

sales_representatives(
  full_name,         -- ФИО менеджера
  phone,             -- телефон
  email,             -- email
  department,        -- подразделение
  user_photo         -- фото
)

managers_plan(
  period,            -- дата (всегда последнее число месяца)
  manager,           -- ФИО менеджера
  client_cod,        -- клиент, на которого ставится план
  categories,        -- список категорий (через ;)
  plan               -- план в кг
)

Ключевые связи:
- profit.product_code → products.product_code; profit.client_code → clients.client_code
- orders.product_code → products.product_code; orders.client_code → clients.client_code
- debt.client_code → clients.client_code; stock.product_code → products.product_code
- products.client_code → clients.client_code (для private-label)


Метрики и правила:
- Выручка (продажи): SUM(p.revenue) WHERE p.revenue > 0
- Возвраты: SUM(p.revenue) WHERE p.revenue < 0
- Вес: SUM(p.weight_kg)
- Количество: SUM(p.quantity) (в profit) или SUM(planned_quantity) (в orders)
- АКБ: COUNT(DISTINCT clients.client_code)
- Недогруз: GREATEST(orders.weight_kg - COALESCE(profit.weight_kg, 0), 0) при корректном JOIN по product_code, shipment_date и client_code

Периоды:
- «прошлый месяц» — предыдущий календарный месяц
- Продажи/возвраты — по profit.profit_date; плановые отгрузки — по orders.shipment_date; закупки — по purchase_prices.order_date

Группировки и связи (примеры):
- «по торговым» → GROUP BY p.manager
- «по каналам» → GROUP BY p.channel
- «по регионам» → JOIN clients c ON p.client_code=c.client_code; GROUP BY c.region
- «по продуктам» → JOIN products pr ON p.product_code=pr.product_code; GROUP BY pr.product_name
- «по брендам» → GROUP BY pr.brand
- «по категориям» → GROUP BY pr.category_1
- «по группам категорий» → GROUP BY pr.category_group_1

Сопоставление сущностей ↔ колонок (используй строго эти поля):
- Менеджер → p.manager (ILIKE '%…%')
- Регион → JOIN public.clients c; c.region (ILIKE '%…%')
- Канал → p.channel
- Бренд → JOIN public.products pr; pr.brand
- Категория → JOIN public.products pr; pr.category_1 (или pr.category_group_1)
- Клиент → JOIN public.clients c; c.client_name OR c.public_name (ILIKE '%…%')
- SKU/товар → JOIN public.products pr; pr.product_name / pr.product_code

Источник данных для продаж/возвратов (обязательно):
- Любая аналитика по продажам/выручке/возвратам/количеству/весу берётся ТОЛЬКО из public.profit p.
- Если нужны бренды/категории/товары — присоединяй public.products pr и используй pr.brand/pr.category_1/pr.product_name.
- Фильтр по менеджеру всегда по p.manager (не через clients).

Самопроверка перед выполнением SQL:
1) Если в запросе есть pr.<…> — обязательно JOIN public.products pr
2) Если есть c.<…> — обязательно JOIN public.clients c
3) Не путай manager/region/brand: менеджер фильтруется по p.manager, регион — по c.region, бренд — по pr.brand
4) Для «по брендам/категориям» — p.revenue > 0, GROUP BY pr.brand/pr.category_1
5) Контекст уточнений: если задан «тот день/тот менеджер/тот период» — используй предыдущие значения, иначе уточни 1 вопрос

Фильтр «Бонус» (обязательно):
p.client_code NOT IN (SELECT client_code FROM public.clients WHERE marker='Бонус')

Формат ответа — ВСЕГДА один JSON-объект:
{
  "output": "Человекочитаемый HTML-текст",
  "send_excel": true/false,
  "table_data": [ { ... }, ... ] | null,
  "sql_query": "SELECT ..."
}

Текстовый формат (строгие правила):
- Только HTML-разметка. Допускаются: <b>, <strong>, <i>, <em>, <u>, <ins>, <s>, <del>, <a href="...">, <code>, <pre>.
- Первая строка — заголовок: <b>Краткая формулировка отчёта</b>
- Вторая строка (если вычислён период): Период: YYYY-MM-DD — YYYY-MM-DD
- Далее — список строк по одной на категорию (или единственная строка при агрегате), формат:
  Название — 12 345 678,90 ₽
  Название — Метрика1: 12 345,67 ₽; Метрика2: −1 234,56 ₽; Метрика3: 789,00 кг
- Разделитель тысяч — пробел. Десятичный разделитель — запятая.
- Единицы: ₽ для revenue/выручка/руб; кг для weight/вес; шт для quantity/шт.
- При единственном числовом результате формируй краткий ответ, например: <b>Количество уникальных клиентов в базе — 3 175</b>
- Если применялись фильтры (бренд/регион/канал/менеджер), укажи их в шапке кратко.
- НИКОГДА не включай сам SQL в "output" (SQL — только для внутреннего выполнения/отладки).

Поведение:
- Если запрос не предполагает БД — ответь текстом.
- Если в результате SQL нет строк — сообщи об отсутствии данных и предложи отправить запрос на обучение.
- По запросу Excel (явные фразы «в excel/эксель/таблицей/отправь в excel») верни send_excel=true и table_data (текущие данные).
- Команда «новый запрос» очищает контекст.
- НИКОГДА не показывай SQL пользователю в «output». (Логи/отладка — отдельно.)

Примеры поведения:
- «динамика продаж по торговым за март» → SQL c SUM(revenue>0) по p.manager за март текущего года; output — структурированный список.
- «выгрузи это в excel Иванову» → send_excel=true, recipient=«Иванову», table_data — текущие данные.
"""

@dataclass
class AgentResult:
    output: str
    send_excel: bool
    table_data: Optional[list]
    sql_query: Optional[str]
    send_card: Optional[bool] = False
    rep_name: Optional[str] = None
    recipient: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    # Clarification flow
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    clarify_slots: Optional[list] = None
    pending_context: Optional[dict] = None
    resolved_entities: Optional[list] = None


_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    """Получить клиент OpenAI"""
    global _client
    if _client is None:
        base_url = os.getenv("OPENAI_BASE_URL")
        timeout_sec = float(os.getenv("OPENAI_TIMEOUT", "30"))
        if base_url:
            _client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=base_url, timeout=timeout_sec)
        else:
            _client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=timeout_sec)
    return _client


def is_chart_edit_command(user_text: str) -> bool:
    """Определить, является ли запрос командой редактирования графика"""
    if not user_text:
        return False
    text = user_text.lower()
    
    edit_keywords = [
        "убери легенду", "покажи легенду", "скрой легенду", "добавь легенду",
        "поменяй цвета", "измени цвета", "другие цвета", "смени цвета",
        "сделай больше", "увеличь размер", "сделай меньше", "уменьши размер",
        "добавь подписи", "убери подписи", "покажи подписи", "скрой подписи",
        "измени заголовок", "поменяй заголовок", "другой заголовок",
        "измени тип", "поменяй тип", "сделай линейный", "сделай столбчатый", "сделай круговой",
        "добавь сетку", "убери сетку", "покажи сетку", "скрой сетку",
        "измени позицию", "поменяй позицию", "легенда справа", "легенда снизу",
        "добавь ось", "убери ось", "покажи ось", "скрой ось"
    ]
    
    return any(keyword in text for keyword in edit_keywords)

def is_show_chart_command(user_text: str) -> bool:
    """Определить, является ли запрос командой показа графика"""
    if not user_text:
        return False
    text = user_text.lower()
    
    # Исключаем отрицательные команды
    if any(neg in text for neg in ["не на", "не в", "не показывай", "не отображай", "не выводи", "не на графике", "не в графике"]):
        return False
    
    show_keywords = [
        "покажи", "покажи график", "покажи диаграмму", "покажи график снова",
        "покажи еще раз", "покажи опять", "покажи снова", "покажи диаграмму снова",
        "отобрази", "отобрази график", "отобрази диаграмму", "отобрази снова",
        "выведи", "выведи график", "выведи диаграмму", "выведи снова",
        "график снова", "диаграмма снова", "на графике", "на диаграмме"
    ]
    
    return any(keyword in text for keyword in show_keywords)

def requires_database(user_text: str) -> bool:
    """Classifier: require DB only when clearly indicated by business terms/dates/numbers.
    Otherwise treat as general conversation."""
    if not user_text:
        return False
    text = (user_text or "").lower().strip()
    if len(text) <= 2:
        return False
    
    # Non-data intents where DB is not required
    non_data_patterns = [
        r"^\s*(привет|здравств|добрый|помощ|help|что ты умеешь)\b",
        r"sql(\s|$)",
        r"новый\s+запрос",
        r"отправ(ить)?\s+(карточк|excel|эксель)",
        r"^\s*[a-zA-Z]{1,3}\s*$",  # Short random letters like "ghb", "A?"
    ]
    for pat in non_data_patterns:
        if re.search(pat, text):
            return False
    
    # Data-indicative keywords
    keywords = [
        # Финансы и продажи
        "продаж", "выручк", "доход", "прибыл", "убытк", "оборот", "объем",
        "клиент", "менеджер", "торгов", "коммерц", "маркет", "сбыт",
        
        # Товары и склад
        "товар", "продукт", "бренд", "остатк", "склад", "запас", "инвентар",
        "заказ", "поставк", "логистик", "транспорт", "груз", "партия",
        
        # Долги и дебиторы
        "дебитор", "задолж", "кредитор", "долг", "оплат", "расчет",
        
        # Время и периоды
        "месяц", "квартал", "год", "период", "дата", "время", "неделя",
        "январ", "феврал", "март", "апрел", "май", "июн", "июл", "август",
        "сентябр", "октябр", "ноябр", "декабр",
        
        # Числа и единицы
        "сумм", "количеств", "вес", "кг", "шт", "руб", "₽", "акб", "тонн",
        "литр", "метр", "штук", "штука", "штуки", "штук",
        
        # Планирование и анализ
        "план", "факт", "динамик", "тренд", "рост", "падение", "изменение",
        "сравнение", "анализ", "отчет", "статистик", "показатель"
    ]
    if any(kw in text for kw in keywords):
        return True
    if re.search(r"\d{4}-\d{2}-\d{2}|\b20\d{2}\b|\b\d+[\s.,]?(₽|руб)\b", text):
        return True
    return False


# Хранилище графиков удалено

async def build_messages(text: str, chat_id: int) -> List[Dict[str, str]]:
    """Собрать сообщения с учетом памяти."""
    messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Получаем актуальную дату/время из БД и добавляем как системную подсказку
    current_date: Optional[datetime.date] = None
    try:
        now_row = await fetch_one("SELECT CURRENT_DATE AS current_date, NOW() AS current_datetime;")
        if now_row:
            messages.append({
                "role": "system",
                "content": f"Текущая дата и время из БД: current_date={now_row.get('current_date')}, current_datetime={now_row.get('current_datetime')}"
            })
            try:
                # asyncpg returns date directly as date; but keep safe conversion
                cd = now_row.get('current_date')
                if isinstance(cd, datetime.date):
                    current_date = cd
                else:
                    current_date = datetime.date.fromisoformat(str(cd))
            except Exception:
                current_date = None
    except Exception:
        pass

    if "новый запрос" in (text or "").lower():
        await clear_history(chat_id)
    else:
        history = await get_history(chat_id, limit=8)
        messages.extend(history)

    # Без справочников: отправляем исходный текст
    messages.append({"role": "user", "content": text or ""})
    return messages


async def run_ai_for_text(*, chat_id: int, user_id: Optional[int], user_name: Optional[str], text: str) -> AgentResult:
    """Запустить AI для обработки текста"""
    client = get_client()
    model = os.environ.get("OPENAI_MODEL_CHAT", "gpt-4.1")
    current_date: Optional[datetime.date] = None  # используется для эвристики будущих периодов

    if not text or not text.strip():
        return AgentResult(
            output="Пожалуйста, введите текст для обработки.",
            send_excel=False,
            table_data=None,
            sql_query=None
        )

    # Обработка графиков отключена

    need_db = requires_database(text)

    # Без доуточнялок на уровне кода: всё решает промпт

    # Сборка сообщений с историей (память включена всегда)
    messages = await build_messages(text, chat_id)

    # Первый вызов
    try:
        # Жёстко требуем структурированный JSON на первом проходе
        messages_with_enforcer = messages + [{
            "role": "system",
            "content": "Если нужна БД — ОБЯЗАТЕЛЬНО верни sql_query в JSON. Не добавляй лишних полей."
        }]
        resp = await client.chat.completions.create(
            model=model,
            messages=messages_with_enforcer,
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        content = resp.choices[0].message.content if resp.choices else "{}"
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        content = '{"output": "Извините, AI-сервис временно недоступен. Попробуйте позже.", "send_excel": false, "table_data": null, "sql_query": null}'

    try:
        data = json.loads(content or "{}")
    except Exception as e:
        logger.error(f"JSON parsing error: {e}")
        data = {}

    # Нормализуем контракт; если текст выглядит как короткий вопрос подтверждения, не инициируем DB
    output: str = str(data.get("output") or "")
    if (not data.get("sql_query")):
        short = (output or "").strip().lower()
        if 0 < len(short) <= 40 and re.search(r"\b(это|те|да|нет|общие|детал|верно|правильно)\b", short):
            need_db = False
    # Поля графиков удалены
    send_excel: bool = bool(data.get("send_excel") or False)
    table_data = data.get("table_data") if isinstance(data.get("table_data"), list) else None
    sql_query: Optional[str] = data.get("sql_query") or None
    send_card: Optional[bool] = bool(data.get("send_card")) if "send_card" in data else False
    rep_name: Optional[str] = data.get("rep_name") or None
    recipient: Optional[str] = data.get("recipient") or None
    subject: Optional[str] = data.get("subject") or None
    body: Optional[str] = data.get("body") or None

    # Игнорируем поля уточнений, даже если модель вернула их

    # Если БД требуется, а sql_query нет и нет запроса на уточнение — строгие повторы
    if need_db and not sql_query:
        for attempt in range(1, 6):
            logger.warning(f"🚨 SQL REQUIRED BUT MISSING — STRICT RETRY #{attempt}")
            strict_messages = messages + [{
                "role": "system",
                "content": "ТВОЯ ЗАДАЧА — СФОРМИРОВАТЬ СТРОГО ТОЛЬКО ПОЛЕ sql_query ДЛЯ ВЫПОЛНЕНИЯ В PostgreSQL по запросу пользователя. Верни JSON с полем sql_query и ничего не выдумывай."
            }]
            try:
                r = await client.chat.completions.create(
                    model=model,
                    messages=strict_messages,
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )
                d = json.loads((r.choices[0].message.content if r.choices else "{}") or "{}")
                if isinstance(d.get("sql_query"), str) and d.get("sql_query").strip():
                    sql_query = d.get("sql_query").strip()
                    logger.info("✅ STRICT RETRY produced sql_query")
                    break
            except Exception as e:
                logger.error(f"Strict retry error: {e}")

    # Если после строгих повторов sql_query всё ещё нет — завершаем без выдумки
    if need_db and not sql_query:
        return AgentResult(
            output=(
                "<b>Нужен SQL-запрос для получения данных, но сформировать его не удалось.</b>\n"
                "Уточните, пожалуйста, период, метрику и фильтры (бренд/менеджер/регион и т.п.)."
            ),
            send_excel=False,
            table_data=None,
            sql_query=None,
        )

    # Если есть sql_query — выполняем БД
    if sql_query:
        logger.info(f"🔍 AI DECIDED TO QUERY DATABASE")
        logger.info(f"🔍 SQL QUERY FROM AI: {str(sql_query)[:400]}{'...' if len(str(sql_query)) > 400 else ''}")
        # Больше не вмешиваемся в фильтры брендов: агент сам принимает решение
        sanitized_sql = sql_query
        # Нормализация частых ошибок сопоставления полей: manager должен быть p.manager
        try:
            # Заменяем c.manager/clients.manager в WHERE/SELECT на p.manager, не трогая алиасов в JOIN
            sanitized_sql = re.sub(r"\b(c|clients)\.manager\b", "p.manager", sanitized_sql, flags=re.IGNORECASE)
        except Exception:
            pass
        # В режиме clarify, если есть resolved_entities менеджера — усиливаем равенство вместо ILIKE
        # Убираем логику привязки к resolved_entities и local resolve — только промпт

        # Больше не удаляем фильтры по p.manager эвристикой — полагаемся на намерение пользователя/модель
        # Вместо этого перед выполнением валидируем ILIKE по менеджеру

        # Предвалидация фильтра по менеджеру: если ILIKE не находит совпадений — возвращаем понятное сообщение;
        # если найден ровно один уникальный менеджер — усиливаем равенство p.manager = 'ФИО'
        try:
            m = re.search(r"p\.manager\s+ILIKE\s+'%([^']+)%'", sanitized_sql, flags=re.IGNORECASE)
            if m:
                token = m.group(1)
                row_cnt = await fetch_one("SELECT COUNT(DISTINCT manager) AS cnt FROM public.profit WHERE manager ILIKE $1;", (f"%{token}%",))
                cnt = int(row_cnt.get('cnt') if row_cnt and row_cnt.get('cnt') is not None else 0)
                if cnt == 0:
                    return AgentResult(
                        output=f"<b>Не нашёл менеджера: {token}</b>",
                        send_excel=False,
                        table_data=[],
                        sql_query=None,
                    )
                if cnt == 1:
                    row_name = await fetch_one("SELECT manager FROM (SELECT DISTINCT manager FROM public.profit WHERE manager ILIKE $1) t LIMIT 1;", (f"%{token}%",))
                    if row_name and row_name.get('manager'):
                        full_name = str(row_name.get('manager')).replace("'", "''")
                        sanitized_sql = re.sub(
                            r"p\.manager\s+ILIKE\s+'%[^']+%'",
                            f"p.manager = '{full_name}'",
                            sanitized_sql,
                            flags=re.IGNORECASE,
                        )
        except Exception:
            pass
        try:
            # Если это не бизнес-запрос (small talk) — игнорируем даже если модель вернула sql_query
            if not need_db:
                sql_query = None
                raise RuntimeError("Conversation message — skipping DB execution")

            logger.info(f"🚀 CALLING DATABASE WITH SQL QUERY...")
            rows = await execute_sql(sanitized_sql)
            logger.info(f"✅ DATABASE RESPONSE: {len(rows) if isinstance(rows, List) else 'unknown'} rows received")
            table_data = rows

            # Нет данных — быстрый ответ без второго прохода
            if not rows:
                # Нет данных — сообщаем и предлагаем обучение
                return AgentResult(
                    output=(
                        "<b>Нет данных по заданным условиям.</b>\n"
                        "Могу отправить запрос на обучение, чтобы улучшить ответы?"
                    ),
                    send_excel=False,
                    table_data=[],
                    sql_query=sql_query,
                )
            # Формируем строгий HTML-ответ ТОЛЬКО из данных БД (без участия AI-текста)
            # 2-й проход (опционально): просим ИИ красиво отформатировать ТЕ ЖЕ rows
            ai_formatted_output: Optional[str] = None
            try:
                if os.getenv("ANALYZE_WITH_AI_SECOND_PASS", "0") == "1":
                    # Подготавливаем компактный JSON данных без Decimal/дат
                    compact: List[Dict[str, Any]] = []
                    for row in rows[:30]:
                        c: Dict[str, Any] = {}
                        for k, v in row.items():
                            if isinstance(v, Decimal):
                                c[k] = float(v)
                            elif isinstance(v, datetime.date):
                                c[k] = v.isoformat()
                            else:
                                c[k] = v
                        compact.append(c)
                    data_json = json.dumps(compact, ensure_ascii=False)

                    format_prompt = (
                        "Сформируй СТРОГО HTML по правилам: первая строка — <b>краткий заголовок</b>; "
                        "вторая строка при наличии — 'Период: YYYY-MM-DD — YYYY-MM-DD'; далее по строке: "
                        "<b>Название</b> — 12 345 678,90 ₽ (или кг/шт). Числа: пробелы как разделитель тысяч, запятая — десятичная. "
                        "НЕ добавляй SQL, не выдумывай числа, используй ТОЛЬКО эти rows."
                    )
                    r2 = await client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": format_prompt + " Отвечай строго на русском языке. Верни JSON-объект с полем 'output'."},
                            {"role": "user", "content": "json:\n" + data_json},
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.1,
                    )
                    d2 = json.loads((r2.choices[0].message.content if r2.choices else "{}") or "{}")
                    if isinstance(d2.get("output"), str):
                        ai_formatted_output = d2["output"].strip()
            except Exception as e:
                logger.error(f"AI second-pass formatting error: {e}")

            def _valid_html(s: Optional[str]) -> bool:
                if not s:
                    return False
                if not s.strip().startswith("<b>"):
                    return False
                if not re.search(r"\n", s):
                    return False
                if not re.search(r"\n.+\s—\s", s):
                    return False
                return True

            if _valid_html(ai_formatted_output):
                output = ai_formatted_output
            else:
                # Фолбэк: локальное форматирование из полученных rows
                existing_title = None
                if output and output.strip().startswith("<b>"):
                    first_line = (output.strip().split("\n", 1)[0] or "").strip()
                    if first_line.endswith("</b>"):
                        existing_title = first_line
                if not existing_title:
                    safe_title = (text or "").strip().rstrip(':')
                    if safe_title:
                        existing_title = f"<b>{safe_title[0].upper() + safe_title[1:]}</b>"
                output = build_html_from_rows(rows, existing_title)
        except Exception as e:
            logger.error(f"SQL execution error: {e}")
            output = output or "<b>Пока не могу получить данные из базы.</b>"
    else:
        logger.info("❌ AI DID NOT PROVIDE SQL_QUERY - NO DATABASE ACCESS")
        logger.info("❌ AI RESPONSE TYPE: General conversation (no data query)")

    # Нормализация шапки и выделений для читабельности; избегаем лишних заголовков при коротких подтверждениях
    try:
        if output:
            lines = (output or "").splitlines()
            if lines:
                first = lines[0].strip()
                if first.startswith("<b>") and first.endswith("</b>") and "Период:" in first:
                    inner = first[3:-4].strip()
                    if "Период:" in inner:
                        t, p = inner.split("Период:", 1)
                        lines[0] = f"<b>{t.strip()}</b>"
                        lines.insert(1, f"Период: {p.strip()}")
                # Жирным названия категорий (часть до « — »), не затрагивая заголовок и строку периода
                start_idx = 1
                if len(lines) > 1 and lines[1].strip().startswith("Период:"):
                    start_idx = 2
                for i in range(start_idx, len(lines)):
                    if " — " in lines[i]:
                        name, rest = lines[i].split(" — ", 1)
                        if not name.strip().startswith("<b>"):
                            lines[i] = f"<b>{name.strip()}</b> — {rest}"
            output = "\n".join(lines)
    except Exception:
        pass

    # Память (всегда) — сохраняем краткий обмен
    try:
        await append_message(chat_id, "user", text)
        if output:
            await append_message(chat_id, "assistant", output)
    except Exception as e:
        logger.error(f"Memory append error: {e}")

    return AgentResult(
        output=output or "",
        send_excel=send_excel,
        table_data=table_data,
        sql_query=sql_query,
        send_card=send_card,
        rep_name=rep_name,
        recipient=recipient,
        subject=subject,
        body=body,
    )


async def process_chart_edit(chat_id: int, text: str, saved_config: Dict[str, Any]) -> AgentResult:
    """Обработать команду редактирования графика"""
    client = get_client()
    model = os.environ.get("OPENAI_MODEL_CHAT", "gpt-4.1")
    
    # Создаем промпт для редактирования
    edit_prompt = f"""
Ты должен отредактировать конфигурацию графика Chart.js согласно команде пользователя.

ТЕКУЩАЯ КОНФИГУРАЦИЯ:
{json.dumps(saved_config, ensure_ascii=False, indent=2)}

КОМАНДА ПОЛЬЗОВАТЕЛЯ: {text}

ПРАВИЛА РЕДАКТИРОВАНИЯ:
- "убери легенду" → "legend": {{"display": false}}
- "покажи легенду" → "legend": {{"display": true}}
- "поменяй цвета" → используй другие цвета в backgroundColor/borderColor
- "сделай больше" / "больше" / "увеличи" → добавь "width": 1000, "height": 800 в корень конфигурации
- "сделай меньше" / "меньше" / "уменьши" → добавь "width": 600, "height": 400 в корень конфигурации
- "добавь подписи" → "datalabels": {{"display": true}}
- "убери подписи" → "datalabels": {{"display": false}}
- "измени заголовок на X" → "title": {{"text": "X"}}
- "сделай линейный" → "type": "line"
- "сделай столбчатый" → "type": "bar"
- "сделай круговой" → "type": "pie"

Верни ТОЛЬКО обновленную конфигурацию в формате JSON без дополнительного текста.
"""

    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": edit_prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        content = resp.choices[0].message.content if resp.choices else "{}"
        updated_config = json.loads(content or "{}")
        
        # Сохраняем обновленную конфигурацию
        save_chart_config(chat_id, updated_config)
        
        return AgentResult(
            output="",  # Пустой текст - только график
            direct_chart=True,
            chart=updated_config,
            send_excel=False,
            table_data=[],
            sql_query=None,
        )
    except Exception as e:
        logger.error(f"Chart edit error: {e}")
        return AgentResult(
            output="<b>Ошибка при редактировании графика.</b> Попробуйте еще раз.",
            direct_chart=False,
            chart=None,
            send_excel=False,
            table_data=[],
            sql_query=None,
        )

