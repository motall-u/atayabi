import { useEffect, useRef } from "react";
import type { LogEntry, LiveUpdate } from "../types/game";
import { LOG_TYPE_ICONS, LOG_TYPE_COLORS } from "../constants/config";

interface ActivityLogProps {
  entries: LogEntry[];
  liveStatus?: LiveUpdate | null;
}

export default function ActivityLog({ entries, liveStatus }: ActivityLogProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [entries, liveStatus]);

  return (
    <div className="activity-log">
      <h3 className="activity-log-title">Journal d&apos;activité</h3>
      <div className="activity-log-entries" ref={containerRef}>
        {entries.length === 0 && !liveStatus ? (
          <p className="log-empty">Aucune activité pour le moment...</p>
        ) : (
          <>
            {entries.map((entry, idx) => (
              <div
                key={idx}
                className={`log-entry log-type-${entry.type}`}
                style={{ color: LOG_TYPE_COLORS[entry.type] || "#F5DEB3" }}
              >
                <span className="log-round">[T{entry.round}]</span>
                <span className="log-icon">{LOG_TYPE_ICONS[entry.type] || "\u2022"}</span>
                <span className="log-text">{entry.text}</span>
              </div>
            ))}
            {liveStatus && liveStatus.message && (
              <div className="log-entry log-type-live" style={{ color: "var(--yellow)" }}>
                <span className="log-round">
                  <span className="pulse-dot" />
                </span>
                <span className="log-icon">{"\u26A1"}</span>
                <span className="log-text">{liveStatus.message}</span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
