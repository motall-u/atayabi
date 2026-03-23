import type { GameResponse } from "../types/game";
import { AGENT_COLORS, DEFAULT_AGENT_COLOR, LOG_TYPE_ICONS, LOG_TYPE_COLORS } from "../constants/config";

interface GameOverScreenProps {
  game: GameResponse;
  onViewReplay: () => void;
  onNewGame: () => void;
  gameMode?: string;
}

export default function GameOverScreen({ game, onViewReplay, onNewGame, gameMode }: GameOverScreenProps) {
  const winner = game.agents.find((a) => a.name === game.winner);
  const winnerColor = game.winner
    ? AGENT_COLORS[game.winner] || DEFAULT_AGENT_COLOR
    : "#FFB300";

  const isBoatMode = gameMode === "boat";

  // Compute stats
  const totalRounds = game.current_round;
  const tradeCount = game.activity_log.filter((e) => e.type === "trade").length;
  const allianceCount = game.activity_log.filter((e) => e.type === "alliance").length;
  const eliminationCount = game.activity_log.filter(
    (e) => e.type === "elimination" || e.type === "death"
  ).length;
  const voteCount = game.activity_log.filter((e) => e.type === "vote").length;

  // Check if multiple winners (shared victory)
  const survivors = game.agents.filter((a) => a.alive);
  const isSharedWin = survivors.length > 1;

  return (
    <div className="gameover-screen">
      <div className="gameover-inner">
        <div className="gameover-header">
          <h1 className="gameover-title">
            {isBoatMode ? "Le Bateau est parti !" : "Partie Terminée"}
          </h1>
          <div className="title-decoration"></div>
        </div>

        {game.winner ? (
          <div className="winner-section">
            <div className="winner-circle" style={{ borderColor: winnerColor }}>
              <span className="winner-initial" style={{ color: winnerColor }}>
                {game.winner[0]}
              </span>
            </div>
            <h2 className="winner-name" style={{ color: winnerColor }}>
              {isBoatMode
                ? `${game.winner} s'échappe sur le bateau !`
                : isSharedWin
                  ? "Victoire partagée !"
                  : `${game.winner} survit !`}
            </h2>
            {winner && (
              <p className="winner-personality">
                {winner.personality} &mdash; {winner.personality_wolof}
              </p>
            )}
          </div>
        ) : (
          <div className="winner-section">
            <h2 className="winner-name" style={{ color: "#f44336" }}>
              {isBoatMode
                ? "Le bateau est resté sur la plage..."
                : "Personne n\u0027a survécu..."}
            </h2>
            <p className="winner-personality">
              {isBoatMode ? "Personne n\u0027a réussi à s\u0027échapper" : "L\u0027île a tout englouti"}
            </p>
          </div>
        )}

        <div className="gameover-stats">
          <div className="stat-card">
            <span className="stat-value">{totalRounds}</span>
            <span className="stat-label">Tours joués</span>
          </div>
          {isBoatMode ? (
            <>
              <div className="stat-card">
                <span className="stat-value">{eliminationCount}</span>
                <span className="stat-label">Assassinats</span>
              </div>
              <div className="stat-card">
                <span className="stat-value">{tradeCount}</span>
                <span className="stat-label">Corruptions</span>
              </div>
              <div className="stat-card">
                <span className="stat-value">{voteCount}</span>
                <span className="stat-label">Votes</span>
              </div>
            </>
          ) : (
            <>
              <div className="stat-card">
                <span className="stat-value">{tradeCount}</span>
                <span className="stat-label">Échanges réalisés</span>
              </div>
              <div className="stat-card">
                <span className="stat-value">{allianceCount}</span>
                <span className="stat-label">Alliances formées</span>
              </div>
              <div className="stat-card">
                <span className="stat-value">{eliminationCount}</span>
                <span className="stat-label">Éliminations</span>
              </div>
            </>
          )}
        </div>

        <div className="gameover-log">
          <h3>Journal complet</h3>
          <div className="gameover-log-entries">
            {game.activity_log.map((entry, idx) => (
              <div
                key={idx}
                className="log-entry"
                style={{ color: LOG_TYPE_COLORS[entry.type] || "#F5DEB3" }}
              >
                <span className="log-round">[T{entry.round}]</span>
                <span className="log-icon">{LOG_TYPE_ICONS[entry.type] || "\u2022"}</span>
                <span className="log-text">{entry.text}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="gameover-actions">
          <button className="btn btn-primary" onClick={onViewReplay}>
            Voir le Replay
          </button>
          <button className="btn btn-secondary" onClick={onNewGame}>
            Nouvelle Partie
          </button>
        </div>
      </div>
    </div>
  );
}
