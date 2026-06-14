import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  staticFile,
  useVideoConfig,
} from "remotion";
import { ClaimScene } from "./scenes/ClaimScene";
import { TensionScene } from "./scenes/TensionScene";
import { ProfileScene } from "./scenes/ProfileScene";
import { VerdictScene } from "./scenes/VerdictScene";
import { LoopScene } from "./scenes/LoopScene";
import { BEAT_START, DURATION_S } from "./theme";
import { ScriptData } from "./types";

// V3: story-first. Five beats — claim, tension, evidence, reveal, loop.
// Props are the full script.json, passed via --props at render time.
export const CaseFile: React.FC<ScriptData> = (props) => {
  const { fps } = useVideoConfig();

  const toF = (s: number) => Math.round(s * fps);

  const beats = {
    claim:    { from: toF(BEAT_START.claim),    dur: toF(BEAT_START.tension  - BEAT_START.claim) },
    tension:  { from: toF(BEAT_START.tension),  dur: toF(BEAT_START.evidence - BEAT_START.tension) },
    evidence: { from: toF(BEAT_START.evidence), dur: toF(BEAT_START.reveal   - BEAT_START.evidence) },
    reveal:   { from: toF(BEAT_START.reveal),   dur: toF(BEAT_START.loop     - BEAT_START.reveal) },
    loop:     { from: toF(BEAT_START.loop),      dur: toF(DURATION_S          - BEAT_START.loop) },
  };

  return (
    <AbsoluteFill>
      <Audio src={staticFile("vo.mp3")} />

      {/* Player image — ghost background visible across all scenes */}
      {props.player_image_key && (
        <AbsoluteFill style={{ zIndex: 0, pointerEvents: "none" }}>
          <Img
            src={staticFile(props.player_image_key)}
            style={{
              position: "absolute",
              right: 0,
              bottom: 0,
              height: "65%",
              opacity: 0.18,
              mixBlendMode: "luminosity",
            }}
          />
        </AbsoluteFill>
      )}

      <Sequence from={beats.claim.from} durationInFrames={beats.claim.dur} name="Claim">
        <ClaimScene
          player={props.player}
          claim={props.beats.claim}
          transferability={props.transferability}
          verdictHook={props.verdict_hook}
          verdictLabel={props.verdict_label}
          durationFrames={beats.claim.dur}
        />
      </Sequence>

      <Sequence from={beats.tension.from} durationInFrames={beats.tension.dur} name="Tension">
        <TensionScene
          tension={props.beats.tension}
          durationFrames={beats.tension.dur}
        />
      </Sequence>

      <Sequence from={beats.evidence.from} durationInFrames={beats.evidence.dur} name="Evidence">
        <ProfileScene
          scores={props.scores}
          axes={props.axes}
          evidence={props.beats.evidence}
          durationFrames={beats.evidence.dur}
        />
      </Sequence>

      <Sequence from={beats.reveal.from} durationInFrames={beats.reveal.dur} name="Reveal">
        <VerdictScene
          transferability={props.transferability}
          reveal={props.beats.reveal}
          verdictLabelText={props.verdict_label}
          durationFrames={beats.reveal.dur}
        />
      </Sequence>

      <Sequence from={beats.loop.from} durationInFrames={beats.loop.dur} name="Loop">
        <LoopScene
          loop={props.beats.loop}
          player={props.player}
          durationFrames={beats.loop.dur}
        />
      </Sequence>
    </AbsoluteFill>
  );
};
