import hashlib
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from backend.config import MAX_WORKERS
from backend.services.douban import get_books_from_series_new
from backend.services.aa_search import build_aa_page_by_isbns

tasks_store: dict[str, dict[str, Any]] = {}
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)


def make_series_task_id(series_urls: list[str]) -> str:
    raw = ",".join(sorted(series_urls))
    digest = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"series_{digest}"


def make_isbn_task_id(isbns: list[str]) -> str:
    raw = ",".join(sorted(isbns))
    return f"isbn_{raw}"


def _process_series_task(task_id: str, series_urls: list[str]) -> None:
    try:
        tasks_store[task_id]["status"] = "processing"
        tasks_store[task_id]["start_time"] = datetime.now()

        all_books: dict[str, str] = {}

        for idx, series_url in enumerate(series_urls, 1):
            tasks_store[task_id]["current_series"] = idx
            tasks_store[task_id]["current_url"] = series_url

            books = get_books_from_series_new(series_url)
            if books:
                all_books.update(books)

            if idx < len(series_urls):
                print(f"处理完第 {idx} 个series，等待60秒...")
                time.sleep(60)

        if all_books:
            tasks_store[task_id]["aa_total"] = len(all_books)
            filename_map: dict[str, str] = {}
            keys: list[str] = []
            for isbn, filename in all_books.items():
                keys.append(isbn)
                filename_map[isbn] = filename

            def _on_aa_progress(current: int, total: int) -> None:
                tasks_store[task_id]["aa_current"] = current

            html = build_aa_page_by_isbns(keys, filename_map, on_progress=_on_aa_progress)
            tasks_store[task_id]["result"] = html
            tasks_store[task_id]["status"] = "completed"
            tasks_store[task_id]["total_books"] = len(all_books)
        else:
            tasks_store[task_id]["status"] = "failed"
            tasks_store[task_id]["error"] = "未找到任何书籍"

    except Exception as e:
        tasks_store[task_id]["status"] = "failed"
        tasks_store[task_id]["error"] = str(e)
        print(f"任务 {task_id} 处理失败: {e}")
    finally:
        tasks_store[task_id]["end_time"] = datetime.now()


def submit_series_task(task_id: str, series_urls: list[str], display_name: str = "") -> bool:
    if task_id in tasks_store and tasks_store[task_id]["status"] == "completed":
        return False
    if task_id in tasks_store and tasks_store[task_id]["status"] in ("processing", "pending"):
        return False
    tasks_store[task_id] = {
        "status": "pending",
        "total_series": len(series_urls),
        "current_series": 0,
        "current_url": "",
        "result": None,
        "error": None,
        "total_books": 0,
        "aa_current": 0,
        "aa_total": 0,
        "display_name": display_name or ", ".join(series_urls),
        "created_at": datetime.now().isoformat(),
    }
    executor.submit(_process_series_task, task_id, series_urls)
    return True


def cache_isbn_result(task_id: str, isbns: list[str], html: str) -> None:
    tasks_store[task_id] = {
        "status": "completed",
        "total_series": 0,
        "current_series": 0,
        "result": html,
        "error": None,
        "total_books": len(isbns),
        "display_name": ", ".join(isbns),
        "created_at": datetime.now().isoformat(),
        "start_time": datetime.now(),
        "end_time": datetime.now(),
    }


def get_task_status(task_id: str) -> dict[str, Any] | None:
    if task_id not in tasks_store:
        return None
    task = tasks_store[task_id]
    return {
        "status": task["status"],
        "total_series": task.get("total_series", 0),
        "current_series": task.get("current_series", 0),
        "current_url": task.get("current_url", ""),
        "error": task.get("error"),
        "total_books": task.get("total_books", 0),
        "aa_current": task.get("aa_current", 0),
        "aa_total": task.get("aa_total", 0),
    }


def get_task_result(task_id: str) -> dict[str, Any] | None:
    if task_id not in tasks_store:
        return None
    task = tasks_store[task_id]
    if task["status"] == "completed" and task["result"]:
        return {
            "html": task["result"],
            "total_books": task.get("total_books", 0),
            "display_name": task.get("display_name", ""),
        }
    elif task["status"] == "failed":
        return {"error": task.get("error", "未知错误")}
    return {"status": task["status"]}


def get_history() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for tid, task in tasks_store.items():
        if task["status"] in ("completed", "failed"):
            entries.append({
                "task_id": tid,
                "display_name": task.get("display_name", tid),
                "status": task["status"],
                "total_books": task.get("total_books", 0),
                "created_at": task.get("created_at", ""),
            })
    entries.sort(key=lambda x: x["created_at"], reverse=True)
    return entries


def clear_history() -> int:
    count = len(tasks_store)
    tasks_store.clear()
    return count
