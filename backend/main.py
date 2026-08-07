from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import FRONTEND_ORIGIN, ensure_directories
from database import init_db
from routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_directories()
    init_db()
    yield


app = FastAPI(
    title="Agent Evaluator API",
    version="0.1.0",
    description="A standalone DeepEval-based black-box agent evaluation service.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(
        dict.fromkeys(
            [
                FRONTEND_ORIGIN,
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ]
        )
    ),
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
def health():
    try:
        import deepeval
        deepeval_version = getattr(deepeval, "__version__", "installed")
    except ImportError:
        deepeval_version = None
    return {"status": "ok", "service": "agent-evaluator", "deepeval_version": deepeval_version}
