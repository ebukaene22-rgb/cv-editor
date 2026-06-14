import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONTS } from "../theme";

interface Props {
  text: string;
  startFrame: number;
  endFrame: number;
}

// Word-by-word reveal driven by frame position (no external word timestamps needed).
export const Caption: React.FC<Props> = ({ text, startFrame, endFrame }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const words = text.split(" ");
  const totalFrames = endFrame - startFrame;
  const framesPerWord = totalFrames / words.length;

  const containerOpacity = interpolate(
    frame,
    [startFrame, startFrame + fps * 0.15],
    [0, 1],
    { extrapolateRight: "clamp" }
  );

  return (
    <div
      style={{
        opacity: containerOpacity,
        fontFamily: FONTS.sans,
        fontSize: 44,
        fontWeight: "bold",
        color: COLORS.text,
        lineHeight: 1.35,
        textAlign: "center",
        padding: "0 60px",
        textTransform: "uppercase",
        letterSpacing: 1,
      }}
    >
      {words.map((word, i) => {
        const wordRevealFrame = startFrame + i * framesPerWord;
        const wordOpacity = interpolate(
          frame,
          [wordRevealFrame, wordRevealFrame + fps * 0.12],
          [0, 1],
          { extrapolateRight: "clamp", extrapolateLeft: "clamp" }
        );
        const wordY = interpolate(
          frame,
          [wordRevealFrame, wordRevealFrame + fps * 0.12],
          [8, 0],
          { extrapolateRight: "clamp", extrapolateLeft: "clamp" }
        );
        return (
          <span
            key={i}
            style={{
              opacity: wordOpacity,
              display: "inline-block",
              transform: `translateY(${wordY}px)`,
              marginRight: "0.3em",
            }}
          >
            {word}
          </span>
        );
      })}
    </div>
  );
};
