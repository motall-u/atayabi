import { useState } from "react";
import type { AgentState, LiveUpdate } from "../types/game";
import { AGENT_COLORS, RESOURCE_ICONS, DEFAULT_AGENT_COLOR } from "../constants/config";

interface AgentCardProps {
  agent: AgentState;
  liveStatus?: LiveUpdate | null;
  gameMode?: string;
}

export default function AgentCard({ agent, liveStatus, gameMode }: AgentCardProps) {
  const [showThinking, setShowThinking] = useState(false);
  const color = AGENT_COLORS[agent.name] || DEFAULT_AGENT_COLOR;

  const isActiveAgent =
    liveStatus != null &&
    liveStatus.agent === agent.name &&
    (liveStatus.type === "thinking" || liveStatus.type === "speaking");

  function getHealthColor(health: number): string {
    if (health > 60) return "#4CAF50";
    if (health > 30) return "#FFB300";
    return "#f44336";
  }

  function getHealthBg(health: number): string {
    if (health > 60) return "rgba(76, 175, 80, 0.2)";
    if (health > 30) return "rgba(255, 179, 0, 0.2)";
    return "rgba(244, 67, 54, 0.2)";
  }

  const inventoryEntries: [string, number][] = gameMode === "boat"
    ? [
        ["xaalis", agent.inventory.xaalis ?? 0],
        ["paxal", agent.inventory.paxal],
        ["garab", agent.inventory.garab],
      ]
    : [
        ["ndox", agent.inventory.ndox],
        ["lekk", agent.inventory.lekk],
        ["garab", agent.inventory.garab],
        ["mbëj", agent.inventory["mbëj"]],
        ["paxal", agent.inventory.paxal],
        ["xaalis", agent.inventory.xaalis ?? 0],
      ];

  return (
    <div className={`agent-card ${!agent.alive ? "agent-dead" : ""} ${isActiveAgent ? "active-agent" : ""}`}>
      {!agent.alive && <div className="eliminated-overlay">ÉLIMINÉ</div>}

      <div className="agent-card-header">
        <span className="agent-color-dot" style={{ backgroundColor: color }}></span>
        <span className="agent-name">{agent.name}</span>
        <span className="agent-personality">{agent.personality_wolof}</span>
      </div>

      {isActiveAgent && (
        <div className="agent-thinking-indicator">
          {liveStatus!.type === "thinking" ? "💭 Réfléchit..." : "💬 Parle..."}
        </div>
      )}

      <div className="agent-health">
        <div className="health-bar-container" style={{ backgroundColor: getHealthBg(agent.health) }}>
          <div
            className="health-bar-fill"
            style={{
              width: `${Math.max(0, Math.min(100, agent.health))}%`,
              backgroundColor: getHealthColor(agent.health),
            }}
          ></div>
        </div>
        <span className="health-value">PV {agent.health}%</span>
      </div>

      <div className="agent-resources">
        {inventoryEntries.map(([key, val]) => (
          <div key={key} className="resource-item">
            <span className="resource-icon">{RESOURCE_ICONS[key]}</span>
            <span className="resource-count">{val}</span>
          </div>
        ))}
      </div>

      {agent.alliances.length > 0 && (
        <div className="agent-alliances">
          <span className="alliance-label">Alliances :</span>
          {agent.alliances.map((ally) => (
            <span
              key={ally}
              className="alliance-badge"
              style={{ borderColor: AGENT_COLORS[ally] || DEFAULT_AGENT_COLOR }}
            >
              {ally}
            </span>
          ))}
        </div>
      )}

      <div className="agent-reputation">
        <span className="reputation-label">Réputation</span>
        <div className="reputation-bar-container">
          <div
            className="reputation-bar-fill"
            style={{ width: `${Math.max(0, Math.min(100, agent.reputation))}%` }}
          ></div>
        </div>
        <span className="reputation-value">{agent.reputation}</span>
      </div>

      {agent.public_message && (
        <div className="agent-message">
          <span className="message-label">Dit :</span>
          <p className="message-text">&ldquo;{agent.public_message}&rdquo;</p>
        </div>
      )}

      {agent.thinking && (
        <div className="agent-thinking-section">
          <button
            className="thinking-toggle"
            onClick={() => setShowThinking(!showThinking)}
          >
            {showThinking ? "▼" : "▶"} Réflexion
          </button>
          {showThinking && (
            <p className="thinking-text">{agent.thinking}</p>
          )}
        </div>
      )}
    </div>
  );
}
