"""Groq-backed text generation, behind a provider-agnostic interface.

`generate_answer()`, `generate_player_report()`, and `generate_team_report()` are the
only things routers depend on -- swapping Groq for another provider later means
writing new functions with these signatures, not touching the routers. Groq
specifically because it has a generous free tier and fast inference; see
docs/ARCHITECTURE.md sections 4.5 and 5.
"""
from __future__ import annotations

import logging
import time

from app.config import settings

logger = logging.getLogger("app.genai")

GENERATION_MODEL = "llama-3.3-70b-versatile"

CHAT_SYSTEM_PROMPT = (
    "You are a football analytics assistant answering questions about a FIFA World Cup "
    "2026 player-performance dataset. Answer ONLY using the player and team summaries given "
    "in the context below -- do not use outside knowledge about real players, teams, or "
    "tournaments. Cite specific numbers from the context when relevant. If the context "
    "doesn't contain enough information to answer, say so plainly rather than guessing."
)

PLAYER_REPORT_SYSTEM_PROMPT = (
    "You are a professional football scout writing a short scouting report on a player, "
    "using ONLY the stats given below -- do not invent achievements, transfer history, or "
    "biographical details not present in the data. Write 3-4 short paragraphs covering: "
    "playing style and strengths (inferred from the stats -- e.g. high tackles suggests a "
    "combative midfielder), weaknesses or areas for improvement, and a notable recent "
    "performance if the match log shows one. Cite specific numbers. Write in plain "
    "professional prose, no headers or bullet points."
)

TEAM_REPORT_SYSTEM_PROMPT = (
    "You are a professional football analyst writing a short scouting report on a "
    "national team, using ONLY the stats given below -- do not invent results, squad "
    "names, or history not present in the data. Write 3-4 short paragraphs covering: "
    "the team's playing style and strengths (inferred from the stats -- e.g. a high "
    "tackle count suggests a combative, defensively organized side), weaknesses or "
    "areas for improvement, and a notable recent result if the match log shows one. "
    "Cite specific numbers. Write in plain professional prose, no headers or bullet "
    "points."
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


def _complete(system_prompt: str, user_content: str, *, max_tokens: int) -> str:
    client = _get_groq_client()

    start = time.perf_counter()
    completion = client.chat.completions.create(
        model=GENERATION_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
        max_tokens=max_tokens,
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


def generate_answer(question: str, context: list[str]) -> str:
    context_block = (
        "\n\n".join(f"- {c}" for c in context) if context else "(no matching players or teams found)"
    )
    return _complete(
        CHAT_SYSTEM_PROMPT,
        f"Context:\n{context_block}\n\nQuestion: {question}",
        max_tokens=400,
    )


def generate_player_report(summary: str, recent_matches: list[dict]) -> str:
    """`summary` is the same build_summary_text() output used for embeddings; recent
    matches add form/narrative color a static season summary doesn't capture.
    """
    if recent_matches:
        match_lines = "\n".join(
            f"- {m['match_date']} vs {m['opponent_team']} ({m['tournament_stage']}): "
            f"{m['match_result']}, {m['minutes_played']} mins, {m['goals']} goals, "
            f"{m['assists']} assists, rating {m['player_rating']}"
            for m in recent_matches
        )
    else:
        match_lines = "(no match log available)"

    return _complete(
        PLAYER_REPORT_SYSTEM_PROMPT,
        f"Season summary:\n{summary}\n\nMost recent matches:\n{match_lines}",
        max_tokens=500,
    )


def generate_team_report(summary: str, recent_matches: list[dict]) -> str:
    """`summary` is the same build_team_summary_text() output used for team
    embeddings; recent matches add form/narrative color a static summary doesn't
    capture -- mirrors generate_player_report()'s shape.
    """
    if recent_matches:
        match_lines = "\n".join(
            f"- {m['match_date']} vs {m['opponent']} ({m['tournament_stage']}): "
            f"{m['goals_for']}-{m['goals_against']}"
            for m in recent_matches
        )
    else:
        match_lines = "(no match log available)"

    return _complete(
        TEAM_REPORT_SYSTEM_PROMPT,
        f"Season summary:\n{summary}\n\nMost recent matches:\n{match_lines}",
        max_tokens=500,
    )
