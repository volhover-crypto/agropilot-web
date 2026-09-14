#!/usr/bin/env python3
# backend/auth/set_password.py -- установка/смена пароля пользователя team.
#
# Запуск на сервере (из /opt/agropilot-web, в venv бэкенда):
#   venv/bin/python -m backend.auth.set_password <login> [password]
#
# Пароль можно передать аргументом (не рекомендуется, остаётся в history)
# или интерактивно (скрытый ввод, затем подтверждение).
# После смены пароля все ранее выданные access/refresh токены пользователя
# остаются валидными до истечения срока -- stateless JWT, отзыва нет.

import asyncio
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.auth.security import hash_password
from backend.team.models import TeamMember
import os


async def main() -> int:
    if len(sys.argv) < 2:
        print("Использование: python -m backend.auth.set_password <login> [password]")
        return 2

    login = sys.argv[1].strip().lower()
    if len(sys.argv) > 2:
        password = sys.argv[2]
    else:
        password = getpass.getpass(f"Пароль для {login}: ")
        confirm = getpass.getpass("Повторите пароль: ")
        if password != confirm:
            print("Пароли не совпадают")
            return 2
    if len(password) < 8:
        print("Пароль должен быть не короче 8 символов")
        return 2

    engine = create_async_engine(
        os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@localhost:5432/agropilot",
        ),
        pool_pre_ping=True,
    )
    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
        q = select(TeamMember).where(TeamMember.login == login)
        member = (await session.execute(q)).scalars().first()
        if member is None:
            print(f"Пользователь с login={login!r} не найден (миграция 016 применена?)")
            await engine.dispose()
            return 1
        member.password_hash = hash_password(password)
        await session.commit()
        print(f"OK: пароль для {member.id} ({member.name}, login={login}) установлен")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
