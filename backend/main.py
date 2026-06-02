from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import search, tasks


app = FastAPI(
    title="Douban Series AA Search API",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router)
app.include_router(tasks.router)
