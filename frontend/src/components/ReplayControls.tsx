interface ReplayControlsProps {
  currentRound: number;
  totalRounds: number;
  onPrev: () => void;
  onNext: () => void;
  playing: boolean;
  onTogglePlay: () => void;
  speed: number;
  onSpeedChange: (speed: number) => void;
  onBackToMenu: () => void;
}

export default function ReplayControls({
  currentRound,
  totalRounds,
  onPrev,
  onNext,
  playing,
  onTogglePlay,
  speed,
  onSpeedChange,
  onBackToMenu,
}: ReplayControlsProps) {
  return (
    <div className="replay-controls">
      <div className="replay-nav">
        <button
          className="btn btn-small"
          onClick={onPrev}
          disabled={currentRound <= 0 || playing}
        >
          &laquo; Préc.
        </button>

        <span className="replay-round-display">
          Replay &mdash; Tour {currentRound + 1} / {totalRounds}
        </span>

        <button
          className="btn btn-small"
          onClick={onNext}
          disabled={currentRound >= totalRounds - 1 || playing}
        >
          Suiv. &raquo;
        </button>
      </div>

      <div className="replay-play-section">
        <button className="btn btn-primary btn-small" onClick={onTogglePlay}>
          {playing ? "\u23F8 Pause" : "\u25B6 Lecture"}
        </button>

        <div className="speed-control">
          <span className="speed-label">Vitesse</span>
          <input
            type="range"
            min={1000}
            max={8000}
            step={500}
            value={speed}
            onChange={(e) => onSpeedChange(Number(e.target.value))}
            className="speed-slider"
          />
          <span className="speed-value">{(speed / 1000).toFixed(1)}s</span>
        </div>
      </div>

      <button className="btn btn-secondary btn-small" onClick={onBackToMenu}>
        Retour au menu
      </button>
    </div>
  );
}
