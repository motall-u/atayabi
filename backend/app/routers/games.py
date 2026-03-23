"""API routes for game management."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.engine.game import GameEngine
from app.models import Game, RoundSnapshot
from app.schemas import (
    CreateGameRequest,
    EventInfo,
    GameResponse,
    GameSummary,
    ReplayResponse,
    RoundSnapshotSchema,
    AgentState,
    LogEntry,
)

router = APIRouter()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _game_to_summary(game: Game) -> GameSummary:
    # Extract game_mode from game_state JSON if available
    game_mode = "survival"
    if game.game_state:
        try:
            state_data = json.loads(game.game_state)
            game_mode = state_data.get("game_mode", "survival")
        except (json.JSONDecodeError, TypeError):
            pass
    return GameSummary(
        id=game.id,
        status=game.status,
        game_mode=game_mode,
        agent_count=game.agent_count,
        current_round=game.current_round,
        max_rounds=game.max_rounds,
        winner=game.winner,
        created_at=game.created_at.isoformat() if game.created_at else "",
    )


def _state_to_response(game: Game, state: dict) -> GameResponse:
    agents = []
    for a in state.get("agents", []):
        agents.append(AgentState(
            name=a["name"],
            personality=a["personality"],
            personality_wolof=a["personality_wolof"],
            health=a["health"],
            inventory=a["inventory"],
            alliances=a["alliances"],
            reputation=a["reputation"],
            alive=a["alive"],
            thinking=a.get("thinking"),
            public_message=a.get("public_message"),
        ))

    log_entries = []
    for entry in state.get("activity_log", []):
        log_entries.append(LogEntry(
            type=entry["type"],
            round=entry["round"],
            agent=entry.get("agent"),
            text=entry["text"],
        ))

    current_event = None
    if state.get("current_event"):
        ev = state["current_event"]
        current_event = EventInfo(
            name=ev["name"],
            description=ev["description"],
            type=ev["type"],
        )

    return GameResponse(
        id=game.id,
        status=game.status,
        game_mode=state.get("game_mode", "survival"),
        current_round=game.current_round,
        max_rounds=game.max_rounds,
        winner=game.winner,
        created_at=game.created_at.isoformat() if game.created_at else "",
        current_event=current_event,
        agents=agents,
        activity_log=log_entries,
    )


def _load_state(game: Game) -> dict:
    if game.game_state:
        return json.loads(game.game_state)
    return {}


def _save_state(game: Game, state: dict) -> None:
    game.game_state = json.dumps(state, ensure_ascii=False)
    game.status = state.get("status", game.status)
    game.current_round = state.get("current_round", game.current_round)
    game.winner = state.get("winner")


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/api/games", response_model=GameResponse, status_code=status.HTTP_201_CREATED)
async def create_game(req: CreateGameRequest, db: AsyncSession = Depends(get_db)):
    """Create a new game with *agent_count* agents (3-5)."""
    if req.game_mode == "boat":
        state = await GameEngine.create_boat_game(req.agent_count)
    else:
        state = await GameEngine.create_game(req.agent_count)

    game = Game(
        agent_count=req.agent_count,
        status=state["status"],
        current_round=state["current_round"],
        max_rounds=state["max_rounds"],
        game_state=json.dumps(state, ensure_ascii=False),
    )
    db.add(game)
    await db.commit()
    await db.refresh(game)

    # Store db id inside state for snapshot references
    state["_db_id"] = game.id
    game.game_state = json.dumps(state, ensure_ascii=False)
    await db.commit()

    return _state_to_response(game, state)


@router.get("/api/games", response_model=list[GameSummary])
async def list_games(db: AsyncSession = Depends(get_db)):
    """List all games, newest first."""
    result = await db.execute(select(Game).order_by(Game.created_at.desc()))
    games = result.scalars().all()
    return [_game_to_summary(g) for g in games]


@router.get("/api/games/{game_id}", response_model=GameResponse)
async def get_game(game_id: int, db: AsyncSession = Depends(get_db)):
    """Return the full current state of a game."""
    game = await db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    state = _load_state(game)
    return _state_to_response(game, state)


@router.post("/api/games/{game_id}/next-round", response_model=GameResponse)
async def next_round(game_id: int, db: AsyncSession = Depends(get_db)):
    """Play the next round of the game."""
    game = await db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    state = _load_state(game)
    if state.get("status") == "finished":
        raise HTTPException(status_code=400, detail="Game is already finished")

    # Ensure db_id is set
    state["_db_id"] = game.id

    engine = GameEngine(state)
    game_mode = state.get("game_mode", "survival")
    if game_mode == "boat":
        updated_state = await engine.play_boat_round(db)
    else:
        updated_state = await engine.play_round(db)

    _save_state(game, updated_state)
    await db.commit()

    return _state_to_response(game, updated_state)


@router.get("/api/games/{game_id}/next-round-stream")
async def next_round_stream(game_id: int, db: AsyncSession = Depends(get_db)):
    """Stream round progress via Server-Sent Events."""
    game = await db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    state = _load_state(game)
    if state.get("status") == "finished":
        raise HTTPException(status_code=400, detail="Game is already finished")

    # Ensure db_id is set
    state["_db_id"] = game.id

    engine = GameEngine(state)
    game_mode = state.get("game_mode", "survival")

    async def event_generator():
        if game_mode == "boat":
            stream = engine.play_boat_round_stream(db)
        else:
            stream = engine.play_round_stream(db)
        async for update in stream:
            if update["type"] == "complete":
                # Save final state to DB
                final_state = update.get("game", state)
                _save_state(game, final_state)
                await db.commit()
                # Build serializable response for the complete event
                game_resp = _state_to_response(game, final_state)
                payload = {
                    "type": "complete",
                    "message": update.get("message"),
                    "agent": update.get("agent"),
                    "game": json.loads(game_resp.model_dump_json()),
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            else:
                payload = {
                    "type": update.get("type", "info"),
                    "message": update.get("message"),
                    "agent": update.get("agent"),
                    "game": None,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.delete("/api/games/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_game(game_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a game and all its snapshots."""
    game = await db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await db.execute(
        delete(RoundSnapshot).where(RoundSnapshot.game_id == game_id)
    )
    await db.delete(game)
    await db.commit()
    return None


@router.get("/api/games/{game_id}/replay", response_model=ReplayResponse)
async def get_replay(game_id: int, db: AsyncSession = Depends(get_db)):
    """Return all round snapshots for replay."""
    game = await db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    result = await db.execute(
        select(RoundSnapshot)
        .where(RoundSnapshot.game_id == game_id)
        .order_by(RoundSnapshot.round_number)
    )
    snapshots = result.scalars().all()

    rounds = []
    for snap in snapshots:
        state_data = json.loads(snap.state_json) if snap.state_json else {}
        log_data = json.loads(snap.log_entries_json) if snap.log_entries_json else []

        event = None
        if state_data.get("current_event"):
            ev = state_data["current_event"]
            event = EventInfo(name=ev["name"], description=ev["description"], type=ev["type"])

        agents = []
        for a in state_data.get("agents", []):
            agents.append(AgentState(
                name=a["name"],
                personality=a["personality"],
                personality_wolof=a["personality_wolof"],
                health=a["health"],
                inventory=a["inventory"],
                alliances=a["alliances"],
                reputation=a["reputation"],
                alive=a["alive"],
                thinking=a.get("thinking"),
                public_message=a.get("public_message"),
            ))

        log_entries = [
            LogEntry(
                type=e["type"],
                round=e["round"],
                agent=e.get("agent"),
                text=e["text"],
            )
            for e in log_data
        ]

        rounds.append(RoundSnapshotSchema(
            round_number=snap.round_number,
            event=event,
            agents=agents,
            log_entries=log_entries,
        ))

    return ReplayResponse(
        game_id=game.id,
        total_rounds=len(rounds),
        rounds=rounds,
    )
