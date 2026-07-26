import os
import uuid

from sqlalchemy import select, delete, func

from backend.app.config import get_settings
from backend.app.core.database import async_session
from backend.app.models.file import FileRecord

settings = get_settings()


async def list_files() -> list[FileRecord]:
    async with async_session() as db:
        result = await db.execute(
            select(FileRecord).order_by(FileRecord.created_at.desc()),
        )
        return list(result.scalars().all())


async def get_file(file_id: uuid.UUID) -> FileRecord | None:
    async with async_session() as db:
        result = await db.execute(
            select(FileRecord).where(FileRecord.id == file_id),
        )
        return result.scalar_one_or_none()


async def create_file_record(
    original_filename: str, size: int, content_type: str | None,
) -> FileRecord:
    file_id = uuid.uuid4()
    ext = os.path.splitext(original_filename)[1] or ""
    stored_name = f"{file_id}{ext}"

    async with async_session() as db:
        record = FileRecord(
            id=file_id, filename=stored_name,
            original_filename=original_filename, size=size,
            content_type=content_type,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record


async def rename_file(file_id: uuid.UUID, new_filename: str) -> FileRecord | None:
    async with async_session() as db:
        result = await db.execute(
            select(FileRecord).where(FileRecord.id == file_id),
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None
        record.original_filename = new_filename
        await db.commit()
        await db.refresh(record)
        return record


async def delete_file(file_id: uuid.UUID) -> bool:
    async with async_session() as db:
        result = await db.execute(
            select(FileRecord).where(FileRecord.id == file_id),
        )
        record = result.scalar_one_or_none()
        if record is None:
            return False

        file_path = os.path.join(settings.UPLOAD_DIR, record.filename)
        if os.path.exists(file_path):
            os.remove(file_path)

        await db.delete(record)
        await db.commit()
        return True


async def delete_files(file_ids: list[uuid.UUID]) -> int:
    deleted = 0
    async with async_session() as db:
        for fid in file_ids:
            result = await db.execute(
                select(FileRecord).where(FileRecord.id == fid),
            )
            record = result.scalar_one_or_none()
            if record is None:
                continue

            file_path = os.path.join(settings.UPLOAD_DIR, record.filename)
            if os.path.exists(file_path):
                os.remove(file_path)

            await db.delete(record)
            deleted += 1
        await db.commit()
    return deleted
