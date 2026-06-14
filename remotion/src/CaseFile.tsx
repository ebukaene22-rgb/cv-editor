import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  staticFile,
  useVideoConfig,
} from "remotion";
import { HookScene } from "./scenes/HookScene";
import { ProfileScene } from "./scenes/ProfileScene";
import { VerdictScene } from "./scenes/VerdictScene";
import { LoopScene } from "./scenes/LoopScene";
import { BEAT_START, DURATION_S } from "./theme";
import { ScriptData } from "./types";

// Props are the full script.json — passed via --props at render time.
export const CaseFile: React.FC<ScriptData> = (props) => {
  const { fps } = useVideoConfig();

  const toF = (s: number) => Math.round(s * fps);

  const beats = {
    hook:    { from: toF(BEAT_START.hook),    dur: toF(BEAT_START.profile - BEAT_START.hook) },
    profile: { from: toF(BEAT_START.profile), dur: toF(BEAT_START.verdict - BEAT_START.profile) },
    verdict: { from: toF(BEAT_START.verdict), dur: toF(BEAT_START.loop    - BEAT_START.verdict) },
    loop:    { from: toF(BEAT_START.loop),    dur: toF(DURATION_S          - BEAT_START.loop) },
  };

  return (
    <AbsoluteFill>
      <Audio src={staticFile("vo.mp3")} />

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

      <Sequence from={beats.hook.from} durationInFrames={beats.hook.dur} name="Hook">
        <HookScene
          player={props.player}
          hook={props.beats.hook}
          durationFrames={beats.hook.dur}
        />
      </Sequence>

      <Sequence from={beats.profile.from} durationInFrames={beats.profile.dur} name="Profile">
        <ProfileScene
          scores={props.scores}
          profile={props.beats.profile}
          durationFrames={beats.profile.dur}
        />
      </Sequence>

      <Sequence from={beats.verdict.from} durationInFrames={beats.verdict.dur} name="Verdict">
        <VerdictScene
          transferability={props.transferability}
          verdict={props.beats.verdict}
          durationFrames={beats.verdict.dur}
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
