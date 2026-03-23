export interface EventInfo {
  name: string;
  description: string;
  type: string;
}

export interface Inventory {
  ndox: number;
  lekk: number;
  garab: number;
  "mbëj": number;
  paxal: number;
  xaalis: number;
}

export interface LiveUpdate {
  type: "phase" | "event" | "scavenge" | "thinking" | "speaking" | "trade" | "vote" | "elimination" | "complete";
  message?: string;
  agent?: string;
  game?: GameResponse;
}

export interface AgentState {
  name: string;
  personality: string;
  personality_wolof: string;
  health: number;
  inventory: Inventory;
  alliances: string[];
  reputation: number;
  alive: boolean;
  thinking: string | null;
  public_message: string | null;
}

export interface LogEntry {
  type: "event" | "scavenge" | "message" | "trade" | "alliance" | "vote" | "elimination" | "death" | "system";
  round: number;
  agent: string | null;
  text: string;
}

export interface GameResponse {
  id: number;
  status: "waiting" | "in_progress" | "finished";
  current_round: number;
  max_rounds: number;
  winner: string | null;
  created_at: string;
  current_event: EventInfo | null;
  agents: AgentState[];
  activity_log: LogEntry[];
  game_mode: "survival" | "boat";
}

export interface GameSummary {
  id: number;
  status: string;
  agent_count: number;
  current_round: number;
  max_rounds: number;
  winner: string | null;
  created_at: string;
  game_mode: string;
}

export interface RoundSnapshot {
  round_number: number;
  event: EventInfo | null;
  agents: AgentState[];
  log_entries: LogEntry[];
}

export interface ReplayResponse {
  game_id: number;
  total_rounds: number;
  rounds: RoundSnapshot[];
}

export interface LLMStatus {
  status: "online" | "offline";
  model: string | null;
}
