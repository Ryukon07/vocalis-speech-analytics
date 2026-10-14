import { useEffect, useRef, useState } from "react";
import { Mic, Square, RotateCcw, Upload } from "lucide-react";
import { api } from "../../api/client";
import type { Recording } from "../../types";
import { Button, ErrorNotice } from "../ui";

export function encodeWav(samples: Float32Array, rate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const text = (offset: number, value: string) => [...value].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
  text(0, "RIFF"); view.setUint32(4, 36 + samples.length * 2, true);
  text(8, "WAVE"); text(12, "fmt "); view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); view.setUint16(22, 1, true); view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  text(36, "data"); view.setUint32(40, samples.length * 2, true);
  samples.forEach((sample, i) => {
    const s = Math.max(-1, Math.min(1, sample));
    view.setInt16(44 + i * 2, Math.round(s * (s < 0 ? 32768 : 32767)), true);
  });
  return new Blob([buffer], { type: "audio/wav" });
}

export default function MicrophoneRecorder({ onChange, category = "participant" }: {
  onChange: (recording: Recording) => void; category?: string;
}) {
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [level, setLevel] = useState(0);
  const [preview, setPreview] = useState<string>();
  const [error, setError] = useState<Error | null>(null);
  const chunks = useRef<Float32Array[]>([]);
  const resource = useRef<{ stream: MediaStream; context: AudioContext; node: AudioWorkletNode } | undefined>(undefined);
  const blob = useRef<Blob | undefined>(undefined);
  const mounted = useRef(true);
  const starting = useRef(false);
  const sampleCount = useRef(0);
  const previewUrl = useRef<string | undefined>(undefined);

  const dispose = () => {
    const current = resource.current;
    if (current) {
      current.node.port.onmessage = null;
      current.node.disconnect();
      current.stream.getTracks().forEach((track) => track.stop());
      void current.context.close();
      resource.current = undefined;
    }
  };
  const reset = () => {
    if (previewUrl.current) URL.revokeObjectURL(previewUrl.current);
    previewUrl.current = undefined; blob.current = undefined; chunks.current = [];
    setPreview(undefined); setSeconds(0); setLevel(0);
  };
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; dispose(); if (previewUrl.current) URL.revokeObjectURL(previewUrl.current); };
  }, []);

  const stop = () => {
    const rate = resource.current?.context.sampleRate;
    if (!rate) return;
    dispose(); setRecording(false); setLevel(0);
    if (sampleCount.current < rate * 0.5) { setError(new Error("Record at least half a second of speech.")); return; }
    const samples = new Float32Array(sampleCount.current);
    let offset = 0;
    chunks.current.forEach((chunk) => { samples.set(chunk, offset); offset += chunk.length; });
    const rms = Math.sqrt(samples.reduce((sum, value) => sum + value * value, 0) / samples.length);
    if (rms < 0.0001) { chunks.current = []; setError(new Error("No usable microphone signal was captured. Check the input device, speak closer to it and record again.")); return; }
    blob.current = encodeWav(samples, rate); chunks.current = [];
    previewUrl.current = URL.createObjectURL(blob.current);
    setPreview(previewUrl.current);
  };
  const stopRef = useRef(stop); stopRef.current = stop;
  useEffect(() => {
    if (!recording) return;
    const timer = window.setInterval(() => {
      const rate = resource.current?.context.sampleRate || 48000;
      const elapsed = sampleCount.current / rate;
      setSeconds(elapsed);
      if (elapsed >= 180) stopRef.current();
    }, 200);
    return () => window.clearInterval(timer);
  }, [recording]);

  const start = async () => {
    if (starting.current) return;
    starting.current = true; setBusy(true); setError(null); reset(); sampleCount.current = 0;
    let stream: MediaStream | undefined;
    let context: AudioContext | undefined;
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Microphone access needs localhost or a secure HTTPS page.");
      if (!("AudioContext" in window) || !("AudioWorkletNode" in window)) throw new Error("This browser does not support microphone processing. Use a recent Chromium or Firefox browser.");
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
      if (!mounted.current) { stream.getTracks().forEach((t) => t.stop()); return; }
      context = new AudioContext(); await context.resume();
      const source = `class Capture extends AudioWorkletProcessor { process(inputs) { const x = inputs[0]?.[0]; if (x) this.port.postMessage(x.slice()); return true; } } registerProcessor('speech-capture', Capture);`;
      const url = URL.createObjectURL(new Blob([source], { type: "application/javascript" }));
      try { await context.audioWorklet.addModule(url); } finally { URL.revokeObjectURL(url); }
      if (!mounted.current) { stream.getTracks().forEach((t) => t.stop()); await context.close(); return; }
      const node = new AudioWorkletNode(context, "speech-capture");
      const silence = context.createGain(); silence.gain.value = 0;
      context.createMediaStreamSource(stream).connect(node); node.connect(silence); silence.connect(context.destination);
      node.port.onmessage = (event: MessageEvent<Float32Array>) => {
        const data = event.data;
        const max = Math.floor(context!.sampleRate * 180);
        if (sampleCount.current >= max) return;
        const chunk = data.slice(0, max - sampleCount.current);
        chunks.current.push(chunk); sampleCount.current += chunk.length;
        if (chunks.current.length % 30 === 0) setLevel(Math.min(1, Math.sqrt(chunk.reduce((sum, v) => sum + v * v, 0) / chunk.length) * 6));
      };
      resource.current = { stream, context, node };
      stream.getAudioTracks().forEach((track) => track.addEventListener("ended", () => { if (mounted.current && resource.current) stopRef.current(); }, { once: true }));
      node.onprocessorerror = () => { if (mounted.current) { stopRef.current(); setError(new Error("Microphone processing stopped unexpectedly. Record again or upload an audio file.")); } };
      setRecording(true);
    } catch (e) {
      stream?.getTracks().forEach((t) => t.stop()); if (context && context.state !== "closed") void context.close();
      if (mounted.current) setError(new Error((e as Error).name === "NotAllowedError" ? "Microphone permission was denied. Allow access in your browser and retry." : (e as Error).message));
    } finally { starting.current = false; if (mounted.current) setBusy(false); }
  };
  const upload = async () => {
    if (!blob.current) return;
    setBusy(true); setError(null);
    try { const saved = await api.upload(new File([blob.current], `speech-${Date.now()}.wav`, { type: "audio/wav" }), category); if (mounted.current) onChange(saved); }
    catch (e) { if (mounted.current) setError(e as Error); }
    finally { if (mounted.current) setBusy(false); }
  };
  return <div className="microphone-recorder">
    <ErrorNotice error={error} />
    <div className="row between wrap"><div><strong>Record your speech</strong><p className="tiny muted">Local microphone · up to 3 minutes · preview before saving</p></div>
      {recording ? <Button type="button" onClick={stop}><Square size={16} /> Stop · {seconds.toFixed(0)}s</Button> : !preview && <Button type="button" variant="secondary" disabled={busy} onClick={() => void start()}><Mic size={16} /> {busy ? "Opening microphone…" : "Start recording"}</Button>}
    </div>
    {recording && <><progress aria-label="Microphone level" max={1} value={level} /><p className="tiny muted" role="status">Recording… speak naturally and keep your microphone position steady.</p></>}
    {preview && <><audio controls src={preview} aria-label="Preview microphone recording" /><div className="row wrap"><Button type="button" disabled={busy} onClick={() => void upload()}><Upload size={16} /> {busy ? "Saving…" : "Use this recording"}</Button><Button type="button" variant="ghost" disabled={busy} onClick={reset}><RotateCcw size={16} /> Record again</Button></div></>}
  </div>;
}
