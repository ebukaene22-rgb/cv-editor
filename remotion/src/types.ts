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

// Annotation drawn on a frozen clip frame (SVG coordinate space: 0-100 wide, 0-177 tall for 9:16)
export interface ClipAnnotation {
  type: "circle" | "arrow" | "zone";
  x: number;
  y: number;
  r?: number;     // circle radius (default 6)
  x2?: number;    // arrow end x
  y2?: number;    // arrow end y
  w?: number;     // zone width
  h?: number;     // zone height
  label?: string;
  color?: string; // defaults to accent red
}

export interface ClipZoom {
  x: number;       // focal point x (0-100, % of clip width)
  y: number;       // focal point y (0-100, % of clip height)
  scale: number;   // final zoom scale at freeze, e.g. 1.4
}

export interface ClipSpec {
  src: string;        // relative to remotion/public/, e.g. "clips/instinct.mp4"
  freezeAt: number;   // seconds into clip to freeze for annotation
  annotations: ClipAnnotation[];
  zoom?: ClipZoom;    // optional Ken Burns zoom toward the evidence
}

export interface EpisodeClips {
  claim?: ClipSpec;
  tension?: ClipSpec;
  instinct?: ClipSpec;
  iq?: ClipSpec;
  gravity?: ClipSpec;
}

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
  // V6: evidence clips injected by CI after fetch_clips.py runs
  clips?: EpisodeClips;
}
