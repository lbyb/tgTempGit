from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.services.task_manager import get_task_status, get_task_result, get_history, clear_history

router = APIRouter(tags=["tasks"])


@router.get("/api/task/{task_id}")
def task_status(task_id: str) -> JSONResponse:
    status = get_task_status(task_id)
    if status is None:
        return JSONResponse({"status": "not_found"})
    return JSONResponse(status)


@router.get("/api/result/{task_id}")
def task_result(task_id: str) -> JSONResponse:
    result = get_task_result(task_id)
    if result is None:
        return JSONResponse({"html": None, "error": "任务不存在"})
    return JSONResponse(result)


@router.get("/api/history")
def history() -> JSONResponse:
    entries = get_history()
    return JSONResponse(entries)


@router.delete("/api/history")
def delete_history() -> JSONResponse:
    count = clear_history()
    return JSONResponse({"cleared": count})
