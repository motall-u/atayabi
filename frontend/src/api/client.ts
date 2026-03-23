import type { GameResponse, GameSummary, LLMStatus, LiveUpdate, ReplayResponse } from "../types/game";

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  try {
    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
      },
      ...options,
    });

    if (!response.ok) {
      let errorMessage = `Request failed with status ${response.status}`;
      try {
        const errorBody = await response.json();
        if (errorBody.detail) {
          errorMessage = typeof errorBody.detail === "string"
            ? errorBody.detail
            : JSON.stringify(errorBody.detail);
        }
      } catch {
        // ignore JSON parse error on error responses
      }
      throw new ApiError(errorMessage, response.status);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new Error(`Network error: ${(error as Error).message}`);
  }
}

export async function checkLLMStatus(): Promise<LLMStatus> {
  return request<LLMStatus>("/api/llm/status");
}

export async function createGame(agentCount: number, gameMode: string = "survival"): Promise<GameResponse> {
  return request<GameResponse>("/api/games", {
    method: "POST",
    body: JSON.stringify({ agent_count: agentCount, game_mode: gameMode }),
  });
}

export async function listGames(): Promise<GameSummary[]> {
  return request<GameSummary[]>("/api/games");
}

export async function getGame(gameId: number): Promise<GameResponse> {
  return request<GameResponse>(`/api/games/${gameId}`);
}

export async function nextRound(gameId: number): Promise<GameResponse> {
  return request<GameResponse>(`/api/games/${gameId}/next-round`, {
    method: "POST",
  });
}

export async function deleteGame(gameId: number): Promise<void> {
  return request<void>(`/api/games/${gameId}`, {
    method: "DELETE",
  });
}

export async function getReplay(gameId: number): Promise<ReplayResponse> {
  return request<ReplayResponse>(`/api/games/${gameId}/replay`);
}

export async function streamNextRound(
  gameId: number,
  onUpdate: (update: LiveUpdate) => void,
  onComplete: (game: GameResponse) => void,
  onError: (error: string) => void
): Promise<void> {
  try {
    const response = await fetch(`/api/games/${gameId}/next-round-stream`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const update = JSON.parse(line.slice(6)) as LiveUpdate;
            if (update.type === "complete" && update.game) {
              onComplete(update.game);
            } else {
              onUpdate(update);
            }
          } catch {
            /* skip malformed */
          }
        }
      }
    }
  } catch (err) {
    onError(err instanceof Error ? err.message : "Erreur de connexion");
  }
}
