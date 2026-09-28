# backend/catalogs/registry.py -- §45: декларативный реестр справочников НСИ
#
# SPEC — единый источник правды о составе справочников: из него движок (engine.py)
# строит CRUD/валидацию/аудит/дедуп, а фронт (GET /v1/catalogs) — таблицы и формы.
# Новый справочник = запись здесь + таблица в миграции + модель в models.py.
#
# Поля field: key, type (string|int|enum), label, required, unique, grid (показывать
# в таблице), width (px, опционально), options (list[str] или dict value->label).
# Права (решение 2026-09-28): создание/изменение/архив — все авторизованные;
# физическое удаление — delete_roles (admin/manager). is_system-записи неизменяемы
# кроме name/sort_order, не архивируются и не удаляются.

CATALOGS: dict = {
    "units": {
        "title": "Единицы измерения",
        "group": "Базовые",
        "icon": "⚖️",
        "model": "Unit",
        "hierarchical": False,
        "code_prefix": "ED",
        "delete_roles": ("admin", "manager"),
        "fields": [
            {"key": "code",      "type": "string", "label": "Код",       "grid": True, "width": 100},
            {"key": "name",      "type": "string", "label": "Наименование", "required": True, "unique": True, "grid": True},
            {"key": "symbol",    "type": "string", "label": "Обозначение", "required": True, "grid": True, "width": 110},
            {"key": "kind",      "type": "enum",   "label": "Тип", "grid": True, "width": 110,
             "options": ["шт", "вес", "объём", "длина", "площадь", "время", "усл"]},
            {"key": "intl_code", "type": "string", "label": "Код ОКЕИ", "grid": True, "width": 90},
        ],
        "dup_fields": ("name", "symbol"),
    },
    "currencies": {
        "title": "Валюты",
        "group": "Базовые",
        "icon": "💱",
        "model": "Currency",
        "hierarchical": False,
        "code_prefix": "CUR",
        "delete_roles": ("admin", "manager"),
        "fields": [
            {"key": "code",       "type": "string", "label": "Код ISO",    "grid": True, "width": 90},
            {"key": "name",       "type": "string", "label": "Наименование", "required": True, "unique": True, "grid": True},
            {"key": "symbol",     "type": "string", "label": "Символ",     "grid": True, "width": 90},
            {"key": "minor_unit", "type": "int",    "label": "Минорные единицы (знаков)", "grid": True, "width": 140},
        ],
        "dup_fields": ("name",),
    },
    "regions": {
        "title": "Регионы и гео",
        "group": "Базовые",
        "icon": "🗺️",
        "model": "Region",
        "hierarchical": True,
        "code_prefix": "GEO",
        "delete_roles": ("admin", "manager"),
        "fields": [
            {"key": "code",  "type": "string", "label": "Код",  "grid": True, "width": 90},
            {"key": "name",  "type": "string", "label": "Наименование", "required": True, "grid": True},
            {"key": "level", "type": "enum",   "label": "Уровень", "required": True, "grid": True, "width": 150,
             "options": {"country": "Страна", "region": "Регион / субъект", "city": "Город"}},
        ],
        "dup_fields": ("name",),
    },
    "tags": {
        "title": "Теги",
        "group": "Базовые",
        "icon": "🏷️",
        "model": "Tag",
        "hierarchical": False,
        "code_prefix": "TAG",
        "delete_roles": ("admin", "manager"),
        "fields": [
            {"key": "code",        "type": "string", "label": "Код",   "grid": True, "width": 100},
            {"key": "name",        "type": "string", "label": "Наименование", "required": True, "unique": True, "grid": True},
            {"key": "color",       "type": "string", "label": "Цвет (HEX)", "grid": True, "width": 100},
            {"key": "description", "type": "string", "label": "Описание"},
        ],
        "dup_fields": ("name",),
    },
    "contractors": {
        "title": "Контрагенты",
        "group": "Партнёры",
        "icon": "🤝",
        "model": "Contractor",
        # фаза 1d (045): подразделы — группы-папки (виноградники/сады/…)
        "hierarchical": True,
        "group_items": True,
        "code_prefix": "KON",
        "form": "drawer",                  # 7+ полей — боковая панель, не модалка
        "delete_roles": ("admin", "manager"),
        "fields": [
            {"key": "code",          "type": "string", "label": "Код",  "grid": True, "width": 100},
            {"key": "name",          "type": "string", "label": "Краткое наименование", "required": True, "grid": True},
            {"key": "name_full",     "type": "string", "label": "Полное наименование"},
            {"key": "kind",          "type": "enum",   "label": "Тип", "required": True, "grid": True, "width": 110,
             "options": {"jur": "Юрлицо", "ip": "ИП", "person": "Физлицо"}},
            {"key": "bin_iin",       "type": "string", "label": "БИН/ИИН", "grid": True, "width": 140},
            {"key": "region_id",     "type": "ref",    "label": "Регион", "ref": "regions", "grid": True},
            {"key": "phone",         "type": "string", "label": "Телефон", "grid": True, "width": 140},
            {"key": "email",         "type": "string", "label": "E-mail"},
            {"key": "website",       "type": "string", "label": "Сайт"},
            {"key": "bank_name",     "type": "string", "label": "Банк"},
            {"key": "bic_iban",      "type": "string", "label": "БИК / IBAN"},
            {"key": "account",       "type": "string", "label": "Счёт"},
            {"key": "legal_address", "type": "string", "label": "Юридический адрес"},
            {"key": "comment",       "type": "string", "label": "Комментарий"},
        ],
        "dup_fields": ("name", "bin_iin"),
        # поля, применимые только к элементам (группы-подразделы — только код+имя)
        "element_fields": ["name_full", "kind", "bin_iin", "region_id", "phone", "email",
                           "website", "bank_name", "bic_iban", "account", "legal_address", "comment"],
        # refs для merge (фаза 1c+): когда появятся ссылки из клиентов/документов
    },
    "nomenclature": {
        "title": "Номенклатура",
        "group": "Номенклатура",
        "icon": "📦",
        "model": "NomenclatureItem",
        "hierarchical": True,
        "group_items": True,               # 1С-стиль: группы + элементы в одной таблице
        "code_prefix": "NOM",
        "form": "drawer",
        "delete_roles": ("admin", "manager"),
        "fields": [
            {"key": "code",        "type": "string",  "label": "Код", "grid": True, "width": 110},
            {"key": "name",        "type": "string",  "label": "Наименование", "required": True, "grid": True},
            {"key": "article",     "type": "string",  "label": "Артикул", "grid": True, "width": 120},
            {"key": "kind",        "type": "enum",    "label": "Тип", "required": True, "grid": True, "width": 100,
             "options": {"goods": "Товар", "service": "Услуга"}},
            {"key": "unit_id",     "type": "ref",     "label": "Ед. изм.", "ref": "units", "required": True, "grid": True, "width": 100},
            {"key": "vat_rate",    "type": "decimal", "label": "НДС, %", "grid": True, "width": 90},
            {"key": "price_base",  "type": "decimal", "label": "Цена базовая", "grid": True, "width": 130},
            {"key": "currency_id", "type": "ref",     "label": "Валюта", "ref": "currencies", "grid": True, "width": 100},
        ],
        # поля, применимые только к элементам (у групп скрываются и не обязательны)
        "element_fields": ["article", "kind", "unit_id", "vat_rate", "price_base", "currency_id"],
        "dup_fields": ("name", "article"),
    },
}


def field_map(spec: dict) -> dict:
    """key -> field-дескриптор справочника."""
    return {f["key"]: f for f in spec["fields"]}
