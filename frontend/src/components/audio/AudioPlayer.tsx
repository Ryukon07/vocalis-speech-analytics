import {
  useEffect,
  useRef,
  useState,
  forwardRef,
  useImperativeHandle,
} from "react";
import WaveSurfer from "wavesurfer.js";
import RegionsPlugin from "wavesurfer.js/dist/plugins/regions.esm.js";
import { Play, Pause, AudioLines } from "lucide-react";
import { Button, ErrorNotice } from "../ui";
import { formatTime } from "../../lib/validation";
export interface AudioHandle {
  seek: (time: number) => void;
}
export interface AudioInterval {
  id: string;
  start_seconds: number;
  end_seconds: number;
  severity?: number;
}
const AudioPlayer = forwardRef<
  AudioHandle,
  {
    url: string;
    title?: string;
    reference?: boolean;
    intervals?: AudioInterval[];
    selected?: string;
    onTime?: (time: number) => void;
    onSelect?: (id: string) => void;
    editable?: boolean;
    onRegionChange?: (id: string, start: number, end: number) => void;
  }
>(function AudioPlayer(
  {
    url,
    title = "Participant recording",
    reference,
    intervals = [],
    selected,
    onTime,
    onSelect,
    editable,
    onRegionChange,
  },
  ref,
) {
  const container = useRef<HTMLDivElement>(null);
  const wave = useRef<WaveSurfer | null>(null);
  const pendingSeek = useRef<number | null>(null);
  const regions = useRef<ReturnType<typeof RegionsPlugin.create> | null>(null);
  const [ready, setReady] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<Error | null>(null);
  const [speed, setSpeed] = useState(1);
  const callbacks = useRef({ onTime, onSelect, onRegionChange });
  callbacks.current = { onTime, onSelect, onRegionChange };
  useImperativeHandle(
    ref,
    () => ({
      seek: (time) => {
        if (wave.current && wave.current.getDuration() > 0)
          wave.current.setTime(time);
        else pendingSeek.current = time;
        callbacks.current.onTime?.(time);
      },
    }),
    [],
  );
  useEffect(() => {
    if (!container.current) return;
    setReady(false);
    setError(null);
    setPlaying(false);
    setCurrent(0);
    setSpeed(1);
    const plugin = RegionsPlugin.create();
    regions.current = plugin;
    const ws = WaveSurfer.create({
      container: container.current,
      url,
      height: 92,
      waveColor: reference ? "#458c8a" : "#5c5589",
      progressColor: reference ? "#7dd4c5" : "#a89aef",
      cursorColor: "#e0d8ff",
      barWidth: 2,
      barGap: 2,
      barRadius: 2,
      plugins: [plugin],
      normalize: true,
    });
    wave.current = ws;
    ws.on("ready", () => {
      setReady(true);
      setDuration(ws.getDuration());
      if (pendingSeek.current !== null) {
        ws.setTime(pendingSeek.current);
        pendingSeek.current = null;
      }
    });
    ws.on("timeupdate", (time) => {
      setCurrent(time);
      callbacks.current.onTime?.(time);
    });
    ws.on("play", () => setPlaying(true));
    ws.on("pause", () => setPlaying(false));
    ws.on("error", (e) => setError(e));
    plugin.on("region-clicked", (region, event) => {
      event.stopPropagation();
      ws.setTime(region.start);
      callbacks.current.onSelect?.(region.id);
    });
    plugin.on("region-updated", (region) =>
      callbacks.current.onRegionChange?.(region.id, region.start, region.end),
    );
    return () => {
      ws.destroy();
      wave.current = null;
      regions.current = null;
    };
  }, [url, reference]);
  useEffect(() => {
    if (!ready || !regions.current) return;
    regions.current.clearRegions();
    intervals.forEach((f, i) =>
      regions.current?.addRegion({
        id: f.id,
        start: f.start_seconds,
        end: f.end_seconds,
        drag: editable || false,
        resize: editable || false,
        color:
          f.id === selected
            ? "rgba(177,153,245,.36)"
            : `rgba(${i % 2 ? "226,161,93" : "227,105,120"},.16)`,
        content: `${editable ? "Label" : "Flaw"} ${i + 1}`,
      }),
    );
  }, [ready, intervals, selected, editable]);
  return (
    <div className="audio-player">
      <div className="row between">
        <span className="row">
          <AudioLines size={17} />
          <strong>{title}</strong>
        </span>
        <span className="tiny muted">
          {reference ? "REFERENCE" : "PARTICIPANT"}
        </span>
      </div>
      <div ref={container} className="wave-container" />
      <ErrorNotice error={error} />
      <div className="row between audio-controls">
        <div className="row">
          <Button
            variant="secondary"
            disabled={!ready}
            onClick={() => {
              void wave.current?.playPause().catch(setError);
            }}
            aria-label={playing ? "Pause audio" : "Play audio"}
          >
            {playing ? <Pause size={16} /> : <Play size={16} />}
          </Button>
          <span className="mono tiny">
            {formatTime(current)} / {formatTime(duration)}
          </span>
        </div>
        <label className="row tiny">
          Speed
          <select
            value={speed}
            onChange={(e) => {
              const value = Number(e.target.value);
              setSpeed(value);
              wave.current?.setPlaybackRate(value);
            }}
          >
            {[0.75, 1, 1.25, 1.5, 2].map((s) => (
              <option key={s} value={s}>
                {s}×
              </option>
            ))}
          </select>
        </label>
      </div>
      {!ready && !error && (
        <p className="tiny muted" role="status">
          Loading waveform…
        </p>
      )}
    </div>
  );
});
export default AudioPlayer;
