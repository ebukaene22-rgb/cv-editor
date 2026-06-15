import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { ScoutNote } from "./ScoutNote";
import { COLORS, FONTS } from "../theme";

interface Props {
  exhibit: string;     // "A" | "B" | "C"
  label: string;       // "INSTINCT"
  score: number;       // 1-10
  evidence: string;    // justification line
  percentile: string;  // benchmark chip
  scoutNote?: string;  // optional analyst card that flies in after reveal
  startFrame: number;
  color?: string;
}

// An axis score presented as a piece of evidence entering the case file:
// score slams in, bar fills, justification + benchmark follow.
export const EvidenceRow: React.FC<Props> = ({
  exhibit,
  label,
  score,
  evidence,
  percentile,
  scoutNote,
  startFrame,
  color = COLORS.scoreBar,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const rel = frame - startFrame;

  const rowOpacity = interpolate(rel, [0, fps * 0.2], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const rowX = interpolate(rel, [0, fps * 0.25], [-24, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const barProgress = interpolate(rel, [fps * 0.15, fps * 0.7], [0, score / 10], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const detailOpacity = interpolate(rel, [fps * 0.5, fps * 0.8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        opacity: rowOpacity,
        transform: `translateX(${rowX}px)`,
        borderLeft: `4px solid ${color}`,
        paddingLeft: 28,
        fontFamily: FONTS.mono,
      }}
    >
      {/* Exhibit marker + axis + score */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontSize: 20, color: COLORS.textDim, letterSpacing: 4 }}>
          EXHIBIT {exhibit}
        </span>
        <div style={{ display: "flex", alignItems: "baseline", gap: 20 }}>
          <span style={{ fontSize: 30, color: COLORS.textMuted, letterSpacing: 4, textTransform: "uppercase" }}>
            {label}
          </span>
          <span style={{ fontSize: 76, fontWeight: "bold", color, lineHeight: 1 }}>
            {score}
          </span>
        </div>
      </div>

      {/* Bar */}
      <div
        style={{
          width: "100%",
          height: 8,
          background: COLORS.scoreBarBg,
          borderRadius: 4,
          overflow: "hidden",
          margin: "14px 0 16px",
        }}
      >
        <div style={{ width: `${barProgress * 100}%`, height: "100%", background: color, borderRadius: 4 }} />
      </div>

      {/* Evidence line */}
      <div
        style={{
          opacity: detailOpacity,
          fontFamily: FONTS.sans,
          fontSize: 34,
          fontWeight: "bold",
          color: COLORS.text,
          lineHeight: 1.25,
          marginBottom: 14,
        }}
      >
        {evidence}
      </div>

      {/* Benchmark chip */}
      <div
        style={{
          opacity: detailOpacity,
          display: "inline-block",
          border: `1px solid ${color}`,
          padding: "6px 18px",
          fontSize: 22,
          color,
          letterSpacing: 3,
          textTransform: "uppercase",
        }}
      >
        {percentile}
      </div>

      {/* Scout note — flies in after the score is fully revealed */}
      {scoutNote && (
        <ScoutNote
          text={scoutNote}
          startFrame={startFrame + Math.round(fps * 0.9)}
          position="top-right"
          accent={color !== COLORS.gravity}
        />
      )}
    </div>
  );
};
