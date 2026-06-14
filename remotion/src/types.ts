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
  // V3 story-first beats — five acts in order.
  claim:    string;   // 0-5s:  one punchy sentence that poses the case
  tension:  string;   // 5-15s: why the popular take is wrong
  evidence: string;   // 15-30s: Instinct/IQ/Gravity as supporting exhibits
  reveal:   string;   // 30-40s: transferability + consequence
  loop:     string;   // 40-50s: polarising comment trigger
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
  verdict_hook?: string;   // accusation stamp, e.g. "TRANSFER TRAP?" (thumbnail hero)
  verdict_label?: string;  // resolved verdict, e.g. "SYSTEM-DEPENDENT WEAPON"
  axes?: ScriptAxes;       // per-axis evidence + benchmark
  image_query?: string;    // Wikipedia search hint for automated player image fetch
  player_image_key?: string;
  // V3: planning artifact — four tweet-style lines before converting to video.
  // [hook_tweet, tension_tweet, evidence_tweet, resolution_tweet]
  thread?: string[];
}
