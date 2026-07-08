// ===== AgroPILOT — ЭСКИЗ: объектная модель моков (навигация ОТ ОБЪЕКТОВ) =====
// Иерархия ТЗ: Стратегия → Цели → Проекты/Сделки/Концепции → Задачи → Артефакты
// Мягкая связь снизу-вверх по industry + need_type.
// M2.5: единый флаг демо-режима. true = использовать mock-сид (MOCKO); false = работа только от BFF. Поведение подключается в M2.6/M2.7.
window.DEV_MOCK = (typeof window.DEV_MOCK === 'boolean') ? window.DEV_MOCK : true;
window.MOCKO = (function () {
    const TODAY = new Date().toISOString().slice(0, 10);

  // --- справочники ---
  const STAGES = ['Зацепка', 'Оценка', 'Договор', 'Проектирование', 'Реализация', 'Сервис'];
  const NEED = ['орошение', 'теплицы', 'логистика', 'хранение', 'автоматизация'];
  const IND = ['овощеводство', 'садоводство', 'зерновые', 'тепличное', 'агрологистика'];

  // --- КЛИЕНТЫ (объект верхнего уровня) ---
  const clients = [
    { id: 'C1', name: 'АО «ЮгАгро»',        industry: 'овощеводство', region: 'Крым',     contact: 'И. Петров',  need: ['орошение','автоматизация'], health: 'green',  dealsCount: 2 },
    { id: 'C2', name: 'ФХ «Северный сад»',  industry: 'садоводство',  region: 'Кубань',   contact: 'А. Лозовая', need: ['хранение'],                 health: 'yellow', dealsCount: 1 },
    { id: 'C3', name: 'ООО «ТеплицаПро»',   industry: 'тепличное',    region: 'Севастополь', contact: 'М. Гром',  need: ['теплицы','автоматизация'],   health: 'green',  dealsCount: 1 },
    { id: 'C4', name: 'КФХ «Степь-Зерно»',  industry: 'зерновые',     region: 'Ростов',   contact: 'В. Соколов', need: ['логистика','хранение'],      health: 'red',    dealsCount: 1 },
  ];

  // --- ВХОДЯЩИЕ (лента событий: Telegram / уведомления / мониторинг → быстрое создание объекта) ---
  // src: канал; kind: тип события; предлагаемый объект: suggest (deal|task|client) + предзаполненные поля.
  // status: 'new' (непрочитано) | 'done' (обработано) | 'dismissed'
  const inbox = [
    { id: 'IN1', src: 'Telegram', icon: '✈️', from: '@yug_agro_bot', time: '2026-06-24 08:12', status: 'new',
      text: 'Новая заявка: КФХ «Рассвет» интересуется капельным орошением на 40 га. Контакт: А. Морозов, +7 978 555-12-34',
      suggest: 'deal', fields: { client: 'КФХ «Рассвет»', title: 'Капельное орошение 40 га', need: 'орошение', stage: 'Зацепка' } },
    { id: 'IN2', src: 'Мониторинг', icon: '📡', from: 'zakupki.gov.ru', time: '2026-06-24 09:40', status: 'new',
      text: 'Тендер: «Система хранения овощей», Ростовская обл., старт 9.2 млн ₽. Подача до 05.07.',
      suggest: 'task', fields: { title: 'Подготовить заявку на тендер (хранение)', type: 'kp', date: '2026-07-03' } },
    { id: 'IN3', src: 'Email', icon: '✉️', from: 'sad@severniy.ru', time: '2026-06-23 17:05', status: 'new',
      text: 'Клиент ФХ «Северный сад» просит перезвонить по договору хранения яблок.',
      suggest: 'task', fields: { title: 'Перезвонить «Северный сад» (договор)', type: 'call', date: '2026-06-25', dealHint: 'D3' } },
    { id: 'IN4', src: 'Telegram', icon: '🌾', from: '@agro_news', time: '2026-06-23 11:20', status: 'new',
      text: 'Рынок: субсидии на теплицы в ЮФО продлены. Можно предложить действующим лидам.',
      suggest: 'task', fields: { title: 'Инфоповод: субсидии на теплицы — разослать лидам', type: 'email', date: '2026-06-26' } },
    { id: 'IN5', src: 'Email', icon: '✉️', from: 'info@teplica-pro.ru', time: '2026-06-22 14:30', status: 'done',
      text: 'Новый контакт: ООО «АгроМир», интерес к автоматизации полива.',
      suggest: 'client', fields: { client: 'ООО «АгроМир»', need: 'автоматизация' } },
  ];

  // --- КОМАНДА (Этап 1: координация; объекты закрепляются за людьми через owner) ---
  // name совпадает с deals.owner / tasks.owner / goals.owner — загрузка считается по совпадению имени.
  const team = [
    { id: 'U1', name: 'Екатерина', role: 'Руководитель продаж', avatar: '👩‍💼', cap: 6 },
    { id: 'U2', name: 'Оксана',    role: 'Менеджер проектов', avatar: '👩‍🔧', cap: 5 },
    { id: 'U3', name: 'Дмитрий',  role: 'Инженер-проектировщик', avatar: '👨‍🔬', cap: 4 },
    { id: 'U4', name: 'Марина',   role: 'Маркетолог / SSM', avatar: '👩‍🎨', cap: 5 },
    { id: 'U5', name: 'Сергей',   role: 'Аналитик / мониторинг', avatar: '👨‍💻', cap: 5 },
  ];

  // --- СТРАТЕГИЯ → НАПРАВЛЕНИЯ → ЦЕЛИ (объект уровня выше сделок) ---
  // Иерархия: Стратегия → Направления (direction) → Цели → Проекты → Сделки
  // Направления — это глубже стратегии, но уже связанные с конкретными нишами.
  const strategy = {
    title: 'Стратегия 2026: рост в орошении и продвижение продукта',
    horizon: '2026',
    directions: [
      { id: 'DIR1', title: 'Автоматизация и орошение', needMatch: ['орошение', 'автоматизация', 'kapelka'], description: 'Капельное, фертигиration, датчики, контроллеры' },
      { id: 'DIR2', title: 'Виноградарство и тепличное хозяйство', needMatch: ['виноград', 'теплицы', 'фрукты'], description: 'Глубоковласные теплицы, машибор, садоводство' },
      { id: 'DIR3', title: 'Хранение и логистика', needMatch: ['хранение', 'логистика', 'склад'], description: 'Холодное хранение, доставка, распределение' },
    ]
  };
  // Цели привязываются к направлениям через directionId (в дополнение к needMatch)
  // Цели: связь со сделками — МЯГКАЯ, снизу вверх (ТЗ 2.1/3.1): выводится по needMatch (потребностям ниши), а не вводится вручную.
  // kind: revenue (сумма сделок) | packages (упаковки «в продвижении»). periodStart/End — для формулы pace (сигнал «отстаёт»).
  const goals = [
    { id: 'G1', title: 'Выручка по орошению 25 млн ₽', metric: 'Сумма сделок (орошение/автоматизация)', target: 25000000, unit: '₽', period: '2026', owner: 'Екатерина', kind: 'revenue', needMatch: ['орошение', 'автоматизация'], periodStart: '2026-01-01', periodEnd: '2026-12-31' },
    { id: 'G2', title: 'Запустить продуктовые упаковки в продвижение', metric: 'Упаковок «в продвижении»', target: 3, unit: 'шт', period: '2026-H2', owner: 'Оксана', kind: 'packages', needMatch: [], periodStart: '2026-07-01', periodEnd: '2026-12-31' },
    { id: 'G3', title: 'Выход в сегмент хранения', metric: 'Сумма сделок (хранение/логистика)', target: 12000000, unit: '₽', period: '2026', owner: 'Екатерина', kind: 'revenue', needMatch: ['хранение', 'логистика'], periodStart: '2026-01-01', periodEnd: '2026-12-31' },
  ];

  // --- ПРОЕКТЫ (ЧАНК 6.13: средний уровень иерархии Стратегия→Цели→ПРОЕКТЫ→Сделки/Задачи) ---
  // goalId — ЖЁСТКАЯ привязка проекта к одной цели. need — ниша проекта (для авто-подбора сделок).
  // Проект↔сделка — SOFT auto: deal.need===project.need И сделка матчит цель проекта; override через dealPin[] (закрепить) или '-' внутри dealPin для исключения сделки.
  // target — план суммы (₽) для прогресса проекта (вариант «а»: сумма сумм сделок проекта / target).
  const projects = [
    { id: 'PR1', title: 'Автополив юга', goalId: 'G1', need: 'орошение',      status: 'активен', ownerId: 'U1', periodStart: '2026-01-01', periodEnd: '2026-09-30', target: 6000000, dealPin: [] },
    { id: 'PR2', title: 'Телеметрия и контроллеры', goalId: 'G1', need: 'автоматизация', status: 'активен', ownerId: 'U3', periodStart: '2026-03-01', periodEnd: '2026-12-31', target: 3000000, dealPin: [] },
    { id: 'PR3', title: 'Склад-хаб (хранение)', goalId: 'G3', need: 'хранение',  status: 'активен', ownerId: 'U2', periodStart: '2026-02-01', periodEnd: '2026-11-30', target: 9000000, dealPin: [] },
  ];

  // --- СДЕЛКИ/ПРОЕКТЫ (центральный объект; единая карточка Клиент↔Сделка) ---
  // goalId — к какой цели тянет сделка ('' — не привязана).
  const deals = [
    { id: 'D1', clientId: 'C1', title: 'Система капельного орошения, 120 га', stage: 'Проектирование', amount: 4200000, need: 'орошение',      owner: 'Екатерина', updated: '2026-06-23', score: 86, goalId: 'G1' },
    { id: 'D2', clientId: 'C1', title: 'Автоматизация полива (контроллеры)',  stage: 'Оценка',        amount: 980000,  need: 'автоматизация', owner: 'Екатерина', updated: '2026-06-22', score: 64, goalId: 'G1' },
    { id: 'D3', clientId: 'C2', title: 'Холодильное хранение яблок',          stage: 'Договор',       amount: 6100000, need: 'хранение',      owner: 'Екатерина', updated: '2026-06-24', score: 78, goalId: 'G3' },
    { id: 'D4', clientId: 'C3', title: 'Теплица 0.5 га под ключ',             stage: 'Реализация',    amount: 8800000, need: 'теплицы',       owner: 'Оксана',    updated: '2026-06-21', score: 90, goalId: '' },
    { id: 'D5', clientId: 'C4', title: 'Зерновая логистика + хранение',       stage: 'Зацепка',       amount: 3300000, need: 'логистика',     owner: 'Екатерина', updated: '2026-06-20', score: 41, goalId: 'G3' },
  ];

  // --- ЗАДАЧИ (привязаны к сделке/клиенту, не к агенту) ---
  const tasks = [
    { id: 'T1', dealId: 'D1', clientId: 'C1', title: 'Согласовать смету по орошению',      type: 'kp',   date: '2026-06-24', owner: 'Екатерина', score: 86, status: 'open',    deps: [],          subtaskOf: null },
    { id: 'T2', dealId: 'D3', clientId: 'C2', title: 'Подписать договор (хранение)',        type: 'meet', date: '2026-06-24', owner: 'Екатерина', score: 78, status: 'open',    deps: ['T1'],      subtaskOf: null },
    { id: 'T3', dealId: 'D2', clientId: 'C1', title: 'Звонок: уточнить кол-во контроллеров', type: 'call', date: '2026-06-22', owner: 'Екатерина', score: 64, status: 'overdue', deps: [],          subtaskOf: null },
    { id: 'T4', dealId: 'D4', clientId: 'C3', title: 'Контроль монтажа теплицы (этап 2)',    type: 'meet', date: '2026-06-25', owner: 'Оксана',    score: 90, status: 'open',    deps: [],          subtaskOf: null },
    { id: 'T5', dealId: 'D3', clientId: 'C2', title: 'Собрать комплект документов к договору',  type: 'email',date: '2026-06-23', owner: 'Екатерина', score: 55, status: 'open',    deps: [],          subtaskOf: 'T2' },
    { id: 'T6', dealId: 'D4', clientId: 'C3', title: 'Проверить каркас и фундамент',     type: 'meet', date: '2026-06-24', owner: 'Дмитрий',   score: 72, status: 'done',    deps: [],          subtaskOf: 'T4' },
    { id: 'T7', dealId: 'D4', clientId: 'C3', title: 'Принять поливочный узел',           type: 'meet', date: '2026-06-26', owner: 'Дмитрий',   score: 68, status: 'open',    deps: [],          subtaskOf: 'T4' },
  ];

  // --- УПАКОВКИ/КОНЦЕПЦИИ (продуктовое предложение под need_type) ---
  // ready: 'черновик' → 'готова' → 'в продвижении' (Этап 2). dealId — источник упаковки (если создана из сделки).
  const packages = [
    { id: 'P1', name: 'Орошение «Старт»',  need: 'орошение',      industry: 'овощеводство', priceFrom: 2500000, ready: 'в продвижении', dealId: '' },
    { id: 'P2', name: 'Теплица «Модуль»',  need: 'теплицы',       industry: 'тепличное',    priceFrom: 7500000, ready: 'готова', dealId: '' },
    { id: 'P3', name: 'Холод «Сохран»',    need: 'хранение',      industry: 'садоводство',  priceFrom: 5000000, ready: 'черновик', dealId: '' },
    { id: 'P4', name: 'Автополив «Умный»', need: 'автоматизация', industry: 'тепличное',    priceFrom: 800000,  ready: 'готова', dealId: '' },
  ];

  // --- ХРАНИЛИЩЕ АРТЕФАКТОВ (проводник: папки + файлы) ---
  // folders: дерево (parent=null — корень). artifacts.folderId — в какой папке лежит файл.
  const folders = [
    { id: 'F_KP',   parent: null,   name: 'Коммерческие предложения' },
    { id: 'F_DOG',  parent: null,   name: 'Договоры' },
    { id: 'F_PRES', parent: null,   name: 'Презентации' },
    { id: 'F_TPL',  parent: null,   name: 'Шаблоны' },
    { id: 'F_TECH', parent: null,   name: 'Техническая документация' },
    { id: 'F_TPL_KP', parent: 'F_TPL', name: 'КП' },
    { id: 'F_TPL_LET', parent: 'F_TPL', name: 'Письма' },
  ];
  const artifacts = [
    { id: 'A1', dealId: 'D1', folderId: 'F_KP',  kind: 'КП',      ext: 'docx', title: 'КП орошение 120га v3',     by: 'встроенная ф-я', date: '2026-06-23', status: 'на проверке' },
    { id: 'A2', dealId: 'D3', folderId: 'F_DOG', kind: 'Договор', ext: 'docx', title: 'Договор хранение',         by: 'встроенная ф-я', date: '2026-06-24', status: 'черновик' },
    { id: 'A3', dealId: 'D4', folderId: 'F_TECH', kind: 'Схема',   ext: 'pdf',  title: 'Монтажная схема теплицы',  by: 'инженер',        date: '2026-06-20', status: 'утверждён' },
    { id: 'A4', dealId: '',   folderId: 'F_PRES', kind: 'Презентация', ext: 'pptx', title: 'О компании AgroPILOT', by: 'маркетинг', date: '2026-06-18', status: 'утверждён' },
    { id: 'A5', dealId: '',   folderId: 'F_TPL_KP', kind: 'Шаблон', ext: 'docx', title: 'Шаблон КП (орошение)', by: 'PETRUSHKA', date: '2026-06-10', status: 'шаблон' },
    { id: 'A6', dealId: '',   folderId: 'F_TPL_KP', kind: 'Шаблон', ext: 'docx', title: 'Шаблон КП (хранение)', by: 'PETRUSHKA', date: '2026-06-10', status: 'шаблон' },
    { id: 'A7', dealId: '',   folderId: 'F_TPL_LET', kind: 'Шаблон', ext: 'docx', title: 'Шаблон письма-напоминания', by: 'PETRUSHKA', date: '2026-06-10', status: 'шаблон' },
  ];

  // --- СИГНАЛЫ/РИСКИ (привязка к объекту, не к агенту-монитору) ---
  const signals = [
    { id: 'S1', dealId: 'D4', sev: 'warning',  text: 'Срыв сроков монтажа теплицы (этап 2)', objectTitle: 'Теплица 0.5 га' },
    { id: 'S2', dealId: 'D5', sev: 'critical', text: 'Сделка остыла: нет касаний 5 дней',    objectTitle: 'Зерновая логистика' },
    { id: 'S3', dealId: 'D2', sev: 'info',     text: 'Клиент открыл КП дважды',              objectTitle: 'Автоматизация полива' },
  ];

  // --- ОРЁЛ (Level-2 модератор НАД объектами; 3 грации автономии) ---
  const owlSuggestions = [
    { id: 'O1', dealId: 'D1', grade: 'CONFIRM', text: 'Подготовил черновик ответа клиенту по смете — проверить и отправить', action: 'task', taskTitle: 'Отправить ответ по смете', taskType: 'email', okMsg: 'Черновик принят → создана задача «Отправить ответ»' },
    { id: 'O2', dealId: 'D5', grade: 'HINT',    text: 'Сделка остывает: предложить созвон или отложить?', action: 'task', taskTitle: 'Созвон по реанимации сделки', taskType: 'call', okMsg: 'Создана задача «Созвон»' },
    { id: 'O3', dealId: 'D3', grade: 'AUTO',    text: 'Карточка хранения переведена в «Договор» автоматически (КП утверждено)' },
    { id: 'O4', dealId: 'D2', grade: 'CONFIRM', text: 'Смета согласована клиентом — предлагаю перевести сделку «Оценка → Договор»', action: 'stage', okMsg: 'Сделка переведена в «Договор» (по подтверждению)' },
  ];

  // --- ИСТОЧНИКИ МОНИТОРИНГА (чанк 2.3) ---
  const SRC_TYPES = ['сайт/RSS', 'Telegram', 'соцсети', 'маркетплейс/тендеры', 'ключевые слова'];
  const sources = [
    { id: 'SRC1', type: 'сайт/RSS',            value: 'agroinvestor.ru/feed', scope: 'глобальный', industry: '', active: true,  last: '2026-06-24' },
    { id: 'SRC2', type: 'маркетплейс/тендеры', value: 'zakupki.gov.ru «орошение»', scope: 'отрасль', industry: 'овощеводство', active: true, last: '2026-06-23' },
    { id: 'SRC3', type: 'Telegram',            value: '@teplichniy_biznes',     scope: 'отрасль', industry: 'тепличное', active: false, last: '2026-06-20' },
    { id: 'SRC4', type: 'ключевые слова',    value: 'хранение яблок CA',    scope: 'глобальный', industry: '', active: true, last: '2026-06-22' },
  ];

  // --- КОНТЕНТ И СОЦСЕТИ (SSM, Этап 2: продвижение; макет hlab.kz/agropilot) ---
  // status: 'согласование' → 'авто черновик' → 'одобрен' (или 'на переработку'/'отклонён')
  const posts = [
    { id: 'PST1', kind: 'Анонс',     icon: '⚠️', title: 'Ночные заморозки в Крыму', status: 'согласование', slot: '2026-06-28 09:00', channel: 'Telegram + VK',
      body: '⚠️ Ночные заморозки в Крыму: риск для завязи винограда. Проверьте прогноз и защиту насаждений. Наш мониторинг MIA предупреждает заранее.',
      hashtags: '#АПК #Крым #виноград #заморозки', media: 'Фото: иней на лозе (из банка)' },
    { id: 'PST2', kind: 'Обучающий', icon: '🌱', title: 'Что такое NDVI и зачем он агроному', status: 'авто черновик', slot: '', channel: 'Telegram',
      body: '🌱 NDVI — индекс вегетации по спутнику. Показывает состояние посевов и помогает вовремя заметить стресс растений.',
      hashtags: '#NDVI #точноеземледелие #агроном', media: 'Схема-инфографика' },
    { id: 'PST3', kind: 'Рынок',     icon: '📈', title: 'Пшеница +14% за сутки', status: 'согласование', slot: '2026-06-27 18:00', channel: 'VK',
      body: '📈 Оптовая цена пшеницы 4 кл. на Кубани — 14 700–15 000 ₽/т. Ориентир для переговоров с аграриями.',
      hashtags: '#пшеница #цены #АПК #Кубань', media: 'График цен' },
    { id: 'PST4', kind: 'Сезонный',  icon: '💧', title: 'Июнь: полив виноградника без перелива', status: 'согласование', slot: '', channel: 'Telegram + VK',
      body: '💧 Июньский полив: капельное орошение экономит воду и бережёт корни. Рассказываем, как не перелить.',
      hashtags: '#полив #виноград #капельноеорошение', media: 'Видео 30 сек' },
    { id: 'PST5', kind: 'Анонс',     icon: '🏆', title: 'Кейс «Золотая Балка»: вода −23%', status: 'одобрен', slot: '2026-06-25 12:00', channel: 'VK',
      body: '🏆 Кейс «Золотая Балка»: внедрение умного полива снизило расход воды на 23% за сезон.',
      hashtags: '#кейс #ЗолотаяБалка #экономияводы', media: 'Фото объекта' },
  ];

  // ===== 6.11: конфигурация автономности ПЕТРУШКА (грейды по категориям действий) =====
  const agentConfig = {
    grades: [
      { id: 'enrich',   cat: 'Обогащение / мониторинг / напоминания', desc: 'Лиды, разведка, протоколы, автокарточки, дайджест', grade: 'AUTO' },
      { id: 'docs',     cat: 'КП / договоры / контент / расчёты', desc: 'Лендинги, упаковки, ТЗ, follow-up', grade: 'CONFIRM' },
      { id: 'advice',   cat: 'Рекомендации / приоритизация / скоринг', desc: 'Предложение исполнителя, скоринг сделок', grade: 'HINT' },
    ],
    privacyLocalOnly: true,  // приватные данные — только локальные LLM
    routing: [
      { data: 'Приватные (финположение, договоры)', model: 'Локальные (owl-alpha / Qwen)', note: 'НИКОГДА не уходит во внешние API', priv: true },
      { data: 'Простые (классификация, ingest, мониторинг)', model: 'Локальные', note: 'Дёшево и приватно', priv: true },
      { data: 'Сложные (копирайтинг, стратегия)', model: 'Внешние (GPT / Claude / Perplexity)', note: 'Только неприватные данные', priv: false },
    ],
  };
  // ===== 6.11: инфраструктура OPEN CLAW (статусы сервисов) =====
  const infra = [
    { name: 'PostgreSQL 16', role: 'Основная БД объектов', status: 'ok' },
    { name: 'Neo4j', role: 'Граф связей', status: 'ok' },
    { name: 'Redis', role: 'Кэш / очереди', status: 'ok' },
    { name: 'n8n', role: 'Интеграции / публикации', status: 'ok' },
    { name: 'Локальные LLM (owl-alpha / Qwen VL)', role: 'Приватные задачи', status: 'ok' },
    { name: 'Whisper STT', role: 'Голос → текст (Telegram ingest)', status: 'ok' },
    { name: 'Telegram-бот', role: 'Канал ingest / уведомления', status: 'ok' },
    { name: 'BFF :5555 / фронт /agropilot', role: 'Шлюз и UI', status: 'ok' },
  ];

  return { TODAY, STAGES, NEED, IND, SRC_TYPES, inbox, team, strategy, goals, projects, clients, deals, tasks, packages, folders, artifacts, signals, sources, owlSuggestions, posts, agentConfig, infra };
})();
