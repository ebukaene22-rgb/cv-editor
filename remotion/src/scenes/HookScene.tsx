import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Caption } from "../components/Caption";
import { COLORS, FONTS } from "../theme";
import { deriveVerdict } from "../verdict";

interface Props {
  player: string;
  hook: string;
  transferability: number;
  verdictHook?: string;
  verdictLabel?: string;
  durationFrames: number;
}

// V2: the VERDICT is the hook. The accusation slams in at frame 0 — no slow
// build — then the player name, the transferability teaser, and the thesis.
export const HookScene: React.FC<Props> = ({
  player,
  hook,
  transferability,
  verdictHook,
  verdictLabel,
  durationFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const verdict = deriveVerdict(transferability, verdictHook, verdictLabel);

  // Accusation slams in hard at frame 0 — overshoot scale + settle.
  const stampScale = interpolate(frame, [0, 3, 7], [1.4, 0.97, 1], {
    extrapolateRight: "clamp",
  });
  const stampOpacity = interpolate(frame, [0, 2], [0, 1], {
    extrapolateRight: "clamp",
  });
  // Camera-shake on the slam: a couple of frames of jitter then dead still.
  const shake = frame < 6 ? Math.sin(frame * 8) * (6 - frame) : 0;

  // Player name + chips fade in just after the slam.
  const metaOpacity = interpolate(frame, [6, fps * 0.5], [0, 1], {
    extrapolateRight: "clamp",
  });
  const metaY = interpolate(frame, [6, fps * 0.5], [16, 0], {
    extrapolateRight: "clamp",
  });

  // Scan-line flicker on entry.
  const scanOpacity = interpolate(frame, [0, 4, 8, 12, 16], [0, 0.18, 0, 0.08, 0], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: COLORS.bg,
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: "90px 60px 90px",
      }}
    >
      {/* File header strip */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontFamily: FONTS.mono,
          fontSize: 22,
          color: COLORS.textDim,
          letterSpacing: 4,
        }}
      >
        <span>FILE #IQ-001</span>
        <span>CLASSIFIED</span>
      </div>

      {/* HERO: the accusation */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 36,
          transform: `translateX(${shake}px)`,
        }}
      >
        <div
          style={{
            opacity: stampOpacity,
            transform: `scale(${stampScale}) rotate(-4deg)`,
            border: `8px solid ${verdict.color}`,
            padding: "24px 48px",
            background: "rgba(0,0,0,0.4)",
          }}
        >
          <span
            style={{
              fontFamily: FONTS.sans,
              fontSize: 130,
              fontWeight: "bold",
              color: verdict.color,
              letterSpacing: 2,
              textTransform: "uppercase",
              lineHeight: 0.95,
              display: "block",
              textAlign: "center",
            }}
          >
            {verdict.hook}
          </span>
        </div>

        {/* Player name */}
        <div
          style={{
            opacity: metaOpacity,
            transform: `translateY(${metaY}px)`,
            fontFamily: FONTS.mono,
            fontSize: 76,
            fontWeight: "bold",
            color: COLORS.text,
            textTransform: "uppercase",
            letterSpacing: 1,
            textAlign: "center",
            lineHeight: 1,
          }}
        >
          {player}
        </div>

        {/* Transferability teaser chip */}
        <div
          style={{
            opacity: metaOpacity,
            transform: `translateY(${metaY}px)`,
            display: "flex",
            alignItems: "baseline",
            gap: 16,
            border: `1px solid ${COLORS.border}`,
            padding: "12px 28px",
            fontFamily: FONTS.mono,
          }}
        >
          <span style={{ fontSize: 24, color: COLORS.textMuted, letterSpacing: 4 }}>
            TRANSFERABILITY
          </span>
          <span style={{ fontSize: 44, fontWeight: "bold", color: verdict.color }}>
            {transferability}%
          </span>
        </div>
      </div>

      {/* Thesis caption */}
      <div>
        <Caption
          text={hook}
          startFrame={Math.round(fps * 0.8)}
          endFrame={durationFrames - Math.round(fps * 0.4)}
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
