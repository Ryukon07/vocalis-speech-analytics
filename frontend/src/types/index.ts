export type Category = "pacing" | "pitch" | "energy" | "pausing" | "clarity";
export type Status =
  | "queued"
  | "processing"
  | "completed"
  | "failed"
  | "cancelled";
export type Mode = "recording" | "profile";
export interface Page<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}
export interface Recording {
  id: string;
  original_filename: string;
  title: string;
  mime_type: string;
  file_size: number;
  duration_seconds: number | null;
  sample_rate: number | null;
  channels: number | null;
  transcript: string;
  speaker_id: string;
  source_url: string;
  license: string;
  notes: string;
  language: string;
  recording_date: string | null;
  category: string;
  created_at: string;
  updated_at: string;
}
export interface Reference {
  id: string;
  title: string;
  recording_id: string;
  transcript: string;
  speaker_id: string;
  source_url: string;
  license: string;
  eligible: boolean;
  profile: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}
export interface Rubric {
  id: string;
  name: string;
  weights: Record<Category, number>;
  enabled_categories: Category[];
  version: number;
  created_at: string;
  updated_at: string;
}
export interface AnalysisSettings {
  comparison_mode: Mode;
  enabled_categories: Category[];
  sensitivity: number;
  window_seconds: number;
  overlap: number;
  detailed_plots: boolean;
}
export interface AnalysisCreate {
  participant_recording_id: string;
  reference_id: string | null;
  rubric_id: string;
  transcript: string;
  transcript_mode: "manual" | "automatic";
  settings: AnalysisSettings;
}
export interface Analysis {
  id: string;
  participant_recording_id: string;
  participant_filename: string;
  reference_id: string | null;
  reference_title: string;
  rubric_id: string;
  rubric_snapshot: Rubric;
  transcript: string;
  settings: AnalysisSettings;
  status: Status;
  execution_mode: "mock" | "real";
  provider_name: string;
  provider_version: string;
  progress_stage: string;
  progress_percent: number;
  created_at: string;
  completed_at: string | null;
  error_code: string | null;
  error_summary: string | null;
  overall_score: number | null;
  flaw_count: number;
}
export interface Evidence {
  baseline_value: number | null;
  participant_value: number | null;
  absolute_deviation: number | null;
  difference_percent: number | null;
  normalized_deviation: number | null;
  units: string;
  measurement_name: string;
  source: "measured" | "mock";
  additional: Record<string, number | null>;
}
export interface Flaw {
  id: string;
  category: Category;
  type: string;
  start_seconds: number;
  end_seconds: number;
  severity: number;
  confidence: number | null;
  transcript_text: string | null;
  evidence: Evidence;
  interpretation_source: "model" | "rule" | "generated" | "mock";
  explanation: string;
  recommendation: string;
}
export interface Point {
  time_seconds: number;
  value: number | null;
}
export interface Series {
  unit: string;
  reference: Point[];
  participant: Point[];
  time_axis: "recording" | "participant_aligned";
  window_metadata: Record<string, unknown>;
}
export interface Word {
  text: string;
  start_seconds: number;
  end_seconds: number;
  confidence: number | null;
}
export interface AnalysisResult {
  analysis_id: string;
  provider_name: string;
  provider_version: string;
  execution_mode: "mock" | "real";
  status: "completed";
  participant_duration_seconds: number | null;
  reference_duration_seconds: number | null;
  scores: {
    overall: number | null;
    dimensions: Partial<Record<Category, number | null>>;
  };
  flaws: Flaw[];
  feature_series: Record<string, Series>;
  alignment: { words: Word[] };
  warnings: string[];
  clarity?: {
    available: boolean; method: string; model_name: string; score: number | null;
    confirmed_word_count: number; minimum_word_count: number; maximum_reference_wer: number;
    reference_text: string; participant_text: string;
    reference: { word_error_rate: number | null; errors: number; substitutions: number; deletions: number; insertions: number };
    participant: { word_error_rate: number | null; errors: number; substitutions: number; deletions: number; insertions: number };
    excess_word_error_rate: number | null; reason: string | null;
  } | null;
}
export interface Provider {
  configured_provider: string;
  ready: boolean;
  execution_mode: "mock" | "real" | null;
  provider_version?: string;
  message: string;
  app_version: string;
  max_upload_mb: number;
  single_user: boolean;
}
export interface Capabilities {
  provider_name: string;
  provider_version: string;
  execution_mode: "mock" | "real";
  ready: boolean;
  requires_transcript: boolean;
  requires_reference: boolean;
  automatic_transcription: boolean;
  comparison_modes: Mode[];
  categories: Category[];
  supports_windows: boolean;
  supports_cancellation: boolean;
  message: string;
}
export interface Transcription {
  id: string; recording_id: string; status: Status; transcript: string;
  language: string; model_name: string; error_summary: string | null;
}
export interface Variant {
  id: string;
  group_id: string;
  recording_id: string;
  level: number;
  flaw_labels: string[];
  speaker_id: string;
  provenance: string;
}
export interface Group {
  source_id?: string;
  id: string;
  title: string;
  reference_recording_id: string;
  transcript: string;
  transcript_version: string;
  speaker_id: string;
  split: "training" | "validation" | "testing";
  provenance: string;
  variants: Variant[];
}
export interface Annotation {
  id: string;
  recording_id: string;
  flaw_type: string;
  start_seconds: number;
  end_seconds: number;
  severity: number;
  source: string;
  notes: string;
}
export interface Dashboard {
  total: number;
  completed: number;
  real_completed: number;
  average_score: number | null;
  references: number;
  groups: number;
  frequent_flaws: { type: string; count: number }[];
  recent: Analysis[];
}
