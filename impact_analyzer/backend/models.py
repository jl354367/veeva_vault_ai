from pydantic import BaseModel
from typing import List, Optional


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    mode: str  # "config" | "help" | "onboard"
    history: List[Message] = []
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    sources: List[str] = []
    mode: str


class SheetStat(BaseModel):
    label: str
    value: int


class UploadResponse(BaseModel):
    message: str
    chunks_added: int
    filename: str
    sheet_stats: List[SheetStat] = []
