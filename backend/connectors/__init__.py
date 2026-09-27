# backend/connectors/__init__.py -- §39: единый слой коннекторов источников (О2)

from backend.connectors.base import Connector
from backend.connectors.registry import (
    REGISTRY,
    fetch_for_source,
    is_eligible,
    eligible_sources_stmt,
    resolve_connector,
)
