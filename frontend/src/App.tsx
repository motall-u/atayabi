import { useState, useEffect, useCallback, useRef } from "react";
import type { GameResponse, LiveUpdate, ReplayResponse } from "./types/game";
import { createGame, nextRound, getReplay, streamNextRound } from "./api/client";
import StartScreen from "./components/StartScreen";
import EventBanner from "./components/EventBanner";
import GameCanvas from "./components/GameCanvas";
import AgentCard from "./components/AgentCard";
import ActivityLog from "./components/ActivityLog";
import RelationshipMap from "./components/RelationshipMap";
import GameControls from "./components/GameControls";
import GameOverScreen from "./components/GameOverScreen";
import ReplayControls from "./components/ReplayControls";
import "./App.css";

type Screen = "start" | "game" | "gameover" | "replay";

export default function App() {
  const [gameState, setGameState] = useState<GameResponse | null>(null);
  const [screen, setScreen] = useState<Screen>("start");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoPlay, setAutoPlay] = useState(false);
  const [autoPlaySpeed, setAutoPlaySpeed] = useState(5000);
  const [replayData, setReplayData] = useState<ReplayResponse | null>(null);
  const [replayRound, setReplayRound] = useState(0);
  const [replayPlaying, setReplayPlaying] = useState(false);
  const [replaySpeed, setReplaySpeed] = useState(3000);
  const [liveStatus, setLiveStatus] = useState<LiveUpdate | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const autoPlayRef = useRef(autoPlay);
  const autoPlaySpeedRef = useRef(autoPlaySpeed);
  const gameStateRef = useRef(gameState);
  const loadingRef = useRef(loading);
  const isProcessingRef = useRef(isProcessing);

  useEffect(() => {
    autoPlayRef.current = autoPlay;
  }, [autoPlay]);
  useEffect(() => {
    autoPlaySpeedRef.current = autoPlaySpeed;
  }, [autoPlaySpeed]);
  useEffect(() => {
    gameStateRef.current = gameState;
  }, [gameState]);
  useEffect(() => {
    loadingRef.current = loading;
  }, [loading]);
  useEffect(() => {
    isProcessingRef.current = isProcessing;
  }, [isProcessing]);

  const handleNextRound = useCallback(async (gameId: number) => {
    if (isProcessingRef.current) return;
    setIsProcessing(true);
    setLoading(true);
    setError(null);
    setLiveStatus(null);

    streamNextRound(
      gameId,
      (update) => {
        setLiveStatus(update);
      },
      (game) => {
        setGameState(game);
        setLiveStatus(null);
        setIsProcessing(false);
        setLoading(false);
        if (game.status === "finished") setScreen("gameover");
      },
      (error) => {
        // Fallback to non-streaming endpoint
        setLiveStatus(null);
        nextRound(gameId)
          .then((updated) => {
            setGameState(updated);
            if (updated.status === "finished") setScreen("gameover");
          })
          .catch((err) => {
            setError(`Erreur: ${(err as Error).message}`);
            setAutoPlay(false);
          })
          .finally(() => {
            setIsProcessing(false);
            setLoading(false);
          });
        // Use error variable to suppress lint warning
        console.warn("SSE stream failed, using fallback:", error);
      }
    );
  }, []);

  // Auto-play interval
  useEffect(() => {
    if (!autoPlay || !gameState || gameState.status === "finished") return;

    const interval = setInterval(async () => {
      if (loadingRef.current || isProcessingRef.current) return;
      const g = gameStateRef.current;
      if (!g || g.status === "finished") {
        setAutoPlay(false);
        return;
      }
      await handleNextRound(g.id);
    }, autoPlaySpeed);

    return () => clearInterval(interval);
  }, [autoPlay, autoPlaySpeed, gameState?.id, gameState?.status, handleNextRound]);

  // Replay auto-play
  useEffect(() => {
    if (!replayPlaying || !replayData) return;

    const interval = setInterval(() => {
      setReplayRound((prev) => {
        if (prev >= replayData.total_rounds - 1) {
          setReplayPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, replaySpeed);

    return () => clearInterval(interval);
  }, [replayPlaying, replayData, replaySpeed]);

  // Detect game finished
  useEffect(() => {
    if (gameState?.status === "finished" && screen === "game") {
      setAutoPlay(false);
      const timeout = setTimeout(() => {
        setScreen("gameover");
      }, 1500);
      return () => clearTimeout(timeout);
    }
  }, [gameState?.status, screen]);

  async function handleStartGame(agentCount: number, gameMode: string) {
    setLoading(true);
    setError(null);
    try {
      const game = await createGame(agentCount, gameMode);
      setGameState(game);
      setScreen("game");
      setAutoPlay(false);
    } catch (err) {
      setError(`Impossible de créer la partie: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleViewReplay(gameId: number) {
    setLoading(true);
    setError(null);
    try {
      const replay = await getReplay(gameId);
      setReplayData(replay);
      setReplayRound(0);
      setReplayPlaying(false);
      setScreen("replay");
    } catch (err) {
      setError(`Impossible de charger le replay: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleViewReplayFromGameover() {
    if (!gameState) return;
    await handleViewReplay(gameState.id);
  }

  function handleNewGame() {
    setGameState(null);
    setAutoPlay(false);
    setReplayData(null);
    setScreen("start");
    setError(null);
    setLiveStatus(null);
    setIsProcessing(false);
  }

  // Build display state for replay mode
  const displayGame: GameResponse | null = (() => {
    if (screen === "replay" && replayData && replayData.rounds.length > 0) {
      const round = replayData.rounds[replayRound];
      if (!round) return null;
      return {
        id: replayData.game_id,
        status:
          replayRound >= replayData.total_rounds - 1 ? "finished" : "in_progress",
        current_round: round.round_number,
        max_rounds: replayData.total_rounds,
        winner: null,
        created_at: "",
        current_event: round.event,
        agents: round.agents,
        activity_log: round.log_entries,
        game_mode: gameState?.game_mode ?? "survival",
      } as GameResponse;
    }
    return gameState;
  })();

  // Start screen
  if (screen === "start") {
    return (
      <div className="app">
        {error && (
          <div className="global-error">
            <span>{error}</span>
            <button onClick={() => setError(null)}>&times;</button>
          </div>
        )}
        <StartScreen
          onStartGame={handleStartGame}
          onViewReplay={handleViewReplay}
          loading={loading}
        />
      </div>
    );
  }

  // Game over screen
  if (screen === "gameover" && gameState) {
    return (
      <div className="app">
        {error && (
          <div className="global-error">
            <span>{error}</span>
            <button onClick={() => setError(null)}>&times;</button>
          </div>
        )}
        <GameOverScreen
          game={gameState}
          onViewReplay={handleViewReplayFromGameover}
          onNewGame={handleNewGame}
          gameMode={gameState.game_mode}
        />
      </div>
    );
  }

  // Game or replay screen
  if ((screen === "game" || screen === "replay") && displayGame) {
    return (
      <div className="app">
        {error && (
          <div className="global-error">
            <span>{error}</span>
            <button onClick={() => setError(null)}>&times;</button>
          </div>
        )}
        <div className="game-layout">
          <div className="layout-banner">
            <EventBanner
              currentRound={displayGame.current_round}
              maxRounds={displayGame.max_rounds}
              event={displayGame.current_event}
              liveStatus={liveStatus}
            />
          </div>

          <div className="layout-canvas">
            <GameCanvas agents={displayGame.agents} liveStatus={liveStatus} gameMode={displayGame.game_mode} />
          </div>

          <div className="layout-side">
            <div className="side-scroll">
              <div className="agent-cards">
                {displayGame.agents.map((agent) => (
                  <AgentCard key={agent.name} agent={agent} liveStatus={liveStatus} gameMode={displayGame.game_mode} />
                ))}
              </div>
              <RelationshipMap
                agents={displayGame.agents}
                log={displayGame.activity_log}
              />
            </div>
          </div>

          <div className="layout-log">
            <ActivityLog entries={displayGame.activity_log} liveStatus={liveStatus} />
          </div>

          <div className="layout-controls">
            {screen === "game" ? (
              <GameControls
                onNextRound={() => gameState && handleNextRound(gameState.id)}
                onNewGame={handleNewGame}
                autoPlay={autoPlay}
                onToggleAutoPlay={() => setAutoPlay((p) => !p)}
                autoPlaySpeed={autoPlaySpeed}
                onSpeedChange={setAutoPlaySpeed}
                loading={loading}
                gameFinished={displayGame.status === "finished"}
                isProcessing={isProcessing}
              />
            ) : (
              <ReplayControls
                currentRound={replayRound}
                totalRounds={replayData?.total_rounds || 0}
                onPrev={() => setReplayRound((p) => Math.max(0, p - 1))}
                onNext={() =>
                  setReplayRound((p) =>
                    Math.min((replayData?.total_rounds || 1) - 1, p + 1)
                  )
                }
                playing={replayPlaying}
                onTogglePlay={() => setReplayPlaying((p) => !p)}
                speed={replaySpeed}
                onSpeedChange={setReplaySpeed}
                onBackToMenu={handleNewGame}
              />
            )}
          </div>
        </div>
      </div>
    );
  }

  // Fallback loading
  return (
    <div className="app">
      <div className="loading-fullscreen">
        <div className="spinner"></div>
        <p>Chargement...</p>
      </div>
    </div>
  );
}
