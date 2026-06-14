import { interpolate, useCurrentFrame } from "remotion";
import { COLORS, FONTS } from "../theme";

interface Props {
  text?: string;
  startFrame?: number;
}

export const CaseFileStamp: React.FC<Props> = ({
  text = "CASE FILE",
  startFrame = 0,
}) => {
  const frame = useCurrentFrame();

  const opacity = interpolate(frame, [startFrame, startFrame + 6], [0, 0.85], {
    extrapolateRight: "clamp",
  });

  const scale = interpolate(frame, [startFrame, startFrame + 6], [1.08, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        border: `6px solid ${COLORS.stamp}`,
        padding: "10px 28px",
        opacity,
        transform: `scale(${scale}) rotate(-8deg)`,
        display: "inline-block",
      }}
    >
      <span
        style={{
          fontFamily: FONTS.mono,
          fontSize: 38,
          color: COLORS.stamp,
          letterSpacing: 10,
          fontWeight: "bold",
          textTransform: "uppercase",
        }}
      >
        {text}
      </span>
    </div>
  );
};
