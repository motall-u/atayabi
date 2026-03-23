from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="waiting")  # waiting | in_progress | finished
    agent_count = Column(Integer)
    current_round = Column(Integer, default=0)
    max_rounds = Column(Integer, default=15)
    winner = Column(String, nullable=True)
    game_state = Column(Text)  # JSON blob of the full current state


class RoundSnapshot(Base):
    __tablename__ = "round_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"))
    round_number = Column(Integer)
    state_json = Column(Text)   # Full state snapshot as JSON
    log_entries_json = Column(Text)  # Log entries for this round as JSON
