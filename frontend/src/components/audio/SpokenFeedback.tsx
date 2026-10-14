import { useEffect, useRef, useState } from "react";
import { Volume2, Square } from "lucide-react";
import { Button, ErrorNotice } from "../ui";

export default function SpokenFeedback({ text }: { text: string }) {
  const [speaking, setSpeaking] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const utterance = useRef<SpeechSynthesisUtterance | null>(null);
  const generation = useRef(0);
  const startTimer = useRef<number | undefined>(undefined);
  const supported = "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
  const stop = () => {
    generation.current += 1;
    window.clearTimeout(startTimer.current);
    utterance.current = null;
    if (supported) window.speechSynthesis.cancel();
    setSpeaking(false);
  };
  useEffect(() => {
    stop(); setError(null);
    if (supported) window.speechSynthesis.getVoices();
    return () => {
      generation.current += 1;
      window.clearTimeout(startTimer.current);
      utterance.current = null;
      if (supported) window.speechSynthesis.cancel();
    };
  }, [text, supported]);

  const speak = () => {
    stop(); setError(null);
    const token = generation.current;
    const chunks: string[] = [];
    // Short chunks avoid Chromium's long-utterance stalls. Hold each until completion.
    text.trim().split(/\s+/).forEach((word) => {
      if (!chunks.length || chunks[chunks.length - 1].length + word.length > 180) chunks.push(word);
      else chunks[chunks.length - 1] += ` ${word}`;
    });
    const read = (index: number) => {
      if (token !== generation.current) return;
      if (index >= chunks.length) { utterance.current = null; setSpeaking(false); return; }
      const next = new SpeechSynthesisUtterance(chunks[index]);
      next.lang = "en-US"; next.rate = 0.95;
      const voices = window.speechSynthesis.getVoices();
      const localEnglish = voices.find((voice) => voice.localService && /^en(?:-|$)/i.test(voice.lang));
      if (!localEnglish) {
        setError(new Error("No local English speech voice is available. Enable an English voice in your operating system to hear feedback offline."));
        setSpeaking(false); return;
      }
      if (localEnglish) next.voice = localEnglish;
      next.onstart = () => { if (token === generation.current) window.clearTimeout(startTimer.current); };
      next.onend = () => { if (token === generation.current) { window.clearTimeout(startTimer.current); read(index + 1); } };
      next.onerror = (event) => {
        if (token !== generation.current) return;
        stop();
        if (!["canceled", "interrupted"].includes(event.error)) setError(new Error(`Spoken feedback could not play (${event.error}). Check your audio output and retry.`));
      };
      utterance.current = next;
      startTimer.current = window.setTimeout(() => {
        if (token !== generation.current) return;
        stop(); setError(new Error("The speech voice did not start. Check that a local English voice and audio output are available, then retry."));
      }, 8000);
      try { window.speechSynthesis.speak(next); }
      catch { stop(); setError(new Error("Spoken feedback could not start. Check your browser's speech support and audio output.")); }
    };
    setSpeaking(true); read(0);
  };
  return <div>
    <Button type="button" variant="secondary" disabled={!supported || !text.trim()} onClick={() => speaking ? stop() : speak()} aria-pressed={speaking}>
      {speaking ? <Square size={16} /> : <Volume2 size={16} />} {speaking ? "Stop reading" : "Listen to feedback"}
    </Button>
    {!supported && <p className="tiny muted">Spoken feedback is unavailable in this browser.</p>}
    <ErrorNotice error={error} />
  </div>;
}
