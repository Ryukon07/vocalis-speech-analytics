import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Plus,
  Search,
  Pencil,
  Trash2,
  Library,
  FileAudio,
  ArrowUpRight,
} from "lucide-react";
import { api, audioUrl } from "../api/client";
import type { Reference, Recording } from "../types";
import { useAction } from "../hooks/useAction";
import {
  Button,
  Card,
  PageTitle,
  Loading,
  ErrorNotice,
  Empty,
  Modal,
  Confirm,
  Pagination,
} from "../components/ui";
import AudioUpload from "../components/forms/AudioUpload";
import TranscriptDraft from "../components/forms/TranscriptDraft";
import { formatTime } from "../lib/validation";
type ReferenceData = Omit<Reference, "id" | "created_at" | "updated_at">;
const blank: ReferenceData = {
  title: "",
  recording_id: "",
  transcript: "",
  speaker_id: "",
  source_url: "",
  license: "",
  eligible: true,
  profile: null,
};
export default function ReferenceLibraryPage() {
  const [tab, setTab] = useState("references");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<string>();
  const [form, setForm] = useState<ReferenceData>(blank);
  const [audio, setAudio] = useState<Recording | null>(null);
  const [deleting, setDeleting] = useState<{ id: string; type: string }>();
  const [recordEdit, setRecordEdit] = useState<Recording>();
  const refs = useQuery({
    queryKey: ["references", search, offset],
    queryFn: () =>
      api.references(`?search=${encodeURIComponent(search)}&offset=${offset}`),
  });
  const recordings = useQuery({
    queryKey: ["recordings", search, offset],
    queryFn: () =>
      api.recordings(`?search=${encodeURIComponent(search)}&offset=${offset}`),
  });
  const choices = useQuery({
    queryKey: ["recordings", "choices"],
    queryFn: () => api.recordings("?limit=100"),
  });
  const save = useAction(
    (data: ReferenceData) => api.saveReference(data, editing),
    "Reference saved.",
    () => {
      setOpen(false);
      setEditing(undefined);
    },
  );
  const del = useAction(
    (item: { id: string; type: string }) =>
      item.type === "reference"
        ? api.deleteReference(item.id)
        : api.deleteRecording(item.id),
    "Record deleted.",
    () => setDeleting(undefined),
  );
  const metadata = useAction(
    (r: Recording) =>
      api.patchRecording(r.id, {
        title: r.title,
        transcript: r.transcript,
        speaker_id: r.speaker_id,
        language: r.language,
        source_url: r.source_url,
        license: r.license,
        notes: r.notes,
        recording_date: r.recording_date,
        category: r.category,
      }),
    "Recording metadata saved.",
    () => setRecordEdit(undefined),
  );
  const edit = (r: Reference) => {
    const { id, created_at, updated_at, ...data } = r;
    void created_at;
    void updated_at;
    setEditing(id);
    setForm(data);
    setAudio(null);
    setOpen(true);
  };
  const update = (key: keyof ReferenceData, value: unknown) =>
    setForm((f) => ({ ...f, [key]: value }));
  return (
    <>
      <PageTitle
        eyebrow="REFERENCE FOUNDATION"
        title="Reference library"
        description="Manage baseline recordings, transcripts and source information."
        action={
          <Button
            onClick={() => {
              setEditing(undefined);
              setForm(blank);
              setAudio(null);
              setOpen(true);
            }}
          >
            <Plus size={17} /> Add reference
          </Button>
        }
      />
      <div className="toolbar">
        <div className="segmented">
          {["references", "recordings"].map((t) => (
            <button
              key={t}
              className={tab === t ? "active" : ""}
              onClick={() => {
                setTab(t);
                setOffset(0);
              }}
            >
              {t === "references" ? "Reference speeches" : "All recordings"}
            </button>
          ))}
        </div>
        <label className="search-field">
          <Search size={17} />
          <input
            aria-label="Search library"
            value={search}
            placeholder="Search your library"
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
          />
        </label>
      </div>
      <ErrorNotice error={refs.error || recordings.error || choices.error} />
      {(tab === "references" ? refs.isPending : recordings.isPending) ? (
        <Loading />
      ) : tab === "references" ? (
        <>
          {!refs.data?.items.length ? (
            <Card>
              <Empty
                title="Your baseline library starts here"
                description="Add a reference recording and its verified transcript."
              />
            </Card>
          ) : (
            <div className="library-grid">
              {refs.data.items.map((r) => (
                <Card key={r.id}>
                  <div className="row between">
                    <Library className="accent" size={22} />
                    <span
                      className={`badge ${r.eligible ? "status-completed" : ""}`}
                    >
                      {r.eligible ? "Eligible baseline" : "Not eligible"}
                    </span>
                  </div>
                  <h3>{r.title}</h3>
                  <p className="muted tiny">
                    {r.speaker_id || "Speaker not specified"} ·{" "}
                    {r.license || "License not specified"}
                  </p>
                  <audio
                    controls
                    preload="none"
                    src={audioUrl(r.recording_id)}
                  />
                  <p className="clamp-text muted">{r.transcript}</p>
                  <div className="row between">
                    <span className="tiny muted">
                      {r.profile
                        ? "Processed profile available"
                        : "Audio reference · unprocessed"}
                    </span>
                    <div className="row">
                      {r.source_url && (
                        <a
                          aria-label="Open source"
                          href={r.source_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <ArrowUpRight size={17} />
                        </a>
                      )}
                      <Button
                        variant="ghost"
                        aria-label="Edit reference"
                        onClick={() => edit(r)}
                      >
                        <Pencil size={16} />
                      </Button>
                      <Button
                        variant="ghost"
                        aria-label="Delete reference"
                        onClick={() =>
                          setDeleting({ id: r.id, type: "reference" })
                        }
                      >
                        <Trash2 size={16} />
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
          <Pagination
            offset={offset}
            total={refs.data?.total || 0}
            onChange={setOffset}
          />
        </>
      ) : (
        <>
          <Card>
            <div className="section-title">
              <h2>Upload a managed recording</h2>
              <FileAudio size={20} />
            </div>
            <AudioUpload
              value={audio}
              onChange={(value) => {
                setAudio(value);
                if (value) {
                  void recordings.refetch();
                  void choices.refetch();
                }
              }}
            />
          </Card>
          <Card>
            {!recordings.data?.items.length ? (
              <Empty title="No recordings yet" />
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Recording</th>
                      <th>Duration / format</th>
                      <th>Metadata</th>
                      <th>Preview</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recordings.data.items.map((r) => (
                      <tr key={r.id}>
                        <td>
                          <strong>{r.title || r.original_filename}</strong>
                          <small className="table-small muted">
                            {r.original_filename} · {r.category}
                          </small>
                        </td>
                        <td>
                          {r.duration_seconds == null
                            ? "Unknown duration"
                            : formatTime(r.duration_seconds)}
                          <small className="table-small muted">
                            {r.mime_type} · {(r.file_size / 1048576).toFixed(2)}{" "}
                            MB
                          </small>
                        </td>
                        <td>
                          {r.speaker_id || "No speaker"}
                          <small className="table-small muted">
                            {r.license || "License unspecified"}
                          </small>
                        </td>
                        <td>
                          <audio controls preload="none" src={audioUrl(r.id)} />
                        </td>
                        <td>
                          <div className="row">
                            <Button
                              variant="ghost"
                              aria-label="Edit recording metadata"
                              onClick={() => setRecordEdit({ ...r })}
                            >
                              <Pencil size={16} />
                            </Button>
                            <Button
                              variant="ghost"
                              aria-label="Delete recording"
                              onClick={() =>
                                setDeleting({ id: r.id, type: "recording" })
                              }
                            >
                              <Trash2 size={16} />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <Pagination
              offset={offset}
              total={recordings.data?.total || 0}
              onChange={setOffset}
            />
          </Card>
        </>
      )}
      <Modal
        open={open}
        onOpenChange={setOpen}
        title={editing ? "Edit reference" : "Add reference speech"}
        description="Link a managed recording and verified transcript. Keep provenance visible."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate(form);
          }}
        >
          <ErrorNotice error={save.error} />
          <label>
            Title
            <input
              required
              maxLength={255}
              value={form.title}
              onChange={(e) => update("title", e.target.value)}
            />
          </label>
          {!editing && (
            <AudioUpload
              category="reference"
              value={audio}
              onChange={(r) => {
                setAudio(r);
                if (r) {
                  update("recording_id", r.id);
                  void choices.refetch();
                }
              }}
            />
          )}
          <label>
            Or link existing recording
            <select
              required
              value={form.recording_id}
              onChange={(e) => {
                update("recording_id", e.target.value);
                const r = choices.data?.items.find(
                  (r) => r.id === e.target.value,
                );
                if (r?.transcript) update("transcript", r.transcript);
              }}
            >
              <option value="">Choose recording</option>
              {choices.data?.items.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.original_filename}
                </option>
              ))}
            </select>
          </label>
          <label>
            Transcript
            <textarea
              rows={5}
              required
              value={form.transcript}
              onChange={(e) => update("transcript", e.target.value)}
            />
          </label>
          <label>
            Import transcript (.txt)
            <input
              type="file"
              accept=".txt,text/plain"
              onChange={async (e) => {
                const f = e.target.files?.[0];
                if (f && f.size <= 1000000)
                  update("transcript", await f.text());
              }}
            />
          </label>
          {!editing && <TranscriptDraft recordingId={form.recording_id || undefined} onText={(text) => update("transcript", text)} />}
          <div className="grid-two">
            <label>
              Speaker / anonymous ID
              <input
                value={form.speaker_id}
                onChange={(e) => update("speaker_id", e.target.value)}
              />
            </label>
            <label>
              License
              <input
                value={form.license}
                onChange={(e) => update("license", e.target.value)}
              />
            </label>
          </div>
          <label>
            Source URL
            <input
              type="url"
              value={form.source_url}
              onChange={(e) => update("source_url", e.target.value)}
            />
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.eligible}
              onChange={(e) => update("eligible", e.target.checked)}
            />
            Eligible comparison baseline
          </label>
          <p className="tiny muted">
            Processed profiles are supplied by your future analysis provider or
            the API. Uploading audio does not create a profile.
          </p>
          <Button disabled={save.isPending} type="submit">
            {save.isPending ? "Saving…" : "Save reference"}
          </Button>
        </form>
      </Modal>
      <Modal
        open={!!recordEdit}
        onOpenChange={(v) => !v && setRecordEdit(undefined)}
        title="Recording metadata"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (recordEdit) metadata.mutate(recordEdit);
          }}
        >
          <ErrorNotice error={metadata.error} />
          {recordEdit && (
            <>
              {(
                [
                  "title",
                  "speaker_id",
                  "language",
                  "source_url",
                  "license",
                ] as const
              ).map((key) => (
                <label key={key}>
                  {key.replaceAll("_", " ")}
                  <input
                    type={key === "source_url" ? "url" : "text"}
                    value={recordEdit[key]}
                    onChange={(e) =>
                      setRecordEdit({ ...recordEdit, [key]: e.target.value })
                    }
                  />
                </label>
              ))}
              <label>
                Recording date
                <input
                  type="date"
                  value={recordEdit.recording_date || ""}
                  onChange={(e) =>
                    setRecordEdit({
                      ...recordEdit,
                      recording_date: e.target.value || null,
                    })
                  }
                />
              </label>
              <label>
                Transcript
                <textarea
                  value={recordEdit.transcript}
                  onChange={(e) =>
                    setRecordEdit({ ...recordEdit, transcript: e.target.value })
                  }
                />
              </label>
              <label>
                Notes
                <textarea
                  value={recordEdit.notes}
                  onChange={(e) =>
                    setRecordEdit({ ...recordEdit, notes: e.target.value })
                  }
                />
              </label>
              <label>
                Category
                <select
                  value={recordEdit.category}
                  onChange={(e) =>
                    setRecordEdit({ ...recordEdit, category: e.target.value })
                  }
                >
                  {["participant", "reference", "variant", "demo"].map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </label>
              <Button type="submit" disabled={metadata.isPending}>
                Save metadata
              </Button>
            </>
          )}
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
