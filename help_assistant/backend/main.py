import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routers import help as help_router
from routers import chat as chat_router
from services.rag_service import RAGService
from services.scraper import load_docs, data_is_stale, run_scrape
from services.help_search import get_engine

load_dotenv()


async def _init_help_index():
    docs = load_docs()
    if docs:
        get_engine().build(docs)
        print(f"[Help Assistant] Help index loaded: {len(docs)} documents.")
    if data_is_stale():
        print("[Help Assistant] Help data is stale — starting background scrape…")
        asyncio.create_task(_background_scrape())


async def _background_scrape():
    try:
        total = await run_scrape()
        docs = load_docs()
        get_engine().build(docs)
        print(f"[Help Assistant] Background scrape complete — {total} docs indexed.")
    except Exception as e:
        print(f"[Help Assistant] Background scrape failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    rag = RAGService()
    app.state.rag = rag
    loop = asyncio.get_running_loop()
    # Run RAG init (blocking) in a thread pool and help index concurrently
    await asyncio.gather(
        loop.run_in_executor(None, rag.initialize),
        _init_help_index(),
    )
    print("Help Assistant initialized.")
    yield


app = FastAPI(title="Help Assistant API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGIN", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(help_router.router, prefix="/api")
app.include_router(chat_router.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Help Assistant"}
