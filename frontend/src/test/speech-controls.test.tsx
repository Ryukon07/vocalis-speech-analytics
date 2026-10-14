import { render, screen, fireEvent, waitFor, act, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import SpokenFeedback from "../components/audio/SpokenFeedback";
import MicrophoneRecorder from "../components/audio/MicrophoneRecorder";
import { api } from "../api/client";

let utterances: TestUtterance[];
class TestUtterance {
  text: string; lang = ""; rate = 1; voice = null;
  onstart?: () => void; onend?: () => void; onerror?: (event: { error: string }) => void;
  constructor(text: string) { this.text = text; }
}
let synthesis: { cancel: ReturnType<typeof vi.fn>; speak: ReturnType<typeof vi.fn>; getVoices: ReturnType<typeof vi.fn> };
let track: { stop: ReturnType<typeof vi.fn>; addEventListener: ReturnType<typeof vi.fn> };
let capture: { port: { onmessage: ((event: { data: Float32Array }) => void) | null }; connect: ReturnType<typeof vi.fn>; disconnect: ReturnType<typeof vi.fn> };
let context: { sampleRate: number; state: string; resume: ReturnType<typeof vi.fn>; close: ReturnType<typeof vi.fn>; audioWorklet: { addModule: ReturnType<typeof vi.fn> }; createGain: () => unknown; createMediaStreamSource: () => unknown };
let getUserMedia: ReturnType<typeof vi.fn>;

beforeEach(() => {
  utterances = [];
  synthesis = { cancel: vi.fn(), speak: vi.fn((u: TestUtterance) => utterances.push(u)), getVoices: vi.fn(() => [{ lang: "en-US", localService: true }]) };
  vi.stubGlobal("speechSynthesis", synthesis); vi.stubGlobal("SpeechSynthesisUtterance", TestUtterance);
  track = { stop: vi.fn(), addEventListener: vi.fn() };
  getUserMedia = vi.fn().mockResolvedValue({ getTracks: () => [track], getAudioTracks: () => [track] });
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
  capture = { port: { onmessage: null }, connect: vi.fn(), disconnect: vi.fn() };
  context = { sampleRate: 16000, state: "running", resume: vi.fn().mockResolvedValue(undefined), close: vi.fn().mockResolvedValue(undefined), audioWorklet: { addModule: vi.fn().mockResolvedValue(undefined) }, createGain: () => ({ gain: { value: 1 }, connect: vi.fn() }), createMediaStreamSource: () => ({ connect: vi.fn() }) };
  vi.stubGlobal("AudioContext", class { constructor() { return context; } });
  vi.stubGlobal("AudioWorkletNode", class { constructor() { return capture; } });
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:test") });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

test("spoken feedback uses a local voice, stops and ignores stale callbacks", () => {
  const { rerender } = render(<SpokenFeedback text="First feedback." />);
  fireEvent.click(screen.getByRole("button", { name: "Listen to feedback" }));
  expect(utterances[0].voice).toEqual({ lang: "en-US", localService: true });
  expect(screen.getByRole("button", { name: "Stop reading" })).toBeInTheDocument();
  const first = utterances[0];
  rerender(<SpokenFeedback text="Changed feedback." />);
  expect(screen.getByRole("button", { name: "Listen to feedback" })).toBeInTheDocument();
  act(() => first.onend?.());
  expect(utterances).toHaveLength(1);
});

test("spoken feedback chunks long reports and surfaces voice failures", () => {
  render(<SpokenFeedback text={"A useful measured recommendation. ".repeat(20)} />);
  fireEvent.click(screen.getByRole("button", { name: "Listen to feedback" }));
  expect(utterances[0].text.length).toBeLessThanOrEqual(180);
  act(() => utterances[0].onend?.()); expect(utterances).toHaveLength(2);
  act(() => utterances[1].onerror?.({ error: "audio-busy" }));
  expect(screen.getByRole("alert")).toHaveTextContent("audio-busy");
  expect(screen.getByRole("button", { name: "Listen to feedback" })).toBeInTheDocument();
});

test("spoken feedback reports a voice that fails to start", () => {
  vi.useFakeTimers(); render(<SpokenFeedback text="Read this feedback." />);
  fireEvent.click(screen.getByRole("button", { name: "Listen to feedback" }));
  act(() => vi.advanceTimersByTime(8000));
  expect(screen.getByRole("alert")).toHaveTextContent("did not start");
});

test("spoken feedback does not send text to a remote voice", () => {
  synthesis.getVoices.mockReturnValue([{ lang: "en-US", localService: false }]);
  render(<SpokenFeedback text="Private local feedback." />);
  fireEvent.click(screen.getByRole("button", { name: "Listen to feedback" }));
  expect(synthesis.speak).not.toHaveBeenCalled();
  expect(screen.getByRole("alert")).toHaveTextContent("No local English speech voice");
});

async function startCapture() {
  fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
  await waitFor(() => expect(screen.getByRole("button", { name: /Stop/ })).toBeInTheDocument());
}

test("microphone captures PCM, releases the device and uploads the preview", async () => {
  const change = vi.fn(); const saved = { id: "saved" };
  const upload = vi.spyOn(api, "upload").mockResolvedValue(saved as never);
  render(<MicrophoneRecorder onChange={change} />); await startCapture();
  act(() => capture.port.onmessage?.({ data: new Float32Array(16000).fill(.1) }));
  fireEvent.click(screen.getByRole("button", { name: /Stop/ }));
  expect(track.stop).toHaveBeenCalled(); expect(context.close).toHaveBeenCalled();
  expect(screen.getByLabelText("Preview microphone recording")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Use this recording" }));
  await waitFor(() => expect(change).toHaveBeenCalledWith(saved));
  expect(upload.mock.calls[0][0].type).toBe("audio/wav");
  expect(upload.mock.calls[0][0].size).toBe(32044);
});

test("microphone rejects silence and allows a new recording", async () => {
  render(<MicrophoneRecorder onChange={vi.fn()} />); await startCapture();
  act(() => capture.port.onmessage?.({ data: new Float32Array(16000) }));
  fireEvent.click(screen.getByRole("button", { name: /Stop/ }));
  expect(screen.getByRole("alert")).toHaveTextContent("No usable microphone signal");
  expect(screen.queryByLabelText("Preview microphone recording")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Start recording" })).toBeEnabled();
});

test("microphone handles denied permission without leaking resources", async () => {
  getUserMedia.mockRejectedValue(Object.assign(new Error("denied"), { name: "NotAllowedError" }));
  render(<MicrophoneRecorder onChange={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("permission was denied"));
  expect(screen.getByRole("button", { name: "Start recording" })).toBeEnabled();
});

test("microphone releases the device when leaving the page", async () => {
  const { unmount } = render(<MicrophoneRecorder onChange={vi.fn()} />); await startCapture();
  unmount(); expect(track.stop).toHaveBeenCalled(); expect(capture.port.onmessage).toBeNull();
});
