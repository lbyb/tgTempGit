from __future__ import annotations

import os
import uuid
from typing import Annotated

import aiofiles
from fastapi import APIRouter, UploadFile, File, HTTPException, Header, Request, Depends
from fastapi.responses import FileResponse, StreamingResponse

from backend.app.config import get_settings
from backend.app.schemas.file import FileRenameRequest, BatchDeleteRequest, FileResponse as FileResp
from backend.app.services import file_service

settings = get_settings()
router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("", response_model=list[FileResp])
async def list_files(request: Request) -> list[FileResp]:
    records = await file_service.list_files()
    return [FileResp.model_validate(r) for r in records]


@router.post("/upload", response_model=FileResp)
async def upload_file(
    request: Request, file: Annotated[UploadFile, File()],
) -> FileResp:
    size = 0
    content_type = file.content_type

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    record = await file_service.create_file_record(
        original_filename=file.filename or "unnamed",
        size=0, content_type=content_type,
    )
    file_path = os.path.join(settings.UPLOAD_DIR, record.filename)

    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    await f.close()
                    os.remove(file_path)
                    await file_service.delete_file(record.id)
                    raise HTTPException(
                        status_code=413,
                        detail=f"文件大小超过 {settings.MAX_UPLOAD_SIZE_MB}MB 限制",
                    )
                await f.write(chunk)

        from backend.app.core.database import async_session as _session
        from backend.app.models.file import FileRecord as FR
        from sqlalchemy import select as sa_select
        async with _session() as db:
            result = await db.execute(
                sa_select(FR).where(FR.id == record.id),
            )
            updated = result.scalar_one()
            updated.size = size
            await db.commit()
            await db.refresh(updated)
            return FileResp.model_validate(updated)
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        await file_service.delete_file(record.id)
        raise HTTPException(status_code=500, detail=f"上传失败: {e}")


@router.get("/{file_id}")
async def download_file(file_id: uuid.UUID) -> FileResponse:
    record = await file_service.get_file(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="文件不存在")

    file_path = os.path.join(settings.UPLOAD_DIR, record.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件数据丢失")

    return FileResponse(
        path=file_path,
        filename=record.original_filename,
        media_type=record.content_type or "application/octet-stream",
    )


@router.patch("/{file_id}", response_model=FileResp)
async def rename_file(file_id: uuid.UUID, body: FileRenameRequest) -> FileResp:
    record = await file_service.rename_file(file_id, body.filename)
    if record is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResp.model_validate(record)


@router.delete("/{file_id}")
async def delete_single(file_id: uuid.UUID) -> dict[str, str]:
    success = await file_service.delete_file(file_id)
    if not success:
        raise HTTPException(status_code=404, detail="文件不存在")
    return {"detail": "ok"}


@router.delete("")
async def delete_batch(body: BatchDeleteRequest) -> dict[str, int]:
    count = await file_service.delete_files(body.ids)
    return {"deleted": count}
