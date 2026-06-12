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
