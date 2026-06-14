import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONTS } from "../theme";

interface Props {
  loop: string;
  player: string;
  durationFrames: number;
}

export const LoopScene: React.FC<Props> = ({ loop, player, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const bgPulse = interpolate(
    frame,
    [0, fps * 1, fps * 2, fps * 3, fps * 4, durationFrames],
    [0, 0.04, 0, 0.04, 0, 0],
    { extrapolateRight: "clamp" }
  );

  const words = loop.split(" ");
  const totalReveal = fps * 1.5;
  const framesPerWord = totalReveal / words.length;

  const ctaOpacity = interpolate(
    frame,
    [Math.round(fps * 2), Math.round(fps * 2.4)],
    [0, 1],
    { extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill
      style={{
        background: COLORS.bg,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        padding: "80px 60px",
        gap: 60,
      }}
    >
      {/* Pulsing accent border overlay */}
      <AbsoluteFill
        style={{
          border: `3px solid ${COLORS.accent}`,
          opacity: bgPulse * 10,
          pointerEvents: "none",
        }}
      />

      {/* The polarizing question */}
      <div
        style={{
          textAlign: "center",
          fontFamily: FONTS.sans,
          fontSize: 58,
          fontWeight: "bold",
          color: COLORS.text,
          lineHeight: 1.3,
          textTransform: "uppercase",
          letterSpacing: 1,
        }}
      >
        {words.map((word, i) => {
          const revealFrame = Math.round(i * framesPerWord);
          const wordOpacity = interpolate(
            frame,
            [revealFrame, revealFrame + Math.round(fps * 0.15)],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );
          const wordScale = interpolate(
            frame,
            [revealFrame, revealFrame + Math.round(fps * 0.15)],
            [1.2, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );
          return (
            <span
              key={i}
              style={{
                opacity: wordOpacity,
                display: "inline-block",
                transform: `scale(${wordScale})`,
                marginRight: "0.3em",
              }}
            >
              {word}
            </span>
          );
        })}
      </div>

      {/* Comment CTA */}
      <div
        style={{
          opacity: ctaOpacity,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 16,
        }}
      >
        <div
          style={{
            width: 60,
            height: 2,
            background: COLORS.accent,
          }}
        />
        <span
          style={{
            fontFamily: FONTS.mono,
            fontSize: 26,
            color: COLORS.textMuted,
            letterSpacing: 4,
            textTransform: "uppercase",
          }}
        >
          Drop your verdict below
        </span>
        <span
          style={{
            fontFamily: FONTS.mono,
            fontSize: 22,
            color: COLORS.textDim,
            letterSpacing: 3,
          }}
        >
          #{player.replace(/\s+/g, "").toUpperCase()}
        </span>
      </div>
    </AbsoluteFill>
  );
};
