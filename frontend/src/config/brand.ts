export const brand = {
  name: "Vocalis",
  tagline: "Speech intelligence",
  version: "3.1.3",
  description: "Understand every moment of your delivery.",
};
export const categories = [
  "pacing",
  "pitch",
  "energy",
  "pausing",
  "clarity",
] as const;
export const labels: Record<string, string> = {
  pacing: "Pacing & cadence",
  pitch: "Pitch & intonation",
  energy: "Energy & volume",
  pausing: "Pauses & timing",
  clarity: "Clarity · word recognition",
};
