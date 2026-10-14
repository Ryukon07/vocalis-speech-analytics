import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, SlidersHorizontal, Cpu } from "lucide-react";
import { api } from "../api/client";
import type { Rubric, Category } from "../types";
import { categories, labels, brand } from "../config/brand";
import { rubricError } from "../lib/validation";
import { useAction } from "../hooks/useAction";
import {
  Button,
  Card,
  PageTitle,
  Modal,
  Confirm,
  ErrorNotice,
  Loading,
  Empty,
} from "../components/ui";
type RubricData = Pick<Rubric, "name" | "weights" | "enabled_categories">;
const initial: RubricData = {
  name: "Balanced delivery",
  weights: { pacing: 25, pitch: 20, energy: 20, pausing: 15, clarity: 20 },
  enabled_categories: ["pacing", "pitch", "energy", "pausing", "clarity"],
};
export default function SettingsPage() {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<string>();
  const [form, setForm] = useState<RubricData>(initial);
  const [deleting, setDeleting] = useState<string>();
  const [display, setDisplay] = useState(
    localStorage.getItem("vocalis-display") || "comfortable",
  );
  const [mode, setMode] = useState(
    localStorage.getItem("vocalis-mode") || "recording",
  );
  const provider = useQuery({ queryKey: ["provider"], queryFn: api.provider });
  const caps = useQuery({
    queryKey: ["capabilities"],
    queryFn: api.capabilities,
    retry: false,
  });
  const rubrics = useQuery({ queryKey: ["rubrics"], queryFn: api.rubrics });
  const save = useAction(
    (data: RubricData) => api.saveRubric(data, editing),
    "Rubric saved. Future jobs use the new version.",
    () => setOpen(false),
  );
  const del = useAction(
    (id: string) => api.deleteRubric(id),
    "Rubric deleted.",
    () => setDeleting(undefined),
  );
  const error = rubricError(form.weights, form.enabled_categories);
  const toggle = (c: Category) =>
    setForm((f) => ({
      ...f,
      enabled_categories: f.enabled_categories.includes(c)
        ? f.enabled_categories.filter((v) => v !== c)
        : [...f.enabled_categories, c],
    }));
  return (
    <>
      <PageTitle
        eyebrow="WORKSPACE CONFIGURATION"
        title="Settings & rubrics"
        description="Make evaluation transparent, consistent and easy to reproduce."
      />
      <div className="grid-two">
        <Card>
          <div className="section-title">
            <h2>Analysis provider</h2>
            <Cpu size={20} />
          </div>
          <ErrorNotice error={provider.error} />
          {provider.isPending ? (
            <Loading />
          ) : (
            <>
              <span
                className={`badge ${provider.data?.ready ? "status-completed" : "status-failed"}`}
              >
                {provider.data?.ready ? "Ready" : "Unavailable"}
              </span>
              <div className="review-list">
                {[
                  ["Provider", provider.data?.configured_provider],
                  ["Version", provider.data?.provider_version || "Unavailable"],
                  [
                    "Execution mode",
                    provider.data?.execution_mode || "Unavailable",
                  ],
                  ["App version", provider.data?.app_version || brand.version],
                ].map(([k, v]) => (
                  <div className="list-row" key={k}>
                    <span className="muted">{k}</span>
                    <strong>{v}</strong>
                  </div>
                ))}
              </div>
              <p className="muted">{provider.data?.message}</p>
              <p className="tiny muted">
                Choose the provider through backend environment configuration.
                Demo mode never silently replaces an unavailable real model.
              </p>
            </>
          )}
        </Card>
        <Card>
          <div className="section-title">
            <h2>Workspace preferences</h2>
            <SlidersHorizontal size={20} />
          </div>
          <label>
            Default comparison mode
            <select
              value={mode}
              onChange={(e) => {
                setMode(e.target.value);
                localStorage.setItem("vocalis-mode", e.target.value);
              }}
            >
              {(caps.data?.comparison_modes || ["recording"]).map((m) => (
                <option key={m} value={m}>
                  {m === "recording"
                    ? "Reference recording"
                    : "Processed profile"}
                </option>
              ))}
            </select>
          </label>
          <label>
            Display density
            <select
              value={display}
              onChange={(e) => {
                setDisplay(e.target.value);
                localStorage.setItem("vocalis-display", e.target.value);
                document.documentElement.dataset.density = e.target.value;
              }}
            >
              <option value="comfortable">Comfortable</option>
              <option value="compact">Compact</option>
            </select>
          </label>
          <p className="muted">
            Upload limit:{" "}
            <strong>{provider.data?.max_upload_mb ?? "—"} MB</strong>
          </p>
          <p className="tiny muted">
            Set MAX_UPLOAD_MB in the backend .env and restart to change the
            enforced limit. Display preferences are saved in this browser.
          </p>
          <p className="notice tiny">
            Single-user development prototype. Authentication and access
            isolation are required before a public multi-user deployment.
          </p>
        </Card>
      </div>
      <Card>
        <div className="section-title">
          <div>
            <h2>Evaluation rubrics</h2>
            <p className="muted">
              Enabled weights total 100%. Jobs retain a snapshot of the rubric
              they used.
            </p>
          </div>
          <Button
            onClick={() => {
              setEditing(undefined);
              setForm(initial);
              setOpen(true);
            }}
          >
            <Plus size={16} /> New rubric
          </Button>
        </div>
        <ErrorNotice error={rubrics.error} />
        {rubrics.isPending ? (
          <Loading />
        ) : !rubrics.data?.items.length ? (
          <Empty
            title="Define your first rubric"
            description="Create Balanced delivery with the suggested weights to begin."
          />
        ) : (
          rubrics.data.items.map((r) => (
            <div className="rubric-row" key={r.id}>
              <div className="row between">
                <h3>
                  {r.name} <span className="badge">v{r.version}</span>
                </h3>
                <div className="row">
                  <Button
                    variant="ghost"
                    aria-label="Edit rubric"
                    onClick={() => {
                      setEditing(r.id);
                      setForm({
                        name: r.name,
                        weights: r.weights,
                        enabled_categories: r.enabled_categories,
                      });
                      setOpen(true);
                    }}
                  >
                    <Pencil size={16} />
                  </Button>
                  <Button
                    variant="ghost"
                    aria-label="Delete rubric"
                    onClick={() => setDeleting(r.id)}
                  >
                    <Trash2 size={16} />
                  </Button>
                </div>
              </div>
              <div className="rubric-weights">
                {categories.map((c) => (
                  <div key={c}>
                    <span className="muted tiny">{labels[c]}</span>
                    <strong>
                      {r.enabled_categories.includes(c)
                        ? `${r.weights[c] ?? 0}%`
                        : "Disabled"}
                    </strong>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </Card>
      <Modal
        open={open}
        onOpenChange={setOpen}
        title={editing ? "Edit rubric" : "Create evaluation rubric"}
        description="Weights for enabled dimensions must total 100%. Existing analysis snapshots are preserved."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!error) save.mutate(form);
          }}
        >
          <ErrorNotice error={save.error} />
          <label>
            Rubric name
            <input
              required
              maxLength={255}
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
          </label>
          {categories.map((c) => (
            <div className="rubric-input" key={c}>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={form.enabled_categories.includes(c)}
                  onChange={() => toggle(c)}
                />
                {labels[c]}
              </label>
              <label>
                <span className="sr-only">{labels[c]} weight</span>
                <input
                  type="number"
                  required
                  min="0"
                  max="100"
                  step=".1"
                  value={form.weights[c] ?? 0}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      weights: { ...f.weights, [c]: Number(e.target.value) },
                    }))
                  }
                />
              </label>
              <span>%</span>
            </div>
          ))}
          <p className={error ? "field-error" : "notice"}>
            {error || "Weights validated · total 100%"}
          </p>
          <Button type="submit" disabled={!!error || save.isPending}>
            {save.isPending ? "Saving…" : "Save rubric"}
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
