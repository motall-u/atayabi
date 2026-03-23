import { useState, useEffect } from "react";
import type { GameSummary, LLMStatus } from "../types/game";
import { checkLLMStatus, listGames } from "../api/client";

interface StartScreenProps {
  onStartGame: (agentCount: number, gameMode: string) => void;
  onViewReplay: (gameId: number) => void;
  loading: boolean;
}

export default function StartScreen({ onStartGame, onViewReplay, loading }: StartScreenProps) {
  const [agentCount, setAgentCount] = useState(3);
  const [gameMode, setGameMode] = useState<string>("survival");
  const [llmStatus, setLlmStatus] = useState<LLMStatus | null>(null);
  const [checkingStatus, setCheckingStatus] = useState(false);
  const [savedGames, setSavedGames] = useState<GameSummary[]>([]);
  const [loadingGames, setLoadingGames] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadSavedGames();
  }, []);

  async function loadSavedGames() {
    setLoadingGames(true);
    try {
      const games = await listGames();
      setSavedGames(games);
    } catch (err) {
      console.error("Impossible de charger les parties:", err);
    } finally {
      setLoadingGames(false);
    }
  }

  async function handleCheckStatus() {
    setCheckingStatus(true);
    setError(null);
    try {
      const status = await checkLLMStatus();
      setLlmStatus(status);
    } catch (err) {
      setError(`Erreur API: ${(err as Error).message}`);
      setLlmStatus(null);
    } finally {
      setCheckingStatus(false);
    }
  }

  function handleStart() {
    setError(null);
    onStartGame(agentCount, gameMode);
  }

  function formatDate(dateStr: string) {
    try {
      return new Date(dateStr).toLocaleDateString("fr-FR", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  }

  function getStatusLabel(status: string): string {
    switch (status) {
      case "in_progress": return "En cours";
      case "finished": return "Terminée";
      case "waiting": return "En attente";
      default: return status;
    }
  }

  return (
    <div className="start-screen">
      <div className="start-screen-inner">
        <div className="start-header">
          <h1 className="game-title">Àttaya bi</h1>
          <p className="game-subtitle">Le Dernier Camp &mdash; Un jeu de survie avec des agents IA parlant Wolof</p>
          <div className="title-decoration"></div>
        </div>

        <div className="start-panels">
          <div className="start-panel main-panel">
            <h2>Nouvelle Partie</h2>

            <div className="agent-count-selector">
              <label>Nombre d&apos;agents</label>
              <div className="count-buttons">
                {[3, 4, 5].map((n) => (
                  <button
                    key={n}
                    className={`count-btn ${agentCount === n ? "active" : ""}`}
                    onClick={() => setAgentCount(n)}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>

            <div className="mode-selector">
              <h3>Mode de jeu</h3>
              <div className="mode-cards">
                <div
                  className={`mode-card ${gameMode === "survival" ? "active" : ""}`}
                  onClick={() => setGameMode("survival")}
                >
                  <span className="mode-icon">🏝️</span>
                  <h4>Survie</h4>
                  <p>Survivez aux catastrophes, récoltez, échangez. Le dernier debout gagne.</p>
                </div>
                <div
                  className={`mode-card ${gameMode === "boat" ? "active" : ""}`}
                  onClick={() => setGameMode("boat")}
                >
                  <span className="mode-icon">🚤</span>
                  <h4>Le Bateau</h4>
                  <p>Un seul bateau, une seule place. Corrompez, assassinez, votez. Tous les coups sont permis.</p>
                </div>
              </div>
            </div>

            <div className="api-status-section">
              <button
                className="btn btn-secondary"
                onClick={handleCheckStatus}
                disabled={checkingStatus}
              >
                {checkingStatus ? "Vérification..." : "Vérifier l'API"}
              </button>
              {llmStatus && (
                <div className={`status-indicator ${llmStatus.status}`}>
                  <span className="status-dot"></span>
                  <span>
                    {llmStatus.status === "online" ? "Connexion réussie" : "API hors ligne"}
                    {llmStatus.model && ` — ${llmStatus.model}`}
                  </span>
                </div>
              )}
            </div>

            {error && <div className="error-message">{error}</div>}

            <button
              className="btn btn-primary btn-large"
              onClick={handleStart}
              disabled={loading}
            >
              {loading ? (
                <span className="spinner-inline"></span>
              ) : (
                "Commencer"
              )}
            </button>

            <div className="rules-summary">
              <h3>Comment ça marche</h3>
              {gameMode === "boat" ? (
                <ul>
                  <li>Un seul bateau, une seule place — qui s'échappera ?</li>
                  <li>Chaque tour : discours en wolof, actions secrètes et vote</li>
                  <li>Actions possibles : corrompre (💰), assassiner (⚔️), voler, se défendre (🛡️)</li>
                  <li>Majorité des votes = victoire immédiate</li>
                  <li>Dernier survivant = victoire automatique</li>
                  <li>Après 10 tours sans majorité : le plus voté gagne (égalité = le plus riche)</li>
                </ul>
              ) : (
                <ul>
                  <li>3 à 5 agents IA négocient en Wolof pour survivre sur une île</li>
                  <li>Chaque tour : événements aléatoires, récolte, échanges et votes</li>
                  <li>Les agents forment des alliances, échangent des ressources et votent pour éliminer</li>
                  <li>Le dernier survivant (ou le dernier debout après 15 tours) gagne</li>
                  <li>Vous êtes spectateur — regardez le drame se dérouler !</li>
                  <li>💰 Xaalis (Argent) : une monnaie utilisée pour les échanges entre agents</li>
                </ul>
              )}
            </div>
          </div>

          <div className="start-panel saved-panel">
            <h2>Parties sauvegardées</h2>
            {loadingGames ? (
              <div className="loading-message">
                <span className="spinner-inline"></span> Chargement...
              </div>
            ) : savedGames.length === 0 ? (
              <p className="no-games">Aucune partie sauvegardée</p>
            ) : (
              <div className="saved-games-list">
                {savedGames.map((game) => (
                  <div key={game.id} className="saved-game-card">
                    <div className="saved-game-info">
                      <span className="saved-game-id">Partie #{game.id}</span>
                      <span className={`saved-game-status status-${game.status}`}>
                        {getStatusLabel(game.status)}
                      </span>
                    </div>
                    <div className="saved-game-details">
                      <span>{game.game_mode === "boat" ? "🚤" : "🏝️"} {game.game_mode === "boat" ? "Bateau" : "Survie"}</span>
                      <span>{game.agent_count} agents</span>
                      <span>Tour {game.current_round}/{game.max_rounds}</span>
                      <span>{formatDate(game.created_at)}</span>
                    </div>
                    {game.winner && (
                      <div className="saved-game-winner">
                        Gagnant : <strong>{game.winner}</strong>
                      </div>
                    )}
                    {game.status === "finished" && (
                      <button
                        className="btn btn-small"
                        onClick={() => onViewReplay(game.id)}
                      >
                        Voir le replay
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
