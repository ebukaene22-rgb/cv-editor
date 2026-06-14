// Visual identity: cold, clinical, dark case-file aesthetic.
export const COLORS = {
  bg: "#0a0a0a",
  surface: "#111111",
  border: "#1e1e1e",
  accent: "#c8102e",       // cold red — verdict / score bars
  accentDim: "#7a0a1a",
  text: "#f0f0f0",
  textMuted: "#888888",
  textDim: "#444444",
  stamp: "#c8102e",
  scoreBar: "#c8102e",
  scoreBarBg: "#1e1e1e",
  gravity: "#4a90d9",      // gravity gets a distinct blue
  gravityDim: "#1a3a5c",
};

export const FONTS = {
  mono: "'Courier New', Courier, monospace",
  sans: "'Arial Narrow', Arial, sans-serif",
};

// 9:16 Shorts format
export const W = 1080;
export const H = 1920;
export const FPS = 30;

// Beat timing in seconds — mirrors structure-beats.md
export const BEAT_START = { hook: 0, profile: 10, verdict: 25, loop: 40 };
export const DURATION_S = 50;
