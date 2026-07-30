"""Answer generation for the RAG chat endpoint, behind a provider-agnostic interface.

`generate_answer()` is the only thing routers/chat.py depends on -- swapping Groq for
another provider later means writing one new function with this signature, not
touching the router. Groq specifically because it has a generous free tier and fast
inference; see docs/ARCHITECTURE.md §4.5 / §5.
"""
from __future__ import annotations

import logging
import time

from app.config import settings

logger = logging.getLogger("app.genai")

GENERATION_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = (
    "You are a football analytics assistant answering questions about a FIFA World Cup "
    "2026 player-performance dataset. Answer ONLY using the player and team summaries given "
    "in the context below -- do not use outside knowledge about real players, teams, or "
    "tournaments. Cite specific numbers from the context when relevant. If the context "
    "doesn't contain enough information to answer, say so plainly rather than guessing."
)

_client = None


def _get_groq_client():
    global _client
    if _client is None:
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not set")
        from groq import Groq

        _client = Groq(api_key=settings.groq_api_key)
    return _client


def generate_answer(question: str, context: list[str]) -> str:
    context_block = (
        "\n\n".join(f"- {c}" for c in context) if context else "(no matching players or teams found)"
    )
    client = _get_groq_client()

    start = time.perf_counter()
    completion = client.chat.completions.create(
        model=GENERATION_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context_block}\n\nQuestion: {question}"},
        ],
        temperature=0.2,
        max_tokens=400,
    )
    duration_ms = (time.perf_counter() - start) * 1000

    usage = completion.usage
    logger.info(
        "groq_completion model=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s duration_ms=%.1f",
        GENERATION_MODEL,
        usage.prompt_tokens if usage else "-",
        usage.completion_tokens if usage else "-",
        usage.total_tokens if usage else "-",
        duration_ms,
    )

    return completion.choices[0].message.content
