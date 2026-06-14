import { Composition } from "remotion";
import { CaseFile } from "./CaseFile";
import { FPS, W, H, DURATION_S } from "./theme";
import type { ScriptData } from "./types";

// Default props pulled from the Nico Williams first-draft script — override
// with --props at render time: remotion render ... --props='{"player": "..."}'
const DEFAULT_PROPS: ScriptData = {
  player: "Nico Williams",
  format: "player-profile",
  scores: { instinct: 9, iq: 6, gravity: 8 },
  context_risk: 13,
  transferability: 61,
  beats: {
    hook: "Forget his dribble count. Everyone calls Nico Williams a finished product. The tape opens a colder case. There's a fault line nobody scouts.",
    profile: "Instinct: nine. In transition, his first step fires before the defender's brain registers danger. Football IQ: a flat six. In structured low blocks he hesitates, takes the wrong half-space, kills his own overload. Gravity: eight. Defenders collapse toward him, bending the backline and freeing the weak side.",
    verdict: "Verdict: this is a transition predator, not a system orchestrator. Drop him into a possession side that asks him to break a parked bus, and the instinct has nothing to feed on. He's a system-dependent weapon. Transferability Score: sixty-one percent.",
    loop: "So is sixty-one percent a bargain, or are you buying a Ferrari with no road? Drop your verdict below.",
  },
  word_count: 129,
};

export const Root: React.FC = () => (
  <Composition
    id="CaseFile"
    component={CaseFile as unknown as React.ComponentType<Record<string, unknown>>}
    durationInFrames={DURATION_S * FPS}
    fps={FPS}
    width={W}
    height={H}
    defaultProps={DEFAULT_PROPS}
  />
);
