import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Caption } from "../components/Caption";
import { COLORS, FONTS } from "../theme";

interface Props {
  tension: string;
  durationFrames: number;
}

// V3: Why the popular take is wrong. 5-15s.
// This scene builds the friction — "Everyone sees X. Nobody sees Y."
// Dossier texture increases information density without needing footage.
export const TensionScene: React.FC<Props> = ({ tension, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const headerOpacity = interpolate(frame, [0, fps * 0.25], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Three redacted lines animate in (dossier visual texture) before the caption.
  const redactedLines = [
    { width: "78%", delay: 0 },
    { width: "55%", delay: fps * 0.12 },
    { width: "88%", delay: fps * 0.22 },
  ];

  const accentBarProgress = interpolate(frame, [fps * 0.1, fps * 0.6], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: COLORS.bg,
        display: "flex",
        flexDirection: "column",
        padding: "90px 60px",
      }}
    >
      {/* "INVESTIGATION" header */}
      <div
        style={{
          opacity: headerOpacity,
          display: "flex",
          alignItems: "center",
          gap: 20,
          marginBottom: 60,
        }}
      >
        {/* Animated accent bar */}
        <div
          style={{
            width: `${accentBarProgress * 60}px`,
            height: 4,
            background: COLORS.accent,
            transition: "none",
          }}
        />
        <span
          style={{
            fontFamily: FONTS.mono,
            fontSize: 22,
            color: COLORS.accent,
            letterSpacing: 6,
            textTransform: "uppercase",
          }}
        >
          The Problem
        </span>
      </div>

      {/* Redacted dossier lines — visual texture, enter staggered */}
      <div style={{ display: "flex", flexDirection: "column", gap: 20, marginBottom: 60 }}>
        {redactedLines.map((line, i) => {
          const lineOpacity = interpolate(
            frame,
            [line.delay, line.delay + fps * 0.2],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );
          return (
            <div
              key={i}
              style={{
                height: 14,
                borderRadius: 3,
                background: COLORS.border,
                width: line.width,
                opacity: lineOpacity,
              }}
            />
          );
        })}
      </div>

      {/* Tension caption — word by word, investigative */}
      <div style={{ flex: 1, display: "flex", alignItems: "center" }}>
        <Caption
          text={tension}
          startFrame={Math.round(fps * 0.5)}
          endFrame={durationFrames - Math.round(fps * 0.4)}
        />
      </div>

      {/* Bottom accent line — "folder closed" feeling */}
      <div
        style={{
          height: 1,
          background: COLORS.border,
          marginTop: 40,
          opacity: interpolate(frame, [fps * 0.3, fps * 0.7], [0, 1], {
            extrapolateRight: "clamp",
          }),
        }}
      />
    </AbsoluteFill>
  );
};
