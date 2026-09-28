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
}


def field_map(spec: dict) -> dict:
    """key -> field-дескриптор справочника."""
    return {f["key"]: f for f in spec["fields"]}
