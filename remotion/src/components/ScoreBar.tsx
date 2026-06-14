import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONTS } from "../theme";

interface Props {
  label: string;
  score: number;          // 1–10
  startFrame: number;     // frame when bar begins animating
  color?: string;
}

export const ScoreBar: React.FC<Props> = ({
  label,
  score,
  startFrame,
  color = COLORS.scoreBar,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progress = interpolate(
    frame,
    [startFrame, startFrame + fps * 0.8],
    [0, score / 10],
    { extrapolateRight: "clamp" }
  );

  const labelOpacity = interpolate(
    frame,
    [startFrame, startFrame + fps * 0.25],
    [0, 1],
    { extrapolateRight: "clamp" }
  );

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 10,
        opacity: labelOpacity,
        fontFamily: FONTS.mono,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
        }}
      >
        <span
          style={{
            color: COLORS.textMuted,
            fontSize: 28,
            letterSpacing: 4,
            textTransform: "uppercase",
          }}
        >
          {label}
        </span>
        <span
          style={{
            color: color,
            fontSize: 72,
            fontWeight: "bold",
            lineHeight: 1,
          }}
        >
          {score}
        </span>
      </div>

      {/* Track */}
      <div
        style={{
          width: "100%",
          height: 8,
          background: COLORS.scoreBarBg,
          borderRadius: 4,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${progress * 100}%`,
            height: "100%",
            background: color,
            borderRadius: 4,
            transition: "none",
          }}
        />
      </div>
    </div>
  );
};
