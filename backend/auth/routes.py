# backend/auth/routes.py -- AgroPILOT auth-роутер (контракт §19)
#
# Mount: app.include_router(auth_router, prefix="/agropilot/api/v1")
# Base path: /agropilot/api/v1/auth
# Контракт ответа: {"ok": true, "data": ...} (backend/common/errors.py).
#
# Эндпоинты (соответствуют фронтенду js/api.js):
#   POST /auth/login   {login, password}          -> {access_token, refresh_token, user}
#   POST /auth/refresh {refresh_token}            -> {access_token, refresh_token, user}
#   POST /auth/logout                               -> {} (токены stateless, клиент чистит localStorage)
#
# Учётные записи — таблица team (колонки login/password_hash, миграция 016).
# Пароли задаёт оператор скриптом backend/auth/set_password.py.

import jwt
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from backend.common.deps import get_db
from backend.common.errors import UnauthorizedError, ValidationError
from backend.team.models import TeamMember

auth_router = APIRouter(prefix="/auth", tags=["auth"])


def _ok(data):
    return {"ok": True, "data": data}


class LoginBody(BaseModel):
    login: str
    password: str


class RefreshBody(BaseModel):
    refresh_token: str


def _user_payload(member: TeamMember) -> dict:
    return {
        "id": member.id,
        "name": member.name,
        "role": member.role,
        "role_key": member.role_key,
    }


async def _authenticate(db: AsyncSession, login: str, password: str) -> TeamMember:
    q = select(TeamMember).where(TeamMember.login == login.strip().lower())
    member = (await db.execute(q)).scalars().first()
    # Одна и та же ошибка для «нет пользователя» и «не тот пароль» —
    # не раскрываем, существует ли логин.
    if (
        member is None
        or not member.password_hash
        or member.status != "active"
        or not verify_password(password, member.password_hash)
    ):
        raise UnauthorizedError("Неверный логин или пароль")
    return member


@auth_router.post("/login")
async def login(body: LoginBody, db: AsyncSession = Depends(get_db)):
    member = await _authenticate(db, body.login, body.password)
    return _ok({
        "access_token": create_access_token(member.id, member.name),
        "refresh_token": create_refresh_token(member.id, member.name),
        "user": _user_payload(member),
    })


@auth_router.post("/refresh")
async def refresh(body: RefreshBody, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
    except jwt.PyJWTError as e:
        raise UnauthorizedError(f"Недействительный refresh-токен: {e}")
    member = await db.get(TeamMember, payload.get("sub"))
    if member is None or member.status != "active":
        raise UnauthorizedError("Пользователь не найден или неактивен")
    return _ok({
        "access_token": create_access_token(member.id, member.name),
        "refresh_token": create_refresh_token(member.id, member.name),
        "user": _user_payload(member),
    })


@auth_router.post("/logout")
async def logout():
    # Токены stateless (без серверного хранилища): серверу нечего отзывать,
    # клиент удаляет agropilot_token / agropilot_refresh из localStorage.
    return _ok({"detail": "logged out"})
