import { useRef, useEffect } from "react";
import type { AgentState, LogEntry } from "../types/game";
import { AGENT_COLORS, DEFAULT_AGENT_COLOR } from "../constants/config";

interface RelationshipMapProps {
  agents: AgentState[];
  log: LogEntry[];
}

export default function RelationshipMap({ agents, log }: RelationshipMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = 280;
    const h = 200;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, w, h);

    // Background
    ctx.fillStyle = "rgba(22, 33, 62, 0.5)";
    ctx.beginPath();
    ctx.roundRect(0, 0, w, h, 8);
    ctx.fill();

    const liveAgents = agents.filter((a) => a.alive);
    const allAgents = agents;

    if (allAgents.length === 0) return;

    // Position agents in a circle
    const cx = w / 2;
    const cy = h / 2;
    const radius = Math.min(w, h) * 0.32;

    const positions: Record<string, { x: number; y: number }> = {};
    allAgents.forEach((agent, i) => {
      const angle = (i / allAgents.length) * Math.PI * 2 - Math.PI / 2;
      positions[agent.name] = {
        x: cx + Math.cos(angle) * radius,
        y: cy + Math.sin(angle) * radius,
      };
    });

    // Build rivalry set from vote log entries
    const rivalries = new Set<string>();
    log.forEach((entry) => {
      if (entry.type === "vote" && entry.agent) {
        // Try to extract target from vote text
        const voteMatch = entry.text.match(/voted to eliminate (\w+)/i)
          || entry.text.match(/votes? for (\w+)/i)
          || entry.text.match(/\b(\w+)\b.*eliminated/i);
        if (voteMatch) {
          const target = voteMatch[1];
          if (target !== entry.agent && positions[target]) {
            const key = [entry.agent, target].sort().join("-");
            rivalries.add(key);
          }
        }
      }
    });

    // Draw alliance lines (green solid)
    liveAgents.forEach((agent) => {
      agent.alliances.forEach((ally) => {
        if (positions[agent.name] && positions[ally]) {
          const from = positions[agent.name];
          const to = positions[ally];
          ctx.beginPath();
          ctx.moveTo(from.x, from.y);
          ctx.lineTo(to.x, to.y);
          ctx.strokeStyle = "rgba(76, 175, 80, 0.6)";
          ctx.lineWidth = 2;
          ctx.stroke();
        }
      });
    });

    // Draw rivalry lines (red dashed)
    rivalries.forEach((key) => {
      const [a, b] = key.split("-");
      if (positions[a] && positions[b]) {
        const from = positions[a];
        const to = positions[b];
        ctx.beginPath();
        ctx.setLineDash([4, 4]);
        ctx.moveTo(from.x, from.y);
        ctx.lineTo(to.x, to.y);
        ctx.strokeStyle = "rgba(244, 67, 54, 0.5)";
        ctx.lineWidth = 1.5;
        ctx.stroke();
        ctx.setLineDash([]);
      }
    });

    // Draw agent nodes
    allAgents.forEach((agent) => {
      const pos = positions[agent.name];
      if (!pos) return;
      const color = AGENT_COLORS[agent.name] || DEFAULT_AGENT_COLOR;

      ctx.save();
      if (!agent.alive) ctx.globalAlpha = 0.3;

      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 12, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = "rgba(255,255,255,0.4)";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Name
      ctx.fillStyle = agent.alive ? "#F5DEB3" : "#888";
      ctx.font = "bold 9px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillText(agent.name, pos.x, pos.y + 15);

      ctx.restore();
    });
  }, [agents, log]);

  return (
    <div className="relationship-map">
      <h3 className="relationship-map-title">Carte des relations</h3>
      <canvas ref={canvasRef} />
      <div className="relationship-legend">
        <span className="legend-item">
          <span className="legend-line legend-alliance"></span> Alliance
        </span>
        <span className="legend-item">
          <span className="legend-line legend-rivalry"></span> Rivalité
        </span>
      </div>
    </div>
  );
}
