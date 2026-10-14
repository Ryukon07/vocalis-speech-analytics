import { z } from "zod";
export const analysisFormSchema = z.object({
  recordingId: z.string().min(1, "Upload or select a recording."),
  transcript: z.string().trim().min(1, "A transcript is required."),
  referenceId: z.string().min(1, "Select a reference."),
  rubricId: z.string().min(1, "Select a rubric."),
});
export type AnalysisForm = z.infer<typeof analysisFormSchema>;
export function validateAudio(file: File, maxMB: number): string | null {
  const ext = file.name.split(".").pop()?.toLowerCase();
  const mime = file.type;
  if (
    !["wav", "mp3", "flac"].includes(ext || "") ||
    ![
      "audio/wav",
      "audio/x-wav",
      "audio/wave",
      "audio/vnd.wave",
      "audio/mpeg",
      "audio/mp3",
      "audio/flac",
      "audio/x-flac",
    ].includes(mime)
  )
    return "Choose a WAV, MP3 or FLAC audio file.";
  if (!file.size) return "The audio file is empty.";
  if (file.size > maxMB * 1048576) return `The upload limit is ${maxMB} MB.`;
  return null;
}
export function rubricError(
  weights: Record<string, number>,
  enabled: string[],
): string | null {
  if (!enabled.length) return "Enable at least one category.";
  if (enabled.some((c) => !Number.isFinite(weights[c]) || weights[c] < 0))
    return "Weights must be finite, nonnegative numbers.";
  if (Math.abs(enabled.reduce((sum, c) => sum + weights[c], 0) - 100) > 0.001)
    return "Enabled weights must total 100%.";
  return null;
}
export const formatTime = (seconds: number) =>
  `${Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0")}:${(seconds % 60).toFixed(1).padStart(4, "0")}`;
export const formatDate = (value: string) =>
  new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
