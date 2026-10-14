import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Upload, AudioLines, X } from "lucide-react";
import { api, audioUrl } from "../../api/client";
import type { Recording } from "../../types";
import { validateAudio, formatTime } from "../../lib/validation";
import { Button, ErrorNotice } from "../ui";
import MicrophoneRecorder from "../audio/MicrophoneRecorder";
export default function AudioUpload({
  value,
  onChange,
  category = "participant",
}: {
  value?: Recording | null;
  onChange: (value: Recording | null) => void;
  category?: string;
}) {
  const provider = useQuery({ queryKey: ["provider"], queryFn: api.provider });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const upload = async (file?: File) => {
    if (!file) return;
    const problem = validateAudio(file, provider.data?.max_upload_mb || 50);
    if (problem) {
      setError(new Error(problem));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onChange(await api.upload(file, category));
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <ErrorNotice error={error} />
      {value ? (
        <div className="uploaded-file">
          <div className="row">
            <AudioLines size={23} />
            <div>
              <strong>{value.original_filename}</strong>
              <p className="muted tiny">
                {(value.file_size / 1048576).toFixed(2)} MB · {value.mime_type}{" "}
                ·{" "}
                {value.duration_seconds == null
                  ? "Duration pending processing"
                  : formatTime(value.duration_seconds)}
              </p>
            </div>
            <Button
              variant="ghost"
              onClick={() => onChange(null)}
              aria-label="Remove selected audio"
            >
              <X size={18} />
            </Button>
          </div>
          <audio controls src={audioUrl(value.id)}>
            Audio playback is unavailable.
          </audio>
        </div>
      ) : (
        <label
          className={`upload-zone ${busy ? "busy" : ""}`}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            if (!busy) void upload(e.dataTransfer.files[0]);
          }}
        >
          <Upload size={27} />
          <strong>
            {busy ? "Uploading recording…" : "Drop your recording here"}
          </strong>
          <span className="muted">or click to browse your files</span>
          <span className="tiny muted">
            WAV, MP3, FLAC · up to {provider.data?.max_upload_mb || 50} MB
          </span>
          <input
            type="file"
            aria-label="Upload audio"
            accept=".wav,.mp3,.flac"
            disabled={busy}
            onChange={(e) => void upload(e.target.files?.[0])}
          />
        </label>
      )}
      {!value && <MicrophoneRecorder category={category} onChange={onChange} />}
    </>
  );
}
