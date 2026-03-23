import type { EventInfo, LiveUpdate } from "../types/game";
import { EVENT_ICONS } from "../constants/config";

interface EventBannerProps {
  currentRound: number;
  maxRounds: number;
  event: EventInfo | null;
  liveStatus?: LiveUpdate | null;
}

export default function EventBanner({ currentRound, maxRounds, event, liveStatus }: EventBannerProps) {
  const eventIcon = event ? EVENT_ICONS[event.type] || "\u26A1" : "";

  return (
    <div className={`event-banner ${event ? "has-event" : ""}`}>
      <div className="event-banner-content">
        <span className="round-info">
          Tour {currentRound} / {maxRounds}
        </span>
        {event && (
          <>
            <span className="event-separator">&mdash;</span>
            <span className="event-icon">{eventIcon}</span>
            <span className="event-name">{event.name}</span>
            <span className="event-description">({event.description})</span>
          </>
        )}
      </div>
      {liveStatus && liveStatus.message && (
        <div className="live-status">
          <span className="pulse-dot" />
          {liveStatus.message}
        </div>
      )}
    </div>
  );
}
