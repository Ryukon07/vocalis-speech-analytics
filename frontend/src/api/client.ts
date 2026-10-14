import type {
  Page,
  Recording,
  Reference,
  Rubric,
  Analysis,
  AnalysisCreate,
  AnalysisResult,
  Provider,
  Capabilities,
  Group,
  Variant,
  Annotation,
  Dashboard,
  Transcription,
} from "../types";
export const base = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1"
).replace(/\/$/, "");
export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(base + path, {
      ...options,
      headers: {
        ...(options.body && !(options.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new ApiError(
      "NETWORK_ERROR",
      "Cannot reach the backend. Check that the API is running.",
      0,
    );
  }
  if (!response.ok) {
    const value = await response.json().catch(() => ({}));
    throw new ApiError(
      value.error?.code || "API_ERROR",
      value.error?.details
        ?.map(
          (d: { field: string; message: string }) => `${d.field}: ${d.message}`,
        )
        .join("; ") ||
        value.error?.message ||
        "Request failed.",
      response.status,
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
const json = (method: string, value: unknown) => ({
  method,
  body: JSON.stringify(value),
});
export const audioUrl = (id: string) =>
  `${base}/recordings/${encodeURIComponent(id)}/audio`;
export const exportUrl = (id: string, format: "json" | "csv" | "pdf") =>
  `${base}/analyses/${encodeURIComponent(id)}/export/${format}`;
export const api = {
  provider: () => request<Provider>("/providers"),
  capabilities: () => request<Capabilities>("/providers/capabilities"),
  dashboard: () => request<Dashboard>("/dashboard"),
  recordings: (query = "") => request<Page<Recording>>("/recordings" + query),
  recording: (id: string) => request<Recording>(`/recordings/${id}`),
  transcribe: (id: string) => request<Transcription>(`/recordings/${id}/transcriptions`, { method: "POST" }),
  transcription: (id: string) => request<Transcription>(`/transcriptions/${id}`),
  cancelTranscription: (id: string) => request<Transcription>(`/transcriptions/${id}/cancel`, { method: "POST" }),
  upload: (file: File, category = "participant") => {
    const data = new FormData();
    data.append("file", file);
    data.append("category", category);
    return request<Recording>("/recordings", { method: "POST", body: data });
  },
  patchRecording: (id: string, data: Partial<Recording>) =>
    request<Recording>(`/recordings/${id}`, json("PATCH", data)),
  deleteRecording: (id: string) =>
    request<void>(`/recordings/${id}`, { method: "DELETE" }),
  references: (query = "") => request<Page<Reference>>("/references" + query),
  reference: (id: string) => request<Reference>(`/references/${id}`),
  saveReference: (
    data: Omit<Reference, "id" | "created_at" | "updated_at">,
    id?: string,
  ) =>
    request<Reference>(
      id ? `/references/${id}` : "/references",
      json(id ? "PATCH" : "POST", data),
    ),
  deleteReference: (id: string) =>
    request<void>(`/references/${id}`, { method: "DELETE" }),
  rubrics: () => request<Page<Rubric>>("/rubrics?limit=100"),
  saveRubric: (
    data: Pick<Rubric, "name" | "weights" | "enabled_categories">,
    id?: string,
  ) =>
    request<Rubric>(
      id ? `/rubrics/${id}` : "/rubrics",
      json(id ? "PATCH" : "POST", data),
    ),
  deleteRubric: (id: string) =>
    request<void>(`/rubrics/${id}`, { method: "DELETE" }),
  analyses: (query = "") => request<Page<Analysis>>("/analyses" + query),
  analysis: (id: string) => request<Analysis>(`/analyses/${id}`),
  createAnalysis: (data: AnalysisCreate, key: string) =>
    request<Analysis>("/analyses", {
      ...json("POST", data),
      headers: { "Idempotency-Key": key },
    }),
  result: (id: string) => request<AnalysisResult>(`/analyses/${id}/result`),
  retry: (id: string) =>
    request<Analysis>(`/analyses/${id}/retry`, { method: "POST" }),
  cancel: (id: string) =>
    request<Analysis>(`/analyses/${id}/cancel`, { method: "POST" }),
  deleteAnalysis: (id: string) =>
    request<void>(`/analyses/${id}`, { method: "DELETE" }),
  groups: (query = "") => request<Page<Group>>("/datasets/groups" + query),
  saveGroup: (data: Omit<Group, "id" | "variants">, id?: string) =>
    request<Group>(
      id ? `/datasets/groups/${id}` : "/datasets/groups",
      json(id ? "PATCH" : "POST", data),
    ),
  deleteGroup: (id: string) =>
    request<void>(`/datasets/groups/${id}`, { method: "DELETE" }),
  addVariant: (id: string, data: Omit<Variant, "id" | "group_id">) =>
    request<Variant>(`/datasets/groups/${id}/variants`, json("POST", data)),
  deleteVariant: (group: string, id: string) =>
    request<void>(`/datasets/groups/${group}/variants/${id}`, {
      method: "DELETE",
    }),
  annotations: (query = "") =>
    request<Page<Annotation>>("/datasets/annotations" + query),
  saveAnnotation: (data: Omit<Annotation, "id">, id?: string) =>
    request<Annotation>(
      id ? `/datasets/annotations/${id}` : "/datasets/annotations",
      json(id ? "PATCH" : "POST", data),
    ),
  deleteAnnotation: (id: string) =>
    request<void>(`/datasets/annotations/${id}`, { method: "DELETE" }),
};
