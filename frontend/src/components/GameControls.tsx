interface GameControlsProps {
  onNextRound: () => void;
  onNewGame: () => void;
  autoPlay: boolean;
  onToggleAutoPlay: () => void;
  autoPlaySpeed: number;
  onSpeedChange: (speed: number) => void;
  loading: boolean;
  gameFinished: boolean;
  isProcessing?: boolean;
}

export default function GameControls({
  onNextRound,
  onNewGame,
  autoPlay,
  onToggleAutoPlay,
  autoPlaySpeed,
  onSpeedChange,
  loading,
  gameFinished,
  isProcessing,
}: GameControlsProps) {
  const busy = loading || (isProcessing ?? false);

  return (
    <div className="game-controls">
      <button
        className="btn btn-primary"
        onClick={onNextRound}
        disabled={busy || gameFinished || autoPlay}
      >
        {busy ? (
          <>
            <span className="spinner-inline"></span>
            {" En cours..."}
          </>
        ) : (
          "Tour Suivant"
        )}
      </button>

      <div className="auto-play-section">
        <label className="toggle-label">
          <span className="toggle-text">Lecture auto</span>
          <div className={`toggle-switch ${autoPlay ? "active" : ""}`} onClick={onToggleAutoPlay}>
            <div className="toggle-knob"></div>
          </div>
        </label>

        <div className="speed-control">
          <span className="speed-label">Vitesse</span>
          <input
            type="range"
            min={3000}
            max={15000}
            step={1000}
            value={autoPlaySpeed}
            onChange={(e) => onSpeedChange(Number(e.target.value))}
            className="speed-slider"
          />
          <span className="speed-value">{(autoPlaySpeed / 1000).toFixed(0)}s</span>
        </div>
      </div>

      <button className="btn btn-secondary" onClick={onNewGame}>
        Nouvelle Partie
      </button>
    </div>
  );
}
