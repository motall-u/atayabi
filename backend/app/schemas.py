from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ── Requests ──────────────────────────────────────────────────────────────────

class CreateGameRequest(BaseModel):
    agent_count: int = Field(..., ge=3, le=5, description="Number of agents (3-5)")
    game_mode: str = "survival"  # "survival" or "boat"


# ── Sub-models ────────────────────────────────────────────────────────────────

class EventInfo(BaseModel):
    name: str
    description: str
    type: str  # storm, raiders, disease, discovery, heat, calm, surge


class AgentState(BaseModel):
    name: str
    personality: str
    personality_wolof: str
    health: int
    inventory: dict
    alliances: list[str]
    reputation: int
    alive: bool
    thinking: Optional[str] = None
    public_message: Optional[str] = None


class LogEntry(BaseModel):
    type: str  # event, scavenge, message, trade, alliance, vote, elimination, death, system
    round: int
    agent: Optional[str] = None
    text: str


# ── Responses ─────────────────────────────────────────────────────────────────

class GameSummary(BaseModel):
    id: int
    status: str
    game_mode: str = "survival"
    agent_count: int
    current_round: int
    max_rounds: int
    winner: Optional[str] = None
    created_at: str


class GameResponse(BaseModel):
    id: int
    status: str
    game_mode: str = "survival"
    current_round: int
    max_rounds: int
    winner: Optional[str] = None
    created_at: str
    current_event: Optional[EventInfo] = None
    agents: list[AgentState]
    activity_log: list[LogEntry]


class RoundSnapshotSchema(BaseModel):
    round_number: int
    event: Optional[EventInfo] = None
    agents: list[AgentState]
    log_entries: list[LogEntry]


class ReplayResponse(BaseModel):
    game_id: int
    total_rounds: int
    rounds: list[RoundSnapshotSchema]


class LiveUpdate(BaseModel):
    type: str  # phase, event, scavenge, thinking, speaking, trade, vote, elimination, complete
    message: Optional[str] = None
    agent: Optional[str] = None
    game: Optional[GameResponse] = None  # Only for "complete" type


class BoatAction(BaseModel):
    agent: str
    action: str  # bribe, assassinate, steal, defend, none
    target: str | None = None
    bribe_amount: int | None = None
    success: bool = True
    detail: str = ""


class LLMStatusResponse(BaseModel):
    status: str
    model: Optional[str] = None
