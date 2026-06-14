import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Caption } from "../components/Caption";
import { ScoreBar } from "../components/ScoreBar";
import { COLORS, FONTS } from "../theme";
import { ScriptScores } from "../types";

interface Props {
  scores: ScriptScores;
  profile: string;
  durationFrames: number;
}

export const ProfileScene: React.FC<Props> = ({ scores, profile, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const headerOpacity = interpolate(frame, [0, fps * 0.3], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Stagger score bars by 0.6s each
  const instinctStart = Math.round(fps * 0.3);
  const iqStart = Math.round(fps * 0.9);
  const gravityStart = Math.round(fps * 1.5);

  return (
    <AbsoluteFill
      style={{
        background: COLORS.bg,
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: "120px 60px 100px",
      }}
    >
      {/* Header */}
      <div
        style={{
          opacity: headerOpacity,
          borderBottom: `1px solid ${COLORS.border}`,
          paddingBottom: 32,
          marginBottom: 60,
        }}
      >
        <span
          style={{
            fontFamily: FONTS.mono,
            fontSize: 24,
            color: COLORS.accent,
            letterSpacing: 6,
            textTransform: "uppercase",
          }}
        >
          Cognitive Profile
        </span>
      </div>

      {/* Score bars — staggered */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", gap: 60 }}>
        <ScoreBar
          label="Instinct"
          score={scores.instinct}
          startFrame={instinctStart}
          color={COLORS.scoreBar}
        />
        <ScoreBar
          label="Football IQ"
          score={scores.iq}
          startFrame={iqStart}
          color={COLORS.scoreBar}
        />
        <ScoreBar
          label="Gravity"
          score={scores.gravity}
          startFrame={gravityStart}
          color={COLORS.gravity}
        />
      </div>

      {/* Divider */}
      <div style={{ height: 1, background: COLORS.border, margin: "40px 0" }} />

      {/* Profile caption */}
      <Caption
        text={profile}
        startFrame={gravityStart + Math.round(fps * 0.8)}
        endFrame={durationFrames - Math.round(fps * 0.3)}
      />
    </AbsoluteFill>
  );
};
