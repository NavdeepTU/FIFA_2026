from fastapi import APIRouter

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/status")
def status():
    """Placeholder until Phase 3 (GenAI/RAG layer via Groq) is built."""
    return {"available": False, "message": "GenAI chat endpoints land in Phase 3."}
