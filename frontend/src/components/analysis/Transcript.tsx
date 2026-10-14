import type { Word, Flaw } from "../../types";
import { formatTime } from "../../lib/validation";
export default function Transcript({
  words,
  text,
  current,
  selected,
  flaws,
  onSeek,
}: {
  words: Word[];
  text: string;
  current: number;
  selected?: string;
  flaws: Flaw[];
  onSeek: (time: number) => void;
}) {
  if (!words.length)
    return (
      <div className="transcript-text">
        <p className="tiny muted">Word alignment unavailable.</p>
        <p>{text || "No transcript supplied."}</p>
      </div>
    );
  const flaw = flaws.find((f) => f.id === selected);
  return (
    <div className="transcript-text">
      {words.map((w, i) => {
        const active = current >= w.start_seconds && current < w.end_seconds;
        const marked = flaws.some(
          (f) =>
            w.start_seconds < f.end_seconds && w.end_seconds > f.start_seconds,
        );
        const chosen =
          flaw &&
          w.start_seconds < flaw.end_seconds &&
          w.end_seconds > flaw.start_seconds;
        return (
          <button
            key={i}
            onClick={() => onSeek(w.start_seconds)}
            className={`word ${active ? "active" : ""} ${marked ? "marked" : ""} ${chosen ? "chosen" : ""}`}
            title={`${formatTime(w.start_seconds)}–${formatTime(w.end_seconds)}${w.confidence == null ? "" : ` · ${(w.confidence * 100).toFixed(0)}% confidence`}`}
          >
            {w.text}
          </button>
        );
      })}
    </div>
  );
}
