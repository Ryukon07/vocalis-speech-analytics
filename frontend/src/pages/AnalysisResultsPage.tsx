import { useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Download,
  Printer,
  ArrowLeft,
  Clock,
  Activity,
  ChevronRight,
  RotateCcw,
} from "lucide-react";
import { api, audioUrl, exportUrl } from "../api/client";
import { labels } from "../config/brand";
import { formatDate, formatTime } from "../lib/validation";
import { useAction } from "../hooks/useAction";
import {
  Button,
  Card,
  PageTitle,
  Loading,
  ErrorNotice,
  DemoBadge,
  Empty,
} from "../components/ui";
import AudioPlayer, { type AudioHandle } from "../components/audio/AudioPlayer";
import FeatureChart from "../components/charts/FeatureChart";
import Transcript from "../components/analysis/Transcript";
import StatusBadge from "../components/analysis/StatusBadge";
import SpokenFeedback from "../components/audio/SpokenFeedback";
export default function AnalysisResultsPage() {
  const { analysisId = "" } = useParams();
  const job = useQuery({
    queryKey: ["analysis", analysisId],
    queryFn: () => api.analysis(analysisId),
    refetchInterval: (q) =>
      ["queued", "processing"].includes(q.state.data?.status || "")
        ? 700
        : false,
  });
  const j = job.data;
  const result = useQuery({
    queryKey: ["result", analysisId],
    queryFn: () => api.result(analysisId),
    enabled: j?.status === "completed",
  });
  const reference = useQuery({
    queryKey: ["reference", j?.reference_id],
    queryFn: () => api.reference(j!.reference_id!),
    enabled: !!j?.reference_id,
  });
  const [current, setCurrent] = useState(0);
  const [selected, setSelected] = useState<string>();
  const [plot, setPlot] = useState<string>();
  const audio = useRef<AudioHandle>(null);
  const retry = useAction(
    () => api.retry(analysisId),
    "Analysis queued again.",
  );
  const cancel = useAction(() => api.cancel(analysisId), "Analysis cancelled.");
  const r = result.data;
  const seek = (time: number) => {
    audio.current?.seek(time);
    setCurrent(time);
  };
  const chosen = r?.flaws.find((f) => f.id === selected);
  const selectFlaw = (id: string) => {
    setSelected(id);
    const f = r?.flaws.find((f) => f.id === id);
    if (f) seek(f.start_seconds);
  };
  return (
    <>
      <Link className="back-link" to="/history">
        <ArrowLeft size={15} /> Analysis history
      </Link>
      <PageTitle
        eyebrow={`ANALYSIS ${analysisId.slice(0, 8).toUpperCase()}`}
        title={j?.participant_filename || "Analysis report"}
        description={
          j
            ? `${formatDate(j.created_at)} · ${j.provider_name} / ${j.provider_version}`
            : "Loading your analysis…"
        }
        action={
          r && (
            <div className="row wrap no-print">
              <SpokenFeedback text={chosen ? `${chosen.type.replaceAll("_", " ")}. ${chosen.explanation} ${chosen.recommendation}` : `Your delivery score is ${r.scores.overall == null ? "unavailable" : r.scores.overall.toFixed(1) + " out of 100"}. ${r.flaws.length} delivery regions were flagged. ${r.flaws.slice(0, 5).map((f) => `At ${f.start_seconds.toFixed(1)} seconds: ${f.recommendation}`).join(" ")}`} />
              <a
                className="btn btn-secondary"
                href={exportUrl(analysisId, "json")}
              >
                <Download size={16} /> JSON
              </a>
              <a
                className="btn btn-secondary"
                href={exportUrl(analysisId, "csv")}
              >
                CSV
              </a>
              <a className="btn btn-secondary" href={exportUrl(analysisId, "pdf")}><Download size={16} /> PDF</a>
              <Button variant="secondary" onClick={() => window.print()}>
                <Printer size={16} /> Print report
              </Button>
            </div>
          )
        }
      />
      <ErrorNotice error={job.error || result.error || reference.error} />
      {job.isPending && <Loading />}
      {j?.execution_mode === "mock" && (
        <div className="notice">
          <DemoBadge />
          <span>
            Scores, acoustic curves, evidence and word timestamps are
            illustrative. They were not inferred from this recording.
          </span>
        </div>
      )}
      {j && j.status !== "completed" && (
        <Card>
          <div className="section-title">
            <h2>{j.progress_stage}</h2>
            <StatusBadge status={j.status} />
          </div>
          <p className="muted mono tiny">Job ID: {j.id}</p>
          {["queued", "processing"].includes(j.status) ? (
            <>
              <progress value={j.progress_percent} max={100} />
              <p className="muted">
                {j.progress_percent.toFixed(0)}% · You can return to this job
                after a refresh.
              </p>
              <Button
                variant="secondary"
                disabled={cancel.isPending}
                onClick={() => cancel.mutate()}
              >
                {cancel.isPending ? "Cancelling…" : "Cancel analysis"}
              </Button>
            </>
          ) : (
            <>
              <p className="notice error">
                {j.error_summary || "This analysis was cancelled."}
              </p>
              {j.status === "failed" && (
                <Button
                  disabled={retry.isPending}
                  onClick={() => retry.mutate()}
                >
                  <RotateCcw size={16} /> Retry analysis
                </Button>
              )}
            </>
          )}
        </Card>
      )}
      {j?.status === "completed" && result.isPending && <Loading />}
      {r && j && (
        <>
          <div className="result-summary">
            <Card className="score-card">
              <p className="eyebrow">OVERALL DELIVERY</p>
              <div className="big-score">
                {r.scores.overall == null ? "—" : r.scores.overall.toFixed(1)}
                <span>/ 100</span>
              </div>
              <p className="muted tiny">
                {r.execution_mode === "mock"
                  ? "Illustrative rubric score"
                  : "Provider result · recorded rubric"}
              </p>
            </Card>
            <Card className="dimensions">
              <div className="section-title">
                <h2>Dimension scores</h2>
                <StatusBadge status={j.status} />
              </div>
              {Object.entries(labels).map(([c, label]) => {
                const score =
                  r.scores.dimensions[c as keyof typeof r.scores.dimensions];
                return (
                  <div className="dimension" key={c}>
                    <span>{label}</span>
                    <div className="score-bar">
                      <i style={{ width: `${score ?? 0}%` }} />
                    </div>
                    <strong>
                      {score == null ? "Unavailable" : score.toFixed(0)}
                    </strong>
                  </div>
                );
              })}
            </Card>
            <Card className="result-facts">
              <div>
                <Activity size={19} />
                <strong>{r.flaws.length}</strong>
                <span className="muted">Flaw intervals</span>
              </div>
              <div>
                <Clock size={19} />
                <strong>
                  {r.participant_duration_seconds == null
                    ? "Unavailable"
                    : formatTime(r.participant_duration_seconds)}
                </strong>
                <span className="muted">Participant duration</span>
              </div>
              <p className="tiny muted">
                Reference: {j.reference_title || "No reference"}
                <br />
                Rubric: {j.rubric_snapshot.name} · v{j.rubric_snapshot.version}
              </p>
            </Card>
          </div>
          {r.clarity && <Card>
            <div className="section-title"><h2>Clarity evidence</h2><span className="tiny muted">Local {r.clarity.model_name} · independent recognition</span></div>
            <p>Clarity measures additional word recognition errors compared with the reference. It is a model-based proxy; accents, microphone quality and background noise can affect it.</p>
            {r.clarity.available ? <p className="mono tiny">Reference word errors: {((r.clarity.reference.word_error_rate ?? 0) * 100).toFixed(1)}% · Participant: {((r.clarity.participant.word_error_rate ?? 0) * 100).toFixed(1)}% · Additional errors: {((r.clarity.excess_word_error_rate ?? 0) * 100).toFixed(1)} percentage points</p> : <p className="notice">{r.clarity.reason}</p>}
            <details><summary>Review independently recognized words</summary><p><strong>Reference:</strong> {r.clarity.reference_text || "No words recognized"}</p><p><strong>Participant:</strong> {r.clarity.participant_text || "No words recognized"}</p><p className="tiny muted">Score = 100 × (1 − additional error rate), bounded to 0–100. No deduction when the participant is recognized as reliably as the reference. Pacing and pausing use separate measurements.</p></details>
          </Card>}
          <Card>
            <div className="section-title">
              <h2>Listen in context</h2>
              <span className="tiny muted">Select a flaw or word to seek</span>
            </div>
            <AudioPlayer
              ref={audio}
              url={audioUrl(j.participant_recording_id)}
              intervals={r.flaws}
              selected={selected}
              onTime={setCurrent}
              onSelect={selectFlaw}
            />
            {reference.data && (
              <details className="reference-audio">
                <summary>Reference recording · {reference.data.title}</summary>
                <AudioPlayer
                  url={audioUrl(reference.data.recording_id)}
                  title="Reference recording"
                  reference
                />
              </details>
            )}
          </Card>
          <div className="result-details">
            <Card>
              <div className="section-title">
                <div>
                  <h2>Acoustic comparison</h2>
                  <p className="muted tiny">
                    {r.execution_mode === "mock"
                      ? "Fixed synthetic curves · not measurements"
                      : "Feature data supplied by your provider"}
                  </p>
                </div>
              </div>
              {Object.keys(r.feature_series).length ? (
                <>
                  <div className="plot-tabs">
                    {Object.keys(r.feature_series).map((name) => (
                      <button
                        key={name}
                        className={
                          (plot || Object.keys(r.feature_series)[0]) === name
                            ? "active"
                            : ""
                        }
                        onClick={() => setPlot(name)}
                      >
                        {name.replaceAll("_", " ")}
                      </button>
                    ))}
                  </div>
                  <FeatureChart
                    name={
                      plot && r.feature_series[plot]
                        ? plot
                        : Object.keys(r.feature_series)[0]
                    }
                    series={
                      r.feature_series[plot || ""] ||
                      Object.values(r.feature_series)[0]
                    }
                    flaws={r.flaws}
                    current={current}
                    onSeek={seek}
                  />
                  <p className="tiny muted">
                    Missing samples remain unavailable. Independent recording
                    clocks are not treated as aligned comparisons.
                  </p>
                </>
              ) : (
                <Empty
                  title="Acoustic features unavailable"
                  description="The provider did not return feature series for this report."
                />
              )}
            </Card>
            <Card>
              <div className="section-title">
                <h2>Detected intervals</h2>
                <span className="badge">{r.flaws.length}</span>
              </div>
              {r.flaws.length ? (
                r.flaws.map((f) => (
                  <button
                    className={`flaw-row ${selected === f.id ? "selected" : ""}`}
                    key={f.id}
                    onClick={() => selectFlaw(f.id)}
                  >
                    <span className={`severity sev-${f.severity}`}>
                      {f.severity}
                    </span>
                    <span>
                      <strong>{f.type.replaceAll("_", " ")}</strong>
                      <small>
                        {formatTime(f.start_seconds)}–
                        {formatTime(f.end_seconds)} ·{" "}
                        {(f.end_seconds - f.start_seconds).toFixed(2)}s
                      </small>
                      <small>
                        {f.confidence == null
                          ? "Confidence unavailable"
                          : `${(f.confidence * 100).toFixed(0)}% confidence`}
                      </small>
                    </span>
                    <ChevronRight size={16} />
                  </button>
                ))
              ) : (
                <Empty
                  title="No intervals returned"
                  description="This does not establish that delivery is flawless."
                />
              )}
            </Card>
          </div>
          {chosen && (
            <Card>
              <div className="section-title">
                <div>
                  <p className="eyebrow">EVIDENCE & INTERPRETATION</p>
                  <h2>{chosen.type.replaceAll("_", " ")}</h2>
                </div>
                <span className="badge">Severity {chosen.severity}/5</span>
              </div>
              <div className="evidence-grid">
                {[
                  [
                    "Baseline",
                    chosen.evidence.baseline_value,
                    chosen.evidence.units,
                  ],
                  [
                    "Participant",
                    chosen.evidence.participant_value,
                    chosen.evidence.units,
                  ],
                  [
                    "Absolute deviation",
                    chosen.evidence.absolute_deviation,
                    chosen.evidence.units,
                  ],
                  [
                    "Percentage deviation",
                    chosen.evidence.difference_percent,
                    "%",
                  ],
                  [
                    "Normalized deviation",
                    chosen.evidence.normalized_deviation,
                    "",
                  ],
                ].map(([label, value, unit]) => (
                  <div key={String(label)}>
                    <span className="muted tiny">{label}</span>
                    <strong>
                      {value == null
                        ? "Unavailable"
                        : `${Number(value).toFixed(2)} ${unit}`}
                    </strong>
                  </div>
                ))}
              </div>
              <p className="tiny muted">
                Evidence source: {chosen.evidence.source} · Interpretation
                source: {chosen.interpretation_source} · Measurement:{" "}
                {chosen.evidence.measurement_name}
              </p>
              {chosen.transcript_text && (
                <blockquote>{chosen.transcript_text}</blockquote>
              )}
              <p>{chosen.explanation || "Explanation unavailable."}</p>
              <div className="recommendation">
                <strong>Suggested next step</strong>
                <p>{chosen.recommendation || "Recommendation unavailable."}</p>
              </div>
            </Card>
          )}
          <Card>
            <div className="section-title">
              <h2>Transcript</h2>
              <span className="tiny muted">
                {r.execution_mode === "mock"
                  ? "Illustrative word positions"
                  : r.alignment.words.length
                    ? "Word alignment supplied by provider"
                    : "Unaligned transcript"}
              </span>
            </div>
            <Transcript
              words={r.alignment.words}
              text={j.transcript}
              current={current}
              selected={selected}
              flaws={r.flaws}
              onSeek={seek}
            />
          </Card>
          {r.warnings.map((w, i) => (
            <p key={i} className="notice tiny">
              {w}
            </p>
          ))}
        </>
      )}
    </>
  );
}
