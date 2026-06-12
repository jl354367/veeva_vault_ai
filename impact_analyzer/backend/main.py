import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routers import chat, upload, release, integration
from services.rag_service import RAGService
from services.bedrock_service import BedrockService

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    rag = RAGService()
    rag.initialize()
    app.state.rag = rag
    app.state.uploaded_impact_config_dfs:    dict = {}
    app.state.uploaded_release_dfs:          dict = {}
    app.state.uploaded_integration_spec_dfs: dict = {}
    app.state.cached_impact_report:          str  = ""
    app.state.cached_integration_report:     str  = ""

    # Amazon Bedrock — activates automatically when AWS credentials are in .env
    bedrock = BedrockService()
    app.state.bedrock = bedrock
    if bedrock.is_configured():
        print(f"Amazon Bedrock enabled: {bedrock.model_id} ({bedrock.region})")
    else:
        print("Amazon Bedrock not configured — running in rule-based mode. "
              "See .env.example to enable AI-enhanced reports.")

    print("Impact Analyzer initialized.")
    yield


app = FastAPI(title="Impact Analyzer API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGIN", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router,        prefix="/api")
app.include_router(upload.router,      prefix="/api")
app.include_router(release.router,     prefix="/api")
app.include_router(integration.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Impact Analyzer"}


@app.get("/api/bedrock-status")
async def bedrock_status():
    return app.state.bedrock.status()
