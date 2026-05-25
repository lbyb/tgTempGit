---
name: python
description: Python best practices and coding conventions. Use when writing Python code, setting up Python projects, or working with Python type hints, async patterns, and package management.
---

# Python 编码规范

## 项目结构

```
my_project/
├── src/
│   └── my_package/
│       ├── __init__.py
│       ├── main.py
│       ├── models.py
│       └── services/
├── tests/
│   ├── __init__.py
│   └── test_main.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 类型标注（Type Hints）

全部代码必须使用类型标注，使用 Python 3.11+ 语法：

```python
from collections.abc import AsyncGenerator, Sequence
from typing import TypedDict

class UserDict(TypedDict):
    id: int
    name: str

async def fetch_users(user_ids: Sequence[int]) -> list[UserDict]:
    result: list[UserDict] = []
    for uid in user_ids:
        result.append({"id": uid, "name": f"user_{uid}"})
    return result
```

## 异步编程

- 使用 `asyncio` 编写异步代码
- 上下文管理器使用 `async with`
- 迭代器使用 `async for`

```python
import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

@asynccontextmanager
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    session = AsyncSession()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

async def get_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User).limit(100))
    return result.scalars().all()
```

## Pydantic 模型

使用 Pydantic v2 定义数据模型：

```python
from pydantic import BaseModel, Field, model_validator

class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    age: int = Field(ge=0, le=150)

    @model_validator(mode="after")
    def validate_age(self) -> "UserCreate":
        if self.age < 18 and "admin" in self.email:
            raise ValueError("未成年人不能使用 admin 邮箱")
        return self
```

## 包管理

使用 `uv` 作为包管理器（推荐），`pyproject.toml` 作为项目配置：

```toml
[project]
name = "my-package"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.5"]
```

## 测试

使用 pytest + pytest-asyncio 编写异步测试：

```python
import pytest
from httpx import ASGITransport, AsyncClient

@pytest.mark.asyncio
async def test_create_user(async_client: AsyncClient) -> None:
    response = await async_client.post("/users", json={"name": "test", "email": "t@t.com", "age": 25})
    assert response.status_code == 201
```

## 代码质量

- 使用 `ruff` 进行 lint 和格式化（替代 flake8/isort/black）
- 使用 `mypy` 进行静态类型检查
- 字符串使用双引号，遵循项目现有风格

```bash
ruff check .
ruff format .
mypy src/
```
