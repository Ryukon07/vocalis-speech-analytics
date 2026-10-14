import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, Database, Search } from "lucide-react";
import { api, audioUrl } from "../api/client";
import type { Group, Annotation, Variant } from "../types";
import { useAction } from "../hooks/useAction";
import {
  Button,
  Card,
  PageTitle,
  Modal,
  Confirm,
  Empty,
  ErrorNotice,
  Loading,
  Pagination,
} from "../components/ui";
import AudioPlayer, { type AudioHandle } from "../components/audio/AudioPlayer";
import { formatTime } from "../lib/validation";
const annotationTypes = [
  "rushed_pacing", "slow_pacing", "awkward_pause", "monotone_delivery",
  "low_energy", "recognition_difficulty",
];
const blankGroup: Omit<Group, "id" | "variants"> = {
  title: "",
  source_id: "",
  reference_recording_id: "",
  transcript: "",
  transcript_version: "1",
  speaker_id: "",
  split: "training",
  provenance: "",
};
const blankAnnotation: Omit<Annotation, "id"> = {
  recording_id: "",
  flaw_type: "rushed_pacing",
  start_seconds: 0,
  end_seconds: 1,
  severity: 2,
  source: "human",
  notes: "",
};
export default function DatasetManagerPage() {
  const [search, setSearch] = useState("");
  const [split, setSplit] = useState("");
  const [offset, setOffset] = useState(0);
  const [groupForm, setGroupForm] = useState(blankGroup);
  const [openGroup, setOpenGroup] = useState(false);
  const [editingGroup, setEditingGroup] = useState<string>();
  const [variantGroup, setVariantGroup] = useState<string>();
  const [variant, setVariant] = useState<Omit<Variant, "id" | "group_id">>({
    recording_id: "",
    level: 1,
    flaw_labels: ["pacing"],
    speaker_id: "",
    provenance: "",
  });
  const [deleting, setDeleting] = useState<{
    id: string;
    type: string;
    group?: string;
  }>();
  const [recordingId, setRecordingId] = useState("");
  const [annotation, setAnnotation] = useState(blankAnnotation);
  const [annotationId, setAnnotationId] = useState<string>();
  const player = useRef<AudioHandle>(null);
  const groups = useQuery({
    queryKey: ["groups", search, split, offset],
    queryFn: () =>
      api.groups(
        `?search=${encodeURIComponent(search)}&split=${split}&offset=${offset}`,
      ),
  });
  const recordings = useQuery({
    queryKey: ["recordings", "dataset"],
    queryFn: () => api.recordings("?limit=100"),
  });
  const annotations = useQuery({
    queryKey: ["annotations", recordingId],
    queryFn: () => api.annotations(`?recording_id=${recordingId}&limit=100`),
    enabled: !!recordingId,
  });
  const rec = recordings.data?.items.find((r) => r.id === recordingId);
  const saveGroup = useAction(
    (g: typeof blankGroup) => api.saveGroup(g, editingGroup),
    "Dataset group saved.",
    () => setOpenGroup(false),
  );
  const addVariant = useAction(
    (v: typeof variant) => api.addVariant(variantGroup!, v),
    "Variant linked.",
    () => setVariantGroup(undefined),
  );
  const saveAnnotation = useAction(
    (a: typeof blankAnnotation) => api.saveAnnotation(a, annotationId),
    "Flaw annotation saved.",
    () => {
      setAnnotationId(undefined);
      setAnnotation({ ...blankAnnotation, recording_id: recordingId });
    },
  );
  const del = useAction(
    (d: NonNullable<typeof deleting>) =>
      d.type === "group"
        ? api.deleteGroup(d.id)
        : d.type === "variant"
          ? api.deleteVariant(d.group!, d.id)
          : api.deleteAnnotation(d.id),
    "Dataset record removed.",
    () => setDeleting(undefined),
  );
  const editGroup = (g: Group) => {
    setGroupForm({
      title: g.title,
      source_id: g.source_id || "",
      reference_recording_id: g.reference_recording_id,
      transcript: g.transcript,
      transcript_version: g.transcript_version,
      speaker_id: g.speaker_id,
      split: g.split,
      provenance: g.provenance,
    });
    setEditingGroup(g.id);
    setOpenGroup(true);
  };
  return (
    <>
      <PageTitle
        eyebrow="DATA ENGINEERING"
        title="Contrastive dataset"
        description="Keep shared transcripts, quality levels and ground-truth intervals together."
        action={
          <Button
            onClick={() => {
              setGroupForm(blankGroup);
              setEditingGroup(undefined);
              setOpenGroup(true);
            }}
          >
            <Plus size={17} /> New group
          </Button>
        }
      />
      <div className="toolbar">
        <label className="search-field">
          <Search size={17} />
          <input
            aria-label="Search dataset"
            placeholder="Search groups"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
          />
        </label>
        <select
          aria-label="Filter dataset split"
          value={split}
          onChange={(e) => {
            setSplit(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All splits</option>
          {["training", "validation", "testing"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </div>
      <ErrorNotice error={groups.error || recordings.error} />
      {groups.isPending ? (
        <Loading />
      ) : !groups.data?.items.length ? (
        <Card>
          <Empty
            title="Create your first contrastive group"
            description="Pair one source recording with flawed variants of its transcript."
          />
        </Card>
      ) : (
        groups.data.items.map((g) => (
          <Card key={g.id}>
            <div className="section-title">
              <div className="row">
                <Database className="accent" size={21} />
                <div>
                  <h2>{g.title}</h2>
                  <p className="muted tiny">
                    Transcript v{g.transcript_version} · {g.split} ·{" "}
                    {g.speaker_id || "Speaker unspecified"}
                  </p>
                </div>
              </div>
              <div className="row">
                <Button
                  variant="secondary"
                  onClick={() => {
                    setVariantGroup(g.id);
                    setVariant({ ...variant, recording_id: "" });
                  }}
                >
                  <Plus size={15} /> Add variant
                </Button>
                <Button
                  variant="ghost"
                  aria-label="Edit group"
                  onClick={() => editGroup(g)}
                >
                  <Pencil size={16} />
                </Button>
                <Button
                  variant="ghost"
                  aria-label="Delete group"
                  onClick={() => setDeleting({ id: g.id, type: "group" })}
                >
                  <Trash2 size={16} />
                </Button>
              </div>
            </div>
            <p className="muted tiny">
              Source:{" "}
              {recordings.data?.items.find(
                (r) => r.id === g.reference_recording_id,
              )?.original_filename || g.reference_recording_id}{" "}
              · {g.provenance || "No provenance supplied"}
            </p>
            <p className="clamp-text">{g.transcript}</p>
            {g.variants.length ? (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Variant recording</th>
                      <th>Level</th>
                      <th>Intended flaws</th>
                      <th>Provenance</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {g.variants.map((v) => (
                      <tr key={v.id}>
                        <td>
                          {recordings.data?.items.find(
                            (r) => r.id === v.recording_id,
                          )?.original_filename || v.recording_id}
                        </td>
                        <td>
                          <span className="badge">{v.level}/5</span>
                        </td>
                        <td>{v.flaw_labels.join(", ") || "—"}</td>
                        <td>{v.provenance || "—"}</td>
                        <td>
                          <div className="row">
                            <Button
                              variant="secondary"
                              onClick={() => {
                                setRecordingId(v.recording_id);
                                setAnnotation({
                                  ...blankAnnotation,
                                  recording_id: v.recording_id,
                                });
                                setAnnotationId(undefined);
                                document
                                  .getElementById("annotation-editor")
                                  ?.scrollIntoView({ behavior: "smooth" });
                              }}
                            >
                              Annotate
                            </Button>
                            <Button
                              variant="ghost"
                              aria-label="Unlink variant"
                              onClick={() =>
                                setDeleting({
                                  id: v.id,
                                  type: "variant",
                                  group: g.id,
                                })
                              }
                            >
                              <Trash2 size={15} />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="muted">No variants linked yet.</p>
            )}
          </Card>
        ))
      )}
      <Pagination
        offset={offset}
        total={groups.data?.total || 0}
        onChange={setOffset}
      />
      <Card>
        <div className="section-title" id="annotation-editor">
          <div>
            <h2>Ground-truth annotation studio</h2>
            <p className="muted">
              Enter precise bounds or drag the selected interval on the
              waveform.
            </p>
          </div>
          <span className="badge">MANUAL LABELS</span>
        </div>
        <label>
          Recording to annotate
          <select
            value={recordingId}
            onChange={(e) => {
              setRecordingId(e.target.value);
              setAnnotation({
                ...blankAnnotation,
                recording_id: e.target.value,
              });
              setAnnotationId(undefined);
            }}
          >
            <option value="">Choose a recording</option>
            {recordings.data?.items.map((r) => (
              <option key={r.id} value={r.id}>
                {r.original_filename}
              </option>
            ))}
          </select>
        </label>
        <ErrorNotice error={annotations.error} />
        {rec && (
          <>
            <AudioPlayer
              ref={player}
              url={audioUrl(rec.id)}
              title="Annotation recording"
              intervals={[
                {
                  id: "draft",
                  start_seconds: annotation.start_seconds,
                  end_seconds: annotation.end_seconds,
                },
              ]}
              editable
              onRegionChange={(_, start, end) =>
                setAnnotation((a) => ({
                  ...a,
                  start_seconds: Number(start.toFixed(3)),
                  end_seconds: Number(end.toFixed(3)),
                }))
              }
            />
            <form
              onSubmit={(e) => {
                e.preventDefault();
                saveAnnotation.mutate({
                  ...annotation,
                  recording_id: recordingId,
                });
              }}
            >
              <ErrorNotice error={saveAnnotation.error} />
              <div className="grid-three">
                <label>
                  Flaw type
                  <select
                    value={annotation.flaw_type}
                    onChange={(e) =>
                      setAnnotation((a) => ({
                        ...a,
                        flaw_type: e.target.value,
                      }))
                    }
                  >
                    {annotationTypes.map((c) => (
                      <option key={c} value={c}>{c.replaceAll("_", " ")}</option>
                    ))}
                    {!annotationTypes.includes(annotation.flaw_type) && (
                      <option value={annotation.flaw_type}>{annotation.flaw_type.replaceAll("_", " ")} (saved label)</option>
                    )}
                  </select>
                </label>
                <label>
                  Start (seconds)
                  <input
                    type="number"
                    step=".001"
                    min="0"
                    max={rec.duration_seconds ?? undefined}
                    required
                    value={annotation.start_seconds}
                    onChange={(e) =>
                      setAnnotation((a) => ({
                        ...a,
                        start_seconds: Number(e.target.value),
                      }))
                    }
                  />
                </label>
                <label>
                  End (seconds)
                  <input
                    type="number"
                    step=".001"
                    min={annotation.start_seconds}
                    max={rec.duration_seconds ?? undefined}
                    required
                    value={annotation.end_seconds}
                    onChange={(e) =>
                      setAnnotation((a) => ({
                        ...a,
                        end_seconds: Number(e.target.value),
                      }))
                    }
                  />
                </label>
              </div>
              <div className="grid-three">
                <label>
                  Severity (1–5)
                  <input
                    type="number"
                    min="1"
                    max="5"
                    value={annotation.severity}
                    onChange={(e) =>
                      setAnnotation((a) => ({
                        ...a,
                        severity: Number(e.target.value),
                      }))
                    }
                  />
                </label>
                <label>
                  Labeling source
                  <input
                    required
                    value={annotation.source}
                    onChange={(e) =>
                      setAnnotation((a) => ({ ...a, source: e.target.value }))
                    }
                  />
                </label>
                <label>
                  Notes / annotator
                  <input
                    value={annotation.notes}
                    onChange={(e) =>
                      setAnnotation((a) => ({ ...a, notes: e.target.value }))
                    }
                  />
                </label>
              </div>
              <div className="row">
                <Button
                  type="submit"
                  disabled={
                    saveAnnotation.isPending || rec.duration_seconds == null
                  }
                >
                  {annotationId ? "Update annotation" : "Save annotation"}
                </Button>
                {annotationId && (
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => {
                      setAnnotationId(undefined);
                      setAnnotation({
                        ...blankAnnotation,
                        recording_id: recordingId,
                      });
                    }}
                  >
                    New annotation
                  </Button>
                )}
              </div>
              {rec.duration_seconds == null && (
                <p className="notice">
                  A known duration is required for labels. Upload PCM WAV or
                  process this recording with a real provider first.
                </p>
              )}
            </form>
            <div className="annotation-list">
              {annotations.data?.items.map((a) => (
                <div className="list-row" key={a.id}>
                  <button
                    className="text-link"
                    onClick={() => {
                      setAnnotationId(a.id);
                      setAnnotation({
                        recording_id: a.recording_id,
                        flaw_type: a.flaw_type,
                        start_seconds: a.start_seconds,
                        end_seconds: a.end_seconds,
                        severity: a.severity,
                        source: a.source,
                        notes: a.notes,
                      });
                      player.current?.seek(a.start_seconds);
                    }}
                  >
                    {a.flaw_type} · {formatTime(a.start_seconds)}–
                    {formatTime(a.end_seconds)}
                  </button>
                  <span className="tiny muted">
                    {a.source} · severity {a.severity}
                  </span>
                  <Button
                    variant="ghost"
                    aria-label="Delete annotation"
                    onClick={() =>
                      setDeleting({ id: a.id, type: "annotation" })
                    }
                  >
                    <Trash2 size={15} />
                  </Button>
                </div>
              ))}
            </div>
          </>
        )}
      </Card>
      <Modal
        open={openGroup}
        onOpenChange={setOpenGroup}
        title={editingGroup ? "Edit dataset group" : "New contrastive group"}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            saveGroup.mutate(groupForm);
          }}
        >
          <ErrorNotice error={saveGroup.error} />
          <label>
            Group title
            <input
              required
              value={groupForm.title}
              onChange={(e) =>
                setGroupForm((f) => ({ ...f, title: e.target.value }))
              }
            />
          </label>
          <label>
            Source recording
            <select
              required
              value={groupForm.reference_recording_id}
              onChange={(e) => {
                const r = recordings.data?.items.find(
                  (r) => r.id === e.target.value,
                );
                setGroupForm((f) => ({
                  ...f,
                  reference_recording_id: e.target.value,
                  transcript: r?.transcript || f.transcript,
                }));
              }}
            >
              <option value="">Choose source</option>
              {recordings.data?.items.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.original_filename}
                </option>
              ))}
            </select>
          </label>
          <label>Source speech ID<input value={groupForm.source_id || ""} maxLength={100}
            placeholder="Same ID for all excerpts of one original speech"
            onChange={(e) => setGroupForm((f) => ({ ...f, source_id: e.target.value }))} /></label>
          <label>
            Shared transcript
            <textarea
              required
              rows={4}
              value={groupForm.transcript}
              onChange={(e) =>
                setGroupForm((f) => ({ ...f, transcript: e.target.value }))
              }
            />
          </label>
          <div className="grid-three">
            <label>
              Transcript version
              <input
                required
                value={groupForm.transcript_version}
                onChange={(e) =>
                  setGroupForm((f) => ({
                    ...f,
                    transcript_version: e.target.value,
                  }))
                }
              />
            </label>
            <label>
              Speaker ID
              <input
                value={groupForm.speaker_id}
                onChange={(e) =>
                  setGroupForm((f) => ({ ...f, speaker_id: e.target.value }))
                }
              />
            </label>
            <label>
              Dataset split
              <select
                value={groupForm.split}
                onChange={(e) =>
                  setGroupForm((f) => ({
                    ...f,
                    split: e.target.value as Group["split"],
                  }))
                }
              >
                {["training", "validation", "testing"].map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
          </div>
          <label>
            Labeling / collection provenance
            <textarea
              value={groupForm.provenance}
              onChange={(e) =>
                setGroupForm((f) => ({ ...f, provenance: e.target.value }))
              }
            />
          </label>
          <Button type="submit" disabled={saveGroup.isPending}>
            Save group
          </Button>
        </form>
      </Modal>
      <Modal
        open={!!variantGroup}
        onOpenChange={(v) => !v && setVariantGroup(undefined)}
        title="Link a paired variant"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            addVariant.mutate(variant);
          }}
        >
          <ErrorNotice error={addVariant.error} />
          <label>
            Variant recording
            <select
              required
              value={variant.recording_id}
              onChange={(e) =>
                setVariant((v) => ({ ...v, recording_id: e.target.value }))
              }
            >
              <option value="">Choose recording</option>
              {recordings.data?.items.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.original_filename}
                </option>
              ))}
            </select>
          </label>
          <label>
            Quality / flaw level (0–5)
            <input
              required
              type="number"
              min="0"
              max="5"
              value={variant.level}
              onChange={(e) =>
                setVariant((v) => ({ ...v, level: Number(e.target.value) }))
              }
            />
          </label>
          <label>
            Flaw labels (comma separated)
            <input
              value={variant.flaw_labels.join(", ")}
              onChange={(e) =>
                setVariant((v) => ({
                  ...v,
                  flaw_labels: e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                }))
              }
            />
          </label>
          <label>
            Speaker ID
            <input
              value={variant.speaker_id}
              onChange={(e) =>
                setVariant((v) => ({ ...v, speaker_id: e.target.value }))
              }
            />
          </label>
          <label>
            Provenance
            <input
              value={variant.provenance}
              onChange={(e) =>
                setVariant((v) => ({ ...v, provenance: e.target.value }))
              }
            />
          </label>
          <Button type="submit" disabled={addVariant.isPending}>
            Link variant
          </Button>
        </form>
      </Modal>
      <Confirm
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(undefined)}
        busy={del.isPending}
        onConfirm={() => deleting && del.mutate(deleting)}
      />
    </>
  );
}
