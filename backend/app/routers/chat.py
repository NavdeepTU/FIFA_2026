from fastapi import APIRouter, Depends, HTTPException
from genai.embeddings import embed_texts, to_pgvector_literal
from pydantic import BaseModel, Field
from sqlalchemy import Connection, text

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


@router.get("/status")
def status():
    return {
        "retrieval_available": True,
        "generation_available": False,
        "message": "Retrieval over player_embeddings is live; Groq-backed answer generation isn't built yet.",
    }


@router.post("/retrieve", response_model=list[RetrieveResult])
def retrieve(payload: RetrieveRequest, db: Connection = Depends(get_db)):
    """Embeds the query with the same local model used to build `player_embeddings`
    and returns the nearest player summaries by cosine/L2 distance -- the retrieval
    half of RAG. No LLM call yet: see docs/project_status.md for what's still Phase 3.
    """
    try:
        query_vector = embed_texts([payload.query])[0]
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"embedding model unavailable: {e}") from e

    rows = db.execute(
        text(
            "select pe.player_id, p.player_name, p.team, p.position, pe.summary_text, "
            "pe.embedding <-> cast(:query_vector as vector) as distance "
            "from player_embeddings pe join players p on p.player_id = pe.player_id "
            "order by distance limit :top_k"
        ),
        {"query_vector": to_pgvector_literal(query_vector), "top_k": payload.top_k},
    ).mappings().all()
    return list(rows)
