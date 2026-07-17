# backend/main.py -- AgroPILOT FastAPI application entry point
#
# Run with: uvicorn backend.main:app --host 127.0.0.1 --port 5555 --reload
#
# Error handlers are registered ONCE here, globally, before any routers.

from fastapi import FastAPI

from backend.common.errors import register_error_handlers
from backend.calendar.routes import router as calendar_router
from backend.versions.deals_versions_router import deals_versions_router
from backend.versions.skills_router import skills_router
from backend.strategy.routes import router as strategy_router
from backend.deals.routes import deals_router
from backend.tasks.routes import tasks_router
from backend.team.routes import team_router
from backend.goals.routes import goals_router

# -----------------------------------------------------------------------
# Application factory
# -----------------------------------------------------------------------

app = FastAPI(
    title="AgroPILOT API",
    version="0.1.0",
    description="Backend API for AgroPILOT — Calendar, Versions, Skills, Deals, Tasks.",
)

register_error_handlers(app)

# -----------------------------------------------------------------------
# Routers
# -----------------------------------------------------------------------

# M7 — Calendar
app.include_router(calendar_router, prefix="/agropilot/api/v1")

# M9 — Deal Versions
app.include_router(deals_versions_router, prefix="/agropilot/api/v1")

# M9 — Team Skills
app.include_router(skills_router, prefix="/agropilot/api/v1")

# M4 — Strategy
app.include_router(strategy_router, prefix="/agropilot/api/v1")

# M9 — Deals (team-wide, no owner filter)
app.include_router(deals_router, prefix="/agropilot/api/v1")

# M9 — Tasks (team-wide, no owner filter)
app.include_router(tasks_router, prefix="/agropilot/api/v1")

# Stage-1 — Team (read-only, fix issue#1: /v1/team 404 → «Команда из 0 человек»)
app.include_router(team_router, prefix="/agropilot/api/v1")

# Stage-1 — Goals (read-only, fix issue#1: /v1/goals 404)
app.include_router(goals_router, prefix="/agropilot/api/v1")

# Future: auth_router, clients_router ...
