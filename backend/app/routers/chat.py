from fastapi import APIRouter, Depends, HTTPException
from genai.embeddings import embed_texts, to_pgvector_literal
from genai.llm import generate_answer
from pydantic import BaseModel, Field
from sqlalchemy import Connection, text

from app.config import settings
from app.db import get_db
from app.rate_limit import MAX_REQUESTS_PER_WINDOW, WINDOW_SECONDS, rate_limit

router = APIRouter(prefix="/chat", tags=["chat"])


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


class RetrieveResult(BaseModel):
    entity_type: str  # "player" or "team"
    entity_id: str
    name: str
    team: str
    position: str | None = None
    summary_text: str
    distance: float


class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


class AskResponse(BaseModel):
    answer: str
    sources: list[RetrieveResult]


def _retrieve_similar_entities(query: str, top_k: int, db: Connection) -> list[dict]:
    """Embeds `query` with the same local model used to build `player_embeddings` /
    `team_embeddings` and returns the nearest player AND team summaries together in
    one ranked list, by pgvector distance -- shared by /retrieve (retrieval only) and
    /ask (retrieval + Groq generation). A single ranked list across both entity types,
    rather than separate player/team buckets, lets similarity decide what's relevant --
    matching how a person would actually ask a mixed question ("who's the best
    defender" vs. "which team defends best" both just need the closest matches).
    """
    try:
        query_vector = embed_texts([query])[0]
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"embedding model unavailable: {e}") from e

    rows = db.execute(
        text(
            "select 'player' as entity_type, pe.player_id as entity_id, p.player_name as name, "
            "p.team, p.position, pe.summary_text, "
            "pe.embedding <-> cast(:query_vector as vector) as distance "
            "from player_embeddings pe join players p on p.player_id = pe.player_id "
            "union all "
            "select 'team' as entity_type, te.team_name as entity_id, te.team_name as name, "
            "te.team_name as team, null as position, te.summary_text, "
            "te.embedding <-> cast(:query_vector as vector) as distance "
            "from team_embeddings te "
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
            "Retrieval over player and team embeddings, plus Groq-backed generation, are both live."
            if settings.groq_api_key
            else "Retrieval is live; generation needs GROQ_API_KEY set to work."
        ),
        "rate_limit": {"requests_per_window": MAX_REQUESTS_PER_WINDOW, "window_seconds": WINDOW_SECONDS},
    }


@router.post("/retrieve", response_model=list[RetrieveResult])
def retrieve(
    payload: RetrieveRequest, db: Connection = Depends(get_db), _rate_limit: None = Depends(rate_limit)
):
    return _retrieve_similar_entities(payload.query, payload.top_k, db)


@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, db: Connection = Depends(get_db), _rate_limit: None = Depends(rate_limit)):
    """Retrieval-augmented generation: retrieves the nearest player/team summaries,
    then asks Groq to answer the question grounded in only that context -- not
    free-form LLM guessing (see docs/project_scope.md §5).
    """
    sources = _retrieve_similar_entities(payload.query, payload.top_k, db)
    try:
        answer = generate_answer(payload.query, [s["summary_text"] for s in sources])
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"generation unavailable: {e}") from e
    return AskResponse(answer=answer, sources=sources)
