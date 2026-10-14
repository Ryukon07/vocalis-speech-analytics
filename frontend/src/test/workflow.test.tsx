import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "../components/ui";
import AnalyzeSpeechPage from "../pages/AnalyzeSpeechPage";
test("continuing to review never submits; only the final action creates a job", async () => {
  const user = userEvent.setup();
  let created = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, options) => {
    const path = String(input);
    let data: unknown = {};
    if (path.endsWith("/providers"))
      data = { ready: true, execution_mode: "mock", max_upload_mb: 50 };
    else if (path.endsWith("/providers/capabilities"))
      data = {
        provider_name: "mock",
        provider_version: "1",
        execution_mode: "mock",
        ready: true,
        requires_transcript: true,
        requires_reference: true,
        automatic_transcription: false,
        comparison_modes: ["recording"],
        categories: ["pacing", "pitch", "energy", "pausing"],
        supports_windows: true,
      };
    else if (path.includes("/recordings"))
      data = {
        items: [
          {
            id: "recording",
            original_filename: "sample.wav",
            transcript: "A meaningful idea.",
            file_size: 1000,
            mime_type: "audio/wav",
            duration_seconds: 3,
          },
        ],
      };
    else if (path.includes("/references"))
      data = {
        items: [
          {
            id: "reference",
            title: "Strong delivery",
            transcript: "A meaningful idea.",
            license: "CC0",
            eligible: true,
          },
        ],
      };
    else if (path.includes("/rubrics"))
      data = {
        items: [
          {
            id: "rubric",
            name: "Balanced",
            version: 1,
            weights: { pacing: 25, pitch: 25, energy: 25, pausing: 25 },
            enabled_categories: ["pacing", "pitch", "energy", "pausing"],
          },
        ],
      };
    else if (path.endsWith("/analyses") && options?.method === "POST") {
      created++;
      data = { id: "created-job" };
    }
    return new Response(JSON.stringify(data), { status: 200 });
  });
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <ToastProvider>
          <AnalyzeSpeechPage />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await screen.findByRole("option", { name: "sample.wav" });
  await user.selectOptions(
    screen.getByRole("combobox", { name: /saved recording/ }),
    "recording",
  );
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await screen.findByText("Give your speech its words");
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await screen.findByRole("combobox", { name: /Reference speech/ });
  await user.selectOptions(
    screen.getByRole("combobox", { name: /Reference speech/ }),
    "reference",
  );
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await screen.findByRole("combobox", { name: /Evaluation rubric/ });
  await user.selectOptions(
    screen.getByRole("combobox", { name: /Evaluation rubric/ }),
    "rubric",
  );
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await screen.findByText("Ready for a closer look?");
  expect(created).toBe(0);
  await user.click(screen.getByRole("button", { name: "Analyze Speech" }));
  await waitFor(() => expect(created).toBe(1));
});
