from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class SourceReference(BaseModel):
    source: str
    score: float
    section: Optional[str] = None
    page_number: Optional[int] = None


class SQLResult(BaseModel):
    query: Optional[str] = None
    columns: list[str] = []
    rows: list[list] = []


class ChatResponse(BaseModel):
    answer: str
    intent: str
    sources: list[SourceReference] = []
    sql_result: Optional[SQLResult] = None
