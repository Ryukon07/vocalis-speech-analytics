import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  analysisFormSchema,
  rubricError,
  validateAudio,
} from "../lib/validation";
import { request } from "../api/client";
import { DemoBadge, ToastProvider } from "../components/ui";
import StatusBadge from "../components/analysis/StatusBadge";
import HistoryTable from "../components/analysis/HistoryTable";
import Transcript from "../components/analysis/Transcript";
import FeatureChart, { chartData } from "../components/charts/FeatureChart";
import App from "../App";
const wrapper = (children: React.ReactNode, route = "/") => (
  <QueryClientProvider
    client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
  >
    <MemoryRouter initialEntries={[route]}>
      <ToastProvider>{children}</ToastProvider>
    </MemoryRouter>
  </QueryClientProvider>
);
test("form requires inputs and rejects empty transcripts", () => {
  expect(
    analysisFormSchema.safeParse({
      recordingId: "",
      transcript: " ",
      referenceId: "",
      rubricId: "",
    }).success,
  ).toBe(false);
  expect(
    analysisFormSchema.safeParse({
      recordingId: "id",
      transcript: "Hello",
      referenceId: "ref",
      rubricId: "rubric",
    }).success,
  ).toBe(true);
});
test("rubric normalization and upload validation", () => {
  expect(rubricError({ pacing: 90 }, ["pacing"])).toMatch(/100/);
  expect(rubricError({ pacing: 100 }, ["pacing"])).toBeNull();
  expect(
    validateAudio(new File(["html"], "fake.wav", { type: "text/html" }), 50),
  ).toMatch(/WAV/);
  expect(
    validateAudio(new File(["a"], "good.wav", { type: "audio/wav" }), 50),
  ).toBeNull();
});
test("API errors preserve backend messages", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        error: { code: "UNSUPPORTED_INPUT", message: "Transcript required." },
      }),
      { status: 400 },
    ),
  );
  await expect(request("/analyses")).rejects.toThrow("Transcript required.");
});
test("network error explains connectivity", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(
    new TypeError("fetch failed"),
  );
  await expect(request("/providers")).rejects.toThrow(
    "Cannot reach the backend",
  );
});
test("history has useful empty state", () => {
  render(wrapper(<HistoryTable items={[]} />));
  expect(screen.getByText("No analyses yet")).toBeVisible();
  expect(
    screen.getByRole("link", { name: "Analyze a speech" }),
  ).toHaveAttribute("href", "/analyze");
});
test("status and demo label are explicit", () => {
  render(
    <>
      <StatusBadge status="processing" />
      <DemoBadge />
    </>,
  );
  expect(screen.getByText("Processing")).toBeVisible();
  expect(screen.getByText("DEMO / MOCK ANALYSIS")).toBeVisible();
});
test("missing features show unavailable and preserve null", () => {
  const series = {
    unit: "Hz",
    reference: [],
    participant: [{ time_seconds: 0, value: null }],
    time_axis: "recording" as const,
    window_metadata: {},
  };
  render(
    <FeatureChart
      name="pitch"
      series={series}
      flaws={[]}
      current={0}
      onSeek={() => {}}
    />,
  );
  expect(screen.getByText("pitch unavailable")).toBeVisible();
  expect(chartData(series)[0].participant).toBeNull();
});
test("word selection seeks to supplied timestamp", () => {
  const seek = vi.fn();
  render(
    <Transcript
      words={[
        {
          text: "Purpose",
          start_seconds: 2.4,
          end_seconds: 3,
          confidence: null,
        },
      ]}
      text=""
      current={0}
      flaws={[]}
      onSeek={seek}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Purpose" }));
  expect(seek).toHaveBeenCalledWith(2.4);
});
test("unaligned transcript fallback is readable", () => {
  render(
    <Transcript
      words={[]}
      text="A meaningful idea."
      current={0}
      flaws={[]}
      onSeek={() => {}}
    />,
  );
  expect(screen.getByText("Word alignment unavailable.")).toBeVisible();
  expect(screen.getByText("A meaningful idea.")).toBeVisible();
});
test("feature timestamps merge by time, not sample index", () => {
  expect(
    chartData({
      unit: "Hz",
      reference: [{ time_seconds: 1, value: 2 }],
      participant: [{ time_seconds: 1.5, value: 3 }],
      time_axis: "recording",
      window_metadata: {},
    }),
  ).toEqual([
    { time: 1, reference: 2 },
    { time: 1.5, participant: 3 },
  ]);
});
test("route smoke: dashboard displays empty data without invented score", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(
    async (input) =>
      new Response(
        JSON.stringify(
          String(input).endsWith("/dashboard")
            ? {
                total: 0,
                completed: 0,
                real_completed: 0,
                average_score: null,
                references: 0,
                groups: 0,
                frequent_flaws: [],
                recent: [],
              }
            : {
                ready: true,
                execution_mode: "mock",
                message: "Demo",
                app_version: "1.0.0",
                max_upload_mb: 50,
              },
        ),
        { status: 200 },
      ),
  );
  render(wrapper(<App />, "/dashboard"));
  await waitFor(() =>
    expect(screen.getByText("No analyses yet")).toBeVisible(),
  );
  expect(screen.getByText("Available after real model results")).toBeVisible();
});
