import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";
import DatasetManagerPage from "../pages/DatasetManagerPage";
import { ToastProvider } from "../components/ui";
import { api } from "../api/client";

vi.mock("../components/audio/AudioPlayer", () => ({ default: () => <div /> }));
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

async function loadSavedLabel(type: string) {
  const record = { id: "record", original_filename: "pause.wav", duration_seconds: 14.3 };
  const label = { id: "label", recording_id: "record", flaw_type: type, start_seconds: 3.125,
    end_seconds: 5.846, severity: 4, source: "controlled_edit", notes: "Exact bounds" };
  const page = (items: unknown[]) => ({ items, total: items.length, offset: 0, limit: 20 });
  vi.spyOn(api, "groups").mockResolvedValue(page([]) as never);
  vi.spyOn(api, "recordings").mockResolvedValue(page([record]) as never);
  vi.spyOn(api, "annotations").mockResolvedValue(page([label]) as never);
  const save = vi.spyOn(api, "saveAnnotation").mockResolvedValue(label as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ToastProvider><DatasetManagerPage /></ToastProvider></QueryClientProvider>);
  await screen.findByRole("option", { name: "pause.wav" });
  fireEvent.change(screen.getByLabelText("Recording to annotate"), { target: { value: "record" } });
  fireEvent.click(await screen.findByRole("button", { name: new RegExp(type + " ·") }));
  return { save, label };
}

test("saved controlled pause labels display correctly and preserve their type when edited", async () => {
  const { save, label } = await loadSavedLabel("awkward_pause");
  expect(screen.getByLabelText("Flaw type")).toHaveValue("awkward_pause");
  expect(screen.getByLabelText("Start (seconds)")).toHaveValue(3.125);
  expect(screen.getByLabelText("End (seconds)")).toHaveValue(5.846);
  fireEvent.click(screen.getByRole("button", { name: "Update annotation" }));
  await waitFor(() => expect(save).toHaveBeenCalledWith(expect.objectContaining({
    flaw_type: label.flaw_type, start_seconds: label.start_seconds, end_seconds: label.end_seconds,
  }), "label"));
});

test("existing custom labels remain selectable instead of silently displaying another type", async () => {
  await loadSavedLabel("custom_delivery_label");
  expect(screen.getByLabelText("Flaw type")).toHaveValue("custom_delivery_label");
  expect(screen.getByRole("option", { name: "custom delivery label (saved label)" })).toBeInTheDocument();
});
