import json

from fastapi import APIRouter, Depends, HTTPException
from genai.chart_specs import CHART_SPECS
from genai.llm import classify_chart_template
from pydantic import BaseModel, Field
from sqlalchemy import Connection, text

from app.db import get_db
from app.rate_limit import rate_limit

router = APIRouter(prefix="/charts", tags=["charts"])

_CATALOG_TEXT = "\n".join(f"- {name}: {spec.description}" for name, spec in CHART_SPECS.items())


class ChartRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)


class ChartDataPoint(BaseModel):
    label: str
    value: float | None = None


class ChartResponse(BaseModel):
    template: str
    chart_type: str
    title: str
    data: list[ChartDataPoint]


@router.get("/catalog")
def catalog():
    """What this feature can currently chart -- lets the frontend show example
    prompts, and is useful for demoing/debugging without spending a Groq call."""
    return [
        {"template": name, "description": spec.description, "title": spec.title}
        for name, spec in CHART_SPECS.items()
    ]


@router.post("/ask", response_model=ChartResponse)
def ask(payload: ChartRequest, db: Connection = Depends(get_db), _rate_limit: None = Depends(rate_limit)):
    """Natural language -> chart, constrained end to end: the LLM only ever selects a
    name from CHART_SPECS' fixed allowlist -- it never generates SQL, and no LLM
    output is ever interpolated into a query (see genai/chart_specs.py's docstring
    and docs/project_scope.md §5). If the model's response doesn't parse to JSON, or
    names something outside the allowlist, this rejects with a 422 rather than
    guessing at intent.
    """
    try:
        raw = classify_chart_template(payload.query, _CATALOG_TEXT)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"chart interpretation unavailable: {e}") from e

    try:
        template_name = json.loads(raw).get("template")
    except (json.JSONDecodeError, AttributeError):
        template_name = None

    spec = CHART_SPECS.get(template_name) if isinstance(template_name, str) else None
    if spec is None:
        raise HTTPException(
            status_code=422,
            detail="Couldn't match that question to an available chart. Try asking about "
            "top scorers, team standings, goals by tournament stage, or similar.",
        )

    # spec.sql is a fixed string literal from the allowlist above, never built from
    # user or LLM input -- see genai/chart_specs.py.
    rows = db.execute(text(spec.sql)).mappings().all()  # noqa: S608
    return ChartResponse(
        template=template_name,
        chart_type=spec.chart_type,
        title=spec.title,
        data=[dict(row) for row in rows],
    )
