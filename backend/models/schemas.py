from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    series_url: str | None = Field(None, description="豆瓣丛书URL，多个以逗号分隔")
    isbns: str | None = Field(None, description="ISBN号码，逗号或空格分隔")


class SearchResponse(BaseModel):
    task_id: str | None = None
    html: str | None = None
    cached: bool = False


class TaskStatusResponse(BaseModel):
    status: str
    total_series: int = 0
    current_series: int = 0
    current_url: str = ""
    error: str | None = None
    total_books: int = 0


class TaskResultResponse(BaseModel):
    html: str | None = None
    error: str | None = None
    status: str | None = None
    total_books: int = 0


class HistoryEntry(BaseModel):
    task_id: str
    display_name: str
    status: str
    total_books: int = 0
    created_at: str = ""


class ClearHistoryResponse(BaseModel):
    cleared: int
