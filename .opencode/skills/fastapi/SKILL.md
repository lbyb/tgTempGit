---
name: fastapi
description: FastAPI best practices and conventions. Use when building REST APIs with FastAPI, defining Pydantic models, dependency injection, middleware, and API route design. Use ONLY when the user is working with FastAPI specifically.
---

# FastAPI 最佳实践

## 项目结构

```
app/
├── __init__.py
├── main.py              # FastAPI 应用入口
├── config.py            # Settings / 配置
├── dependencies.py      # 依赖注入
├── models/              # SQLAlchemy 模型
│   └── user.py
├── schemas/             # Pydantic 请求/响应模型
│   └── user.py
├── api/                 # 路由模块
│   ├── __init__.py
│   └── v1/
│       ├── __init__.py
│       └── users.py
├── services/            # 业务逻辑
│   └── user_service.py
└── core/
    ├── database.py      # 数据库连接
    └── exceptions.py    # 自定义异常
```

## 应用入口

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from fastapi import FastAPI

from app.api.v1.users import router as users_router
from app.core.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="My API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(users_router, prefix="/api/v1/users", tags=["users"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

## 始终使用 Annotated 风格

```python
from typing import Annotated
from fastapi import Depends, Query, Path, Body

# 依赖注入
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session

DBSession = Annotated[AsyncSession, Depends(get_db)]

# 路由参数
@app.get("/users/{user_id}")
async def get_user(
    user_id: Annotated[int, Path(ge=1)],
    include_deleted: Annotated[bool, Query()] = False,
    db: DBSession = ...,  # fastapi v0.115+
) -> UserResponse:
    ...
```

## Pydantic Schema

```python
from pydantic import BaseModel, ConfigDict, Field

class UserBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str

class UserCreate(UserBase):
    password: str = Field(min_length=8)

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
```

## 异常处理

```python
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

class NotFoundError(HTTPException):
    def __init__(self, entity: str, entity_id: int) -> None:
        super().__init__(status_code=404, detail=f"{entity} #{entity_id} not found")

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
```

## 依赖注入模式

```python
from fastapi import Depends

async def pagination(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> dict[str, int]:
    return {"offset": (page - 1) * size, "limit": size}

Pagination = Annotated[dict[str, int], Depends(pagination)]

@app.get("/users")
async def list_users(db: DBSession, pag: Pagination) -> list[UserResponse]:
    result = await db.execute(
        select(User).offset(pag["offset"]).limit(pag["limit"])
    )
    return result.scalars().all()
```

## 中间件

```python
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import time

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.time()
        response = await call_next(request)
        response.headers["X-Process-Time"] = f"{time.time() - start:.4f}"
        return response
```
