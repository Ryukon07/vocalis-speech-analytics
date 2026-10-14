import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { Button, ErrorNotice } from "../ui";
import { FileAudio, Square } from "lucide-react";

export default function TranscriptDraft({ recordingId, onText }: { recordingId?: string; onText: (text: string) => void }) {
  const [jobId, setJobId] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const accepted = useRef<string | undefined>(undefined);
  const callback = useRef(onText); callback.current = onText;
  const provider = useQuery({ queryKey: ["capabilities"], queryFn: api.capabilities });
  useEffect(() => {
    setJobId(recordingId ? localStorage.getItem(`vocalis-transcription-${recordingId}`) || undefined : undefined);
    accepted.current = undefined; setError(null);
  }, [recordingId]);
  const job = useQuery({ queryKey: ["transcription", jobId], enabled: !!jobId,
    queryFn: () => api.transcription(jobId!),
    refetchInterval: (query) => ["queued", "processing"].includes(query.state.data?.status || "") ? 1000 : false,
  });
  useEffect(() => {
    const data = job.data;
    if (!data || data.recording_id !== recordingId) return;
    if (data.status === "completed" && accepted.current !== data.id) {
      accepted.current = data.id; callback.current(data.transcript);
      localStorage.removeItem(`vocalis-transcription-${recordingId}`);
    }
    if (["failed", "cancelled"].includes(data.status)) localStorage.removeItem(`vocalis-transcription-${recordingId}`);
  }, [job.data, recordingId]);
  const active = ["queued", "processing"].includes(job.data?.status || "") || (!!jobId && job.isPending);
  const generate = async () => {
    if (!recordingId) return;
    setBusy(true); setError(null);
    try { const data = await api.transcribe(recordingId); localStorage.setItem(`vocalis-transcription-${recordingId}`, data.id); setJobId(data.id); }
    catch (e) { setError(e as Error); }
    finally { setBusy(false); }
  };
  const cancel = async () => {
    if (!jobId) return;
    setBusy(true); setError(null);
    try { await api.cancelTranscription(jobId); await job.refetch(); }
    catch (e) { setError(e as Error); }
    finally { setBusy(false); }
  };
  if (!provider.data?.automatic_transcription) return null;
  return <div className="transcript-draft">
    <ErrorNotice error={error || job.error || (job.data?.status === "failed" ? new Error(job.data.error_summary || "Transcription failed.") : null)} />
    <div className="row wrap">
      <Button type="button" variant="secondary" disabled={!recordingId || busy || active} onClick={() => void generate()}><FileAudio size={16} /> {busy || active ? "Transcribing locally…" : "Generate transcript"}</Button>
      {active && <Button type="button" variant="ghost" disabled={busy} onClick={() => void cancel()}><Square size={14} /> Cancel</Button>}
    </div>
    <p className="tiny muted" role="status">{active ? "CPU processing continues if you leave this page. If the first model cannot recover a reliable draft, a larger local model is tried. The first run may load model files." : `${job.data?.status === "completed" ? `Draft generated locally with ${job.data.model_name}. ` : ""}Review the generated words against the full recording; words may be missing or wrong. Spell out numbers and confirm the same text as your reference.`}</p>
  </div>;
}
