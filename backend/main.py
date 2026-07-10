# backend/main.py -- AgroPILOT FastAPI application entry point
#
# This is the SINGLE entry point for the backend application.
# Run with: uvicorn backend.main:app --reload
#
# Error handlers are registered ONCE here, globally, before any routers.
# All routers (calendar, versions, skills, ...) automatically inherit them.

from fastapi import FastAPI

from backend.common.errors import register_error_handlers
from backend.calendar.routes import router as calendar_router
from backend.versions.deals_versions_router import router as deals_versions_router
from backend.versions.skills_router import router as skills_router

# -----------------------------------------------------------------------
# Application factory
# -----------------------------------------------------------------------

app = FastAPI(
    title="AgroPILOT API",
    version="0.1.0",
    description="Backend API for AgroPILOT — Calendar, Versions, Skills, Deals, Tasks.",
)

# Register shared error handlers BEFORE including routers.
# This ensures all HTTPException / APIError / RequestValidationError
# raised anywhere in the app are formatted per CONTRACTS.md §0.
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

# Future modules: deals, tasks, contacts ...
# app.include_router(deals_router, prefix="/agropilot/api/v1")
