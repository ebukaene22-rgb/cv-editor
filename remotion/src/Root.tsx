import { Composition } from "remotion";
import { CaseFile } from "./CaseFile";
import { ThumbnailScene, ThumbnailProps } from "./scenes/ThumbnailScene";
import { FPS, W, H, DURATION_S } from "./theme";
import type { ScriptData } from "./types";

const DEFAULT_CASEFILE_PROPS: ScriptData = {
  player: "Nico Williams",
  format: "player-profile",
  scores: { instinct: 9, iq: 6, gravity: 8 },
  context_risk: 13,
  transferability: 61,
  verdict_hook: "TRANSFER TRAP?",
  verdict_label: "SYSTEM-DEPENDENT WEAPON",
  beats: {
    claim: "Arsenal may be paying sixty million pounds for the wrong winger.",
    tension: "Everyone's watching the dribbling. Nobody's watching what happens when the ball stops moving. Nico Williams disappears in possession systems.",
    evidence: "Instinct: nine. In transition his first step fires before defenders process danger. IQ: a flat six. In low blocks he hesitates, kills overloads, finds the wrong half-space. Gravity: eight. Defenders collapse toward him without him touching the ball.",
    reveal: "Transferability: sixty-one percent. That survives a move. But not to a possession side. Arsenal's transitions work. Barcelona's structure collapses this.",
    loop: "Would you spend sixty million knowing the system might break him?",
  },
  axes: {
    instinct: { evidence: "First step fires before defenders process danger.", percentile: "Top 5% in transition" },
    iq:       { evidence: "Hesitates in low blocks. Kills his own overloads.",  percentile: "Bottom 40% in possession" },
    gravity:  { evidence: "Defenders collapse toward him before he touches it.", percentile: "Top 10% off-ball pull" },
  },
  word_count: 136,
};

const DEFAULT_THUMBNAIL_PROPS: ThumbnailProps = {
  player_name: "PEDRI",
  variant: "fraud_watch",
  scores: { instinct: 7, iq: 6, gravity: 5 },
  transferability: 42,
  verdict_label: "FRAUD WATCH?",
  verdict_color: "red",
};

export const Root: React.FC = () => (
  <>
    <Composition
      id="CaseFile"
      component={CaseFile as unknown as React.ComponentType<Record<string, unknown>>}
      durationInFrames={DURATION_S * FPS}
      fps={FPS}
      width={W}
      height={H}
      defaultProps={DEFAULT_CASEFILE_PROPS}
    />
    <Composition
      id="Thumbnail"
      component={ThumbnailScene as unknown as React.ComponentType<Record<string, unknown>>}
      durationInFrames={1}
      fps={FPS}
      width={W}
      height={H}
      defaultProps={DEFAULT_THUMBNAIL_PROPS}
    />
  </>
);
