"""Core game engine for Àttaya bi — The Last Camp."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from copy import deepcopy
from datetime import datetime
from typing import Any, AsyncGenerator

import httpx

from app import config
from app.engine.prompts import AGENT_PERSONALITIES, STRICT_RETRY_SUFFIX, build_system_prompt, build_user_message
from app.models import Game, RoundSnapshot

logger = logging.getLogger(__name__)

# ── Events Pool (French descriptions) ────────────────────────────────────────

EVENTS: list[dict[str, Any]] = [
    {
        "name": "Nawet bi",
        "description": "Une tempête féroce frappe le camp ! Tous les agents subissent des dégâts.",
        "type": "storm",
    },
    {
        "name": "Sàcc-sàcc yi",
        "description": "Des pillards attaquent ! Les agents sans armes perdent des ressources.",
        "type": "raiders",
    },
    {
        "name": "Feebar bi",
        "description": "Une maladie se répand ! Un agent au hasard perd 20 PV sans médicament.",
        "type": "disease",
    },
    {
        "name": "Feeñ bi",
        "description": "Une découverte ! Des ressources bonus ont été trouvées.",
        "type": "discovery",
    },
    {
        "name": "Safara si",
        "description": "Une vague de chaleur ! Consommation d'eau doublée ce tour.",
        "type": "heat",
    },
    {
        "name": "Jàmm bi",
        "description": "Une journée calme. Pas de dégâts — bon moment pour négocier.",
        "type": "calm",
    },
    {
        "name": "Géej gi",
        "description": "Un raz-de-marée ! Les abris sont endommagés, matériaux perdus.",
        "type": "surge",
    },
]

# ── Utility helpers ───────────────────────────────────────────────────────────

def _clamp(value: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, value))


def _default_response() -> dict:
    """Fallback response when the LLM fails to produce valid JSON."""
    return {
        "thinking": "(échec de réponse)",
        "public_message": None,
        "trade_offers": [],
        "alliance_action": "none",
        "alliance_target": None,
        "vote_to_eliminate": None,
    }


def _parse_llm_json(text: str) -> dict | None:
    """Try to extract a JSON object from LLM output."""
    # 1. Direct parse
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Try to find JSON block inside markdown fences
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 3. Greedy regex for outermost { ... }
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _format_resources(resources: dict[str, int]) -> str:
    """Format a resources dict into a readable French string."""
    parts = []
    for k, v in resources.items():
        if v > 0:
            parts.append(f"{v} {k}")
    return ", ".join(parts) if parts else "rien"


# ── Game Engine ───────────────────────────────────────────────────────────────

class GameEngine:
    """Operates on an in-memory game state dict, persists via DB."""

    def __init__(self, game_state: dict[str, Any]):
        self.state = game_state

    # ── Factory ───────────────────────────────────────────────────────────

    @staticmethod
    async def create_game(agent_count: int) -> dict[str, Any]:
        """Create a fresh game state with *agent_count* agents."""
        agents: list[dict[str, Any]] = []
        for p in AGENT_PERSONALITIES[:agent_count]:
            agents.append({
                "name": p["name"],
                "personality": p["personality"],
                "personality_wolof": p["personality_wolof"],
                "description": p["description"],
                "health": config.STARTING_HEALTH,
                "inventory": deepcopy(config.STARTING_RESOURCES),
                "alliances": [],
                "reputation": 50,
                "alive": True,
                "thinking": None,
                "public_message": None,
            })

        state: dict[str, Any] = {
            "status": "waiting",
            "current_round": 0,
            "max_rounds": config.MAX_ROUNDS,
            "winner": None,
            "current_event": None,
            "agents": agents,
            "activity_log": [],
            "pending_alliances": {},  # {proposer_name: target_name}
        }
        return state

    # ── Main round loop ──────────────────────────────────────────────────

    async def play_round(self, db_session) -> dict[str, Any]:
        """Execute one full round and return updated state."""

        state = self.state
        if state["status"] == "finished":
            return state

        state["status"] = "in_progress"
        state["current_round"] += 1
        round_num = state["current_round"]

        # Clear per-round transient data
        round_log: list[dict] = []

        # ---- 1. Event Phase ----
        event = random.choice(EVENTS)
        state["current_event"] = {
            "name": event["name"],
            "description": event["description"],
            "type": event["type"],
        }
        round_log.append({
            "type": "event",
            "round": round_num,
            "agent": None,
            "text": f"{event['name']}: {event['description']}",
        })

        # ---- 2. Scavenge Phase ----
        alive_agents = [a for a in state["agents"] if a["alive"]]
        resource_keys = [k for k in config.STARTING_RESOURCES.keys() if k != "xaalis"]
        for agent in alive_agents:
            found_resource = random.choice(resource_keys)
            found_amount = random.randint(config.SCAVENGE_MIN, config.SCAVENGE_MAX)
            agent["inventory"][found_resource] = agent["inventory"].get(found_resource, 0) + found_amount
            # Small random xaalis find (0-2)
            xaalis_found = random.randint(0, 2)
            if xaalis_found > 0:
                agent["inventory"]["xaalis"] = agent["inventory"].get("xaalis", 0) + xaalis_found
            found_parts = f"{found_amount} {found_resource}"
            if xaalis_found > 0:
                found_parts += f", {xaalis_found} xaalis"
            round_log.append({
                "type": "scavenge",
                "round": round_num,
                "agent": agent["name"],
                "text": f"{agent['name']} a trouvé {found_parts}.",
            })

        # ---- 3. Negotiation Phase (first LLM call per agent) ----
        agent_responses: dict[str, dict] = {}
        for agent in alive_agents:
            resp = await self._call_llm(agent)
            agent_responses[agent["name"]] = resp

            # Record public message
            agent["thinking"] = resp.get("thinking")
            agent["public_message"] = resp.get("public_message")
            if resp.get("public_message"):
                round_log.append({
                    "type": "message",
                    "round": round_num,
                    "agent": agent["name"],
                    "text": resp["public_message"],
                })

        # ---- 4. Trade Response Phase ----
        # Collect incoming trades per target
        incoming_by_target: dict[str, list[dict]] = {}
        for sender_name, resp in agent_responses.items():
            for offer in resp.get("trade_offers", []):
                target = offer.get("to")
                if not target:
                    continue
                trade_record = {
                    "from": sender_name,
                    "to": target,
                    "offer": offer.get("offer", {}),
                    "request": offer.get("request", {}),
                    "message": offer.get("message", ""),
                }
                incoming_by_target.setdefault(target, []).append(trade_record)

        # Second LLM call for agents that received trade offers
        trade_responses: dict[str, dict] = {}
        for agent in alive_agents:
            trades_for_agent = incoming_by_target.get(agent["name"])
            if trades_for_agent:
                resp2 = await self._call_llm(agent, incoming_trades=trades_for_agent)
                trade_responses[agent["name"]] = resp2
            else:
                trade_responses[agent["name"]] = agent_responses[agent["name"]]

        # ---- 5. Resolution Phase ----

        # 5a. Execute trades (including xaalis)
        executed_trades: set[tuple[str, str]] = set()
        for sender_name, resp in agent_responses.items():
            for offer in resp.get("trade_offers", []):
                target_name = offer.get("to")
                if not target_name:
                    continue
                pair = tuple(sorted([sender_name, target_name]))
                if pair in executed_trades:
                    continue
                # Check if the target also proposed a trade back to sender
                target_resp = trade_responses.get(target_name, {})
                target_offers_back = [
                    t for t in target_resp.get("trade_offers", [])
                    if t.get("to") == sender_name
                ]
                if target_offers_back:
                    # Execute the original trade
                    sender_agent = self._get_agent(sender_name)
                    target_agent = self._get_agent(target_name)
                    if sender_agent and target_agent:
                        success = self._execute_trade(
                            sender_agent, target_agent,
                            offer.get("offer", {}), offer.get("request", {}),
                        )
                        if success:
                            executed_trades.add(pair)
                            offer_str = _format_resources(offer.get("offer", {}))
                            request_str = _format_resources(offer.get("request", {}))
                            round_log.append({
                                "type": "trade",
                                "round": round_num,
                                "agent": sender_name,
                                "text": f"Échange: {sender_name} donne [{offer_str}] à {target_name} contre [{request_str}].",
                            })
                            sender_agent["reputation"] = _clamp(
                                sender_agent["reputation"] + config.REPUTATION_TRADE_BONUS
                            )
                            target_agent["reputation"] = _clamp(
                                target_agent["reputation"] + config.REPUTATION_TRADE_BONUS
                            )

        # 5b. Alliance logic
        pending = state.get("pending_alliances", {})
        # Use the trade_responses (or first response) for alliance actions
        for agent in alive_agents:
            resp = trade_responses.get(agent["name"], agent_responses.get(agent["name"], {}))
            action = resp.get("alliance_action", "none")
            target = resp.get("alliance_target")

            if action == "propose" and target:
                target_agent = self._get_agent(target)
                if target_agent and target_agent["alive"] and target != agent["name"]:
                    # Check if target already proposed to this agent
                    if pending.get(target) == agent["name"]:
                        # Both proposed to each other — form alliance
                        if target not in agent["alliances"]:
                            agent["alliances"].append(target)
                        if agent["name"] not in target_agent["alliances"]:
                            target_agent["alliances"].append(agent["name"])
                        pending.pop(target, None)
                        round_log.append({
                            "type": "alliance",
                            "round": round_num,
                            "agent": agent["name"],
                            "text": f"{agent['name']} et {target} ont formé une alliance !",
                        })
                    else:
                        pending[agent["name"]] = target
                        round_log.append({
                            "type": "alliance",
                            "round": round_num,
                            "agent": agent["name"],
                            "text": f"{agent['name']} propose une alliance à {target}.",
                        })

            elif action == "break" and target:
                target_agent = self._get_agent(target)
                if target_agent:
                    if target in agent["alliances"]:
                        agent["alliances"].remove(target)
                    if agent["name"] in target_agent["alliances"]:
                        target_agent["alliances"].remove(agent["name"])
                    agent["reputation"] = _clamp(
                        agent["reputation"] - config.REPUTATION_BETRAY_PENALTY
                    )
                    round_log.append({
                        "type": "alliance",
                        "round": round_num,
                        "agent": agent["name"],
                        "text": f"{agent['name']} a rompu son alliance avec {target} !",
                    })
                    # Remove pending
                    pending.pop(agent["name"], None)

        state["pending_alliances"] = pending

        # 5c. Consume resources (xaalis is NOT consumed)
        water_consumption = config.WATER_CONSUMPTION_PER_ROUND
        if event["type"] == "heat":
            water_consumption *= 2  # double water consumption for heat wave

        for agent in alive_agents:
            inv = agent["inventory"]
            # Food
            if inv.get("lekk", 0) >= config.FOOD_CONSUMPTION_PER_ROUND:
                inv["lekk"] -= config.FOOD_CONSUMPTION_PER_ROUND
            else:
                agent["health"] = _clamp(agent["health"] - config.NO_FOOD_DAMAGE)
                round_log.append({
                    "type": "system",
                    "round": round_num,
                    "agent": agent["name"],
                    "text": f"{agent['name']} n'a pas de nourriture et perd {config.NO_FOOD_DAMAGE} PV.",
                })
            # Water
            if inv.get("ndox", 0) >= water_consumption:
                inv["ndox"] -= water_consumption
            else:
                agent["health"] = _clamp(agent["health"] - config.NO_WATER_DAMAGE)
                round_log.append({
                    "type": "system",
                    "round": round_num,
                    "agent": agent["name"],
                    "text": f"{agent['name']} n'a pas d'eau et perd {config.NO_WATER_DAMAGE} PV.",
                })

        # 5d. Apply event damage
        self._apply_event(event, alive_agents, round_num, round_log)

        # 5e. Medicine auto-heal for very low health agents
        for agent in alive_agents:
            if agent["health"] <= 30 and agent["inventory"].get("garab", 0) > 0:
                agent["inventory"]["garab"] -= 1
                agent["health"] = _clamp(agent["health"] + config.MEDICINE_HEAL)
                round_log.append({
                    "type": "system",
                    "round": round_num,
                    "agent": agent["name"],
                    "text": f"{agent['name']} a utilisé un médicament et récupère {config.MEDICINE_HEAL} PV.",
                })

        # ---- 6. Elimination Check ----
        # 6a. Death from health
        for agent in state["agents"]:
            if agent["alive"] and agent["health"] <= 0:
                agent["alive"] = False
                round_log.append({
                    "type": "death",
                    "round": round_num,
                    "agent": agent["name"],
                    "text": f"{agent['name']} est mort.",
                })

        # 6b. Vote counting
        alive_after_damage = [a for a in state["agents"] if a["alive"]]
        vote_counts: dict[str, int] = {}
        for agent in alive_after_damage:
            resp = trade_responses.get(agent["name"], agent_responses.get(agent["name"], {}))
            vote_target = resp.get("vote_to_eliminate")
            if vote_target and vote_target != agent["name"]:
                vote_counts[vote_target] = vote_counts.get(vote_target, 0) + 1
                round_log.append({
                    "type": "vote",
                    "round": round_num,
                    "agent": agent["name"],
                    "text": f"{agent['name']} vote pour éliminer {vote_target}.",
                })

        majority_threshold = len(alive_after_damage) / 2
        for target_name, count in vote_counts.items():
            if count > majority_threshold:
                target_agent = self._get_agent(target_name)
                if target_agent and target_agent["alive"]:
                    target_agent["alive"] = False
                    target_agent["reputation"] = _clamp(
                        target_agent["reputation"] - config.REPUTATION_VOTE_PENALTY * count
                    )
                    round_log.append({
                        "type": "elimination",
                        "round": round_num,
                        "agent": target_name,
                        "text": f"{target_name} a été éliminé avec {count} votes !",
                    })

        # ---- 7. Victory Check ----
        still_alive = [a for a in state["agents"] if a["alive"]]
        game_over = False
        winner = None

        if len(still_alive) == 0:
            game_over = True
            winner = None
            round_log.append({
                "type": "system",
                "round": round_num,
                "agent": None,
                "text": "Tous les survivants ont péri. Personne ne gagne.",
            })
        elif len(still_alive) == 1:
            game_over = True
            winner = still_alive[0]["name"]
            round_log.append({
                "type": "system",
                "round": round_num,
                "agent": winner,
                "text": f"{winner} est le seul survivant et remporte la partie !",
            })
        elif len(still_alive) == 2:
            # Check if both are allied
            a, b = still_alive
            if b["name"] in a["alliances"] and a["name"] in b["alliances"]:
                game_over = True
                winner = f"{a['name']} & {b['name']}"
                round_log.append({
                    "type": "system",
                    "round": round_num,
                    "agent": None,
                    "text": f"{a['name']} et {b['name']} survivent ensemble en tant qu'alliés !",
                })

        if not game_over and round_num >= state["max_rounds"]:
            game_over = True
            if still_alive:
                best = max(still_alive, key=lambda a: a["health"])
                winner = best["name"]
                round_log.append({
                    "type": "system",
                    "round": round_num,
                    "agent": winner,
                    "text": f"Tours maximum atteints. {winner} gagne avec {best['health']} PV !",
                })
            else:
                round_log.append({
                    "type": "system",
                    "round": round_num,
                    "agent": None,
                    "text": "Tours maximum atteints. Aucun survivant.",
                })

        if game_over:
            state["status"] = "finished"
            state["winner"] = winner

        # Append round log to activity log
        state["activity_log"].extend(round_log)

        # ---- 8. Save round snapshot ----
        snapshot = RoundSnapshot(
            game_id=state.get("_db_id"),
            round_number=round_num,
            state_json=json.dumps({
                "current_event": state["current_event"],
                "agents": self._agents_for_snapshot(),
            }),
            log_entries_json=json.dumps(round_log),
        )
        db_session.add(snapshot)
        await db_session.flush()

        return state

    # ── SSE Streaming round ──────────────────────────────────────────────

    async def play_round_stream(self, db_session) -> AsyncGenerator[dict[str, Any], None]:
        """Play a round and yield SSE events for live feedback."""

        state = self.state
        if state["status"] == "finished":
            yield {"type": "complete", "message": "La partie est terminée.", "agent": None, "game": state}
            return

        state["status"] = "in_progress"
        state["current_round"] += 1
        round_num = state["current_round"]

        round_log: list[dict] = []

        # ---- 1. Event Phase ----
        yield {"type": "phase", "message": "Phase événement...", "agent": None}
        event = random.choice(EVENTS)
        state["current_event"] = {
            "name": event["name"],
            "description": event["description"],
            "type": event["type"],
        }
        round_log.append({
            "type": "event",
            "round": round_num,
            "agent": None,
            "text": f"{event['name']}: {event['description']}",
        })
        yield {"type": "event", "message": f"{event['name']} — {event['description']}", "agent": None}

        # ---- 2. Scavenge Phase ----
        yield {"type": "phase", "message": "Phase récolte...", "agent": None}
        alive_agents = [a for a in state["agents"] if a["alive"]]
        resource_keys = [k for k in config.STARTING_RESOURCES.keys() if k != "xaalis"]
        for agent in alive_agents:
            found_resource = random.choice(resource_keys)
            found_amount = random.randint(config.SCAVENGE_MIN, config.SCAVENGE_MAX)
            agent["inventory"][found_resource] = agent["inventory"].get(found_resource, 0) + found_amount
            # Small random xaalis find (0-2)
            xaalis_found = random.randint(0, 2)
            if xaalis_found > 0:
                agent["inventory"]["xaalis"] = agent["inventory"].get("xaalis", 0) + xaalis_found
            found_parts = f"{found_amount} {found_resource}"
            if xaalis_found > 0:
                found_parts += f", {xaalis_found} xaalis"
            round_log.append({
                "type": "scavenge",
                "round": round_num,
                "agent": agent["name"],
                "text": f"{agent['name']} a trouvé {found_parts}.",
            })
            yield {"type": "scavenge", "agent": agent["name"], "message": f"{agent['name']} a trouvé {found_parts}"}

        # ---- 3. Negotiation Phase (first LLM call per agent) ----
        yield {"type": "phase", "message": "Phase négociation...", "agent": None}
        agent_responses: dict[str, dict] = {}
        for agent in alive_agents:
            yield {"type": "thinking", "agent": agent["name"], "message": f"{agent['name']} réfléchit..."}
            resp = await self._call_llm(agent)
            agent_responses[agent["name"]] = resp

            agent["thinking"] = resp.get("thinking")
            agent["public_message"] = resp.get("public_message")
            if resp.get("public_message"):
                round_log.append({
                    "type": "message",
                    "round": round_num,
                    "agent": agent["name"],
                    "text": resp["public_message"],
                })
                yield {"type": "speaking", "agent": agent["name"], "message": f"{agent['name']}: {resp['public_message']}"}

        # ---- 4. Trade Response Phase ----
        yield {"type": "phase", "message": "Phase réponse aux échanges...", "agent": None}
        incoming_by_target: dict[str, list[dict]] = {}
        for sender_name, resp in agent_responses.items():
            for offer in resp.get("trade_offers", []):
                target = offer.get("to")
                if not target:
                    continue
                trade_record = {
                    "from": sender_name,
                    "to": target,
                    "offer": offer.get("offer", {}),
                    "request": offer.get("request", {}),
                    "message": offer.get("message", ""),
                }
                incoming_by_target.setdefault(target, []).append(trade_record)

        trade_responses: dict[str, dict] = {}
        for agent in alive_agents:
            trades_for_agent = incoming_by_target.get(agent["name"])
            if trades_for_agent:
                yield {"type": "thinking", "agent": agent["name"], "message": f"{agent['name']} évalue les offres..."}
                resp2 = await self._call_llm(agent, incoming_trades=trades_for_agent)
                trade_responses[agent["name"]] = resp2
            else:
                trade_responses[agent["name"]] = agent_responses[agent["name"]]

        # ---- 5. Resolution Phase ----
        yield {"type": "phase", "message": "Résolution...", "agent": None}

        # 5a. Execute trades (including xaalis)
        executed_trades: set[tuple[str, str]] = set()
        for sender_name, resp in agent_responses.items():
            for offer in resp.get("trade_offers", []):
                target_name = offer.get("to")
                if not target_name:
                    continue
                pair = tuple(sorted([sender_name, target_name]))
                if pair in executed_trades:
                    continue
                target_resp = trade_responses.get(target_name, {})
                target_offers_back = [
                    t for t in target_resp.get("trade_offers", [])
                    if t.get("to") == sender_name
                ]
                if target_offers_back:
                    sender_agent = self._get_agent(sender_name)
                    target_agent = self._get_agent(target_name)
                    if sender_agent and target_agent:
                        success = self._execute_trade(
                            sender_agent, target_agent,
                            offer.get("offer", {}), offer.get("request", {}),
                        )
                        if success:
                            executed_trades.add(pair)
                            offer_str = _format_resources(offer.get("offer", {}))
                            request_str = _format_resources(offer.get("request", {}))
                            trade_msg = f"Échange: {sender_name} donne [{offer_str}] à {target_name} contre [{request_str}]."
                            round_log.append({
                                "type": "trade",
                                "round": round_num,
                                "agent": sender_name,
                                "text": trade_msg,
                            })
                            yield {"type": "trade", "agent": sender_name, "message": trade_msg}
                            sender_agent["reputation"] = _clamp(
                                sender_agent["reputation"] + config.REPUTATION_TRADE_BONUS
                            )
                            target_agent["reputation"] = _clamp(
                                target_agent["reputation"] + config.REPUTATION_TRADE_BONUS
                            )

        # 5b. Alliance logic
        pending = state.get("pending_alliances", {})
        for agent in alive_agents:
            resp = trade_responses.get(agent["name"], agent_responses.get(agent["name"], {}))
            action = resp.get("alliance_action", "none")
            target = resp.get("alliance_target")

            if action == "propose" and target:
                target_agent = self._get_agent(target)
                if target_agent and target_agent["alive"] and target != agent["name"]:
                    if pending.get(target) == agent["name"]:
                        if target not in agent["alliances"]:
                            agent["alliances"].append(target)
                        if agent["name"] not in target_agent["alliances"]:
                            target_agent["alliances"].append(agent["name"])
                        pending.pop(target, None)
                        alliance_msg = f"{agent['name']} et {target} ont formé une alliance !"
                        round_log.append({
                            "type": "alliance",
                            "round": round_num,
                            "agent": agent["name"],
                            "text": alliance_msg,
                        })
                        yield {"type": "alliance", "agent": agent["name"], "message": alliance_msg}
                    else:
                        pending[agent["name"]] = target
                        alliance_msg = f"{agent['name']} propose une alliance à {target}."
                        round_log.append({
                            "type": "alliance",
                            "round": round_num,
                            "agent": agent["name"],
                            "text": alliance_msg,
                        })
                        yield {"type": "alliance", "agent": agent["name"], "message": alliance_msg}

            elif action == "break" and target:
                target_agent = self._get_agent(target)
                if target_agent:
                    if target in agent["alliances"]:
                        agent["alliances"].remove(target)
                    if agent["name"] in target_agent["alliances"]:
                        target_agent["alliances"].remove(agent["name"])
                    agent["reputation"] = _clamp(
                        agent["reputation"] - config.REPUTATION_BETRAY_PENALTY
                    )
                    alliance_msg = f"{agent['name']} a rompu son alliance avec {target} !"
                    round_log.append({
                        "type": "alliance",
                        "round": round_num,
                        "agent": agent["name"],
                        "text": alliance_msg,
                    })
                    yield {"type": "alliance", "agent": agent["name"], "message": alliance_msg}
                    pending.pop(agent["name"], None)

        state["pending_alliances"] = pending

        # 5c. Consume resources (xaalis is NOT consumed)
        water_consumption = config.WATER_CONSUMPTION_PER_ROUND
        if event["type"] == "heat":
            water_consumption *= 2

        for agent in alive_agents:
            inv = agent["inventory"]
            if inv.get("lekk", 0) >= config.FOOD_CONSUMPTION_PER_ROUND:
                inv["lekk"] -= config.FOOD_CONSUMPTION_PER_ROUND
            else:
                agent["health"] = _clamp(agent["health"] - config.NO_FOOD_DAMAGE)
                round_log.append({
                    "type": "system",
                    "round": round_num,
                    "agent": agent["name"],
                    "text": f"{agent['name']} n'a pas de nourriture et perd {config.NO_FOOD_DAMAGE} PV.",
                })
            if inv.get("ndox", 0) >= water_consumption:
                inv["ndox"] -= water_consumption
            else:
                agent["health"] = _clamp(agent["health"] - config.NO_WATER_DAMAGE)
                round_log.append({
                    "type": "system",
                    "round": round_num,
                    "agent": agent["name"],
                    "text": f"{agent['name']} n'a pas d'eau et perd {config.NO_WATER_DAMAGE} PV.",
                })

        # 5d. Apply event damage
        self._apply_event(event, alive_agents, round_num, round_log)

        # 5e. Medicine auto-heal
        for agent in alive_agents:
            if agent["health"] <= 30 and agent["inventory"].get("garab", 0) > 0:
                agent["inventory"]["garab"] -= 1
                agent["health"] = _clamp(agent["health"] + config.MEDICINE_HEAL)
                round_log.append({
                    "type": "system",
                    "round": round_num,
                    "agent": agent["name"],
                    "text": f"{agent['name']} a utilisé un médicament et récupère {config.MEDICINE_HEAL} PV.",
                })

        # ---- 6. Elimination Check ----
        yield {"type": "phase", "message": "Vérification des éliminations...", "agent": None}

        # 6a. Death from health
        for agent in state["agents"]:
            if agent["alive"] and agent["health"] <= 0:
                agent["alive"] = False
                death_msg = f"{agent['name']} est mort."
                round_log.append({
                    "type": "death",
                    "round": round_num,
                    "agent": agent["name"],
                    "text": death_msg,
                })
                yield {"type": "elimination", "agent": agent["name"], "message": death_msg}

        # 6b. Vote counting
        alive_after_damage = [a for a in state["agents"] if a["alive"]]
        vote_counts: dict[str, int] = {}
        for agent in alive_after_damage:
            resp = trade_responses.get(agent["name"], agent_responses.get(agent["name"], {}))
            vote_target = resp.get("vote_to_eliminate")
            if vote_target and vote_target != agent["name"]:
                vote_counts[vote_target] = vote_counts.get(vote_target, 0) + 1
                vote_msg = f"{agent['name']} vote pour éliminer {vote_target}."
                round_log.append({
                    "type": "vote",
                    "round": round_num,
                    "agent": agent["name"],
                    "text": vote_msg,
                })
                yield {"type": "vote", "agent": agent["name"], "message": vote_msg}

        majority_threshold = len(alive_after_damage) / 2
        for target_name, count in vote_counts.items():
            if count > majority_threshold:
                target_agent = self._get_agent(target_name)
                if target_agent and target_agent["alive"]:
                    target_agent["alive"] = False
                    target_agent["reputation"] = _clamp(
                        target_agent["reputation"] - config.REPUTATION_VOTE_PENALTY * count
                    )
                    elim_msg = f"{target_name} a été éliminé avec {count} votes !"
                    round_log.append({
                        "type": "elimination",
                        "round": round_num,
                        "agent": target_name,
                        "text": elim_msg,
                    })
                    yield {"type": "elimination", "agent": target_name, "message": elim_msg}

        # ---- 7. Victory Check ----
        still_alive = [a for a in state["agents"] if a["alive"]]
        game_over = False
        winner = None

        if len(still_alive) == 0:
            game_over = True
            winner = None
            round_log.append({
                "type": "system",
                "round": round_num,
                "agent": None,
                "text": "Tous les survivants ont péri. Personne ne gagne.",
            })
        elif len(still_alive) == 1:
            game_over = True
            winner = still_alive[0]["name"]
            round_log.append({
                "type": "system",
                "round": round_num,
                "agent": winner,
                "text": f"{winner} est le seul survivant et remporte la partie !",
            })
        elif len(still_alive) == 2:
            a, b = still_alive
            if b["name"] in a["alliances"] and a["name"] in b["alliances"]:
                game_over = True
                winner = f"{a['name']} & {b['name']}"
                round_log.append({
                    "type": "system",
                    "round": round_num,
                    "agent": None,
                    "text": f"{a['name']} et {b['name']} survivent ensemble en tant qu'alliés !",
                })

        if not game_over and round_num >= state["max_rounds"]:
            game_over = True
            if still_alive:
                best = max(still_alive, key=lambda a: a["health"])
                winner = best["name"]
                round_log.append({
                    "type": "system",
                    "round": round_num,
                    "agent": winner,
                    "text": f"Tours maximum atteints. {winner} gagne avec {best['health']} PV !",
                })
            else:
                round_log.append({
                    "type": "system",
                    "round": round_num,
                    "agent": None,
                    "text": "Tours maximum atteints. Aucun survivant.",
                })

        if game_over:
            state["status"] = "finished"
            state["winner"] = winner

        # Append round log to activity log
        state["activity_log"].extend(round_log)

        # ---- 8. Save round snapshot ----
        snapshot = RoundSnapshot(
            game_id=state.get("_db_id"),
            round_number=round_num,
            state_json=json.dumps({
                "current_event": state["current_event"],
                "agents": self._agents_for_snapshot(),
            }),
            log_entries_json=json.dumps(round_log),
        )
        db_session.add(snapshot)
        await db_session.flush()

        # Final complete event with full game state
        yield {"type": "complete", "message": None, "agent": None, "game": state}

    # ── Event application ─────────────────────────────────────────────────

    def _apply_event(self, event: dict, alive_agents: list[dict],
                     round_num: int, round_log: list[dict]) -> None:
        etype = event["type"]

        if etype == "storm":
            for agent in alive_agents:
                damage = random.randint(10, 25)
                if agent["inventory"].get("mbëj", 0) > 0:
                    damage = int(damage * config.SHELTER_DAMAGE_REDUCTION)
                agent["health"] = _clamp(agent["health"] - damage)
                round_log.append({
                    "type": "event",
                    "round": round_num,
                    "agent": agent["name"],
                    "text": f"{agent['name']} subit {damage} dégâts de tempête.",
                })

        elif etype == "raiders":
            for agent in alive_agents:
                if agent["inventory"].get("paxal", 0) <= 0:
                    # Lose 1-2 random resources (not xaalis — raiders take physical goods)
                    losses = random.randint(1, 2)
                    available = [k for k, v in agent["inventory"].items() if v > 0 and k not in ("paxal", "xaalis")]
                    for _ in range(losses):
                        if not available:
                            break
                        res = random.choice(available)
                        agent["inventory"][res] = max(0, agent["inventory"][res] - 1)
                        if agent["inventory"][res] == 0:
                            available.remove(res)
                    round_log.append({
                        "type": "event",
                        "round": round_num,
                        "agent": agent["name"],
                        "text": f"Les pillards ont volé {agent['name']} !",
                    })

        elif etype == "disease":
            victim = random.choice(alive_agents)
            if victim["inventory"].get("garab", 0) > 0:
                victim["inventory"]["garab"] -= 1
                round_log.append({
                    "type": "event",
                    "round": round_num,
                    "agent": victim["name"],
                    "text": f"{victim['name']} est tombé malade mais a utilisé un médicament pour guérir.",
                })
            else:
                victim["health"] = _clamp(victim["health"] - 20)
                round_log.append({
                    "type": "event",
                    "round": round_num,
                    "agent": victim["name"],
                    "text": f"{victim['name']} est tombé malade et perd 20 PV !",
                })

        elif etype == "discovery":
            resource_keys = [k for k in config.STARTING_RESOURCES.keys() if k != "xaalis"]
            for agent in alive_agents:
                bonus_res = random.choice(resource_keys)
                bonus_amt = random.randint(1, 2)
                agent["inventory"][bonus_res] = agent["inventory"].get(bonus_res, 0) + bonus_amt
                # Also find some xaalis in the discovery
                bonus_xaalis = random.randint(1, 3)
                agent["inventory"]["xaalis"] = agent["inventory"].get("xaalis", 0) + bonus_xaalis
                round_log.append({
                    "type": "event",
                    "round": round_num,
                    "agent": agent["name"],
                    "text": f"{agent['name']} a trouvé {bonus_amt} {bonus_res} et {bonus_xaalis} xaalis dans la découverte !",
                })

        elif etype == "heat":
            round_log.append({
                "type": "event",
                "round": round_num,
                "agent": None,
                "text": "La vague de chaleur double la consommation d'eau ce tour.",
            })

        elif etype == "calm":
            round_log.append({
                "type": "event",
                "round": round_num,
                "agent": None,
                "text": "Une journée calme. Aucun dégât.",
            })

        elif etype == "surge":
            for agent in alive_agents:
                if agent["inventory"].get("mbëj", 0) > 0:
                    agent["inventory"]["mbëj"] = 0
                    round_log.append({
                        "type": "event",
                        "round": round_num,
                        "agent": agent["name"],
                        "text": f"L'abri de {agent['name']} a été emporté par le raz-de-marée !",
                    })

    # ── LLM interaction ───────────────────────────────────────────────────

    async def _call_llm(self, agent: dict,
                        incoming_trades: list[dict] | None = None,
                        is_retry: bool = False,
                        system_prompt_override: str | None = None,
                        user_msg_override: str | None = None) -> dict:
        """Call the LLM for one agent and return parsed response."""
        if system_prompt_override:
            system_prompt = system_prompt_override
            user_content = user_msg_override or "Make your decision."
        else:
            system_prompt = build_system_prompt(agent, self.state, incoming_trades)
            user_content = build_user_message(agent, self.state)

        if is_retry:
            system_prompt += STRICT_RETRY_SUFFIX

        timeout_s = config.API_TIMEOUT_MS / 1000
        delay_s = config.API_CALL_DELAY_MS / 1000

        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(
                    f"{config.OPENAI_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": config.OPENAI_MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "temperature": 0.8,
                        "max_tokens": 512,
                        "stop": ["\n\n\n"],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                parsed = _parse_llm_json(content)
                if parsed is not None:
                    await asyncio.sleep(delay_s)
                    if system_prompt_override:
                        return self._validate_boat_response(parsed, agent)
                    return self._validate_agent_response(parsed, agent)

                # Parse failed — retry once
                if not is_retry:
                    logger.warning("Échec du parsing JSON pour %s, nouvelle tentative…", agent["name"])
                    await asyncio.sleep(delay_s)
                    return await self._call_llm(agent, incoming_trades, is_retry=True,
                                                system_prompt_override=system_prompt_override,
                                                user_msg_override=user_msg_override)

        except Exception as exc:
            logger.error("Appel LLM échoué pour %s: %s", agent["name"], exc)

        await asyncio.sleep(delay_s)
        return _default_response()

    def _validate_agent_response(self, resp: dict, agent: dict) -> dict:
        """Sanitise / fill in missing fields from the LLM response."""
        clean: dict[str, Any] = {}
        clean["thinking"] = resp.get("thinking") or "(pas de réflexion)"
        clean["public_message"] = resp.get("public_message")
        clean["trade_offers"] = []

        for t in resp.get("trade_offers", []) or []:
            if isinstance(t, dict) and t.get("to"):
                clean["trade_offers"].append({
                    "to": str(t["to"]),
                    "offer": t.get("offer", {}),
                    "request": t.get("request", {}),
                    "message": t.get("message", ""),
                })

        action = resp.get("alliance_action", "none")
        if action not in ("propose", "break", "none"):
            action = "none"
        clean["alliance_action"] = action
        clean["alliance_target"] = resp.get("alliance_target")
        clean["vote_to_eliminate"] = resp.get("vote_to_eliminate")
        return clean

    # ── Trade execution ───────────────────────────────────────────────────

    @staticmethod
    def _execute_trade(sender: dict, receiver: dict,
                       offer: dict, request: dict) -> bool:
        """Swap resources between two agents. Returns True on success.
        Supports xaalis as a tradeable resource."""
        # Verify sender has offered resources
        for res, amount in offer.items():
            if not isinstance(amount, (int, float)):
                return False
            if sender["inventory"].get(res, 0) < int(amount):
                return False
        # Verify receiver has requested resources
        for res, amount in request.items():
            if not isinstance(amount, (int, float)):
                return False
            if receiver["inventory"].get(res, 0) < int(amount):
                return False
        # Execute
        for res, amount in offer.items():
            amt = int(amount)
            sender["inventory"][res] = sender["inventory"].get(res, 0) - amt
            receiver["inventory"][res] = receiver["inventory"].get(res, 0) + amt
        for res, amount in request.items():
            amt = int(amount)
            receiver["inventory"][res] = receiver["inventory"].get(res, 0) - amt
            sender["inventory"][res] = sender["inventory"].get(res, 0) + amt
        return True

    # ── Helpers ───────────────────────────────────────────────────────────

    def _get_agent(self, name: str) -> dict | None:
        for a in self.state["agents"]:
            if a["name"] == name:
                return a
        return None

    def _agents_for_snapshot(self) -> list[dict]:
        """Return agents without internal engine fields for snapshot."""
        out = []
        for a in self.state["agents"]:
            out.append({
                "name": a["name"],
                "personality": a["personality"],
                "personality_wolof": a["personality_wolof"],
                "health": a["health"],
                "inventory": a["inventory"],
                "alliances": a["alliances"],
                "reputation": a["reputation"],
                "alive": a["alive"],
                "thinking": a.get("thinking"),
                "public_message": a.get("public_message"),
            })
        return out

    async def _save_round_snapshot(self, db_session, round_num: int, round_log: list[dict]) -> None:
        """Save a round snapshot to the database."""
        snapshot = RoundSnapshot(
            game_id=self.state.get("_db_id"),
            round_number=round_num,
            state_json=json.dumps({
                "current_event": self.state.get("current_event"),
                "agents": self._agents_for_snapshot(),
            }),
            log_entries_json=json.dumps(round_log),
        )
        db_session.add(snapshot)
        await db_session.flush()

    def _validate_boat_response(self, resp: dict, agent: dict) -> dict:
        """Sanitise / fill in missing fields from a boat mode LLM response."""
        clean: dict[str, Any] = {}
        clean["thinking"] = resp.get("thinking") or "(pas de réflexion)"
        clean["public_message"] = resp.get("public_message")

        action = resp.get("action", "none")
        if action not in ("bribe", "assassinate", "steal", "defend", "none"):
            action = "none"
        clean["action"] = action
        clean["action_target"] = resp.get("action_target")
        clean["bribe_amount"] = resp.get("bribe_amount")
        clean["vote_for_boat"] = resp.get("vote_for_boat") or agent["name"]
        clean["private_message_to"] = resp.get("private_message_to")
        clean["private_message"] = resp.get("private_message")
        return clean

    # ── Boat Mode Factory ────────────────────────────────────────────────

    @staticmethod
    async def create_boat_game(agent_count: int) -> dict[str, Any]:
        """Create a new boat mode game."""
        from app.config import (BOAT_MAX_ROUNDS, BOAT_STARTING_XAALIS,
                                BOAT_STARTING_PAXAL, BOAT_STARTING_GARAB)
        from app.engine.prompts import BOAT_PERSONALITIES

        selected = BOAT_PERSONALITIES[:agent_count]
        agents = []
        for p in selected:
            agents.append({
                "name": p["name"],
                "personality": p["personality"],
                "personality_wolof": p["personality_wolof"],
                "health": 100,
                "inventory": {
                    "ndox": 0, "lekk": 0, "garab": BOAT_STARTING_GARAB,
                    "mbëj": 0, "paxal": BOAT_STARTING_PAXAL, "xaalis": BOAT_STARTING_XAALIS,
                },
                "alliances": [],
                "reputation": 50,
                "alive": True,
                "thinking": None,
                "public_message": None,
            })

        return {
            "status": "waiting",
            "game_mode": "boat",
            "current_round": 0,
            "max_rounds": BOAT_MAX_ROUNDS,
            "current_event": None,
            "agents": agents,
            "activity_log": [],
            "winner": None,
            "vote_history": [],
            "action_history": [],
            "chat_history": [],
        }

    # ── Boat Mode Round (non-streaming) ──────────────────────────────────

    async def play_boat_round(self, db_session) -> dict[str, Any]:
        """Execute one full boat-mode round and return updated state."""
        # Collect all events from the streaming generator and return final state
        final_state = self.state
        async for update in self.play_boat_round_stream(db_session):
            if update["type"] == "complete" and update.get("game"):
                final_state = update["game"]
        return final_state

    # ── Boat Mode Round (streaming) ──────────────────────────────────────

    async def play_boat_round_stream(self, db_session) -> AsyncGenerator[dict[str, Any], None]:
        """Play one round of boat mode, yielding SSE updates."""
        from app.config import (BOAT_SCAVENGE_XAALIS_MIN, BOAT_SCAVENGE_XAALIS_MAX,
                                BOAT_SCAVENGE_PAXAL_CHANCE, BOAT_SCAVENGE_GARAB_CHANCE,
                                BOAT_STEAL_AMOUNT, API_CALL_DELAY_MS)
        from app.engine.prompts import build_boat_system_prompt

        self.state["current_round"] += 1
        round_num = self.state["current_round"]
        self.state["status"] = "in_progress"
        round_log: list[dict] = []

        alive_agents = [a for a in self.state["agents"] if a["alive"]]

        # Phase 1: Scavenging (find small resources)
        yield {"type": "phase", "message": "Fouille de l'île...", "agent": None, "game": None}
        for agent in alive_agents:
            found = []
            xaalis_found = random.randint(BOAT_SCAVENGE_XAALIS_MIN, BOAT_SCAVENGE_XAALIS_MAX)
            if xaalis_found > 0:
                agent["inventory"]["xaalis"] += xaalis_found
                found.append(f"{xaalis_found} xaalis")
            if random.random() < BOAT_SCAVENGE_PAXAL_CHANCE:
                agent["inventory"]["paxal"] += 1
                found.append("1 paxal")
            if random.random() < BOAT_SCAVENGE_GARAB_CHANCE:
                agent["inventory"]["garab"] += 1
                found.append("1 garab")
            if found:
                msg = f"{agent['name']} a trouvé {', '.join(found)}."
                round_log.append({"type": "scavenge", "round": round_num, "agent": agent["name"], "text": msg})
                yield {"type": "scavenge", "message": msg, "agent": agent["name"], "game": None}

        # Phase 2: Negotiation — each agent speaks and decides
        yield {"type": "phase", "message": "Phase de négociation...", "agent": None, "game": None}

        agent_decisions: dict[str, dict] = {}
        for agent in alive_agents:
            yield {"type": "thinking", "message": f"{agent['name']} réfléchit...", "agent": agent["name"], "game": None}

            system_prompt, user_msg = build_boat_system_prompt(
                agent=agent,
                all_agents=self.state["agents"],
                round_number=round_num,
                max_rounds=self.state["max_rounds"],
                vote_history=self.state.get("vote_history", []),
                action_history=self.state.get("action_history", []),
                chat_history=self.state.get("chat_history", []),
            )

            response = await self._call_llm(agent, system_prompt_override=system_prompt, user_msg_override=user_msg)
            agent_decisions[agent["name"]] = response

            # Store public message
            public_msg = response.get("public_message", "...")
            agent["public_message"] = public_msg
            agent["thinking"] = response.get("thinking", "")

            if public_msg and public_msg != "...":
                round_log.append({"type": "message", "round": round_num, "agent": agent["name"], "text": public_msg})
                yield {"type": "speaking", "message": f"{agent['name']}: {public_msg}", "agent": agent["name"], "game": None}

            # Store private message in chat_history (only visible to recipient next round)
            pm_to = response.get("private_message_to")
            pm_text = response.get("private_message")
            if pm_to and pm_text:
                self.state.setdefault("chat_history", []).append(
                    f"[Message privé de {agent['name']} à {pm_to}]: {pm_text}"
                )
                round_log.append({"type": "message", "round": round_num, "agent": agent["name"],
                                "text": f"{agent['name']} murmure quelque chose à {pm_to}..."})
                yield {"type": "trade", "message": f"{agent['name']} murmure à {pm_to}...", "agent": agent["name"], "game": None}

            await asyncio.sleep(API_CALL_DELAY_MS / 1000)

        # Phase 3: Resolve Actions
        yield {"type": "phase", "message": "Résolution des actions...", "agent": None, "game": None}

        round_actions: list[str] = []

        # Collect all actions
        actions = []
        for agent_name, decision in agent_decisions.items():
            action = decision.get("action", "none")
            target = decision.get("action_target")
            bribe_amt = decision.get("bribe_amount", 0)
            actions.append({"agent": agent_name, "action": action, "target": target, "bribe_amount": bribe_amt})

        # Resolve defenses first (mark who is defending)
        defenders: set[str] = set()
        for act in actions:
            if act["action"] == "defend":
                defenders.add(act["agent"])
                msg = f"{act['agent']} se met en position défensive."
                round_log.append({"type": "system", "round": round_num, "agent": act["agent"], "text": msg})
                round_actions.append(msg)
                yield {"type": "event", "message": msg, "agent": act["agent"], "game": None}

        # Resolve assassinations
        for act in actions:
            if act["action"] == "assassinate" and act["target"]:
                attacker = next((a for a in self.state["agents"] if a["name"] == act["agent"]), None)
                target = next((a for a in self.state["agents"] if a["name"] == act["target"]), None)

                if not attacker or not target or not attacker["alive"] or not target["alive"]:
                    continue

                if attacker["inventory"]["paxal"] <= 0:
                    msg = f"{act['agent']} tente d'assassiner {act['target']} mais n'a pas d'arme !"
                    round_log.append({"type": "system", "round": round_num, "agent": act["agent"], "text": msg})
                    round_actions.append(msg)
                    yield {"type": "event", "message": msg, "agent": act["agent"], "game": None}
                    continue

                attacker["inventory"]["paxal"] -= 1

                if act["target"] in defenders:
                    msg = f"{act['agent']} tente d'assassiner {act['target']} mais sa cible se défend !"
                    round_log.append({"type": "system", "round": round_num, "agent": act["agent"], "text": msg})
                    round_actions.append(msg)
                    yield {"type": "event", "message": msg, "agent": act["agent"], "game": None}
                elif target["inventory"]["garab"] > 0:
                    target["inventory"]["garab"] -= 1
                    msg = f"{act['agent']} tente d'assassiner {act['target']} — mais l'antidote le sauve ! (garab consommé)"
                    round_log.append({"type": "system", "round": round_num, "agent": act["agent"], "text": msg})
                    round_actions.append(msg)
                    yield {"type": "event", "message": msg, "agent": act["agent"], "game": None}
                else:
                    target["alive"] = False
                    target["health"] = 0
                    msg = f"{act['agent']} a assassiné {act['target']} !"
                    round_log.append({"type": "elimination", "round": round_num, "agent": act["agent"], "text": msg})
                    round_actions.append(msg)
                    yield {"type": "elimination", "message": msg, "agent": act["target"], "game": None}

        # Resolve steals
        for act in actions:
            if act["action"] == "steal" and act["target"]:
                thief = next((a for a in self.state["agents"] if a["name"] == act["agent"]), None)
                victim = next((a for a in self.state["agents"] if a["name"] == act["target"]), None)

                if not thief or not victim or not thief["alive"] or not victim["alive"]:
                    continue

                if thief["inventory"]["paxal"] <= 0:
                    msg = f"{act['agent']} tente de voler {act['target']} mais n'a pas d'arme pour intimider !"
                    round_log.append({"type": "system", "round": round_num, "agent": act["agent"], "text": msg})
                    round_actions.append(msg)
                    yield {"type": "event", "message": msg, "agent": act["agent"], "game": None}
                    continue

                stolen = min(BOAT_STEAL_AMOUNT, victim["inventory"]["xaalis"])
                victim["inventory"]["xaalis"] -= stolen
                thief["inventory"]["xaalis"] += stolen
                msg = f"{act['agent']} vole {stolen} xaalis à {act['target']} !"
                round_log.append({"type": "trade", "round": round_num, "agent": act["agent"], "text": msg})
                round_actions.append(msg)
                yield {"type": "trade", "message": msg, "agent": act["agent"], "game": None}

        # Resolve bribes
        for act in actions:
            if act["action"] == "bribe" and act["target"]:
                briber = next((a for a in self.state["agents"] if a["name"] == act["agent"]), None)
                target = next((a for a in self.state["agents"] if a["name"] == act["target"]), None)

                if not briber or not target or not briber["alive"] or not target["alive"]:
                    continue

                amount = min(act.get("bribe_amount", 0) or 0, briber["inventory"]["xaalis"])
                if amount > 0:
                    briber["inventory"]["xaalis"] -= amount
                    target["inventory"]["xaalis"] += amount
                    msg = f"{act['agent']} offre {amount} xaalis à {act['target']} (corruption)."
                    round_log.append({"type": "trade", "round": round_num, "agent": act["agent"], "text": msg})
                    round_actions.append(msg)
                    yield {"type": "trade", "message": msg, "agent": act["agent"], "game": None}

        # Phase 4: Votes
        yield {"type": "phase", "message": "Phase de vote — qui prend le bateau ?", "agent": None, "game": None}

        alive_agents = [a for a in self.state["agents"] if a["alive"]]
        vote_counts: dict[str, int] = {}
        votes_detail: list[str] = []

        for agent_name, decision in agent_decisions.items():
            agent_obj = next((a for a in self.state["agents"] if a["name"] == agent_name), None)
            if not agent_obj or not agent_obj["alive"]:
                continue

            vote_for = decision.get("vote_for_boat", agent_name)
            # Validate vote target exists and is alive
            valid_target = next((a for a in alive_agents if a["name"] == vote_for), None)
            if not valid_target:
                vote_for = agent_name  # Default to self

            vote_counts[vote_for] = vote_counts.get(vote_for, 0) + 1
            votes_detail.append(f"{agent_name} -> {vote_for}")

            msg = f"{agent_name} vote pour {vote_for}."
            round_log.append({"type": "vote", "round": round_num, "agent": agent_name, "text": msg})
            yield {"type": "vote", "message": msg, "agent": agent_name, "game": None}

        # Store vote history
        self.state.setdefault("vote_history", []).append(
            f"Tour {round_num}: " + ", ".join(votes_detail)
        )
        self.state.setdefault("action_history", []).extend(round_actions)

        # Check for majority
        majority_needed = len(alive_agents) // 2 + 1
        winner = None
        for name, count in vote_counts.items():
            if count >= majority_needed:
                winner = name
                break

        # Phase 5: Check win conditions
        yield {"type": "phase", "message": "Vérification du résultat...", "agent": None, "game": None}

        # Check if only one alive
        alive_agents = [a for a in self.state["agents"] if a["alive"]]

        if len(alive_agents) == 1:
            winner = alive_agents[0]["name"]
            msg = f"{winner} est le dernier survivant et prend le bateau !"
            round_log.append({"type": "system", "round": round_num, "agent": winner, "text": msg})
            yield {"type": "elimination", "message": msg, "agent": winner, "game": None}
        elif len(alive_agents) == 0:
            msg = "Tous les agents sont morts. Personne ne prend le bateau."
            round_log.append({"type": "system", "round": round_num, "agent": None, "text": msg})
            yield {"type": "elimination", "message": msg, "agent": None, "game": None}
        elif winner:
            msg = f"Majorité atteinte ! {winner} remporte le bateau avec {vote_counts[winner]} votes !"
            round_log.append({"type": "system", "round": round_num, "agent": winner, "text": msg})
            yield {"type": "event", "message": msg, "agent": winner, "game": None}
        elif round_num >= self.state["max_rounds"]:
            # Final round: most votes wins, tie = richest
            if vote_counts:
                max_votes = max(vote_counts.values())
                candidates = [name for name, count in vote_counts.items() if count == max_votes]
                if len(candidates) == 1:
                    winner = candidates[0]
                else:
                    # Tiebreaker: most xaalis
                    winner = max(candidates, key=lambda n: next(
                        (a["inventory"]["xaalis"] for a in self.state["agents"] if a["name"] == n), 0
                    ))
                msg = (f"Temps écoulé ! {winner} remporte le bateau ! "
                       f"(votes: {vote_counts.get(winner, 0)}, "
                       f"xaalis: {next((a['inventory']['xaalis'] for a in self.state['agents'] if a['name'] == winner), 0)})")
                round_log.append({"type": "system", "round": round_num, "agent": winner, "text": msg})
                yield {"type": "event", "message": msg, "agent": winner, "game": None}

        # Show vote summary
        vote_summary = " | ".join(f"{name}: {count}" for name, count in sorted(vote_counts.items(), key=lambda x: -x[1]))
        summary_msg = f"Résultat du vote — {vote_summary} (majorité requise: {majority_needed})"
        round_log.append({"type": "system", "round": round_num, "agent": None, "text": summary_msg})
        yield {"type": "event", "message": summary_msg, "agent": None, "game": None}

        # Set winner and status
        if winner:
            self.state["winner"] = winner
            self.state["status"] = "finished"
        elif round_num >= self.state["max_rounds"]:
            self.state["status"] = "finished"

        # Update activity log
        self.state["activity_log"].extend(round_log)

        # Set current event for display
        self.state["current_event"] = {
            "name": "Le Bateau",
            "description": f"Tour {round_num}/{self.state['max_rounds']} — Qui prendra le bateau ?",
            "type": "boat",
        }

        # Save snapshot
        await self._save_round_snapshot(db_session, round_num, round_log)

        yield {"type": "complete", "message": None, "agent": None, "game": self.state}
