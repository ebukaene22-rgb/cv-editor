import { interpolate, useCurrentFrame } from "remotion";
import { COLORS, FONTS } from "../theme";

interface Props {
  text: string;
  startFrame: number;
  position?: "top-left" | "top-right" | "bottom-left" | "bottom-right";
  accent?: boolean;   // true = use accent red, false = muted
}

// Analyst annotation card — flies in from the edge like a sticky note
// dropped onto the dossier. Used during evidence reveals to reinforce
// what the viewer should take from each score.
export const ScoutNote: React.FC<Props> = ({
  text,
  startFrame,
  position = "top-right",
  accent = false,
}) => {
  const frame = useCurrentFrame();

  const rel = frame - startFrame;

  const opacity = interpolate(rel, [0, 6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Slide in from the relevant edge
  const isRight = position.includes("right");
  const isTop = position.includes("top");
  const slideX = interpolate(rel, [0, 10], [isRight ? 40 : -40, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const slideY = interpolate(rel, [0, 10], [isTop ? -20 : 20, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  // Tiny rotation — handwritten feel
  const rotate = isRight ? 2 : -2;

  const posStyles: React.CSSProperties = {
    top: isTop ? 40 : undefined,
    bottom: isTop ? undefined : 40,
    left: isRight ? undefined : 40,
    right: isRight ? 40 : undefined,
  };

  const borderColor = accent ? COLORS.accent : COLORS.textDim;
  const textColor = accent ? COLORS.accent : COLORS.textMuted;

  return (
    <div
      style={{
        position: "absolute",
        ...posStyles,
        opacity,
        transform: `translate(${slideX}px, ${slideY}px) rotate(${rotate}deg)`,
        borderLeft: `3px solid ${borderColor}`,
        background: "rgba(10,10,10,0.85)",
        padding: "12px 20px",
        backdropFilter: "blur(4px)",
        zIndex: 10,
      }}
    >
      <span
        style={{
          fontFamily: FONTS.mono,
          fontSize: 24,
          color: textColor,
          letterSpacing: 2,
          textTransform: "uppercase",
          display: "block",
          lineHeight: 1.3,
        }}
      >
        {text}
      </span>
    </div>
  );
};
