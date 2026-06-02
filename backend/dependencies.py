from fastapi import Header, Query, HTTPException

from backend.config import SECRET_TOKEN


def verify_token(
    token: str | None = Query(None, alias="token"),
    x_token: str | None = Header(None, alias="X-Token"),
) -> None:
    if not token and not x_token:
        raise HTTPException(status_code=401, detail="缺少 token")
    if (token or x_token) != SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="token 无效")
