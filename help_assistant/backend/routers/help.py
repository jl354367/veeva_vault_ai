import asyncio
from fastapi import APIRouter, BackgroundTasks

from services.scraper     import run_scrape, load_docs, data_exists, data_is_stale, DATA_FILE
from services.help_search import get_engine

router = APIRouter()

_scraping = False   # simple flag to prevent concurrent scrapes


@router.get("/help/status")
async def help_status():
    engine = get_engine()
    return {
        "data_exists":  data_exists(),
        "data_stale":   data_is_stale(),
        "docs_indexed": len(engine._docs) if engine.ready else 0,
        "index_ready":  engine.ready,
        "data_file":    str(DATA_FILE),
    }


@router.post("/help/refresh")
async def help_refresh(background_tasks: BackgroundTasks):
    global _scraping
    if _scraping:
        return {"status": "already_running", "message": "Scrape already in progress."}
    _scraping = True
    background_tasks.add_task(_do_scrape)
    return {"status": "started", "message": "Scraping veevavault.help in the background. This takes 2–5 minutes."}


async def _do_scrape():
    global _scraping
    try:
        total = await run_scrape()
        # Reload the engine with fresh data
        docs = load_docs()
        get_engine().build(docs)
        print(f"[HelpRefresh] Done — {total} docs, index rebuilt.")
    except Exception as e:
        print(f"[HelpRefresh] Error: {e}")
    finally:
        _scraping = False
