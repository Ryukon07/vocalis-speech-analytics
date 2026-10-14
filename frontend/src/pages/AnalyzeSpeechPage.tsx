import { useEffect, useRef, useState } from "react";
import { z } from "zod";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, ArrowRight, Check, ScanLine, FileText } from "lucide-react";
import { api } from "../api/client";
import type {
  Recording,
  Reference,
  Category,
  AnalysisSettings,
} from "../types";
import { analysisFormSchema, type AnalysisForm } from "../lib/validation";
import { labels } from "../config/brand";
import {
  Button,
  Card,
  PageTitle,
  ErrorNotice,
  DemoBadge,
  useToast,
} from "../components/ui";
import AudioUpload from "../components/forms/AudioUpload";
import TranscriptDraft from "../components/forms/TranscriptDraft";

const steps = [
  "Recording",
  "Transcript",
  "Reference",
  "Evaluation",
  "Review & run",
];
export default function AnalyzeSpeechPage() {
  const [step, setStep] = useState(0);
  const [transcriptMode, setTranscriptMode] = useState<"manual" | "automatic">(
    "manual",
  );
  const [participant, setParticipant] = useState<Recording | null>(null);
  const [referenceAudio, setReferenceAudio] = useState<Recording | null>(null);
  const [referenceMode, setReferenceMode] = useState(
    localStorage.getItem("vocalis-mode") === "profile" ? "profile" : "library",
  );
  const [referenceTranscript, setReferenceTranscript] = useState("");
  const [referenceTitle, setReferenceTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [settings, setSettings] = useState<AnalysisSettings>({
    comparison_mode:
      localStorage.getItem("vocalis-mode") === "profile"
        ? "profile"
        : "recording",
    enabled_categories: ["pacing", "pitch", "energy", "pausing", "clarity"],
    sensitivity: 0.5,
    window_seconds: 2,
    overlap: 0.5,
    detailed_plots: true,
  });
  const key = useRef(crypto.randomUUID());
  const navigate = useNavigate();
  const client = useQueryClient();
  const toast = useToast();
  const caps = useQuery({
    queryKey: ["capabilities"],
    queryFn: api.capabilities,
  });
  const form = useForm<AnalysisForm>({
    resolver: zodResolver(
      analysisFormSchema.extend({
        transcript:
          transcriptMode === "automatic" ||
          caps.data?.requires_transcript === false
            ? z.string()
            : analysisFormSchema.shape.transcript,
        referenceId:
          caps.data?.requires_reference === false
            ? z.string()
            : analysisFormSchema.shape.referenceId,
      }),
    ),
    defaultValues: {
      recordingId: "",
      transcript: "",
      referenceId: "",
      rubricId: "",
    },
  });
  const provider = useQuery({ queryKey: ["provider"], queryFn: api.provider });
  useEffect(() => {
    if (!caps.data) return;
    const capabilities = caps.data;
    setSettings((s) => ({
      ...s,
      comparison_mode: capabilities.comparison_modes.includes(s.comparison_mode)
        ? s.comparison_mode
        : capabilities.comparison_modes[0],
      enabled_categories: s.enabled_categories.filter((c) =>
        capabilities.categories.includes(c),
      ),
    }));
    if (!capabilities.comparison_modes.includes("profile"))
      setReferenceMode("library");
  }, [caps.data]);
  const references = useQuery({
    queryKey: ["references", "eligible"],
    queryFn: () => api.references("?eligible=true&limit=100"),
  });
  const recordings = useQuery({
    queryKey: ["recordings", "select"],
    queryFn: () => api.recordings("?limit=100"),
  });
  const rubrics = useQuery({ queryKey: ["rubrics"], queryFn: api.rubrics });
  const values = form.watch();
  const rubric = rubrics.data?.items.find((r) => r.id === values.rubricId);
  const selected = references.data?.items.find(
    (r) => r.id === values.referenceId,
  );
  const chooseReference = (id: string) => {
    form.setValue("referenceId", id, { shouldValidate: true });
    const ref = references.data?.items.find((r) => r.id === id);
    if (ref && !values.transcript.trim())
      form.setValue("transcript", ref.transcript);
  };
  const changeParticipant = (recording: Recording | null) => {
    setParticipant(recording);
    form.setValue("recordingId", recording?.id || "", { shouldValidate: true });
    if (recording?.id !== participant?.id)
      form.setValue("transcript", recording?.transcript || "");
  };
  const next = async () => {
    setError(null);
    if (step === 0 && !(await form.trigger("recordingId"))) return;
    if (
      step === 1 &&
      transcriptMode === "manual" &&
      !(await form.trigger("transcript"))
    )
      return;
    if (step === 2) {
      if (referenceMode === "upload") {
        if (
          !referenceAudio ||
          !referenceTranscript.trim() ||
          !referenceTitle.trim()
        ) {
          setError(
            new Error(
              "Upload reference audio, enter a title and provide its transcript.",
            ),
          );
          return;
        }
        setBusy(true);
        try {
          const ref = await api.saveReference({
            title: referenceTitle,
            recording_id: referenceAudio.id,
            transcript: referenceTranscript,
            speaker_id: "",
            source_url: "",
            license: "",
            eligible: true,
            profile: null,
          });
          await client.invalidateQueries({ queryKey: ["references"] });
          form.setValue("referenceId", ref.id);
          setReferenceMode("library");
        } catch (e) {
          setError(e as Error);
          return;
        } finally {
          setBusy(false);
        }
      }
      if (
        caps.data?.requires_reference !== false &&
        !(await form.trigger("referenceId"))
      )
        return;
    }
    if (
      step === 3 &&
      (!(await form.trigger("rubricId")) || !settings.enabled_categories.length)
    ) {
      setError(
        new Error("Select a rubric and at least one supported category."),
      );
      return;
    }
    setStep(Math.min(4, step + 1));
  };
  const submit = form.handleSubmit(async (data) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const job = await api.createAnalysis(
        {
          participant_recording_id: data.recordingId,
          reference_id: data.referenceId || null,
          rubric_id: data.rubricId,
          transcript: data.transcript,
          transcript_mode: transcriptMode,
          settings,
        },
        key.current,
      );
      await client.invalidateQueries();
      toast("Analysis job created.");
      navigate(`/analyses/${job.id}`);
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  });
  const toggle = (category: Category) =>
    setSettings((s) => ({
      ...s,
      enabled_categories: s.enabled_categories.includes(category)
        ? s.enabled_categories.filter((c) => c !== category)
        : [...s.enabled_categories, category],
    }));
  return (
    <>
      <PageTitle
        eyebrow="NEW ANALYSIS"
        title="Understand your delivery"
        description="Bring a recording, choose your reference, and define what matters."
      />
      {provider.data?.execution_mode === "mock" && (
        <div className="notice">
          <DemoBadge />
          <span>
            Results will be illustrative fixtures, not predictions from your
            audio.
          </span>
        </div>
      )}
      <ErrorNotice
        error={
          provider.error ||
          caps.error ||
          references.error ||
          recordings.error ||
          rubrics.error
        }
      />
      <div className="analysis-layout">
        <Card className="workflow-card">
          <ol className="stepper">
            {steps.map((name, i) => (
              <li
                key={name}
                className={i === step ? "active" : i < step ? "done" : ""}
              >
                <span>{i < step ? <Check size={15} /> : i + 1}</span>
                {name}
              </li>
            ))}
          </ol>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (step === 4) void submit(e);
            }}
          >
            <div className="step-content">
              <p className="eyebrow">STEP {step + 1} OF 5</p>
              <h2>
                {
                  [
                    "Add your speech recording",
                    "Give your speech its words",
                    "Choose the comparison reference",
                    "Configure your evaluation",
                    "Ready for a closer look?",
                  ][step]
                }
              </h2>
              <p className="muted">
                {
                  [
                    "Choose an existing recording or upload new audio.",
                    "Provide the exact transcript spoken in the recording.",
                    "Recording comparisons require the same transcript.",
                    "Only settings supported by your provider are available.",
                    "Review your inputs before creating a persistent analysis job.",
                  ][step]
                }
              </p>
              <ErrorNotice error={error} />
              {step === 0 && (
                <>
                  <AudioUpload
                    value={participant}
                    onChange={changeParticipant}
                  />
                  <label>
                    Or choose a saved recording
                    <select
                      value={values.recordingId}
                      onChange={(e) =>
                        changeParticipant(
                          recordings.data?.items.find(
                            (r) => r.id === e.target.value,
                          ) || null,
                        )
                      }
                    >
                      <option value="">Select recording</option>
                      {recordings.data?.items.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.original_filename}
                        </option>
                      ))}
                    </select>
                  </label>
                  <p className="field-error">
                    {form.formState.errors.recordingId?.message}
                  </p>
                </>
              )}
              {step === 1 && (
                <>
                  <TranscriptDraft recordingId={participant?.id} onText={(text) => { setTranscriptMode("manual"); form.setValue("transcript", text, { shouldValidate: true }); }} />
                  <label>
                    Confirmed transcript
                    <textarea
                      rows={10}
                      {...form.register("transcript")}
                      placeholder="Paste the words spoken in your recording…"
                    />
                  </label>
                  <p className="field-error">
                    {form.formState.errors.transcript?.message}
                  </p>
                  <label className="btn btn-secondary transcript-upload">
                    <FileText size={16} /> Import text file
                    <input
                      type="file"
                      accept=".txt,text/plain"
                      onChange={async (e) => {
                        const f = e.target.files?.[0];
                        if (!f) return;
                        if (f.size > 1000000) {
                          setError(
                            new Error("Transcript must be smaller than 1 MB."),
                          );
                          return;
                        }
                        form.setValue("transcript", await f.text(), {
                          shouldValidate: true,
                        });
                      }}
                    />
                  </label>
                </>
              )}
              {step === 2 && (
                <>
                  <div className="segmented">
                    {[
                      ["library", "Reference library"],
                      ["upload", "Upload reference"],
                      ["profile", "Processed profile"],
                    ].map(([value, label]) => (
                      <button
                        key={value}
                        type="button"
                        className={referenceMode === value ? "active" : ""}
                        onClick={() => {
                          setReferenceMode(value);
                          form.setValue("referenceId", "");
                          setSettings((s) => ({
                            ...s,
                            comparison_mode:
                              value === "profile" ? "profile" : "recording",
                          }));
                        }}
                        disabled={
                          value === "profile" &&
                          !caps.data?.comparison_modes.includes("profile")
                        }
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  {referenceMode === "upload" ? (
                    <>
                      <AudioUpload
                        category="reference"
                        value={referenceAudio}
                        onChange={setReferenceAudio}
                      />
                      <label>
                        Reference title
                        <input
                          value={referenceTitle}
                          onChange={(e) => setReferenceTitle(e.target.value)}
                        />
                      </label>
                      <label>
                        Reference transcript
                        <textarea
                          rows={5}
                          value={referenceTranscript}
                          onChange={(e) =>
                            setReferenceTranscript(e.target.value)
                          }
                        />
                      </label>
                      <TranscriptDraft recordingId={referenceAudio?.id} onText={setReferenceTranscript} />
                    </>
                  ) : (
                    <>
                      <label>
                        {referenceMode === "profile"
                          ? "Processed reference profile"
                          : "Reference speech"}
                        <select
                          value={values.referenceId}
                          onChange={(e) => chooseReference(e.target.value)}
                        >
                          <option value="">Select reference</option>
                          {references.data?.items
                            .filter(
                              (r) => referenceMode !== "profile" || r.profile,
                            )
                            .map((r) => (
                              <option key={r.id} value={r.id}>
                                {r.title}
                              </option>
                            ))}
                        </select>
                      </label>
                      <p className="field-error">
                        {form.formState.errors.referenceId?.message}
                      </p>
                      {selected && (
                        <div className="reference-preview">
                          <strong>{selected.title}</strong>
                          <p className="muted tiny">
                            {selected.speaker_id || "Speaker not specified"} ·{" "}
                            {selected.license || "License not specified"}
                          </p>
                          {selected.source_url && (
                            <a
                              href={selected.source_url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              View source
                            </a>
                          )}
                          <p>{selected.transcript}</p>
                        </div>
                      )}
                    </>
                  )}
                </>
              )}
              {step === 3 && (
                <>
                  <label>
                    Evaluation rubric
                    <select
                      {...form.register("rubricId")}
                      onChange={(e) => {
                        form.setValue("rubricId", e.target.value);
                        const r = rubrics.data?.items.find(
                          (r) => r.id === e.target.value,
                        );
                        if (r)
                          setSettings((s) => ({
                            ...s,
                            enabled_categories: r.enabled_categories.filter(
                              (c) => caps.data?.categories.includes(c),
                            ),
                          }));
                      }}
                    >
                      <option value="">Choose a rubric</option>
                      {rubrics.data?.items.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name} · v{r.version}
                        </option>
                      ))}
                    </select>
                  </label>
                  <p className="field-error">
                    {form.formState.errors.rubricId?.message}
                  </p>
                  <label>
                    Baseline comparison mode
                    <select
                      value={settings.comparison_mode}
                      onChange={(e) =>
                        setSettings((s) => ({
                          ...s,
                          comparison_mode: e.target.value as
                            | "recording"
                            | "profile",
                        }))
                      }
                    >
                      {caps.data?.comparison_modes.map((m) => (
                        <option value={m} key={m}>
                          {m === "recording"
                            ? "Same-text reference recording"
                            : "Reusable processed profile"}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="category-options">
                    {caps.data?.categories.map((c) => (
                      <label key={c} className="checkbox">
                        <input
                          type="checkbox"
                          checked={settings.enabled_categories.includes(c)}
                          disabled={
                            !!rubric && !rubric.enabled_categories.includes(c)
                          }
                          onChange={() => toggle(c)}
                        />
                        {labels[c]}
                        <span className="muted">
                          {rubric?.weights[c] ?? "—"}%
                        </span>
                      </label>
                    ))}
                  </div>
                  <label>
                    Severity sensitivity{" "}
                    <span className="muted">
                      {settings.sensitivity.toFixed(2)}
                    </span>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step=".05"
                      value={settings.sensitivity}
                      onChange={(e) =>
                        setSettings((s) => ({
                          ...s,
                          sensitivity: Number(e.target.value),
                        }))
                      }
                    />
                    <span className="muted tiny">Higher sensitivity flags smaller deviations from the matched reference.</span>
                  </label>
                  {caps.data?.supports_windows && (
                    <div className="grid-two">
                      <label>
                        Window (seconds)
                        <input
                          type="number"
                          min=".5"
                          max="60"
                          step=".1"
                          required
                          value={settings.window_seconds}
                          onChange={(e) =>
                            setSettings((s) => ({
                              ...s,
                              window_seconds: Number(e.target.value),
                            }))
                          }
                        />
                      </label>
                      <label>
                        Overlap (0–0.99)
                        <input
                          type="number"
                          min="0"
                          max=".99"
                          step=".05"
                          required
                          value={settings.overlap}
                          onChange={(e) =>
                            setSettings((s) => ({
                              ...s,
                              overlap: Number(e.target.value),
                            }))
                          }
                        />
                      </label>
                    </div>
                  )}
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={settings.detailed_plots}
                      onChange={(e) =>
                        setSettings((s) => ({
                          ...s,
                          detailed_plots: e.target.checked,
                        }))
                      }
                    />
                    Include detailed acoustic plots
                  </label>
                  <p className="tiny muted">
                    Enabled scoring weights are normalized over available scored
                    dimensions. In demo mode these settings do not run
                    signal-processing models.
                  </p>
                </>
              )}
              {step === 4 && (
                <>
                  <div className="review-list">
                    {[
                      ["Recording", participant?.original_filename],
                      [
                        "Transcript",
                        `${values.transcript.split(/\s+/).filter(Boolean).length} words`,
                      ],
                      ["Reference", selected?.title],
                      ["Rubric", rubric?.name],
                      [
                        "Categories",
                        settings.enabled_categories
                          .map((c) => labels[c])
                          .join(", "),
                      ],
                      [
                        "Provider",
                        `${caps.data?.provider_name || "Unavailable"} · ${caps.data?.provider_version || ""}`,
                      ],
                    ].map(([label, value]) => (
                      <div className="list-row" key={label}>
                        <span className="muted">{label}</span>
                        <strong>{value || "—"}</strong>
                      </div>
                    ))}
                  </div>
                  {provider.data?.execution_mode === "mock" && (
                    <p className="notice">
                      Every score, curve and word timestamp will be labelled as
                      a demonstration fixture.
                    </p>
                  )}
                  <p className="muted">
                    You can leave this page after submission and return through
                    Analysis history.
                  </p>
                </>
              )}
            </div>
            <div className="step-actions">
              <Button
                type="button"
                variant="secondary"
                disabled={!step || busy}
                onClick={() => setStep(step - 1)}
              >
                <ArrowLeft size={16} /> Back
              </Button>
              {step < 4 ? (
                <Button
                  key="continue"
                  type="button"
                  disabled={busy || !provider.data?.ready}
                  onClick={(e) => {
                    e.preventDefault();
                    void next();
                  }}
                >
                  Continue <ArrowRight size={16} />
                </Button>
              ) : (
                <Button
                  key="submit"
                  type="submit"
                  disabled={busy || !provider.data?.ready}
                >
                  <ScanLine size={17} />
                  {busy ? "Creating job…" : "Analyze Speech"}
                </Button>
              )}
            </div>
          </form>
        </Card>
        <aside>
          <Card className="help-card">
            <ScanLine size={25} />
            <h3>A comparison with context</h3>
            <p className="muted">
              Your reference and participant should speak the same text. Their
              recordings can have different timings.
            </p>
            <hr />
            <h4>What you’ll see</h4>
            <ul>
              <li>Rubric scores when available</li>
              <li>Timestamped flaw intervals</li>
              <li>Acoustic evidence and explanations</li>
              <li>Downloadable JSON and CSV reports</li>
            </ul>
            <p className="tiny muted">
              WAV duration is read on upload. Compressed audio duration remains
              unavailable until a real provider processes it.
            </p>
          </Card>
        </aside>
      </div>
    </>
  );
}
