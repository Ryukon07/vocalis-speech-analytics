import { encodeWav } from "../components/audio/MicrophoneRecorder";
import { describe, it, expect } from "vitest";

describe("microphone WAV encoding", () => {
  it("writes a mono PCM header and clips samples without wrapping", async () => {
    const blob = encodeWav(new Float32Array([-2, -1, 0, 1, 2]), 16000);
    const bytes = await new Promise<ArrayBuffer>((resolve) => {
      const reader = new FileReader(); reader.onload = () => resolve(reader.result as ArrayBuffer); reader.readAsArrayBuffer(blob);
    });
    const view = new DataView(bytes);
    expect(view.getUint32(24, true)).toBe(16000);
    expect(view.getUint16(22, true)).toBe(1);
    expect(view.getUint32(40, true)).toBe(10);
    expect(view.getInt16(44, true)).toBe(-32768);
    expect(view.getInt16(50, true)).toBe(32767);
    expect(view.getInt16(52, true)).toBe(32767);
  });
});
