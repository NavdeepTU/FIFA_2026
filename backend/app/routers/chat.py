from fastapi import APIRouter, Depends, HTTPException
from genai.embeddings import embed_texts, to_pgvector_literal
from genai.llm import generate_answer
from pydantic import BaseModel, Field
from sqlalchemy import Connection, text

from app.config import settings
from app.db import get_db

router = APIRouter(prefix="/chat", tags=["chat"])


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


class RetrieveResult(BaseModel):
    player_id: str
    player_name: str
    team: str
    position: str
    summary_text: str
    distance: float


class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


class AskResponse(BaseModel):
    answer: str
    sources: list[RetrieveResult]


def _retrieve_similar_players(query: str, top_k: int, db: Connection) -> list[dict]:
    """Embeds `query` with the same local model used to build `player_embeddings` and
    returns the nearest player summaries by pgvector distance -- shared by /retrieve
    (retrieval only) and /ask (retrieval + Groq generation).
    """
    try:
        query_vector = embed_texts([query])[0]
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"embedding model unavailable: {e}") from e

    rows = db.execute(
        text(
            "select pe.player_id, p.player_name, p.team, p.position, pe.summary_text, "
            "pe.embedding <-> cast(:query_vector as vector) as distance "
            "from player_embeddings pe join players p on p.player_id = pe.player_id "
            "order by distance limit :top_k"
        ),
        {"query_vector": to_pgvector_literal(query_vector), "top_k": top_k},
    ).mappings().all()
    return list(rows)


@router.get("/status")
def status():
    return {
        "retrieval_available": True,
        "generation_available": bool(settings.groq_api_key),
        "message": (
            "Retrieval over player_embeddings and Groq-backed generation are both live."
            if settings.groq_api_key
            else "Retrieval is live; generation needs GROQ_API_KEY set to work."
        ),
    }


@router.post("/retrieve", response_model=list[RetrieveResult])
def retrieve(payload: RetrieveRequest, db: Connection = Depends(get_db)):
    return _retrieve_similar_players(payload.query, payload.top_k, db)


@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, db: Connection = Depends(get_db)):
    """Retrieval-augmented generation: retrieves the nearest player summaries, then
    asks Groq to answer the question grounded in only that context -- not free-form
    LLM guessing (see docs/project_scope.md §5).
    """
    sources = _retrieve_similar_players(payload.query, payload.top_k, db)
    try:
        answer = generate_answer(payload.query, [s["summary_text"] for s in sources])
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"generation unavailable: {e}") from e
    return AskResponse(answer=answer, sources=sources)
