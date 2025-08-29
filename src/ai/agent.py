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
import datetime

logger = get_logger("ai.agent")

SYSTEM_PROMPT = """Ты — интеллектуальный, точный и надёжный агент-аналитик, встроенный в Telegram-бота. Работаешь с PostgreSQL-базой данных milk (версия 16.9), схема public.

🚨 КРИТИЧЕСКИ ВАЖНОЕ ПРАВИЛО - 100% ГАРАНТИЯ ОБРАЩЕНИЯ К БАЗЕ:
1) ВСЕГДА формируй sql_query для ЛЮБОГО запроса, который подразумевает данные
2) НЕ ВЫДУМЫВАТЬ ДАННЫЕ - брать ТОЛЬКО из БД
3) НЕ ИСПОЛЬЗОВАТЬ данные из памяти (Redis) - ВСЕГДА свежий запрос к БД
4) Даже если тот же запрос был в предыдущем сообщении - ВСЕГДА новый SQL
5) Если запрос касается продаж, выручки, клиентов, товаров, остатков - ОБЯЗАТЕЛЬНО sql_query
6) НЕ ОТВЕЧАТЬ без sql_query для запросов с данными

❗️Сегодняшняя дата не передаётся напрямую. Чтобы её узнать — делай SQL-запрос:
SELECT CURRENT_DATE AS current_date, NOW() AS current_datetime;
Используй результат как текущую дату и время. Не запоминай их, а запрашивай при каждом новом вопросе.
Используй её при интерпретации слов «сегодня», «сейчас», «за последние дни», «на этой неделе», «в этом месяце» и т.д.

📌 Твоя задача:
🚨 100% ГАРАНТИЯ ОБРАЩЕНИЯ К БАЗЕ ДАННЫХ:
- Понимать смысл пользовательских запросов на русском языке
- ВСЕГДА формировать SQL-запрос для любых данных
- НЕ ИСПОЛЬЗОВАТЬ данные из памяти (Redis)
- НЕ ВЫДУМЫВАТЬ данные - брать ТОЛЬКО из БД
- ВСЕГДА свежий запрос к БД, даже для повторяющихся вопросов

📋 ОБЯЗАТЕЛЬНЫЕ СЛУЧАИ ДЛЯ SQL_QUERY:
- Продажи, выручка, доходы
- Клиенты, менеджеры, торговые представители
- Товары, продукты, бренды
- Остатки, складские запасы
- Заказы, поставки
- Дебиторская задолженность
- Любые числовые данные
- Любые списки из БД

❌ ЗАПРЕЩЕНО:
- Отвечать без sql_query для запросов с данными
- Использовать данные из памяти
- Выдумывать числа или имена
- Показывать "примеры" вместо реальных данных

✅ РАЗРЕШЕНО БЕЗ SQL:
- Приветствия, прощания
- Общие вопросы о работе бота
- Запросы на показ SQL-кода
- Запросы на отправку Excel/карточек

📦 Структура базы данных:

clients(справочник клиентов) — client_code, client_name, public_name, region, manager, is_client, is_supplier, legal_type, registration_date,marker  
products(справочник продукции) — product_code, product_name, print_name, unit, type, brand, weight, client_code, category_1, category_group_1, product_group  
orders(заказы) — order_number, client_code, product_code, order_date, shipment_date, planned_quantity, weight_kg, warehouse  
profit(продажи и возвраты) — order_number, client_code, product_code, order_date, profit_date, quantity, weight_kg, revenue, manager, channel, warehouse  
debt(дебиторка) — client_code, contractor, payment_term, manager, total_debt, overdue_debt, not_overdue_debt, debt_date  
stock(остатки) — product_code, warehouse, stock_date, income, outcome, initial_quantity, final_quantity  
purchase_prices(закупки) - product_code, order_date, order_number, quantity, client_code, price_per_unit, var_rate(столбец где содержится процент НДС или текст \"Без НДС\"), warehouse, contract_type
sales_representatives (справочник менеджеров) - full_name, phone, email, department,user_photo (фото менеджера)
managers_plan (план продаж в кг.)— period (период имеется ввиду месяц на который устанавливается план),manager,client_code,categories,plan

Связи между таблицами:

profit.product_code → products.product_code → purchase_prices.product_code 
profit.client_code → clients.client_code  
orders.product_code → products.product_code  
orders.client_code → clients.client_code  
debt.client_code → clients.client_code  
stock.product_code → products.product_code  
products.client_code → clients.client_code (если private-label)

🔒 ВАЖНОЕ ПРАВИЛО
Во всех SQL-запросах, где используется таблица profit, orders, debt, stock или любая таблица, связанная с клиентами, обязательно исключай клиентов, у которых в таблице clients поле marker = Бонус.
Это условие фильтрации добавляется в каждый такой запрос:

client_code NOT IN (SELECT client_code FROM clients WHERE marker = Бонус)
Даже если клиент не явно упоминается, но используется таблица profit, orders, debt, stock или managers_plan, ты обязан добавить этот фильтр.
Это обязательное правило для любого запроса, даже если фильтрация выглядит необязательной.
Нельзя его игнорировать.

📊 Основные метрики и контрольные источники:
Поле period в таблице managers_plan — это тип DATE, всегда указывай период в формате диапазона дат: >= YYYY-MM-01 и < YYYY-MM+1-01. Не сравнивай period = 2025-05, это некорректно
продажи или выручка → SUM(p.revenue) WHERE p.revenue > 0   (p - profit) 
возвраты → SUM(p.revenue) WHERE p.revenue < 0  
вес → SUM(weight_kg)  
количество → SUM(quantity) (в profit) или SUM(planned_quantity) (в orders)  
недогруз → GREATEST(orders.weight_kg - COALESCE(profit.weight_kg, 0), 0) — при JOIN по product_code, shipment_date и client_code
АКБ - Количество уникальных клиентов-Пример: SELECT COUNT(DISTINCT clients.client_code)
Контрольные отчёты: использовать агрегированные представления/функции вашей БД, например: plan_perf_manager_reports, service_level_reports (day/MTD), product_abcxyz, get_control_anomalies(<date>).

📝 Формат ответа:
Всегда возвращай один JSON-объект с полями:

{
  \"output\": \"Человекочитаемый текст\",
  \"direct_chart\": true/false,
  \"chart\": {...} или null,
  \"send_excel\": true/false,
  \"table_data\": [...] или null,
  \"sql_query\": созданный запрос,Прописывай всегда
}

📊 ФОРМАТ ГРАФИКА (Chart.js):
❗️ ВАЖНО: Создавай графики ТОЛЬКО если пользователь ЯВНО просит график/диаграмму/линейный/столбчатый/круговая!
НЕ создавай графики автоматически для обычных запросов данных.

ЯВНЫЕ ЗАПРОСЫ ГРАФИКОВ:
- "на графике покажи" / "на диаграмме покажи" - создай график на основе последних данных
- "сделай график" / "создай диаграмму" - создай график
- "линейный график" / "столбчатая диаграмма" - создай график указанного типа
- "покажи график" / "отобрази диаграмму" - покажи сохраненный график

Если пользователь ЯВНО просит график/диаграмму/линейный/столбчатый/круговая — заполни поле chart в формате Chart.js:

{
  \"type\": \"line|bar|barh|pie|doughnut|scatter\",
  \"data\": {
    \"labels\": [\"Январь 2025\", \"Февраль 2025\", \"Март 2025\"],
    \"datasets\": [
      {
        \"label\": \"Выручка\",
        \"data\": [8956617.99, 10041366.98, 10358562.52],
        \"backgroundColor\": \"rgba(54, 162, 235, 0.2)\",
        \"borderColor\": \"rgba(54, 162, 235, 1)\"
      }
    ]
  },
  \"options\": {
    \"plugins\": {
      \"title\": {
        \"text\": \"Динамика продаж за 1 квартал 2025\"
      },
      \"legend\": {
        \"display\": true,
        \"position\": \"top\"
      },
      \"datalabels\": {
        \"display\": true
      }
    }
  }
}

❗️ ПРАВИЛА ГРАФИКОВ:
- Создавай графики ТОЛЬКО при ЯВНОМ запросе пользователя
- НЕ создавай графики для обычных запросов данных (списки, таблицы)
- type: \"line\" для динамики/трендов, \"bar\" для сравнения, \"pie\" для долей
- labels: подписи по оси X (месяцы, менеджеры, бренды)
- datasets[].data: числовые значения из БД
- datasets[].label: название ряда данных
- title.text: описательный заголовок графика
- Используй реальные данные из БД, не выдумывай

❌ НЕ СОЗДАВАЙ ГРАФИКИ для:
- Обычных запросов данных (\"покажи продажи\", \"список клиентов\")
- Запросов без явного упоминания графика/диаграммы
- Простых списков и таблиц

🔄 РЕДАКТИРОВАНИЕ ГРАФИКОВ:
Если пользователь просит изменить существующий график (\"убери легенду\", \"поменяй цвета\", \"сделай больше\", \"добавь подписи\" и т.д.):
1. Сохрани текущую конфигурацию графика в памяти
2. Примени изменения к options или datasets
3. Верни обновленную конфигурацию

Примеры команд редактирования:
- \"убери легенду\" → \"legend\": {\"display\": false}
- \"покажи легенду\" → \"legend\": {\"display\": true}
- \"поменяй цвета\" → используй другие цвета в backgroundColor/borderColor
- \"сделай больше\" → увеличь размеры в options
- \"добавь подписи\" → \"datalabels\": {\"display\": true}
- \"убери подписи\" → \"datalabels\": {\"display\": false}
- \"измени заголовок на X\" → \"title\": {\"text\": \"X\"}

❗️ КРИТИЧЕСКИ ВАЖНО для поля output:
Если запрос требует данных из БД — НЕ ПИШИ общие описания типа "Показаны суммы выручки по каждому торговому представителю". 
ВМЕСТО ЭТОГО:
1. Выполни SQL-запрос
2. Проанализируй полученные данные
3. Представь их в виде структурированного списка

Пример правильного ответа:
<b>Продажи по торговым представителям за март 2025</b>

Иванов И.И. — 1 234 567,89 ₽
Петров П.П. — 987 654,32 ₽
Сидоров С.С. — 543 210,00 ₽

Если пользователь просит «скинь sql запрос» или «покажи sql», обязательно заполни поле output текстом, укажи, что это SQL-запрос, и покажи его.

Если пользователь просит Excel — обязательно верни `\"table_data\"` — массив объектов (одна строка = один объект). Это используется для генерации Excel.

Формат текстового ответа:
📌 ВАЖНО: ВСЕ ВЫДЕЛЕНИЯ ДОЛЖНЫ БЫТЬ В ФОРМАТЕ HTML.  
НЕ ИСПОЛЬЗУЙ `**звёздочки**`, Markdown или другие формы.  
ВСЕ ЖИРНЫЕ ВЫДЕЛЕНИЯ — ЧЕРЕЗ <b>ТЕГИ</b>.
Используй только следующие выделения:<b>, <strong>, <i>, <em>, <u>, <ins>, <s>, <strike>, <del>,
<span class=\"tg-spoiler\">, <tg-spoiler>, <a href=\"...\">, <code>, <pre>
Больше никаких

❗️ КРИТИЧЕСКИ ВАЖНО для поля output:
Если запрос требует данных из БД — НЕ ПИШИ общие описания типа "Показаны суммы выручки по каждому торговому представителю" или "Данные по продажам".

ВМЕСТО этого анализируй полученные данные и представляй их в виде красивого структурированного списка:

<b>Продажи по торговым представителям за март 2025</b>

Балахов Алим Юрьевич — 24 923 684,84 ₽
Петров Петр Петрович — 18 765 432,10 ₽
Сидоров Сидор Сидорович — 12 345 678,90 ₽

❗️ ПРАВИЛА ФОРМАТИРОВАНИЯ (ОБЯЗАТЕЛЬНО):
1. Заголовок: ВСЕГДА используй <b>ТЕКСТ</b> (жирный через HTML-теги)
2. Разделитель тысяч: пробел (24 923 684)
3. Десятичная: запятая (684,84)
4. Единицы измерения: ₽ для revenue, кг для weight_kg, шт для quantity
5. Разделитель между именем и суммой: длинное тире (—)
6. Каждая строка с новой строки
7. НЕ добавляй лишние слова типа "Итого", "Всего" и т.д.
8. НЕ используй обычный текст для заголовков - ТОЛЬКО HTML-теги <b>

❗️ НЕ ВЫДУМЫВАЙ данные — используй ТОЛЬКО то, что получил из БД!

Если пользователь просит \"покажи карточку\", \"карточка\", \"карточку торгового\", \"информация о торговом\", то:
- Обратись к базе к таблице managers_plan и через ILIKE определи ФИО торгового представителя (например: \"Альборов Феликс Олегович\").
- Верни JSON:
  {
    \"send_card\": true,
    \"rep_name\": \"<ФИО торгового представителя>\"
  }
- Не передавай это в LangChain, просто сгенерируй JSON.
-Если пользователь просит все карточки разом (фразы: \"все карточки\", \"все торговые\", \"карточки всех\"), 
верни JSON: { \"send_card\": true, \"rep_name\": \"all\" }.

📨 MAIL EXCEL (фразы вида: \"отправь это в эксель/в excel/таблицей … <кому>\"):
- В ЭТОМ СЛУЧАЕ НЕ ВЫЗЫВАЙ SendMailWorkflow напрямую.
- Верни один JSON (без обёрток) с полями:
{
  \"output\": \"<краткое подтверждение>\",
  \"send_excel\": true,
  \"excel\": { \"filename\": \"<имя>.xlsx\", \"sheet\": \"Данные\" },
  \"table_data\": [ { ... }, ... ],
  \"recipient\": \"<строка как у пользователя>\",
  \"subject\": \"<или Без
темы>",
  "body": "<или ''>",
  "sql_query": "<schema-qualified SQL к источнику данных>"
}
- Данные формируй по текущему запросу пользователя (те же фильтры/период).
- Исключай клиентов marker='Бонус' (если применимо).

Ты — деловой SQL-аналитик, а не чат-бот. Работай строго с тем, что реально содержится в базе milk (схема public). Сейчас 2025 год — ориентируйся на актуальные данные.
"""

@dataclass
class AgentResult:
    output: str
    direct_chart: bool
    chart: Optional[Dict[str, Any]]
    send_excel: bool
    table_data: Optional[list]
    sql_query: Optional[str]
    send_card: Optional[bool] = False
    rep_name: Optional[str] = None
    recipient: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None


_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    """Получить клиент OpenAI"""
    global _client
    if _client is None:
        base_url = os.getenv("OPENAI_BASE_URL")
        timeout_sec = float(os.getenv("OPENAI_TIMEOUT", "15"))
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
    """Heuristic classifier: does this request require DB data?
    We bias towards True to avoid hallucinations. Memory is still used for context.
    """
    if not user_text:
        return False
    text = user_text.lower()
    
    # Short/nonsense messages that don't need DB
    if len(text.strip()) <= 3:
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
        "продаж", "выручк", "доход", "клиент", "менеджер", "торгов", "товар",
        "продукт", "бренд", "остатк", "склад", "заказ", "поставк", "дебитор",
        "задолж", "месяц", "квартал", "год", "период", "сумм", "количеств",
        "вес", "кг", "шт", "руб", "₽", "акб", "план", "факт", "динамик"
    ]
    if any(kw in text for kw in keywords):
        return True
    
    # Numbers or dates often indicate data needs
    if re.search(r"\d{4}-\d{2}-\d{2}|\b20\d{2}\b|\b\d+[\s.,]?(₽|руб)\b", text):
        return True
    
    # If text is too short/random, don't require DB
    if len(text.strip()) < 5:
        return False
        
    return True  # default to requiring DB to be safe


# Простое хранилище для конфигураций графиков (в памяти)
_chart_memory: Dict[int, Dict[str, Any]] = {}

def save_chart_config(chat_id: int, config: Dict[str, Any]) -> None:
    """Сохранить конфигурацию графика для чата"""
    _chart_memory[chat_id] = config.copy()

def get_chart_config(chat_id: int) -> Optional[Dict[str, Any]]:
    """Получить сохраненную конфигурацию графика для чата"""
    return _chart_memory.get(chat_id)

def clear_chart_config(chat_id: int) -> None:
    """Очистить сохраненную конфигурацию графика для чата"""
    _chart_memory.pop(chat_id, None)

async def build_messages(chat_id: int, text: str) -> List[Dict[str, str]]:
    """Собрать сообщения с учетом памяти (всегда используем память)."""
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

    messages.append({"role": "user", "content": text or ""})
    return messages


async def run_ai_for_text(*, chat_id: int, user_id: Optional[int], user_name: Optional[str], text: str) -> AgentResult:
    """Запустить AI для обработки текста"""
    client = get_client()
    model = os.environ.get("OPENAI_MODEL_CHAT", "gpt-4.1")

    if not text or not text.strip():
        return AgentResult(
            output="Пожалуйста, введите текст для обработки.",
            direct_chart=False,
            chart=None,
            send_excel=False,
            table_data=None,
            sql_query=None
        )

    # Проверяем, является ли это командой показа графика
    if is_show_chart_command(text):
        # Если это "на графике покажи" - создаем новый график
        if "на графике" in text.lower() or "на диаграмме" in text.lower():
            logger.info(f"📊 CREATE CHART COMMAND: {text}")
            # Продолжаем обработку как обычный запрос, но с флагом создания графика
            need_db = True
        else:
            # Это команда показа существующего графика
            saved_config = get_chart_config(chat_id)
            if saved_config:
                logger.info(f"📊 SHOW CHART COMMAND: {text}")
                return AgentResult(
                    output="<b>Вот ваш график!</b>",
                    direct_chart=True,
                    chart=saved_config,
                    send_excel=False,
                    table_data=[],
                    sql_query=None,
                )
            else:
                # Нет сохраненного графика для показа
                return AgentResult(
                    output="<b>Нет сохраненного графика.</b> Сначала создайте график, а затем используйте команды показа.",
                    direct_chart=False,
                    chart=None,
                    send_excel=False,
                    table_data=[],
                    sql_query=None,
                )

    # Проверяем, является ли это командой редактирования графика
    if is_chart_edit_command(text):
        saved_config = get_chart_config(chat_id)
        if saved_config:
            # Это команда редактирования существующего графика
            logger.info(f"🔄 CHART EDIT COMMAND: {text}")
            return await process_chart_edit(chat_id, text, saved_config)
        else:
            # Нет сохраненного графика для редактирования
            return AgentResult(
                output="<b>Нет графика для редактирования.</b> Сначала создайте график, а затем используйте команды редактирования.",
                direct_chart=False,
                chart=None,
                send_excel=False,
                table_data=[],
                sql_query=None,
            )

    need_db = requires_database(text)

    # Сборка сообщений с историей (память включена всегда)
    messages = await build_messages(chat_id, text)

    # Первый вызов
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = resp.choices[0].message.content if resp.choices else "{}"
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        content = '{"output": "Извините, AI-сервис временно недоступен. Попробуйте позже.", "direct_chart": false, "chart": null, "send_excel": false, "table_data": null, "sql_query": null}'

    try:
        data = json.loads(content or "{}")
    except Exception as e:
        logger.error(f"JSON parsing error: {e}")
        data = {}

    # Нормализуем контракт
    output: str = str(data.get("output") or "")
    direct_chart: bool = bool(data.get("direct_chart") or False)
    chart: Optional[Dict[str, Any]] = data.get("chart") if isinstance(data.get("chart"), dict) else None
    send_excel: bool = bool(data.get("send_excel") or False)
    table_data = data.get("table_data") if isinstance(data.get("table_data"), list) else None
    sql_query: Optional[str] = data.get("sql_query") or None
    send_card: Optional[bool] = bool(data.get("send_card")) if "send_card" in data else False
    rep_name: Optional[str] = data.get("rep_name") or None
    recipient: Optional[str] = data.get("recipient") or None
    subject: Optional[str] = data.get("subject") or None
    body: Optional[str] = data.get("body") or None

    # Если БД требуется, а sql_query нет — несколько строгих повторов
    if need_db and not sql_query:
        for attempt in range(1, 4):
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
            direct_chart=False,
            chart=None,
            send_excel=False,
            table_data=None,
            sql_query=None,
        )

    # Если есть sql_query — выполняем БД
    if sql_query:
        logger.info(f"🔍 AI DECIDED TO QUERY DATABASE")
        logger.info(f"🔍 SQL QUERY FROM AI: {str(sql_query)[:400]}{'...' if len(str(sql_query)) > 400 else ''}")
        try:
            logger.info(f"🚀 CALLING DATABASE WITH SQL QUERY...")
            rows = await execute_sql(sql_query)
            logger.info(f"✅ DATABASE RESPONSE: {len(rows) if isinstance(rows, List) else 'unknown'} rows received")
            table_data = rows

            # Нет данных — быстрый ответ без второго прохода
            if not rows:
                # Определяем, не запрошен ли будущий период
                future_msg = None
                try:
                    txt = (text or "").lower()
                    # Простые эвристики будущего периода
                    future_keywords = [
                        "следующ", "в будущем", "через", "в следующем месяце", "в следующем квартале", "в следующем году"
                    ]
                    looks_future = any(k in txt for k in future_keywords)
                    # Поиск шаблонов дат YYYY-MM(-DD) и сравнение с current_date
                    if current_date is not None:
                        m = re.findall(r"(20\\d{2})-(0[1-9]|1[0-2])(?:-(0[1-9]|[12]\\d|3[01]))?", txt)
                        for y, mo, dd in m:
                            yy = int(y); mm = int(mo); dd_i = int(dd) if dd else 1
                            dt = datetime.date(yy, mm, dd_i)
                            if dt > current_date:
                                looks_future = True
                                break
                    if looks_future:
                        future_msg = "<b>Запрошенный период ещё не наступил.</b>"
                except Exception:
                    future_msg = None

                return AgentResult(
                    output=future_msg or "<b>Нет данных по заданным условиям.</b>",
                    direct_chart=False,
                    chart=None,
                    send_excel=False,
                    table_data=[],
                    sql_query=sql_query,
                )
            # Второй проход: анализ реальных данных (как ранее)
            try:
                formatted_data = []
                for row in rows[:10]:
                    formatted_row = {}
                    for k, v in row.items():
                        if isinstance(v, Decimal):
                            formatted_row[k] = float(v)
                        elif isinstance(v, datetime.date):
                            formatted_row[k] = v.isoformat()
                        else:
                            formatted_row[k] = v
                    formatted_data.append(formatted_row)
                data_context = json.dumps(formatted_data, ensure_ascii=False, indent=2)
                analysis_messages = messages + [{
                    "role": "system",
                    "content": (
                        "Проанализируй ЭТИ РЕАЛЬНЫЕ данные из БД и представь их в красивом структурированном виде. "
                        "НЕ выдумывай, используй ТОЛЬКО эти данные.\n" + data_context
                    ),
                }]
                if os.getenv("ANALYZE_WITH_AI_SECOND_PASS", "0") == "1":
                    r3 = await client.chat.completions.create(
                        model=model,
                        messages=analysis_messages,
                        response_format={"type": "json_object"},
                        temperature=0.1,
                    )
                    d3 = json.loads((r3.choices[0].message.content if r3.choices else "{}") or "{}")
                    if d3.get("output"):
                        output = d3.get("output")
                # Формируем строгое HTML по ТЗ из данных
                def _fallback_from_rows(rows_list: List[Dict[str, Any]]) -> str:
                    existing_title = None
                    if output and output.strip().startswith("<b>"):
                        first_line = (output.strip().split("\n", 1)[0] or "").strip()
                        if first_line.endswith("</b>"):
                            existing_title = first_line
                    return build_html_from_rows(rows_list, existing_title)

                placeholder_patterns = [
                    r"данн(ые|ых)\s+будут.*после\s+выполнени[яе].*sql",
                    r"после\s+выполнени[яе]\s+sql",
                    r"результат(ы)?\s+будут\s+выведен",
                    r"ожидайте",
                    r"sql-?запрос[а]?\s+ниже",
                    r"список.*сформирован.*по данным",
                    r"ниже приведен.*список",
                    r"исключая клиентов.*бонус",
                ]
                looks_like_placeholder = bool(re.search("(" + ")|(".join(placeholder_patterns) + ")", (output or "").lower()))
                has_numbers = bool(re.search(r"\d", output or ""))
                
                # Проверяем, содержит ли ответ реальные данные из БД
                has_real_data = False
                if rows and len(rows) > 0:
                    # Ищем в output числа, которые есть в реальных данных
                    sample_values = []
                    for row in rows[:5]:  # первые 5 строк
                        for k, v in row.items():
                            if isinstance(v, (int, float, Decimal)):
                                sample_values.append(str(v))
                                # Также добавляем округленные версии для поиска
                                if isinstance(v, (float, Decimal)):
                                    sample_values.append(str(int(float(v))))
                    if sample_values:
                        has_real_data = any(val in (output or "") for val in sample_values)
                    
                    # Дополнительная проверка: если AI не использует реальные данные, принудительно форматируем
                    if not has_real_data and len(rows) > 0:
                        # Проверяем, не является ли ответ общим описанием без конкретных данных
                        generic_patterns = [
                            r"список.*сформирован",
                            r"вот.*результат",
                            r"по.*вашему.*запросу",
                            r"найдено.*запис",
                            r"данные.*по.*запросу",
                            r"исключая.*бонус",
                        ]
                        looks_generic = any(re.search(pattern, (output or "").lower()) for pattern in generic_patterns)
                        if looks_generic:
                            has_real_data = False  # Принудительно используем fallback

                if not output or looks_like_placeholder or not has_numbers or not has_real_data:
                    output = _fallback_from_rows(rows)
            except Exception as e:
                logger.error(f"Retry with data analysis failed: {e}")
        except Exception as e:
            logger.error(f"SQL execution error: {e}")
            output = output or "<b>Пока не могу получить данные из базы.</b>"
    else:
        logger.info("❌ AI DID NOT PROVIDE SQL_QUERY - NO DATABASE ACCESS")
        logger.info("❌ AI RESPONSE TYPE: General conversation (no data query)")

    # Память (всегда) — сохраняем краткий обмен
    try:
        await append_message(chat_id, "user", text)
        if output:
            await append_message(chat_id, "assistant", output)
    except Exception as e:
        logger.error(f"Memory append error: {e}")

    # Сохраняем конфигурацию графика для возможного редактирования
    if chart and direct_chart:
        save_chart_config(chat_id, chart)
        logger.info(f"💾 CHART CONFIG SAVED for chat {chat_id}")

    return AgentResult(
        output=output or "",
        direct_chart=direct_chart,
        chart=chart,
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
