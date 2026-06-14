export interface ScriptScores {
  instinct: number;
  iq: number;
  gravity: number;
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
  player_image_key?: string;
}
