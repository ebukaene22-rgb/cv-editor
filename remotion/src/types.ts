export interface ScriptScores {
  instinct: number;
  iq: number;
  gravity: number;
}

// Per-axis qualitative evidence shown on screen as the score is revealed.
// The number lives in `scores`; this carries the justification + benchmark
// that makes the score feel earned rather than arbitrary.
export interface AxisEvidence {
  evidence: string;    // one-line justification ("First step fires before...")
  percentile: string;  // benchmark chip ("TOP 5% IN TRANSITION")
}

export interface ScriptAxes {
  instinct: AxisEvidence;
  iq: AxisEvidence;
  gravity: AxisEvidence;
}

export interface ScriptBeats {
  hook: string;
  profile: string;
  verdict: string;
  loop: string;
}

export type VideoFormat =
  | "player-profile"
  | "player-comparison"
  | "team-top-transfers"
  | "player-best-moves";

export interface ScriptData {
  player: string;
  format: VideoFormat;
  scores: ScriptScores;
  context_risk: number;
  transferability: number;
  beats: ScriptBeats;
  word_count: number;
  // V2 verdict-first fields (optional; scenes fall back if absent).
  verdict_hook?: string;   // the 0-2s accusation, e.g. "TRANSFER TRAP?"
  verdict_label?: string;  // final verdict, e.g. "SYSTEM-DEPENDENT WEAPON"
  axes?: ScriptAxes;       // per-axis evidence + benchmark
  player_image_key?: string;
}
