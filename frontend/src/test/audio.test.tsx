import { createRef } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import AudioPlayer, { type AudioHandle } from "../components/audio/AudioPlayer";
const mocks = vi.hoisted(() => ({
  setTime: vi.fn(),
  destroy: vi.fn(),
  playPause: vi.fn().mockResolvedValue(undefined),
  handlers: {} as Record<string, (...args: unknown[]) => void>,
  regionHandlers: {} as Record<string, (...args: any[]) => void>,
  addRegion: vi.fn(),
}));
vi.mock("wavesurfer.js", () => ({
  default: {
    create: () => ({
      on: (event: string, callback: (...args: unknown[]) => void) => {
        mocks.handlers[event] = callback;
        if (event === "ready") callback();
      },
      getDuration: () => 18,
      setTime: mocks.setTime,
      destroy: mocks.destroy,
      playPause: mocks.playPause,
      setPlaybackRate: vi.fn(),
    }),
  },
}));
vi.mock("wavesurfer.js/dist/plugins/regions.esm.js", () => ({
  default: {
    create: () => ({
      on: (event: string, callback: (...args: any[]) => void) => {
        mocks.regionHandlers[event] = callback;
      },
      clearRegions: vi.fn(),
      addRegion: mocks.addRegion,
    }),
  },
}));
test("seek handle and region click use actual interval start", () => {
  const ref = createRef<AudioHandle>();
  const select = vi.fn();
  render(
    <AudioPlayer
      ref={ref}
      url="/test.wav"
      intervals={[{ id: "flaw", start_seconds: 4.2, end_seconds: 5.4 }]}
      onSelect={select}
    />,
  );
  ref.current?.seek(4.2);
  expect(mocks.setTime).toHaveBeenCalledWith(4.2);
  mocks.regionHandlers["region-clicked"](
    { id: "flaw", start: 4.2 },
    { stopPropagation: vi.fn() },
  );
  expect(select).toHaveBeenCalledWith("flaw");
  expect(mocks.addRegion).toHaveBeenCalledWith(
    expect.objectContaining({ start: 4.2, end: 5.4 }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Play audio" }));
  expect(mocks.playPause).toHaveBeenCalled();
});
