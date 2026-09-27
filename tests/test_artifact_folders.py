# tests/test_artifact_folders.py -- файловый менеджер артефактов (миграция 040):
# папки, folder_id, защита от циклов, подъём содержимого при удалении папки.

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.artifacts.models import Artifact, ArtifactFolder, Base


def _run_with_session(coro_fn):
    async def wrap():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            return await coro_fn(session)

    return asyncio.run(wrap())


def test_folder_tree_persist_and_rename():
    async def scenario(s):
        root = ArtifactFolder(name="КП", parent_id=None)
        s.add(root)
        await s.flush()
        sub = ArtifactFolder(name="2026", parent_id=root.id)
        s.add(sub)
        await s.flush()  # sub.id до конструирования артефакта
        art = Artifact(kind="other", title="файл.txt", folder_id=sub.id)
        s.add(art)
        await s.commit()
        await s.refresh(root)
        await s.refresh(sub)
        await s.refresh(art)
        # переименование (эндпоинт PATCH меняет name)
        sub.name = "2026-осень"
        await s.commit()
        return root.id, sub.id, art.id, sub.name, art.folder_id

    rid, sid, aid, name, fid = _run_with_session(scenario)
    assert name == "2026-осень"
    assert fid == sid  # файл привязан к подпапке


def test_folder_delete_lifts_content_to_parent():
    """Как проводник: удаление папки поднимает подпапки и файлы в родителя."""
    async def scenario(s):
        from sqlalchemy import select, update as sa_update

        root = ArtifactFolder(name="root", parent_id=None)
        s.add(root)
        await s.flush()
        mid = ArtifactFolder(name="mid", parent_id=root.id)
        s.add(mid)
        await s.flush()
        leaf = ArtifactFolder(name="leaf", parent_id=mid.id)
        s.add(leaf)
        await s.flush()  # leaf.id до конструирования артефактов
        art1 = Artifact(kind="other", title="a.txt", folder_id=mid.id)
        art2 = Artifact(kind="other", title="b.txt", folder_id=leaf.id)
        s.add_all([art1, art2])
        await s.commit()
        await s.refresh(mid)

        # повторение логики DELETE /folders/{id}
        parent = mid.parent_id
        await s.execute(sa_update(ArtifactFolder).where(
            ArtifactFolder.parent_id == mid.id).values(parent_id=parent))
        await s.execute(sa_update(Artifact).where(
            Artifact.folder_id == mid.id).values(folder_id=parent))
        await s.delete(mid)
        await s.commit()

        folders = {f.name: f.parent_id for f in (await s.execute(
            select(ArtifactFolder))).scalars().all()}
        arts = {a.title: a.folder_id for a in (await s.execute(
            select(Artifact))).scalars().all()}
        return folders, arts, parent

    folders, arts, parent = _run_with_session(scenario)
    assert "mid" not in folders                 # папка удалена
    assert folders["leaf"] == parent            # подпапка поднята в root
    assert arts["a.txt"] == parent              # файл из mid -- в root
    assert arts["b.txt"] is not None            # b.txt остался в leaf


def test_folder_move_cycle_rejected():
    """Папку нельзя переместить внутрь её собственного потомка."""
    async def scenario(s):
        root = ArtifactFolder(name="root", parent_id=None)
        s.add(root)
        await s.flush()
        sub = ArtifactFolder(name="sub", parent_id=root.id)
        s.add(sub)
        await s.commit()
        await s.refresh(root)
        await s.refresh(sub)

        # повторение логики _assert_parent_ok: root -> sub должно упасть
        async def assert_parent(folder, new_parent):
            if new_parent is None:
                return
            parent = await s.get(ArtifactFolder, new_parent)
            seen = {folder.id}
            cur = parent
            while cur is not None:
                if cur.id in seen:
                    raise ValueError("cycle")
                seen.add(cur.id)
                cur = await s.get(ArtifactFolder, cur.parent_id) if cur.parent_id else None

        try:
            await assert_parent(root, sub.id)
            raised = False
        except ValueError:
            raised = True
        # а sub -> root (обычное перемещение вверх) -- допустимо
        await assert_parent(sub, root.id)
        return raised

    assert _run_with_session(scenario) is True
