import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Caption } from "../components/Caption";
import { CaseFileStamp } from "../components/CaseFileStamp";
import { COLORS, FONTS, FPS } from "../theme";

interface Props {
  player: string;
  hook: string;
  durationFrames: number;
}

export const HookScene: React.FC<Props> = ({ player, hook, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const playerOpacity = interpolate(frame, [0, fps * 0.4], [0, 1], {
    extrapolateRight: "clamp",
  });
  const playerY = interpolate(frame, [0, fps * 0.4], [-20, 0], {
    extrapolateRight: "clamp",
  });

  // Scan-line flicker effect on entry
  const scanOpacity = interpolate(frame, [0, 4, 8, 12, 16], [0, 0.15, 0, 0.08, 0], {
    extrapolateRight: "clamp",
  });

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
      {/* Top: file header bar */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 16,
          borderBottom: `1px solid ${COLORS.border}`,
          paddingBottom: 40,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span
            style={{
              fontFamily: FONTS.mono,
              fontSize: 22,
              color: COLORS.textDim,
              letterSpacing: 4,
            }}
          >
            FILE #IQ-001
          </span>
          <span
            style={{
              fontFamily: FONTS.mono,
              fontSize: 22,
              color: COLORS.textDim,
              letterSpacing: 4,
            }}
          >
            CLASSIFIED
          </span>
        </div>

        <div
          style={{
            opacity: playerOpacity,
            transform: `translateY(${playerY}px)`,
            fontFamily: FONTS.mono,
            fontSize: 88,
            fontWeight: "bold",
            color: COLORS.text,
            lineHeight: 1,
            textTransform: "uppercase",
            letterSpacing: -1,
          }}
        >
          {player}
        </div>

        <div style={{ marginTop: 8 }}>
          <CaseFileStamp startFrame={fps * 0.5} />
        </div>
      </div>

      {/* Middle: redacted dossier lines (visual texture) */}
      <div style={{ display: "flex", flexDirection: "column", gap: 18, flex: 1, paddingTop: 60 }}>
        {[1, 0.3, 0.7, 0.2, 0.5].map((opacity, i) => (
          <div
            key={i}
            style={{
              height: 16,
              borderRadius: 3,
              background: COLORS.border,
              opacity,
              width: `${[85, 60, 78, 45, 92][i]}%`,
            }}
          />
        ))}
      </div>

      {/* Bottom: hook caption */}
      <div style={{ paddingTop: 40 }}>
        <Caption
          text={hook}
          startFrame={fps * 1}
          endFrame={durationFrames - fps * 0.5}
        />
      </div>

      {/* Scan-line flicker overlay */}
      <AbsoluteFill
        style={{
          background: `repeating-linear-gradient(
            0deg,
            transparent,
            transparent 3px,
            rgba(255,255,255,0.03) 3px,
            rgba(255,255,255,0.03) 4px
          )`,
          opacity: scanOpacity,
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};
