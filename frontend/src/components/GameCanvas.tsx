import { useRef, useEffect, useCallback } from "react";
import type { AgentState, LiveUpdate } from "../types/game";
import { AGENT_COLORS, DEFAULT_AGENT_COLOR } from "../constants/config";

interface GameCanvasProps {
  agents: AgentState[];
  liveStatus?: LiveUpdate | null;
  gameMode?: string;
}

interface AgentPosition {
  x: number;
  y: number;
  name: string;
  alive: boolean;
  color: string;
  message: string | null;
}

export default function GameCanvas({ agents, liveStatus, gameMode }: GameCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animFrameRef = useRef<number>(0);
  const timeRef = useRef<number>(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const liveStatusRef = useRef(liveStatus);
  const gameModeRef = useRef(gameMode);

  useEffect(() => {
    liveStatusRef.current = liveStatus;
  }, [liveStatus]);

  useEffect(() => {
    gameModeRef.current = gameMode;
  }, [gameMode]);

  const getAgentPositions = useCallback(
    (cx: number, cy: number, radius: number): AgentPosition[] => {
      return agents.map((agent, i) => {
        const angle = (i / agents.length) * Math.PI * 2 - Math.PI / 2;
        return {
          x: cx + Math.cos(angle) * radius,
          y: cy + Math.sin(angle) * radius,
          name: agent.name,
          alive: agent.alive,
          color: AGENT_COLORS[agent.name] || DEFAULT_AGENT_COLOR,
          message: agent.public_message,
        };
      });
    },
    [agents]
  );

  const drawCampfire = useCallback((ctx: CanvasRenderingContext2D, cx: number, cy: number, t: number) => {
    // fire pit base
    ctx.beginPath();
    ctx.ellipse(cx, cy + 8, 28, 12, 0, 0, Math.PI * 2);
    ctx.fillStyle = "#5D4037";
    ctx.fill();

    // flames
    const flames = [
      { dx: 0, dy: 0, r: 16, color: "rgba(255, 179, 0, 0.9)" },
      { dx: -6, dy: -4, r: 12, color: "rgba(255, 152, 0, 0.8)" },
      { dx: 6, dy: -4, r: 12, color: "rgba(255, 152, 0, 0.8)" },
      { dx: 0, dy: -10, r: 10, color: "rgba(255, 87, 34, 0.7)" },
      { dx: -3, dy: -16, r: 7, color: "rgba(255, 235, 59, 0.6)" },
      { dx: 3, dy: -14, r: 6, color: "rgba(255, 235, 59, 0.5)" },
    ];

    flames.forEach((f, i) => {
      const flicker = Math.sin(t * 3 + i * 1.5) * 3;
      const flickerY = Math.cos(t * 4 + i * 2) * 2;
      const sizeFlicker = Math.sin(t * 5 + i) * 2;
      ctx.beginPath();
      ctx.arc(cx + f.dx + flicker, cy + f.dy + flickerY - 4, Math.max(2, f.r + sizeFlicker), 0, Math.PI * 2);
      ctx.fillStyle = f.color;
      ctx.fill();
    });

    // glow
    const gradient = ctx.createRadialGradient(cx, cy - 6, 0, cx, cy - 6, 60);
    gradient.addColorStop(0, "rgba(255, 179, 0, 0.15)");
    gradient.addColorStop(1, "rgba(255, 179, 0, 0)");
    ctx.beginPath();
    ctx.arc(cx, cy - 6, 60, 0, Math.PI * 2);
    ctx.fillStyle = gradient;
    ctx.fill();

    // sparks
    for (let i = 0; i < 4; i++) {
      const sparkT = (t + i * 0.7) % 2;
      if (sparkT < 1.2) {
        const sparkX = cx + Math.sin(t * 2 + i * 3) * 10;
        const sparkY = cy - 20 - sparkT * 30;
        const sparkAlpha = 1 - sparkT / 1.2;
        ctx.beginPath();
        ctx.arc(sparkX, sparkY, 1.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 200, 50, ${sparkAlpha})`;
        ctx.fill();
      }
    }
  }, []);

  const drawAgent = useCallback(
    (ctx: CanvasRenderingContext2D, pos: AgentPosition, t: number) => {
      const agentRadius = 22;
      const currentLiveStatus = liveStatusRef.current;
      const isActive =
        currentLiveStatus != null &&
        currentLiveStatus.agent === pos.name &&
        (currentLiveStatus.type === "thinking" || currentLiveStatus.type === "speaking");

      ctx.save();

      if (!pos.alive) {
        ctx.globalAlpha = 0.35;
      }

      // Active agent glow
      if (isActive && pos.alive) {
        const glowRadius = agentRadius + 10 + Math.sin(t * 3) * 4;
        const glowGrad = ctx.createRadialGradient(pos.x, pos.y, agentRadius, pos.x, pos.y, glowRadius);
        glowGrad.addColorStop(0, "rgba(255, 179, 0, 0.4)");
        glowGrad.addColorStop(1, "rgba(255, 179, 0, 0)");
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, glowRadius, 0, Math.PI * 2);
        ctx.fillStyle = glowGrad;
        ctx.fill();
      }

      // shadow
      ctx.beginPath();
      ctx.ellipse(pos.x, pos.y + agentRadius + 6, agentRadius * 0.8, 5, 0, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(0,0,0,0.2)";
      ctx.fill();

      // body circle
      const breathe = Math.sin(t * 1.5) * 1.2;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, agentRadius + breathe, 0, Math.PI * 2);

      if (!pos.alive) {
        ctx.fillStyle = "#666";
      } else {
        const grad = ctx.createRadialGradient(
          pos.x - 5,
          pos.y - 5,
          0,
          pos.x,
          pos.y,
          agentRadius + breathe
        );
        grad.addColorStop(0, lightenColor(pos.color, 30));
        grad.addColorStop(1, pos.color);
        ctx.fillStyle = grad;
      }
      ctx.fill();

      // border
      if (isActive && pos.alive) {
        ctx.strokeStyle = "rgba(255, 179, 0, 0.8)";
        ctx.lineWidth = 3;
      } else {
        ctx.strokeStyle = pos.alive ? "rgba(255,255,255,0.5)" : "rgba(255,255,255,0.15)";
        ctx.lineWidth = 2;
      }
      ctx.stroke();

      // initial letter
      ctx.fillStyle = "#fff";
      ctx.font = "bold 18px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(pos.name[0], pos.x, pos.y);

      // name label
      ctx.font = "bold 12px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillStyle = pos.alive ? "#F5DEB3" : "#888";
      ctx.fillText(pos.name, pos.x, pos.y + agentRadius + 18);

      if (!pos.alive) {
        ctx.font = "bold 10px system-ui, sans-serif";
        ctx.fillStyle = "#f44336";
        ctx.fillText("ÉLIMINÉ", pos.x, pos.y + agentRadius + 32);
      }

      ctx.restore();

      // speech bubble (only for alive agents with messages)
      if (pos.alive && pos.message) {
        drawSpeechBubble(ctx, pos.x, pos.y - agentRadius - 16, pos.message);
      }
    },
    []
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const resizeCanvas = () => {
      const rect = container.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
    };

    resizeCanvas();
    const resizeObserver = new ResizeObserver(resizeCanvas);
    resizeObserver.observe(container);

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const animate = (timestamp: number) => {
      timeRef.current = timestamp / 1000;
      const t = timeRef.current;
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.width / dpr;
      const h = canvas.height / dpr;

      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, w, h);

      // Background gradient (sandy beach)
      const bgGrad = ctx.createLinearGradient(0, 0, 0, h);
      bgGrad.addColorStop(0, "#1a2a4a");
      bgGrad.addColorStop(0.4, "#1B6CA8");
      bgGrad.addColorStop(0.7, "#c2956b");
      bgGrad.addColorStop(1, "#e8c889");
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, w, h);

      // Stars (top area)
      for (let i = 0; i < 30; i++) {
        const sx = ((i * 137.5) % w);
        const sy = ((i * 97.3) % (h * 0.35));
        const twinkle = Math.sin(t * 2 + i) * 0.5 + 0.5;
        ctx.beginPath();
        ctx.arc(sx, sy, 1 + twinkle * 0.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 255, 255, ${0.3 + twinkle * 0.4})`;
        ctx.fill();
      }

      // Ocean waves
      ctx.save();
      for (let wave = 0; wave < 3; wave++) {
        ctx.beginPath();
        const waveY = h * 0.52 + wave * 8;
        ctx.moveTo(0, waveY);
        for (let x = 0; x <= w; x += 5) {
          const y = waveY + Math.sin(x * 0.02 + t * (1 + wave * 0.3) + wave) * 4;
          ctx.lineTo(x, y);
        }
        ctx.lineTo(w, h);
        ctx.lineTo(0, h);
        ctx.closePath();
        ctx.fillStyle = `rgba(27, 108, 168, ${0.15 - wave * 0.04})`;
        ctx.fill();
      }
      ctx.restore();

      // Palm tree silhouettes
      drawPalmTree(ctx, w * 0.08, h * 0.55, 0.6, t);
      drawPalmTree(ctx, w * 0.92, h * 0.52, 0.7, t);

      // Center and radius for agent circle
      const cx = w / 2;
      const cy = h * 0.55;
      const radius = Math.min(w, h) * 0.28;

      // Campfire
      drawCampfire(ctx, cx, cy, t);

      // Draw boat (only in boat mode)
      if (gameModeRef.current === "boat") {
        const boatX = w * 0.82;
        const boatY = h * 0.7;

        // Water under boat
        ctx.fillStyle = "rgba(27, 108, 168, 0.4)";
        ctx.beginPath();
        ctx.ellipse(boatX, boatY + 20, 45, 8, 0, 0, Math.PI * 2);
        ctx.fill();

        // Hull
        ctx.fillStyle = "#5D4037";
        ctx.beginPath();
        ctx.moveTo(boatX - 35, boatY);
        ctx.quadraticCurveTo(boatX, boatY + 25, boatX + 35, boatY);
        ctx.lineTo(boatX + 30, boatY - 5);
        ctx.lineTo(boatX - 30, boatY - 5);
        ctx.closePath();
        ctx.fill();

        // Mast
        ctx.strokeStyle = "#8D6E63";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(boatX, boatY - 5);
        ctx.lineTo(boatX, boatY - 45);
        ctx.stroke();

        // Sail
        ctx.fillStyle = "rgba(245, 222, 179, 0.9)";
        ctx.beginPath();
        ctx.moveTo(boatX, boatY - 42);
        ctx.lineTo(boatX + 25, boatY - 15);
        ctx.lineTo(boatX, boatY - 10);
        ctx.closePath();
        ctx.fill();

        // Label
        ctx.font = "bold 11px system-ui, sans-serif";
        ctx.fillStyle = "#FFB300";
        ctx.textAlign = "center";
        ctx.fillText("🚤 Le Bateau", boatX, boatY + 40);
      }

      // Agents
      const positions = getAgentPositions(cx, cy, radius);
      positions.forEach((pos) => drawAgent(ctx, pos, t));

      ctx.restore();
      animFrameRef.current = requestAnimationFrame(animate);
    };

    animFrameRef.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animFrameRef.current);
      resizeObserver.disconnect();
    };
  }, [agents, drawCampfire, drawAgent, getAgentPositions, gameMode]);

  return (
    <div className="game-canvas-container" ref={containerRef}>
      <canvas ref={canvasRef} />
    </div>
  );
}

function drawSpeechBubble(ctx: CanvasRenderingContext2D, x: number, y: number, text: string) {
  const maxWidth = 160;
  ctx.font = "11px system-ui, sans-serif";

  // Word wrap
  const words = text.split(" ");
  const lines: string[] = [];
  let currentLine = "";
  for (const word of words) {
    const testLine = currentLine ? `${currentLine} ${word}` : word;
    if (ctx.measureText(testLine).width > maxWidth && currentLine) {
      lines.push(currentLine);
      currentLine = word;
    } else {
      currentLine = testLine;
    }
    if (lines.length >= 3) {
      currentLine = currentLine + "...";
      break;
    }
  }
  if (currentLine) lines.push(currentLine);

  const lineHeight = 14;
  const padding = 8;
  const bubbleWidth = Math.min(
    maxWidth + padding * 2,
    Math.max(...lines.map((l) => ctx.measureText(l).width)) + padding * 2
  );
  const bubbleHeight = lines.length * lineHeight + padding * 2;
  const bx = x - bubbleWidth / 2;
  const by = y - bubbleHeight - 8;

  // Bubble background
  ctx.save();
  ctx.globalAlpha = 0.92;
  ctx.fillStyle = "rgba(30, 30, 50, 0.9)";
  ctx.strokeStyle = "rgba(245, 222, 179, 0.5)";
  ctx.lineWidth = 1;

  // Rounded rect
  const r = 6;
  ctx.beginPath();
  ctx.moveTo(bx + r, by);
  ctx.lineTo(bx + bubbleWidth - r, by);
  ctx.arcTo(bx + bubbleWidth, by, bx + bubbleWidth, by + r, r);
  ctx.lineTo(bx + bubbleWidth, by + bubbleHeight - r);
  ctx.arcTo(bx + bubbleWidth, by + bubbleHeight, bx + bubbleWidth - r, by + bubbleHeight, r);
  ctx.lineTo(bx + r, by + bubbleHeight);
  ctx.arcTo(bx, by + bubbleHeight, bx, by + bubbleHeight - r, r);
  ctx.lineTo(bx, by + r);
  ctx.arcTo(bx, by, bx + r, by, r);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  // Triangle pointer
  ctx.beginPath();
  ctx.moveTo(x - 5, by + bubbleHeight);
  ctx.lineTo(x, by + bubbleHeight + 8);
  ctx.lineTo(x + 5, by + bubbleHeight);
  ctx.closePath();
  ctx.fillStyle = "rgba(30, 30, 50, 0.9)";
  ctx.fill();

  // Text
  ctx.globalAlpha = 1;
  ctx.fillStyle = "#F5DEB3";
  ctx.font = "11px system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  lines.forEach((line, i) => {
    ctx.fillText(line, bx + padding, by + padding + i * lineHeight);
  });

  ctx.restore();
}

function drawPalmTree(ctx: CanvasRenderingContext2D, x: number, y: number, scale: number, t: number) {
  ctx.save();
  ctx.globalAlpha = 0.3;

  // Trunk
  ctx.strokeStyle = "#2a1a0a";
  ctx.lineWidth = 4 * scale;
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.quadraticCurveTo(x - 5 * scale, y - 40 * scale, x + 3 * scale, y - 80 * scale);
  ctx.stroke();

  // Fronds
  const sway = Math.sin(t * 0.5) * 3 * scale;
  for (let i = 0; i < 5; i++) {
    const angle = ((i / 5) * Math.PI * 2) - Math.PI / 2;
    const fx = x + 3 * scale + Math.cos(angle) * 30 * scale + sway;
    const fy = y - 80 * scale + Math.sin(angle) * 15 * scale;
    ctx.strokeStyle = "#1a3a1a";
    ctx.lineWidth = 2 * scale;
    ctx.beginPath();
    ctx.moveTo(x + 3 * scale, y - 80 * scale);
    ctx.quadraticCurveTo(
      (x + 3 * scale + fx) / 2 + sway,
      Math.min(fy, y - 80 * scale) - 10 * scale,
      fx,
      fy
    );
    ctx.stroke();
  }

  ctx.restore();
}

function lightenColor(hex: string, percent: number): string {
  const num = parseInt(hex.replace("#", ""), 16);
  const r = Math.min(255, (num >> 16) + percent);
  const g = Math.min(255, ((num >> 8) & 0xff) + percent);
  const b = Math.min(255, (num & 0xff) + percent);
  return `rgb(${r},${g},${b})`;
}
