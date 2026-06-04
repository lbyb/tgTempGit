import re
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.dependencies import verify_token
from backend.models.schemas import SearchRequest, SearchResponse
from backend.services.task_manager import (
    submit_series_task,
    make_series_task_id,
    make_isbn_task_id,
    cache_isbn_result,
    get_task_status,
    get_task_result,
)
from backend.services.aa_search import build_aa_page_by_isbns

router = APIRouter(tags=["search"])


@router.post("/api/search", response_model=SearchResponse)
def create_search(body: SearchRequest, _: None = Depends(verify_token)) -> JSONResponse:
    if body.series_url:
        series_urls = []
        series_names = []
        for url in body.series_url.split(","):
            raw = url.strip()
            if raw:
                displayed = raw
                if raw.startswith("http"):
                    m2 = re.search(r"series/(\d+)", raw)
                    displayed = m2.group(1) if m2 else raw
                url = raw
                match = re.match(r"^(\d+)", url)
                if match:
                    url = f"https://book.douban.com/series/{match.group(1)}"
                series_urls.append(url)
                series_names.append(displayed)

        if series_urls:
            task_id = make_series_task_id(series_urls)
            existing = get_task_result(task_id)
            if existing and existing.get("html"):
                return JSONResponse({"task_id": task_id, "html": None, "cached": True})
            submit_series_task(task_id, series_urls, display_name=", ".join(series_names))
            return JSONResponse({"task_id": task_id, "html": None, "cached": False})

    if body.isbns:
        parts = [p for p in re.split(r"[,\s;]+", body.isbns.strip()) if p]
        task_id = make_isbn_task_id(parts)
        existing = get_task_result(task_id)
        if existing and existing.get("html"):
            return JSONResponse({"task_id": task_id, "html": None, "cached": True})
        html = build_aa_page_by_isbns(parts)
        cache_isbn_result(task_id, parts, html)
        return JSONResponse({"task_id": task_id, "html": None, "cached": False})

    return JSONResponse({"task_id": None, "html": None, "cached": False})
