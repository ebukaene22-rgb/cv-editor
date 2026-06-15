import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONTS } from "../theme";

// Dramatic transferability reveal — the emotional climax of the video.
// Three phases: scanning → number drops → classification confirmed.

interface Props {
  score: number;             // 0-100
  verdictColor: string;
  verdictLabel: string;
  durationFrames: number;
}

export const ClassificationReveal: React.FC<Props> = ({
  score,
  verdictColor,
  verdictLabel,
  durationFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Phase 1 (0 – 1.5s): scanning animation — horizontal lines sweep down
  const phase1End = Math.round(fps * 1.5);
  // Phase 2 (1.5 – 3s): number counts up rapidly
  const phase2End = Math.round(fps * 3.0);
  // Phase 3 (3s – end): verdict label stamps in + holds

  // Scanning lines — 6 horizontal bars that strobe top to bottom
  const scanProgress = interpolate(frame, [0, phase1End], [0, 1], {
    extrapolateRight: "clamp",
  });
  const scanLineY = scanProgress * 100; // 0-100%

  // "ANALYSING..." text during scan
  const analysingOpacity = interpolate(frame, [0, fps * 0.2, phase1End - fps * 0.3, phase1End], [0, 1, 1, 0], {
    extrapolateRight: "clamp",
  });

  // Score counts up — fast in phase 2, then holds
  const scoreProgress = interpolate(
    frame,
    [phase1End, phase2End],
    [0, score],
    { extrapolateRight: "clamp" }
  );
  const scoreOpacity = interpolate(frame, [phase1End, phase1End + fps * 0.2], [0, 1], {
    extrapolateRight: "clamp",
  });

  // "CLASSIFICATION COMPLETE" label drops in after score
  const labelOpacity = interpolate(
    frame,
    [phase2End, phase2End + fps * 0.3],
    [0, 1],
    { extrapolateRight: "clamp" }
  );
  const labelY = interpolate(
    frame,
    [phase2End, phase2End + fps * 0.4],
    [-24, 0],
    { extrapolateRight: "clamp" }
  );

  // Verdict stamp slams in
  const stampScale = interpolate(
    frame,
    [phase2End + fps * 0.4, phase2End + fps * 0.55, phase2End + fps * 0.7],
    [1.4, 0.95, 1],
    { extrapolateRight: "clamp" }
  );
  const stampOpacity = interpolate(
    frame,
    [phase2End + fps * 0.4, phase2End + fps * 0.5],
    [0, 1],
    { extrapolateRight: "clamp" }
  );
  // Shake on stamp
  const shake = frame >= phase2End + fps * 0.4 && frame < phase2End + fps * 0.6
    ? Math.sin((frame - (phase2End + fps * 0.4)) * 12) * 4
    : 0;

  // Risk band: ≥75 LOW RISK (green), 60-74 MEDIUM RISK (amber), <60 HIGH RISK (red)
  const riskLabel = score >= 75 ? "LOW RISK" : score >= 60 ? "MEDIUM RISK" : "HIGH RISK";
  const riskColor = score >= 75 ? "#22c55e" : score >= 60 ? "#f59e0b" : COLORS.accent;

  return (
    <AbsoluteFill
      style={{
        background: COLORS.bg,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 0,
        transform: `translateX(${shake}px)`,
      }}
    >
      {/* Phase 1: scan line sweeping down */}
      {frame < phase1End && (
        <AbsoluteFill style={{ pointerEvents: "none" }}>
          <div
            style={{
              position: "absolute",
              top: `${scanLineY}%`,
              left: 0,
              right: 0,
              height: 3,
              background: `linear-gradient(90deg, transparent, ${verdictColor}, transparent)`,
              opacity: 0.8,
              boxShadow: `0 0 20px ${verdictColor}`,
            }}
          />
          {/* Scan stripes above the line */}
          {[0, 1, 2, 3, 4].map((i) => (
            <div
              key={i}
              style={{
                position: "absolute",
                top: `${Math.max(0, scanLineY - i * 6)}%`,
                left: 0, right: 0,
                height: 2,
                background: verdictColor,
                opacity: 0.08 - i * 0.015,
              }}
            />
          ))}
          {/* "ANALYSING..." */}
          <div
            style={{
              position: "absolute",
              bottom: 120,
              left: 0, right: 0,
              textAlign: "center",
              fontFamily: FONTS.mono,
              fontSize: 26,
              color: verdictColor,
              letterSpacing: 8,
              opacity: analysingOpacity,
            }}
          >
            ANALYSING...
          </div>
        </AbsoluteFill>
      )}

      {/* FILE HEADER */}
      <div
        style={{
          position: "absolute",
          top: 90,
          left: 60, right: 60,
          display: "flex",
          justifyContent: "space-between",
          fontFamily: FONTS.mono,
          fontSize: 20,
          color: COLORS.textDim,
          letterSpacing: 4,
        }}
      >
        <span>TRANSFERABILITY ASSESSMENT</span>
        <span>CLASSIFIED</span>
      </div>

      {/* SCORE — big, dramatic */}
      <div
        style={{
          opacity: scoreOpacity,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 0,
          marginTop: -60,
        }}
      >
        <div
          style={{
            fontFamily: FONTS.mono,
            fontSize: 24,
            color: COLORS.textMuted,
            letterSpacing: 8,
            marginBottom: 16,
          }}
        >
          TRANSFERABILITY SCORE
        </div>

        <div
          style={{
            fontFamily: FONTS.sans,
            fontSize: 220,
            fontWeight: "bold",
            color: verdictColor,
            lineHeight: 0.9,
            letterSpacing: -4,
          }}
        >
          {Math.round(scoreProgress)}
        </div>

        <div
          style={{
            fontFamily: FONTS.mono,
            fontSize: 60,
            color: verdictColor,
            letterSpacing: 4,
            marginTop: 8,
          }}
        >
          %
        </div>

        {/* Progress bar */}
        <div
          style={{
            width: 480,
            height: 6,
            background: COLORS.scoreBarBg,
            borderRadius: 3,
            overflow: "hidden",
            marginTop: 32,
          }}
        >
          <div
            style={{
              width: `${Math.round(scoreProgress)}%`,
              height: "100%",
              background: verdictColor,
              borderRadius: 3,
            }}
          />
        </div>
        <div
          style={{
            width: 480,
            display: "flex",
            justifyContent: "space-between",
            fontFamily: FONTS.mono,
            fontSize: 18,
            color: COLORS.textDim,
            marginTop: 8,
          }}
        >
          <span>HIGH RISK</span>
          <span>SAFE</span>
        </div>
      </div>

      {/* CLASSIFICATION COMPLETE + verdict */}
      <div
        style={{
          opacity: labelOpacity,
          transform: `translateY(${labelY}px)`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 24,
          marginTop: 48,
        }}
      >
        <div
          style={{
            fontFamily: FONTS.mono,
            fontSize: 22,
            color: COLORS.textMuted,
            letterSpacing: 6,
          }}
        >
          CLASSIFICATION COMPLETE
        </div>

        {/* Risk band */}
        <div
          style={{
            border: `3px solid ${riskColor}`,
            padding: "12px 36px",
            fontFamily: FONTS.mono,
            fontSize: 32,
            color: riskColor,
            letterSpacing: 6,
            fontWeight: "bold",
          }}
        >
          {riskLabel}
        </div>
      </div>

      {/* Verdict stamp — slams in last */}
      <div
        style={{
          position: "absolute",
          bottom: 120,
          left: 60,
          opacity: stampOpacity,
          transform: `scale(${stampScale}) rotate(-10deg)`,
        }}
      >
        <div
          style={{
            border: `6px solid ${verdictColor}`,
            padding: "14px 32px",
          }}
        >
          <span
            style={{
              fontFamily: FONTS.mono,
              fontSize: 34,
              color: verdictColor,
              letterSpacing: 8,
              fontWeight: "bold",
            }}
          >
            {verdictLabel}
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
