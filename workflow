{
  "name": "For_Muslim sql",
  "nodes": [
    {
      "parameters": {
        "promptType": "define",
        "text": "={{ $json.text || $('Get Last Message').item.json.text}}",
        "hasOutputParser": true,
        "options": {
          "systemMessage": "=Ты — интеллектуальный, точный и надёжный агент-аналитик, встроенный в Telegram-бота. Работаешь с PostgreSQL-базой данных milk (версия 16.9), схема public.\n\nСАМОЕ ВАЖНОЕ ПРАВИЛО:\n1)НЕ ВЫДУМЫВАТЬ ДАННЫЕ А БРАТЬ ИХ ИЗ БАЗЫ(ФОРМИРОВАТЬ sql_query).Не бери данные из памяти и не придумывай.При каждом запросе если он подозревает обращение к базе,формируй sql_query и доставай данные из базы.Даже если тот же запрос был использован пользователем в предыдущем сообщении\n\n❗️Сегодняшняя дата не передаётся напрямую. Чтобы её узнать — делай SQL-запрос:\nSELECT CURRENT_DATE AS current_date, NOW() AS current_datetime;\nИспользуй результат как текущую дату и время. Не запоминай их, а запрашивай при каждом новом вопросе.\nИспользуй её при интерпретации слов «сегодня», «сейчас», «за последние дни», «на этой неделе», «в этом месяце» и т.д.\n\n📌 Твоя задача:\n!!!САМОЕ ГЛАВНОЕ - НЕ ВЫДУМЫВАТЬ ДАННЫЕ,А БРАТЬ ИХ ИЗ БАЗЫ!!!\nПонимать смысл пользовательских запросов на русском языке, включая опечатки, сокращения и синонимы.\n\nИнтерпретировать запрос, формировать точный SQL-запрос и выполнять его через n8n.\n\nНикогда не отправляй sql запрос который ты формируешь пользователю.Вместо этого писать что сейчас не владеешь этой информацией и предлагать пойти на обучение\n\n\nВозвращать только фактические строки из базы. Не фантазируй, не выдумывай данные и не показывай «примеры».\n\nОтвечай в деловом, но дружелюбном стиле — приветствуй пользователя, желай хорошего дня и т.д.\n\nЕсли запрос не предполагает SQL-запрос — ответь текстом.\n\nЕсли в запросе есть слово «новый запрос» — игнорируй предыдущий контекст.\n\nЕсли не указан год или месяц — всегда используй текущие значения.\n\nЕсли период указан частично (например, только месяц), также используй текущий год.\n\n\n!!!САМОЕ ГЛАВНОЕ - НЕ ВЫДУМЫВАТЬ ДАННЫЕ,А БРАТЬ ИХ ИЗ БАЗЫ!!!\n\n📦 Структура базы данных:\n\nclients(справочник клиентов) — client_code, client_name, public_name, region, manager, is_client, is_supplier, legal_type, registration_date,marker  \nproducts(справочник продукции) — product_code, product_name, print_name, unit, type, brand, weight, client_code, category_1, category_group_1, product_group  \norders(заказы) — order_number, client_code, product_code, order_date, shipment_date, planned_quantity, weight_kg, warehouse  \nprofit(продажи и возвраты) — order_number, client_code, product_code, order_date, profit_date, quantity, weight_kg, revenue, manager, channel, warehouse  \ndebt(дебиторка) — client_code, contractor, payment_term, manager, total_debt, overdue_debt, not_overdue_debt, debt_date  \nstock(остатки) — product_code, warehouse, stock_date, income, outcome, initial_quantity, final_quantity  \npurchase_prices(закупки) - product_code, order_date, order_number, quantity, client_code, price_per_unit, var_rate(столбец где содержится процент НДС или текст \"Без НДС\"), warehouse, contract_type\nsales_representatives (справочник менеджеров) - full_name, phone, email, department,user_photo (фото менеджера)\nmanagers_plan (план продаж в кг.)— period (период имеется ввиду месяц на который устанавливается план),manager,client_cod,categories,plan\n\nСвязи между таблицами:\n\nprofit.product_code → products.product_code → purchase_prices.product_code \nprofit.client_code → clients.client_code  \norders.product_code → products.product_code  \norders.client_code → clients.client_code  \ndebt.client_code → clients.client_code  \nstock.product_code → products.product_code  \nproducts.client_code → clients.client_code (если private-label)\n\n🔒 ВАЖНОЕ ПРАВИЛО\nВо всех SQL-запросах, где используется таблица profit, orders или любая таблица, связанная с клиентами, обязательно исключай клиентов, у которых в таблице clients поле marker = 'Бонус'.\nЭто условие фильтрации добавляется в каждый такой запрос:\n\nclient_code NOT IN (SELECT client_code FROM clients WHERE marker = 'Бонус')\nДаже если клиент не явно упоминается, но используется таблица profit, orders, debt, stock или managers_plan, ты обязан добавить этот фильтр.\nЭто обязательное правило для любого запроса, даже если фильтрация выглядит необязательной.\nНельзя его игнорировать.\n\n📊 Основные метрики:\nПоле period в таблице managers_plan — это тип DATE, всегда указывай период в формате диапазона дат: >= 'YYYY-MM-01' и < 'YYYY-MM+1-01'. Не сравнивай period = '2025-05', это некорректно\nпродажи или выручка → SUM(p.revenue) WHERE p.revenue > 0   (p - profit) \nвозвраты → SUM(p.revenue) WHERE p.revenue < 0  \nвес → SUM(weight_kg)  \nколичество → SUM(quantity) (в profit) или SUM(planned_quantity) (в orders)  \nнедогруз → GREATEST(orders.weight_kg - COALESCE(profit.weight_kg, 0), 0) — при JOIN по product_code, shipment_date и client_code\nАКБ - Количество уникальных клиентов-Пример: SELECT COUNT(DISTINCT clients.client_code)\n📅 Периоды:\n\nМесяцы: «январь», «февраль» и т.д. → соответствующий месяц текущего года  \n«прошлый месяц» → предыдущий календарный месяц  \n«вчера», «сегодня», «на этой неделе» — интерпретировать буквально  \nПродажи и возвраты — по полю profit.profit_date  \nПлановые отгрузки — по orders.shipment_date\nЗакупочные цены и даты закупки - по purchase_prices.order_date и purchase_prices.price_per_unit \nЕсли период не указан — уточни у пользователя. Но если указан день или месяц, то бери текущий год (2025)\n\n🎯 Группировки и фильтры:\n\n«по торговым» → GROUP BY profit.manager  \n«по каналам» → GROUP BY profit.channel  \n«по регионам» → JOIN clients ON profit.client_code = clients.client_code, GROUP BY clients.region  \n«по продуктам» → JOIN products ON profit.product_code = products.product_code, GROUP BY products.product_name  \n«по брендам» → GROUP BY products.brand\n«по категориям» → GROUP BY products.category_1\n«по группам категорий» → GROUP BY products.category_group_1\n\n🧠 Работа со справочниками:\n\nФильтрация должна учитывать ошибки в написании — всегда используй ILIKE '%значение%'.\n\nСправочники:\n\nМенеджеры:\n\"Альборов Феликс Олегович\", \"Альборов Эльдар Олегович\", \"Балов Альберт Мартинович\", \"Балахов Алим Юрьевич\", \"Гергов Рустам Русланович\", \"Жаниюков Марат Олиевич\", \"Люев Мурат Темболатович\", \"Махиев Аслан Русланович\", \"Мудранов Ризуан Замирович\", \"Нартоков Руслан Рамазанович\", \"Ораков Адам Азнорович\", \"Светлана Дыгова\", \"Тепсаев Адам Рамазанович\", \"Токлуев Алик Мурадинович\", \"Хакиев Тамерлан Владимирович\", \"Хежев Залим Исмагилович\", \"Ширитов Алим Артурович\", \"Шувалов Хазрет Артурович\"\n\nКаналы сбыта:\n\"HoReCa\", \"АЗС и СТО\", \"Игровые и компьютерные клубы\", \"Крупный ОПТ\", \"ОПТ\", \"Пивные и табачные магазины\", \"Производство на дому\", \"Розница\", \"Собственная розница\", \"Специализированные магазины\", \"Спорт залы и фитнес клубы\", \"Супермаркеты\", \"Школы и садики\"\n\nРегионы:\nг.о. Нальчик, Майский район, Чегемский район, Зольский район, Баксанский район, Черекский район, Урванский район, Эльбрусский район, Ставропольский край, Северная Осетия — Алания Респ и др.\n\nКонтракты / поставщики:\nООО НМК ТК, ООО \"Русский Холод\", Ceramics Rostov, Бобимэкс, Брянконфи, Лит Энерджи, Измайлов\n\n\nНе используй ILIKE для этих справочников.Ты должен понимать чего хочет пользователь,какой он фильтр запрашивает исходя из справочников\n\n🧾 SQL-правила:\n❗ Если используешь подзапрос с алиасом (например, sub), во внешнем SELECT/ORDER/GROUP запрещено писать p.<поле>.  \nСнаружи можно использовать только sub.<поле> (из подзапроса) и c.<поле> (из JOIN clients).  \n\nПлохо: SELECT p.profit_date, c.region FROM (SELECT ... FROM public.profit p) sub JOIN public.clients c ...  \nХорошо: SELECT sub.month, c.region FROM (SELECT DATE_TRUNC('month', p.profit_date) AS month, ... FROM public.profit p) sub JOIN public.clients c ...\n❗ Самопроверка перед вызовом БД:\nЕсли есть подзапрос (aliас sub), во внешних SELECT/ORDER/GROUP запрещено p.<поле>. Снаружи допустимы только sub.<поле> и поля присоединённых таблиц (например, c.<поле>). Если обнаружил \"p.\" снаружи — перепиши SQL (замени на sub.<поле> и/или добавь нужный JOIN).\n\n\nВсегда используй public.<table>  \nПроверяй наличие колонок через information_schema.columns  \nНе строй SQL без фильтра по дате  \nИспользуй оконные функции (например: RANK() OVER) для топов  \nНе включай лишние поля  \nДля длинных сообщений учитывай лимит ~4000 символов (Telegram)\n\n\n📎 Пример корректного SQL:\nSELECT\n    c.region,\n    SUM(p.revenue) AS total_revenue\nFROM public.profit p\nJOIN public.clients c\n    ON p.client_code = c.client_code\nWHERE p.revenue > 0\n  AND p.profit_date BETWEEN DATE '2025-01-01' AND DATE '2025-01-31'\n  AND p.client_code NOT IN (\n      SELECT client_code\n      FROM public.clients\n      WHERE marker = 'Бонус'\n  )\nGROUP BY c.region\nORDER BY total_revenue DESC;\n\n\n📝 Формат ответа:\nВсегда возвращай один JSON-объект с полями:\n\n{\n  \"output\": \"Человекочитаемый текст\",\n  \"direct_chart\": true/false,\n  \"chart\": {...} или null,\n  \"send_excel\": true/false,\n  \"table_data\": [...] или null\n  \"sql_query\": созданный запрос,Прописывай всегда\n}\nЕсли пользователь просит «скинь sql запрос» или «покажи sql», обязательно заполни поле output текстом, укажи, что это SQL-запрос, и покажи его.\n\nЕсли пользователь просит Excel — обязательно верни `\"table_data\"` — массив объектов (одна строка = один объект). Это используется для генерации Excel.\n\nПример:\n\"table_data\": [\n  { \"manager\": \"Альборов\", \"revenue\": 1234567.8 },\n  { \"manager\": \"Махиев\",   \"revenue\": 2222000.0 }\n]\n\nФормат текстового ответа:\n📌 ВАЖНО: ВСЕ ВЫДЕЛЕНИЯ ДОЛЖНЫ БЫТЬ В ФОРМАТЕ HTML.  \nНЕ ИСПОЛЬЗУЙ `**звёздочки**`, Markdown или другие формы.  \nВСЕ ЖИРНЫЕ ВЫДЕЛЕНИЯ — ЧЕРЕЗ <b>ТЕГИ</b>.\nИспользуй только следующие выделения:<b>, <strong>, <i>, <em>, <u>, <ins>, <s>, <strike>, <del>,\n<span class=\"tg-spoiler\">, <tg-spoiler>, <a href=\"...\">, <code>, <pre>\nБольше никаких\n\nВсегда предоставляй красивый структурированный ответ.\nТам где необходимо выделяй жирным через HTML выделения \nЗаголовок первой строкой:\n<b>Продажи по регионам за январь 2025</b>\n\nЗатем строки в формате:\nг.о. Нальчик — 12 345 678,90 ₽\nМайский район — 8 765 432,10 ₽\n\nРазделитель тысяч — пробел\n\nДесятичная — запятая\n\nВ зависимости от того что суммируешь проставляй ОБЯЗАТЕЛЬНО единицы измерения(ЭТО ВАЖНО!)\n₽ — если revenue\nКг - если weight_kg\nШт - если quantity\nВ шапке указывай фильтры, если они есть (например: «по бренду Славница»)\n\n📊 Chart Mode — SMART\n─────────────────────────────\n\nВсегда анализируй смысл запроса и структуру данных:\n\nЕсли данных недостаточно для осмысленной визуализации (нет числовых значений или категорий, или вопрос информационный) —\n\"direct_chart\": false, \"chart\": null\n\nЕсли есть категории + значения (или пользователь явно  просит график) —\n\"direct_chart\": true и заполни \"chart\" по правилам ниже.Пока пользователь явно не попросит построить график direct_chart всегда false,даже если в предыдущем запросе он строил график не додумывай за него.\n\nТипы графиков (определи автоматически или по явному запросу пользователя):\n\"bar\" — для сравнения значений между категориями (по умолчанию, если ≥3 категории и 1 ряд данных)\n\n\"pie\" — для отображения долей, когда сумма данных ≈100%, либо если пользователь явно просит \"круговую\"\n\n\"doughnut\" — кольцевая диаграмма (аналог pie, но с дыркой)\n\n\"line\" — для отображения динамики по времени или сравнения трендов\n\n\"stacked\" — для сравнения структур по нескольким категориям/рядам\n\n\"scatter\" — для парных числовых данных (x, y)\n\n\"histogram\" — для распределения числовых данных\n\nТребования:\n\n🎯 Всегда возвращай полный chart-конфиг JSON для построения графика. Включай все возможные опции, даже если они отключены:\n- Всегда указывай `\"legend\": { \"display\": true/false, \"position\": \"top/right/...\" }`\n- Всегда указывай `\"scales\"` с `x`, `y`, `title`, `ticks` и `display`\n- Всегда указывай `\"plugins.datalabels\"` с `display`, `formatter`, `font`, `color`\n- Всегда указывай `\"responsive\"`, `\"maintainAspectRatio\"`, `\"aspectRatio\"` даже если они равны `false`\n- Никогда не пропускай `\"options\"`, даже если он пуст\n- Никогда не используй значения по умолчанию без явного указания\n\nЕсли пользователь просит «убрать подписи», то нужно:\n- `\"plugins\": { \"datalabels\": { \"display\": false } }`\n- `\"scales\": { \"x\": { \"display\": false }, \"y\": { \"display\": false } }`\n- `\"legend\": { \"display\": false }`\n\n\nГенерируй валидный, красиво отформатированный JSON без пропусков ключей, даже если display = false\nДругие типы добавляй при необходимости (bubble, radar и т.д.).\n\nЕсли пользователь просит неуместный график (например, pie по временным рядам) —\n\nОбъясни, почему данный тип не подходит для этих данных, и предложи лучший вариант.\n\nПример: \"Круговая диаграмма не подходит для временных рядов. Предлагаю построить линейный график.\"\n\nОбщие требования к графикам:\nВсегда формируй читабельный, красивый и информативный график:\n\nФорматируй большие числа: 10 000 → 10K, 2 500 000 → 2.5M и т.д.\n\nДобавляй legend, подписи осей, title.\n\nДля pie/doughnut: подписывай проценты и значения.\n\nДля bar/line: подписи на оси X/Y.\n\nЕсли есть поле backgroundColor — для каждого сегмента свой цвет (Chart.js формат).\n\nВсе параметры (title, legend, подписи, цвет, формат осей, ширина кольца и пр.) указывай в options:\n\noptions.plugins.title.text — заголовок\n\noptions.plugins.legend.position — позиция легенды (\"right\", \"top\", ...)\n\noptions.plugins.datalabels.formatter — функция форматирования подписей как строка\n(пример: \"formatter\": \"(v) => v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(1)+'K' : v\")\n\noptions.scales.y.ticks.callback — форматирование значений по оси Y (то же через строку-функцию)\n\nДля doughnut можешь добавить в options параметр cutout: \"60%\" (ширина кольца)\n\nДля bar: options.indexAxis = \"y\" (если нужен горизонтальный график)\n\nЕсли пользователь хочет сравнить периоды (например, 2024 и 2025) — построй line-график с несколькими рядами (datasets). Каждый ряд — отдельный год, цвет должен отличаться. В datasets укажи: label, data, borderColor, fill: false\n\nФормируй конфиг только как корректный JSON-объект для Chart.js v3+ (НЕ как строку с JSON).\n\nВсе функции (formatter, callback) — только как строка в поле (без eval).\n\nПример шаблона Chart.js:\n\n\"chart\": {\n  \"type\": \"bar\",\n  \"data\": {\n    \"labels\": [...],\n    \"datasets\": [\n      {\n        \"label\": \"...\",\n        \"data\": [...],\n        \"backgroundColor\": [...]\n      }\n    ]\n  },\n  \"options\": {\n    \"plugins\": {\n      \"legend\": { \"position\": \"right\" },\n      \"title\": { \"display\": true, \"text\": \"...\" },\n      \"datalabels\": {\n        \"display\": true,\n        \"color\": \"#000\",\n        \"font\": { \"size\": 13, \"weight\": \"bold\" },\n        \"formatter\": \"(v) => v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(1)+'K' : v\"\n      }\n    },\n    \"scales\": {\n      \"y\": {\n        \"beginAtZero\": true,\n        \"ticks\": {\n          \"callback\": \"(v) => v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(1)+'K' : v\"\n        }\n      }\n    }\n  }\n}\n\n❗ Если запрос неясен:\nПопроси уточнить: «Пожалуйста, укажите период, метрику и фильтры.»\n────────────────────────────\n📄 ФОРМАТ ОТВЕТА, ЕСЛИ ДАННЫХ НЕТ\nЕсли пользователь запрашивает дату > сегодня скажи ему об этом\nЕсли другая причина,то пиши что пока что не можешь предоставить эти данные и спрашивай пойти ли тебе на обучение\n\n─────────────────────────────\n\n\n❌ Нельзя:\nПридумывать названия товаров, брендов, клиентов\nПоказывать \"примерные\" данные\nИспользовать Markdown или HTML\nВозвращать колонки, которых нет в таблицах\nПропускать SQL-валидацию\n\nЕсли пользователь просит \"покажи карточку\", \"карточка\", \"карточку торгового\", \"информация о торговом\", то:\n- Обратись к базе к таблице managers_plan и через ILIKE определи ФИО торгового представителя (например: \"Альборов Феликс Олегович\").\n- Верни JSON:\n  {\n    \"send_card\": true,\n    \"rep_name\": \"<ФИО торгового представителя>\"\n  }\n- Не передавай это в LangChain, просто сгенерируй JSON.\n-Если пользователь просит все карточки разом (фразы: \"все карточки\", \"все торговые\", \"карточки всех\"), \nверни JSON: { \"send_card\": true, \"rep_name\": \"all\" }.\n\n-Не трогай send_excel, оставляй его false\n\nТы — деловой SQL-аналитик, а не чат-бот. Работай строго с тем, что реально содержится в базе milk (схема public). Сейчас 2025 год — ориентируйся на актуальные данные.\n\n📍 Точки контроля\nЧасто используемые агрегированные отчёты, хранящиеся в отдельных таблицах:\n\n1. plan_perf_manager_reports — выполнение плана менеджерами\nperiod (date): последний день месяца\n\nmanager (text): ФИО\n\nplan_kg, fact_kg (numeric): план и факт в кг\n\nkpi (numeric): % выполнения плана (уже рассчитан, от 0 до 100). Не умножать на 100!\n\nbad_categories (jsonb): список категорий с недогрузами\n\nai_recommendation (text): рекомендация от ИИ\n\n📌 Для фильтрации используй: kpi < 95.\nПериод фильтруется как: period = 'YYYY-MM-DD'.\n\nservice_level_reports — уровень сервиса (дневной + MTD)\nreport_date (date): дата отчёта (например, 2025-06-01)\n\n🟢 Основные поля (записываются каждый день):\ntotal_order_kg (numeric): суммарные заказы за день\n\ntotal_sales_kg (numeric): суммарные продажи за день\n\nservice_level (numeric): уровень сервиса за день = продажи / заказы × 100\n\nstatus (text): \"OK\" — если service_level ≥ 98, \"ALERT\" — иначе\n\nmtd_order_kg, mtd_sales_kg (numeric): суммарные заказы и продажи с начала месяца\n\nmtd_service_level (numeric): уровень сервиса с 1-го числа по report_date\n\ntop10_sku (jsonb): топ-10 товаров по недогрузу за MTD-период\n\ntop10_reasons (jsonb): топ-10 причин недогруза за MTD-период\n\nai_recommendation (text): рекомендация от ИИ (заполняется только в последний день месяца, если mtd_service_level < 98)\n\ncreated_at (timestamp): дата и время расчёта\n\n📌 Правила анализа:\n\nЕжедневно формируется одна строка с накопительным расчётом на дату report_date\n\ntop10_sku и top10_reasons всегда относятся к периоду с начала месяца по report_date\n\nВ последний день месяца, если mtd_service_level < 98, появляется поле ai_recommendation\n\n📌 Примеры фильтрации:\n\nСрез на конкретный день:\nWHERE report_date = '2025-06-03'\n\nПоследний день месяца:\nWHERE report_date = '2025-06-30'\n\nРабота с JSON:\njsonb_array_elements(top10_sku), jsonb_array_elements(top10_reasons)\n\n3. product_abcxyz — ABC/XYZ-анализ по товарам\nproduct_code, product_name\n\ntotal_revenue (numeric): суммарная выручка по товару\n\nabc_group (text): группа A / B / C\n\nxyz_group (text): группа X / Y / Z\n\n📌 Для фильтрации используй:\n\nпо группе: abc_group = 'A'\n\nкомбинированно: abc_group = 'C' AND xyz_group = 'Z'\n\n\n📣 Общий вопрос\nКогда пользователь спрашивает: «Что на предприятии?», «Есть ли проблемы?», «Какие отклонения?», «Как ситуация?» и т.п.\n\nSQL-вызов\n→ SELECT get_control_anomalies(current_date);\n\nСтруктура ответа\n\nвыполнение плана — список менеджеров с kpi < 95, их недогруженные категории и AI-советы\n\nуровень сервиса — дни с service_level < 98 % и/или месячный mtd_service_level < 98 %, топ-10 SKU и причин\n\nпроблемные товары (CZ) — топ-5 SKU из группы abc_group = 'C' & xyz_group = 'Z'\n\nрекомендации — все AI-подсказки из планов и уровня сервиса\n\nКОГДА ПОЛЬЗОВАТЕЛЬ ПРОСИТ ОТПРАВИТЬ ПИСЬМО — НЕ ПИШИ ТЕКСТ.\nВЫЗЫВАЙ инструмент SendMailWorkflow строго с аргументами JSON-объекта:\n{ \"recipient\": \"<строка>\", \"subject\": \"<строка>\", \"body\": \"<строка>\" }\n\nЖЁСТКИЕ ПРАВИЛА:\n- recipient = исходная фраза пользователя (ФИО/фраза/или e-mail). trim(); пусто запрещено.\n- subject: если не указан — \"Без темы\". trim().\n- body: если не указан — \"\" (пустая строка). trim().\n- Никаких обёрток/markdown/`query`. Поля `attachments` не передавать, если пользователь их не задал.\n- Никогда не передавать \"none\", \"null\", \"[]\", пустые строки.\n\n📨 MAIL EXCEL (фразы вида: \"отправь это в эксель/в excel/таблицей … <кому>\"):\n- В ЭТОМ СЛУЧАЕ НЕ ВЫЗЫВАЙ SendMailWorkflow напрямую.\n- Верни один JSON (без обёрток) с полями:\n{\n  \"output\": \"<краткое подтверждение>\",\n  \"send_excel\": true,\n  \"excel\": { \"filename\": \"<имя>.xlsx\", \"sheet\": \"Данные\" },\n  \"table_data\": [ { ... }, ... ],\n  \"recipient\": \"<строка как у пользователя>\",\n  \"subject\": \"<или 'Без темы'>\",\n  \"body\": \"<или ''>\",\n  \"sql_query\": \"<schema-qualified SQL к источнику данных>\"\n}\n- Данные формируй по текущему запросу пользователя (те же фильтры/период).\n- Исключай клиентов marker='Бонус' (если применимо).\n- Фразы типа \"в марте\" трактуй как полный календарный месяц соответствующего года.\n- Без поля `attachments`. Без `query`.\n\nПРИМЕРЫ (КРАТКО):\nUser: \"отправь письмо темботову с темой Привет\"\n→ TOOL: SendMailWorkflow\n→ ARGS: {\"recipient\":\"темботову\",\"subject\":\"Привет\",\"body\":\"\"}\n\nUser: \"отправь это в excel темботову\"\n→ (НЕ ВЫЗЫВАТЬ TOOL) → вернуть JSON с send_excel=true + table_data.\n"
        }
      },
      "id": "191394b6-672f-4685-a841-afe0de0603c9",
      "name": "AI Agent",
      "type": "@n8n/n8n-nodes-langchain.agent",
      "position": [
        -1216,
        336
      ],
      "typeVersion": 1.7
    },
    {
      "parameters": {
        "model": {
          "__rl": true,
          "value": "gpt-4.1",
          "mode": "list",
          "cachedResultName": "gpt-4.1"
        },
        "options": {
          "responseFormat": "json_object"
        }
      },
      "id": "f7ad3723-c503-4439-8642-606a07f99750",
      "name": "OpenAI Chat Model",
      "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
      "position": [
        -1408,
        592
      ],
      "typeVersion": 1.2,
      "credentials": {
        "openAiApi": {
          "id": "Qc85KFzgvCeEqnB7",
          "name": "OpenAi account 3"
        }
      }
    },
    {
      "parameters": {},
      "type": "@n8n/n8n-nodes-langchain.toolCalculator",
      "typeVersion": 1,
      "position": [
        -1040,
        592
      ],
      "id": "96c6a98c-dc15-4e6c-ba2b-ca8dafd1f979",
      "name": "Calculator"
    },
    {
      "parameters": {
        "url": "http://84.19.3.244/tg/bot8307440026:AAHlFCU6CCar7-xA3nGvhN1CQH9Lh-3N3UQ/getUpdates",
        "options": {},
        "queryParametersUi": {
          "parameter": [
            {
              "name": "limit",
              "value": "1"
            },
            {
              "name": "offset",
              "value": "={{ $node['Parse Update ID'].json.last_processed_update_id + 1 }}"
            }
          ]
        }
      },
      "name": "Get Updates",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 1,
      "position": [
        -2576,
        640
      ],
      "id": "fbf5135e-857f-42fc-8c3a-174190eff810"
    },
    {
      "parameters": {
        "functionCode": "// Берём данные напрямую из узла \"Get Updates\", а не из входа текущей ноды.\nconst src = $('Get Updates');\nconst items = src.all(); // обычно 1 item с полем result (polling), но подстрахуемся\n\nlet updates = [];\n\n// 1) polling (getUpdates): json.result = массив апдейтов\nif (items.length) {\n  const js = items[items.length - 1].json;            // берём самый свежий item\n  if (Array.isArray(js.result)) updates = js.result;   // classic getUpdates\n  // 2) webhook-стиль (на всякий случай): апдейт сразу в корне\n  else if (js.update_id || js.message || js.callback_query) updates = [js];\n}\n\n// 3) запасной план: если апдейтов нет, но во вход пришёл апдейт — используем его\nif (!updates.length) {\n  const j = $json;\n  if (j.update_id || j.message || j.callback_query) updates = [j];\n}\n\nif (!updates.length) {\n  return []; // нет новых апдейтов\n}\n\n// Берём самый свежий апдейт\nconst upd = updates[updates.length - 1];\n\n// Нормализуем в единый формат\nif (upd.callback_query) {\n  const cq = upd.callback_query;\n  return [{\n    json: {\n      is_callback: true,\n      update_type: 'callback_query',\n      data: cq.data || null,\n      log_id: Number((cq.data || '').split(':')[1] || 0),\n      chat_id: cq.message.chat.id,\n      clicked_by: cq.from.id,\n      user_name: [cq.from.first_name, cq.from.last_name].filter(Boolean).join(' ') || cq.from.username || null,\n      update_id: upd.update_id,\n      callback_query_id: cq.id\n    }\n  }];\n}\n\nif (upd.message) {\n  const m = upd.message;\n  return [{\n    json: {\n      is_callback: false,\n      update_type: 'message',\n      text: m.text || '',\n      voice: m.voice ? m.voice.file_id : null,\n      chat_id: m.chat.id,\n      user_id: m.from?.id ?? null,\n      user_name: [m.from?.first_name, m.from?.last_name].filter(Boolean).join(' ') || m.from?.username || null,\n      update_id: upd.update_id\n    }\n  }];\n}\n\nreturn [];\n"
      },
      "name": "Get Last Message",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [
        -2384,
        640
      ],
      "id": "af535c1d-a59d-42f9-9b83-14d6fce7f66a"
    },
    {
      "parameters": {
        "operation": "write",
        "fileName": "/home/adminvm/n8n_data/tg_id",
        "dataPropertyName": "=data",
        "options": {
          "append": "={{ $json.update_id }}"
        }
      },
      "type": "n8n-nodes-base.readWriteFile",
      "typeVersion": 1,
      "position": [
        -1680,
        -448
      ],
      "id": "29fa7e18-533a-4a92-85e0-8d2f51a33127",
      "name": "Read/Write Files from Disk"
    },
    {
      "parameters": {
        "jsCode": "const updateId = $items(\"Get Last Message\")[0].json.update_id;\n\n\n// Преобразуем update_id в JSON и затем в бинарный формат\nconst data = JSON.stringify({ last_processed_update_id: updateId });\nconsole.log('Preparing data for file:', data);\n\nreturn [{\n  json: {},\n  binary: {\n    data: {\n      data: Buffer.from(data).toString('base64'),\n      mimeType: 'application/json'\n    }\n  }\n}];"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [
        -1856,
        -320
      ],
      "id": "8c95b79d-33b9-4031-804c-7af6e7bb1a84",
      "name": "Code"
    },
    {
      "parameters": {
        "fileSelector": "/home/adminvm/n8n_data/tg_id",
        "options": {}
      },
      "type": "n8n-nodes-base.readWriteFile",
      "typeVersion": 1,
      "position": [
        -2976,
        640
      ],
      "id": "919b371d-838b-482d-9507-e9618ca8a049",
      "name": "Read/Write Files from Disk2"
    },
    {
      "parameters": {
        "jsCode": "try {\n  // Декодируем base64-данные из бинарного поля\n  const binaryData = items[0].binary.data.data;\n  const decodedData = Buffer.from(binaryData, 'base64').toString('utf8');\n  \n  // Парсим JSON\n  const data = JSON.parse(decodedData);\n  \n  // Логируем для отладки\n  console.log('Parsed data:', data);\n  \n  return [{ json: { last_processed_update_id: data.last_processed_update_id || 0 } }];\n} catch (e) {\n  console.log('Error parsing update ID file:', e.message);\n  return [{ json: { last_processed_update_id: 0 } }];\n}"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [
        -2784,
        640
      ],
      "id": "f5d73113-78ce-4773-adfe-e689868e0926",
      "name": "Parse Update ID"
    },
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "field": "seconds",
              "secondsInterval": 5
            }
          ]
        }
      },
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1.2,
      "position": [
        -3168,
        640
      ],
      "id": "ad9316f3-204a-4cb2-9879-51eb35ee5489",
      "name": "Schedule Trigger"
    },
    {
      "parameters": {
        "rules": {
          "values": [
            {
              "conditions": {
                "options": {
                  "caseSensitive": true,
                  "leftValue": "",
                  "typeValidation": "strict",
                  "version": 2
                },
                "conditions": [
                  {
                    "leftValue": "={{ $('Get Last Message').item.json.is_callback }}",
                    "rightValue": true,
                    "operator": {
                      "type": "boolean",
                      "operation": "true",
                      "singleValue": true
                    },
                    "id": "7ad4d126-53d6-4db4-8484-e723d8925525"
                  }
                ],
                "combinator": "and"
              },
              "renameOutput": true,
              "outputKey": "callback"
            },
            {
              "conditions": {
                "options": {
                  "caseSensitive": true,
                  "leftValue": "",
                  "typeValidation": "strict",
                  "version": 2
                },
                "conditions": [
                  {
                    "id": "62ec01ec-ff8d-4a52-ab47-f61f653d73a5",
                    "leftValue": "={{ $('Get Last Message').item.json.voice }}",
                    "rightValue": "",
                    "operator": {
                      "type": "string",
                      "operation": "notEmpty",
                      "singleValue": true
                    }
                  }
                ],
                "combinator": "and"
              },
              "renameOutput": true,
              "outputKey": "voice"
            },
            {
              "conditions": {
                "options": {
                  "caseSensitive": true,
                  "leftValue": "",
                  "typeValidation": "strict",
                  "version": 2
                },
                "conditions": [
                  {
                    "id": "04392c2d-95f5-46fe-ae98-265082003e53",
                    "leftValue": "={{ $('Get Last Message').item.json.text }}",
                    "rightValue": true,
                    "operator": {
                      "type": "string",
                      "operation": "notEmpty",
                      "singleValue": true
                    }
                  }
                ],
                "combinator": "and"
              },
              "renameOutput": true,
              "outputKey": "text"
            }
          ]
        },
        "options": {}
      },
      "type": "n8n-nodes-base.switch",
      "typeVersion": 3.2,
      "position": [
        -1888,
        464
      ],
      "id": "b2392f35-1596-49f4-8b5a-6de5af81b538",
      "name": "Switch"
    },
    {
      "parameters": {
        "jsCode": "return [{\n  json: {\n    file_path: $json[\"result\"][\"file_path\"]\n  }\n}];"
      },
      "name": "Extract File Path1",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [
        -1328,
        32
      ],
      "id": "20eecf01-7bc7-4ba4-ad4d-882750c73f11"
    },
    {
      "parameters": {
        "url": "={{\"http://84.19.3.244/tg/file/bot8307440026:AAHlFCU6CCar7-xA3nGvhN1CQH9Lh-3N3UQ/\" + $json[\"file_path\"]}}",
        "responseFormat": "file",
        "options": {}
      },
      "name": "Download Voice1",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 1,
      "position": [
        -1168,
        32
      ],
      "id": "d774df0c-db5f-4406-98f9-1a9e4a6e57be"
    },
    {
      "parameters": {
        "url": "=http://84.19.3.244/tg/bot8307440026:AAHlFCU6CCar7-xA3nGvhN1CQH9Lh-3N3UQ/getFile?file_id={{ $('Get Updates').item.json.result[0].message.voice.file_id }}",
        "options": {}
      },
      "name": "Get Updates1",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 1,
      "position": [
        -1472,
        32
      ],
      "id": "f7ad450e-912d-4fde-9cee-5f355e788bf1"
    },
    {
      "parameters": {
        "command": "=echo '{{ JSON.stringify($json) }}' | /home/adminvm/venv/bin/python3 /home/adminvm/scripts/generate_chart.py\n"
      },
      "type": "n8n-nodes-base.executeCommand",
      "typeVersion": 1,
      "position": [
        -80,
        -384
      ],
      "id": "9e4d62cd-bda9-474f-854d-115b5a4d8646",
      "name": "Execute Command"
    },
    {
      "parameters": {
        "operation": "sendPhoto",
        "chatId": "={{ $('Get Updates').item.json.result[0].message.chat.id }}",
        "binaryData": true,
        "additionalFields": {}
      },
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1.2,
      "position": [
        544,
        -384
      ],
      "id": "ba1782db-e63a-4002-9139-c0a1c209090c",
      "name": "Telegram2",
      "webhookId": "26cea149-fec1-48bb-b1e1-4c487fa7d77b",
      "credentials": {
        "telegramApi": {
          "id": "LK8mWaz3RxYafXEV",
          "name": "Telegram account 5"
        }
      }
    },
    {
      "parameters": {
        "fileSelector": "/home/adminvm/scripts/chart.png",
        "options": {
          "dataPropertyName": "data"
        }
      },
      "type": "n8n-nodes-base.readWriteFile",
      "typeVersion": 1,
      "position": [
        256,
        -384
      ],
      "id": "30b5235d-fe35-4374-bef1-74bb348dea28",
      "name": "Read/Write Files from Disk3"
    },
    {
      "parameters": {
        "jsCode": "/**\n * Code6 — Telegram-safe HTML + поддержка <pre><code>...</code></pre>\n */\n\nfunction escapeHTML(s) {\n  return s.replace(/&/g, '&amp;')\n          .replace(/</g, '&lt;')\n          .replace(/>/g, '&gt;')\n          .replace(/\"/g, '&quot;')\n          .replace(/'/g, '&#039;');\n}\n\nconst ALLOWED_TAGS = new Set([\n  'b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del',\n  'code', 'pre', 'a', 'span'\n]);\nconst ALLOWED_ATTR = {\n  a: ['href'],\n  span: ['class']\n};\n\n// Сохраняем <pre><code>...</code></pre> блоки временно\nconst preBlocks = [];\n\nfor (const item of $input.all()) {\n  let html = (item.json.output ?? '').trim();\n\n  if (!html) {\n    item.json.html = '⚠️ Нет текстового ответа от агента.';\n    continue;\n  }\n\n  // 1️⃣ Вырезаем <pre><code>...</code></pre> и экранируем содержимое\n  html = html.replace(/<pre>\\s*<code>([\\s\\S]*?)<\\/code>\\s*<\\/pre>/gi, (_, code) => {\n    const idx = preBlocks.length;\n    preBlocks.push(`<pre><code>${escapeHTML(code)}</code></pre>`);\n    return `__PRE_BLOCK_${idx}__`;\n  });\n\n  // 2️⃣ Переносы: <br>, <p> → \\n\n  html = html.replace(/<\\s*br\\s*\\/?>/gi, '\\n')\n             .replace(/<\\s*\\/?\\s*p[^>]*>/gi, '\\n');\n\n  // 3️⃣ Списки: <li> → • …\\n, а контейнеры удалить\n  html = html.replace(/<li[^>]*>/gi, '• ')\n             .replace(/<\\/li>/gi, '\\n')\n             .replace(/<\\/?(ul|ol|div|table)[^>]*>/gi, '');\n\n  // 4️⃣ Удаляем неразрешённые теги\n  html = html.replace(/<\\/?([a-zA-Z][\\w\\-]*)\\b([^>]*)>/g, (m, tag, attrs) => {\n    tag = tag.toLowerCase();\n    if (!ALLOWED_TAGS.has(tag)) return '';\n\n    if (ALLOWED_ATTR[tag]) {\n      const keep = ALLOWED_ATTR[tag];\n      attrs = attrs.replace(/\\s+([\\w\\-:]+)(=\"[^\"]*\")?/g,\n        (_, name, val) => keep.includes(name.toLowerCase()) ? ` ${name}${val || ''}` : '');\n    } else {\n      attrs = '';\n    }\n\n    if (tag === 'span' && !/class\\s*=\\s*\"tg-spoiler\"/i.test(attrs)) return '';\n    return `<${m.startsWith('</') ? '/' : ''}${tag}${attrs}>`;\n  });\n\n  // 5️⃣ Вернём <pre><code>...</code></pre> обратно\n  html = html.replace(/__PRE_BLOCK_(\\d+)__/g, (_, n) => preBlocks[n] || '');\n\n// 6️⃣ Удаляем невидимые символы, но оставляем ₽ и валютные знаки\nhtml = html.replace(/[^\\x09\\x0A\\x0D\\x20-\\x7Eа-яА-ЯёЁ0-9₽¥€$£.,:;'\"!?<>\\s\\-–—=_()\\[\\]{}|\\\\/@#$%^&*~`+]/g, '');\n\n\n  // 7️⃣ Убираем лишние \\n\n  html = html.replace(/\\n{3,}/g, '\\n\\n').trim();\n\n  if (!html) html = '⚠️ После фильтрации текст отсутствует.';\n  item.json.html = html;\n}\n\nreturn $input.all();\n"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [
        -304,
        240
      ],
      "id": "36e59431-15a0-4044-bfbe-453ff9f58d50",
      "name": "Code6"
    },
    {
      "parameters": {
        "mode": "runOnceForEachItem",
        "jsCode": "let raw = $json.output ?? \"\";\n\nif (typeof raw === \"object\") {\n\treturn { json: raw };\n}\n\nif (typeof raw === \"string\") {\n\traw = raw.trim();\n\tif (raw.startsWith('\"') && raw.endsWith('\"')) {\n\t\traw = raw.slice(1, -1)\n\t\t         .replace(/\\\\n/g, \"\\n\")\n\t\t         .replace(/\\\\\"/g, '\"');\n\t}\n\n\ttry {\n\t\tconst parsed = JSON.parse(raw);\n\t\treturn { json: parsed };\n\t} catch {}\n}\n\nreturn { json: { output: raw, direct_chart: false, chart: null } };\n"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [
        -768,
        320
      ],
      "id": "77acdc32-f718-4ffb-92ca-dc349dce9486",
      "name": "Parse Chart Data2"
    },
    {
      "parameters": {
        "rules": {
          "values": [
            {
              "conditions": {
                "options": {
                  "caseSensitive": true,
                  "leftValue": "",
                  "typeValidation": "loose",
                  "version": 2
                },
                "conditions": [
                  {
                    "leftValue": "={{ $json.direct_chart }}",
                    "rightValue": "true",
                    "operator": {
                      "type": "string",
                      "operation": "equals"
                    },
                    "id": "d30cf634-21eb-4260-b6b7-07935827945d"
                  }
                ],
                "combinator": "and"
              }
            },
            {
              "conditions": {
                "options": {
                  "caseSensitive": true,
                  "leftValue": "",
                  "typeValidation": "loose",
                  "version": 2
                },
                "conditions": [
                  {
                    "id": "2ccb3b8b-36b3-49e0-a046-f2154b3b4230",
                    "leftValue": "={{$json.send_excel}}",
                    "rightValue": "true",
                    "operator": {
                      "type": "string",
                      "operation": "equals",
                      "name": "filter.operator.equals"
                    }
                  }
                ],
                "combinator": "and"
              }
            },
            {
              "conditions": {
                "options": {
                  "caseSensitive": true,
                  "leftValue": "",
                  "typeValidation": "loose",
                  "version": 2
                },
                "conditions": [
                  {
                    "id": "0b82796d-a0c8-4799-b14f-9a59f17323c7",
                    "leftValue": "={{ $json.send_card }}",
                    "rightValue": "true",
                    "operator": {
                      "type": "string",
                      "operation": "equals",
                      "name": "filter.operator.equals"
                    }
                  }
                ],
                "combinator": "and"
              }
            },
            {
              "conditions": {
                "options": {
                  "caseSensitive": true,
                  "leftValue": "",
                  "typeValidation": "loose",
                  "version": 2
                },
                "conditions": [
                  {
                    "id": "643ab08f-8fea-4e35-ad6a-37ba18e6a094",
                    "leftValue": "={{$json.callback_query.data}}",
                    "rightValue": "",
                    "operator": {
                      "type": "string",
                      "operation": "empty",
                      "singleValue": true
                    }
                  }
                ],
                "combinator": "and"
              }
            }
          ]
        },
        "looseTypeValidation": true,
        "options": {}
      },
      "type": "n8n-nodes-base.switch",
      "typeVersion": 3.2,
      "position": [
        -528,
        0
      ],
      "id": "77bd1788-e863-49fd-9723-e6b41426b4aa",
      "name": "Switch1"
    },
    {
      "parameters": {
        "sessionIdType": "customKey",
        "sessionKey": "chat_id"
      },
      "type": "@n8n/n8n-nodes-langchain.memoryRedisChat",
      "typeVersion": 1.5,
      "position": [
        -1296,
        592
      ],
      "id": "99e4c854-fedd-4e68-835a-2cfd54826323",
      "name": "Redis Chat Memory",
      "credentials": {
        "redis": {
          "id": "ow6dH5LI0bWpG5Xc",
          "name": "Redis account 3"
        }
      }
    },
    {
      "parameters": {
        "jsCode": "// Берём весь chart-конфиг и отправляем дальше\nreturn [{\n  json: $json.chart\n}];\n\n"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [
        -304,
        -384
      ],
      "id": "72e53f24-6734-4e65-9147-db5192102363",
      "name": "Chart Builder"
    },
    {
      "parameters": {
        "descriptionType": "manual",
        "toolDescription": "Get all the data from Postgres, make sure you append the tables with correct schema. Every table is associated with some schema in the database.",
        "operation": "executeQuery",
        "query": "{{ $fromAI(\"sql_query\", \"SQL Query\") }}",
        "options": {}
      },
      "type": "n8n-nodes-base.postgresTool",
      "typeVersion": 2.6,
      "position": [
        -896,
        592
      ],
      "id": "a4498901-92a3-4e33-8677-fb8a3d576d78",
      "name": "Execute a SQL query in Postgres",
      "credentials": {
        "postgres": {
          "id": "rwMxCroQkG7g1tMx",
          "name": "Postgres account"
        }
      }
    },
    {
      "parameters": {
        "operation": "sendDocument",
        "chatId": "={{ $('Get Updates').item.json.result[0].message.chat.id }}",
        "binaryData": true,
        "additionalFields": {}
      },
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1.2,
      "position": [
        544,
        48
      ],
      "id": "afa1b6fe-2e88-4d6c-b23d-3ea4e373c77e",
      "name": "Send a document",
      "webhookId": "c6720f13-8ba7-4178-8e91-16ce745d45ac",
      "credentials": {
        "telegramApi": {
          "id": "LK8mWaz3RxYafXEV",
          "name": "Telegram account 5"
        }
      }
    },
    {
      "parameters": {
        "jsCode": "/**\n * Code4 – определяем, какой файл отправлять\n *\n *  ▸ если rep_name === \"all\" – берём архив всех карточек\n *  ▸ иначе – одну html-карточку конкретного торгового\n */\n\nconst rep   = $json.rep_name || '';\nconst isAll = rep.trim().toLowerCase() === 'all';\n\nreturn [{\n  json: {\n    rep_name: rep,\n    // путь к файлу, который будет читать следующая нода\n    file_path: isAll\n      ? '/home/adminvm/cards/card_*.html'                        // архив\n      : `/home/adminvm/cards/card_${rep.replace(/ /g, '_')}.html`  // одна карточка\n  }\n}];\n"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [
        -304,
        48
      ],
      "id": "efe794d4-8db6-4518-8336-621b09d65b58",
      "name": "Code4"
    },
    {
      "parameters": {
        "chatId": "={{ $('Get Updates').item.json.result[0].message.chat.id }}",
        "text": "={{ $('Code6').item.json.html }}",
        "replyMarkup": "inlineKeyboard",
        "inlineKeyboard": {
          "rows": [
            {
              "row": {
                "buttons": [
                  {
                    "text": "🚀 Отправить на обучение",
                    "additionalFields": {
                      "callback_data": "=train:{{ $json.log_id }}"
                    }
                  }
                ]
              }
            }
          ]
        },
        "additionalFields": {
          "appendAttribution": false,
          "parse_mode": "HTML"
        }
      },
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1.2,
      "position": [
        544,
        256
      ],
      "id": "d9414711-2d39-43ed-8e1b-87b6341c007d",
      "name": "Send a text message",
      "webhookId": "0c834359-b1c7-4b27-ae26-2106eb13a9d6",
      "credentials": {
        "telegramApi": {
          "id": "LK8mWaz3RxYafXEV",
          "name": "Telegram account 5"
        }
      }
    },
    {
      "parameters": {
        "fileSelector": "={{ $json.file_path }}",
        "options": {}
      },
      "type": "n8n-nodes-base.readWriteFile",
      "typeVersion": 1,
      "position": [
        128,
        48
      ],
      "id": "ec56e89c-15c2-40fd-ad1c-1386fd9ec0f5",
      "name": "Read/Write Filesfrom  Disk5"
    },
    {
      "parameters": {
        "jsCode": "const isCb = $json.is_callback ?? false;\n\nreturn [{\n  json: {\n    chat_id:        $json.chat_id,\n    user_id:        isCb ? $json.clicked_by : $json.user_id,\n    user_name:      $json.user_name || null,\n    user_request:   isCb ? $json.data : $json.text || null,\n    agent_response: isCb ? null : ($json.html || null),\n    n8n_execution:  $execution.id\n  }\n}];\n"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [
        0,
        240
      ],
      "id": "e74aa6e3-ad7c-4c59-929b-f51c8c7f58fa",
      "name": "Prepare Log"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "INSERT INTO public.agent_logs (\n  chat_id,\n  user_id,\n  user_name,\n  user_request,\n  agent_response,\n  n8n_execution\n)\nVALUES (\n  {{ $json.chat_id }},\n  {{ $json.user_id }},\n  {{ $json.user_name ? `'${$json.user_name.replace(/'/g,\"''\")}'` : 'NULL' }},\n  {{ $json.user_request ? `'${$json.user_request.replace(/'/g,\"''\")}'` : 'NULL' }},\n  {{ $json.agent_response ? `'${$json.agent_response.replace(/'/g,\"''\")}'` : 'NULL' }},\n  {{ $json.n8n_execution ? `'${$json.n8n_execution.replace(/'/g,\"''\")}'` : 'NULL' }}\n)\nRETURNING id AS log_id;\n",
        "options": {}
      },
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [
        208,
        416
      ],
      "id": "1a7e8438-0ca1-4c50-a580-7c84a176bc86",
      "name": "Execute a SQL query",
      "credentials": {
        "postgres": {
          "id": "rwMxCroQkG7g1tMx",
          "name": "Postgres account"
        }
      }
    },
    {
      "parameters": {
        "mode": "combine",
        "combineBy": "combineByPosition",
        "options": {}
      },
      "type": "n8n-nodes-base.merge",
      "typeVersion": 3.2,
      "position": [
        -160,
        656
      ],
      "id": "25924fb2-3e95-4678-9c12-c5f6aaa997f6",
      "name": "Merge"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "INSERT INTO public.training_clicks (log_id, chat_id, clicked_by, status)\nVALUES (\n  {{ $('Get Last Message').item.json.log_id }},\n  {{ $('Get Last Message').item.json.chat_id }},\n  {{ $('Get Last Message').item.json.clicked_by }},\n  'в очереди'\n)\nRETURNING id;\n",
        "options": {}
      },
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [
        -1520,
        -144
      ],
      "id": "99a8c75d-50d2-4790-ba0f-cad07a7d671c",
      "name": "Execute a SQL query1",
      "credentials": {
        "postgres": {
          "id": "rwMxCroQkG7g1tMx",
          "name": "Postgres account"
        }
      }
    },
    {
      "parameters": {
        "chatId": "={{ $('Get Last Message').item.json.chat_id }}",
        "text": "Ваш запрос принят в работу, ожидайте",
        "additionalFields": {
          "appendAttribution": false
        }
      },
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1.2,
      "position": [
        -1872,
        -496
      ],
      "id": "257a269a-12c8-4bf7-b602-d35ea55a8d33",
      "name": "Send a text message2",
      "webhookId": "23519533-f8e9-42ea-8e67-26b940da6bfc",
      "credentials": {
        "telegramApi": {
          "id": "LK8mWaz3RxYafXEV",
          "name": "Telegram account 5"
        }
      }
    },
    {
      "parameters": {
        "mode": "combine",
        "combineBy": "combineByPosition",
        "options": {}
      },
      "type": "n8n-nodes-base.merge",
      "typeVersion": 3.2,
      "position": [
        384,
        256
      ],
      "id": "762eb050-cf86-4c10-bcb3-403053235c68",
      "name": "Merge1"
    },
    {
      "parameters": {
        "chatId": "={{ $('Get Last Message').item.json.chat_id }}",
        "text": "Сделано!",
        "additionalFields": {
          "appendAttribution": false
        }
      },
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1.2,
      "position": [
        -1024,
        -448
      ],
      "id": "d3cf2f00-7dc5-4487-bed0-8e4e6f2decdb",
      "name": "Send a text message3",
      "webhookId": "efb2320b-b32d-415b-ba42-72c41f46696b",
      "credentials": {
        "telegramApi": {
          "id": "LK8mWaz3RxYafXEV",
          "name": "Telegram account 5"
        }
      }
    },
    {
      "parameters": {
        "workflowId": {
          "__rl": true,
          "value": "ZnhDE5fEX25JEZUO",
          "mode": "list",
          "cachedResultName": "Mail Packager & Send"
        },
        "workflowInputs": {
          "mappingMode": "defineBelow",
          "value": {
            "recipient": "={{$json.recipient || $json.query.recipient}}",
            "subject": "={{ $json.subject }}",
            "body": "={{ $json.body }}"
          },
          "matchingColumns": [],
          "schema": [
            {
              "id": "recipient",
              "displayName": "recipient",
              "required": false,
              "defaultMatch": false,
              "display": true,
              "canBeUsedToMatch": true,
              "type": "string"
            },
            {
              "id": "subject",
              "displayName": "subject",
              "required": false,
              "defaultMatch": false,
              "display": true,
              "canBeUsedToMatch": true,
              "type": "string"
            },
            {
              "id": "body",
              "displayName": "body",
              "required": false,
              "defaultMatch": false,
              "display": true,
              "canBeUsedToMatch": true,
              "type": "string"
            },
            {
              "id": "attachments",
              "displayName": "attachments",
              "required": false,
              "defaultMatch": false,
              "display": true,
              "canBeUsedToMatch": true,
              "type": "string",
              "removed": true
            }
          ],
          "attemptToConvertTypes": true,
          "convertFieldsToString": true
        },
        "options": {
          "waitForSubWorkflow": true
        }
      },
      "type": "n8n-nodes-base.executeWorkflow",
      "typeVersion": 1.2,
      "position": [
        -880,
        816
      ],
      "id": "993db747-dd46-4b24-97f7-047e01db392c",
      "name": "Execute Workflow"
    },
    {
      "parameters": {
        "jsCode": "// минимальный чистый пайп без вложений\nconst trig = $item(0, 'When Executed by Another Workflow')?.json ?? {};\nconst rq   = trig.query ?? {};\n\nconst recipient = $json.recipient ?? trig.recipient ?? rq.recipient ?? null;\nconst subject   = $json.subject   ?? trig.subject   ?? rq.subject   ?? 'Без темы';\nconst body      = $json.body      ?? trig.body      ?? rq.body      ?? '';\n\nif (!recipient) throw new Error('recipient пуст в родительском WF');\n\n// НИЧЕГО про attachments и binary не передаём\nreturn [{ json: { recipient, subject, body } }];\n"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [
        -1024,
        816
      ],
      "id": "ae1dab3f-d655-4155-8d77-89f5433570ad",
      "name": "Code1"
    },
    {
      "parameters": {
        "workflowInputs": {
          "values": [
            {
              "name": "recipient"
            },
            {
              "name": "subject"
            },
            {
              "name": "body"
            }
          ]
        }
      },
      "type": "n8n-nodes-base.executeWorkflowTrigger",
      "typeVersion": 1.1,
      "position": [
        -1312,
        816
      ],
      "id": "e382e80a-4b41-4a41-be48-bfdf826a0a77",
      "name": "When Executed by Another Workflow"
    },
    {
      "parameters": {
        "jsCode": "const q = $json.query || {};\nreturn [{\n  json: {\n    recipient: q.recipient ?? $json.recipient ?? null,\n    subject:   q.subject   ?? $json.subject   ?? 'Без темы',\n    body:      q.body      ?? $json.body      ?? '',\n    attachments: Array.isArray(q.attachments ?? $json.attachments)\n      ? (q.attachments ?? $json.attachments) : [],\n  },\n  binary: $binary,\n}];\n"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [
        -1168,
        816
      ],
      "id": "7019ff4b-6464-4d52-b070-11747596acc0",
      "name": "Code7"
    },
    {
      "parameters": {
        "command": "=echo '{{ $json.jsonText }}' > /tmp/input.txt && \\\n/home/adminvm/venv/bin/python /home/adminvm/scripts/generate_excel.py --json-out < /tmp/input.txt\n"
      },
      "type": "n8n-nodes-base.executeCommand",
      "typeVersion": 1,
      "position": [
        -144,
        -176
      ],
      "id": "42ccd7f8-b358-4002-a558-05280b20346b",
      "name": "generate_excel"
    },
    {
      "parameters": {
        "jsCode": "/**\n * Code3 – готовим данные для Excel\n * Сохраняем ВСЕ поля, чтобы subject не потерялся\n */\nreturn $input.all().map(item => {\n  const table   = item.json.table_data || [];\n  const subject = item.json.subject    || 'Excel-отчёт';\n\n  return {\n    json: {\n      ...item.json,                 // ⬅️   сохраняем всё, что пришло\n      jsonText: JSON.stringify(table),\n      subject,                      // дублируем, на всякий случай\n    }\n  };\n});\n"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [
        -304,
        -176
      ],
      "id": "d5e2ea23-0006-40d8-a87f-fd68dc6926b7",
      "name": "Code3"
    },
    {
      "parameters": {
        "fileSelector": "/home/adminvm/scripts/report.xlsx",
        "options": {
          "dataPropertyName": "data"
        }
      },
      "type": "n8n-nodes-base.readWriteFile",
      "typeVersion": 1,
      "position": [
        0,
        -176
      ],
      "id": "9f636349-d9dc-44ef-b480-e64b1ff57518",
      "name": "Read/Write Files from Disk1"
    },
    {
      "parameters": {
        "chatId": "={{ $('Get Updates').item.json.result[0].message.chat.id }}",
        "text": "Отправил",
        "additionalFields": {
          "appendAttribution": false
        }
      },
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1.2,
      "position": [
        544,
        -176
      ],
      "id": "a1e6f189-24fc-47d4-bb62-d0f3f41181e2",
      "name": "Send a text message1",
      "webhookId": "0babe63a-c35f-4ed6-94c1-a54f1e990178",
      "credentials": {
        "telegramApi": {
          "id": "LK8mWaz3RxYafXEV",
          "name": "Telegram account 5"
        }
      }
    },
    {
      "parameters": {
        "jsCode": "// Вход: { stdout: \"<BASE64>\", exitCode: 0 }\n// Выход: json с полями письма + binary.data c Excel\n\n// 1) base64 из stdout\nconst b64 = String($json.stdout || '').trim();\nif (!b64) throw new Error('stdout пуст: нет base64 Excel');\n\n// 2) подтягиваем поля письма из узла, где они лежат (замени имя узла на своё)\nconst src = $('Parse Chart Data2').first().json || {}; // <- твой узел с subject/body/recipient\n\n// 3) формируем item для подворкфлоу SendMailWorkflow\nreturn [{\n  json: {\n    recipient: String(src.recipient || '').trim(),\n    subject:   String(src.subject   || 'Без темы'),\n    body:      String(src.body      || ''),\n    attachments: ['data']                 // скажем саб-воркфлоу прикрепить binary \"data\"\n  },\n  binary: {\n    data: {\n      data: b64,                           // <-- сам файл (base64)\n      fileName: 'report.xlsx',\n      mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'\n    }\n  }\n}];\n"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [
        288,
        -176
      ],
      "id": "0feecadd-2e6c-4ce7-af18-f024b8d61f34",
      "name": "Code2"
    },
    {
      "parameters": {
        "workflowId": {
          "__rl": true,
          "value": "ZnhDE5fEX25JEZUO",
          "mode": "list",
          "cachedResultName": "Mail Packager & Send"
        },
        "workflowInputs": {
          "mappingMode": "defineBelow",
          "value": {},
          "matchingColumns": [],
          "schema": [
            {
              "id": "recipient",
              "displayName": "recipient",
              "required": false,
              "defaultMatch": false,
              "display": true,
              "canBeUsedToMatch": true,
              "type": "string"
            },
            {
              "id": "subject",
              "displayName": "subject",
              "required": false,
              "defaultMatch": false,
              "display": true,
              "canBeUsedToMatch": true,
              "type": "string"
            },
            {
              "id": "body",
              "displayName": "body",
              "required": false,
              "defaultMatch": false,
              "display": true,
              "canBeUsedToMatch": true,
              "type": "string"
            },
            {
              "id": "attachments",
              "displayName": "attachments",
              "required": false,
              "defaultMatch": false,
              "display": true,
              "canBeUsedToMatch": true,
              "type": "array"
            }
          ],
          "attemptToConvertTypes": false,
          "convertFieldsToString": true
        },
        "options": {}
      },
      "type": "n8n-nodes-base.executeWorkflow",
      "typeVersion": 1.2,
      "position": [
        416,
        -176
      ],
      "id": "18dc96bd-7331-4a79-8300-87c564b945be",
      "name": "Execute Workflow1"
    },
    {
      "parameters": {
        "command": "base64 -w 0 /home/adminvm/scripts/report.xlsx\n"
      },
      "type": "n8n-nodes-base.executeCommand",
      "typeVersion": 1,
      "position": [
        144,
        -176
      ],
      "id": "a57c6eab-89b1-40bf-8755-83496ce1ea89",
      "name": "Execute Command1"
    },
    {
      "parameters": {
        "description": "Send email with optional attachments.\nInputs (JSON):\n- recipient: string (email or contact name/alias)\n- subject: string (default: \"Без темы\")\n- body: string (email HTML/text)\n- attachments?: array<string> — names of binary props; if not provided, do NOT send this field. The workflow will generate note.txt from body.\nReturn: status and messageId.\nNever pass \"none\" for attachments.\n",
        "workflowId": {
          "__rl": true,
          "value": "Zy5T19Qy9MXp5t1v",
          "mode": "list",
          "cachedResultName": "For_Muslim"
        },
        "workflowInputs": {
          "mappingMode": "defineBelow",
          "value": {
            "recipient": "={{ $fromAI('recipient', ``, 'string') }}",
            "subject": "={{ $fromAI('subject', ``, 'string') }}",
            "body": "={{ $fromAI('body', ``, 'string') }}"
          },
          "matchingColumns": [],
          "schema": [
            {
              "id": "recipient",
              "displayName": "recipient",
              "required": false,
              "defaultMatch": false,
              "display": true,
              "canBeUsedToMatch": true,
              "type": "string"
            },
            {
              "id": "subject",
              "displayName": "subject",
              "required": false,
              "defaultMatch": false,
              "display": true,
              "canBeUsedToMatch": true,
              "type": "string"
            },
            {
              "id": "body",
              "displayName": "body",
              "required": false,
              "defaultMatch": false,
              "display": true,
              "canBeUsedToMatch": true,
              "type": "string"
            }
          ],
          "attemptToConvertTypes": false,
          "convertFieldsToString": false
        }
      },
      "type": "@n8n/n8n-nodes-langchain.toolWorkflow",
      "typeVersion": 2.2,
      "position": [
        -1184,
        592
      ],
      "id": "736b43c6-34c9-4069-9cd2-048da35d3a21",
      "name": "SendMailWorkflow"
    },
    {
      "parameters": {
        "operation": "deleteMessage",
        "chatId": "={{ $('Send a text message2').item.json.result.chat.id }}",
        "messageId": "={{ $('Send a text message2').item.json.result.message_id }}"
      },
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1.2,
      "position": [
        976,
        -64
      ],
      "id": "a92c30aa-c951-4e8c-b833-e5a579c9bb7a",
      "name": "Delete a chat message3",
      "webhookId": "eaa669a2-0b08-449d-a9b8-f30abfad2b19",
      "credentials": {
        "telegramApi": {
          "id": "LK8mWaz3RxYafXEV",
          "name": "Telegram account 5"
        }
      }
    },
    {
      "parameters": {
        "mode": "combine",
        "combineBy": "combineByPosition",
        "options": {}
      },
      "type": "n8n-nodes-base.merge",
      "typeVersion": 3.2,
      "position": [
        816,
        -464
      ],
      "id": "2417dd69-9178-4246-b41a-2286343ff19a",
      "name": "Merge2"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT EXISTS(\n  SELECT 1 FROM bot_autorized_chats WHERE chat_id = $1\n) AS allowed;\n",
        "options": {
          "queryReplacement": "={{ $json.chat_id }}"
        }
      },
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [
        -2256,
        400
      ],
      "id": "15f260ee-13ee-4b51-a313-a292eb242fb5",
      "name": "Execute a SQL query2",
      "credentials": {
        "postgres": {
          "id": "rwMxCroQkG7g1tMx",
          "name": "Postgres account"
        }
      }
    },
    {
      "parameters": {
        "rules": {
          "values": [
            {
              "conditions": {
                "options": {
                  "caseSensitive": true,
                  "leftValue": "",
                  "typeValidation": "strict",
                  "version": 2
                },
                "conditions": [
                  {
                    "leftValue": "={{ $json.allowed }}",
                    "rightValue": "",
                    "operator": {
                      "type": "boolean",
                      "operation": "true",
                      "singleValue": true
                    },
                    "id": "1548867d-fd58-4df4-a461-c1a894c9d633"
                  }
                ],
                "combinator": "and"
              },
              "renameOutput": true,
              "outputKey": "Доступ есть"
            },
            {
              "conditions": {
                "options": {
                  "caseSensitive": true,
                  "leftValue": "",
                  "typeValidation": "strict",
                  "version": 2
                },
                "conditions": [
                  {
                    "id": "69f03a16-13f2-4fc4-b927-92aa470e7b89",
                    "leftValue": "={{ $json.allowed }}",
                    "rightValue": "",
                    "operator": {
                      "type": "boolean",
                      "operation": "false",
                      "singleValue": true
                    }
                  }
                ],
                "combinator": "and"
              },
              "renameOutput": true,
              "outputKey": "Доступа нет"
            }
          ]
        },
        "options": {}
      },
      "type": "n8n-nodes-base.switch",
      "typeVersion": 3.2,
      "position": [
        -2112,
        16
      ],
      "id": "7b807b88-68ae-458c-b210-b16b5c0ca4d6",
      "name": "Switch2"
    },
    {
      "parameters": {
        "operation": "write",
        "fileName": "/home/adminvm/n8n_data/tg_id",
        "dataPropertyName": "=data",
        "options": {
          "append": "={{ $json.update_id }}"
        }
      },
      "type": "n8n-nodes-base.readWriteFile",
      "typeVersion": 1,
      "position": [
        -1664,
        -256
      ],
      "id": "c98bd494-3dc9-4935-a568-d800d40b84fa",
      "name": "Read/Write Files from Disk4"
    },
    {
      "parameters": {
        "jsCode": "const updateId = $items(\"Get Last Message\")[0].json.update_id;\n\n\n// Преобразуем update_id в JSON и затем в бинарный формат\nconst data = JSON.stringify({ last_processed_update_id: updateId });\nconsole.log('Preparing data for file:', data);\n\nreturn [{\n  json: {},\n  binary: {\n    data: {\n      data: Buffer.from(data).toString('base64'),\n      mimeType: 'application/json'\n    }\n  }\n}];"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [
        -1840,
        -80
      ],
      "id": "2b528f90-9a50-4f9b-b34a-d4b229e6bcb5",
      "name": "Code5"
    },
    {
      "parameters": {
        "chatId": "={{ $('Get Last Message').item.json.chat_id }}",
        "text": "У вас нет доступа к этому боту",
        "additionalFields": {
          "appendAttribution": false
        }
      },
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1.2,
      "position": [
        -1408,
        -448
      ],
      "id": "7d2f6a77-4584-4f5c-8286-dff0e9a98141",
      "name": "Send a text message4",
      "webhookId": "d4b36267-6e4d-4533-b4c9-be78a88acadf",
      "credentials": {
        "telegramApi": {
          "id": "LK8mWaz3RxYafXEV",
          "name": "Telegram account 5"
        }
      }
    },
    {
      "parameters": {
        "resource": "audio",
        "operation": "transcribe",
        "options": {
          "language": "ru"
        }
      },
      "type": "@n8n/n8n-nodes-langchain.openAi",
      "typeVersion": 1.8,
      "position": [
        -1024,
        32
      ],
      "id": "b1bb20f6-b845-482f-bbb7-b0401a89abc2",
      "name": "Transcribe a recording",
      "credentials": {
        "openAiApi": {
          "id": "Qc85KFzgvCeEqnB7",
          "name": "OpenAi account 3"
        }
      }
    }
  ],
  "pinData": {},
  "connections": {
    "AI Agent": {
      "main": [
        [
          {
            "node": "Parse Chart Data2",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "OpenAI Chat Model": {
      "ai_languageModel": [
        [
          {
            "node": "AI Agent",
            "type": "ai_languageModel",
            "index": 0
          }
        ]
      ]
    },
    "Calculator": {
      "ai_tool": [
        [
          {
            "node": "AI Agent",
            "type": "ai_tool",
            "index": 0
          }
        ]
      ]
    },
    "Get Updates": {
      "main": [
        [
          {
            "node": "Get Last Message",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Get Last Message": {
      "main": [
        [
          {
            "node": "Merge",
            "type": "main",
            "index": 1
          },
          {
            "node": "Execute a SQL query2",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Code": {
      "main": [
        [
          {
            "node": "Read/Write Files from Disk",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Read/Write Files from Disk2": {
      "main": [
        [
          {
            "node": "Parse Update ID",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Parse Update ID": {
      "main": [
        [
          {
            "node": "Get Updates",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Schedule Trigger": {
      "main": [
        [
          {
            "node": "Read/Write Files from Disk2",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Switch": {
      "main": [
        [
          {
            "node": "Execute a SQL query1",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Get Updates1",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "AI Agent",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Extract File Path1": {
      "main": [
        [
          {
            "node": "Download Voice1",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Download Voice1": {
      "main": [
        [
          {
            "node": "Transcribe a recording",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Get Updates1": {
      "main": [
        [
          {
            "node": "Extract File Path1",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Execute Command": {
      "main": [
        [
          {
            "node": "Read/Write Files from Disk3",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Read/Write Files from Disk3": {
      "main": [
        [
          {
            "node": "Telegram2",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Code6": {
      "main": [
        [
          {
            "node": "Merge",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Parse Chart Data2": {
      "main": [
        [
          {
            "node": "Switch1",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Switch1": {
      "main": [
        [
          {
            "node": "Chart Builder",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Code3",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Code4",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Code6",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Redis Chat Memory": {
      "ai_memory": [
        [
          {
            "node": "AI Agent",
            "type": "ai_memory",
            "index": 0
          }
        ]
      ]
    },
    "Chart Builder": {
      "main": [
        [
          {
            "node": "Execute Command",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Execute a SQL query in Postgres": {
      "ai_tool": [
        [
          {
            "node": "AI Agent",
            "type": "ai_tool",
            "index": 0
          }
        ]
      ]
    },
    "Code4": {
      "main": [
        [
          {
            "node": "Read/Write Filesfrom  Disk5",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Send a text message": {
      "main": [
        [
          {
            "node": "Merge2",
            "type": "main",
            "index": 1
          }
        ]
      ]
    },
    "Read/Write Filesfrom  Disk5": {
      "main": [
        [
          {
            "node": "Send a document",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Prepare Log": {
      "main": [
        [
          {
            "node": "Execute a SQL query",
            "type": "main",
            "index": 0
          },
          {
            "node": "Merge1",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Execute a SQL query": {
      "main": [
        [
          {
            "node": "Merge1",
            "type": "main",
            "index": 1
          }
        ]
      ]
    },
    "Merge": {
      "main": [
        [
          {
            "node": "Prepare Log",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Execute a SQL query1": {
      "main": [
        [
          {
            "node": "Send a text message3",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Merge1": {
      "main": [
        [
          {
            "node": "Send a text message",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Code1": {
      "main": [
        [
          {
            "node": "Execute Workflow",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "When Executed by Another Workflow": {
      "main": [
        [
          {
            "node": "Code7",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Code7": {
      "main": [
        [
          {
            "node": "Code1",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "generate_excel": {
      "main": [
        [
          {
            "node": "Read/Write Files from Disk1",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Code3": {
      "main": [
        [
          {
            "node": "generate_excel",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Read/Write Files from Disk1": {
      "main": [
        [
          {
            "node": "Execute Command1",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Code2": {
      "main": [
        [
          {
            "node": "Execute Workflow1",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Execute Workflow1": {
      "main": [
        [
          {
            "node": "Send a text message1",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Execute Command1": {
      "main": [
        [
          {
            "node": "Code2",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "SendMailWorkflow": {
      "ai_tool": [
        [
          {
            "node": "AI Agent",
            "type": "ai_tool",
            "index": 0
          }
        ]
      ]
    },
    "Send a text message2": {
      "main": [
        [
          {
            "node": "Merge2",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Telegram2": {
      "main": [
        [
          {
            "node": "Merge2",
            "type": "main",
            "index": 1
          }
        ]
      ]
    },
    "Send a text message1": {
      "main": [
        [
          {
            "node": "Merge2",
            "type": "main",
            "index": 1
          }
        ]
      ]
    },
    "Send a document": {
      "main": [
        [
          {
            "node": "Merge2",
            "type": "main",
            "index": 1
          }
        ]
      ]
    },
    "Delete a chat message3": {
      "main": [
        []
      ]
    },
    "Merge2": {
      "main": [
        [
          {
            "node": "Delete a chat message3",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Send a text message3": {
      "main": [
        [
          {
            "node": "Merge2",
            "type": "main",
            "index": 1
          }
        ]
      ]
    },
    "Execute a SQL query2": {
      "main": [
        [
          {
            "node": "Switch2",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Switch2": {
      "main": [
        [
          {
            "node": "Switch",
            "type": "main",
            "index": 0
          },
          {
            "node": "Code",
            "type": "main",
            "index": 0
          },
          {
            "node": "Send a text message2",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Code5",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Code5": {
      "main": [
        [
          {
            "node": "Read/Write Files from Disk4",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Read/Write Files from Disk4": {
      "main": [
        [
          {
            "node": "Send a text message4",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Transcribe a recording": {
      "main": [
        [
          {
            "node": "AI Agent",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  },
  "active": false,
  "settings": {
    "executionOrder": "v1"
  },
  "versionId": "8a3ca006-96ba-4fba-a629-3a27fc01d23a",
  "meta": {
    "templateCredsSetupCompleted": true,
    "instanceId": "14d29bd49266811c3d746addfedf829ab5a522313a58bcf72777d5e72c76d232"
  },
  "id": "VL0ysfTmWyWfcLGZ",
  "tags": []
}