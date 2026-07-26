from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    original_filename: str
    size: int
    content_type: str | None
    created_at: datetime
    updated_at: datetime


class FileRenameRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=512)


class BatchDeleteRequest(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1)
