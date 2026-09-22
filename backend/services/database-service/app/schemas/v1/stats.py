from pydantic import BaseModel, Field


class CandidateStatusStat(BaseModel):
    status: str
    count: int


class CandidateStatsResponse(BaseModel):
    """Counts keyed by funnel status label (Russian enum value)."""

    stats: dict[str, int] = Field(default_factory=dict)
