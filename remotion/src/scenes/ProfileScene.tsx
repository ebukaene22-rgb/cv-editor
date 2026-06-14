import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { EvidenceRow } from "../components/EvidenceRow";
import { COLORS, FONTS } from "../theme";
import { ScriptAxes, ScriptScores } from "../types";

interface Props {
  scores: ScriptScores;
  axes?: ScriptAxes;
  evidence: string;      // spoken narration for this beat (15-30s)
  durationFrames: number;
}

// Fallback evidence if a script predates the V2 `axes` field.
const FALLBACK: ScriptAxes = {
  instinct: { evidence: "Reads danger before it forms.", percentile: "ELITE TRAIT" },
  iq: { evidence: "Solves moments, not structures.", percentile: "ROLE-DEPENDENT" },
  gravity: { evidence: "Defenders react before he touches it.", percentile: "HIGH PULL" },
};

export const ProfileScene: React.FC<Props> = ({ scores, axes, durationFrames }) => {
  // `evidence` prop is spoken by voiceover — on screen the exhibits carry
  // the same information in dossier form so both channels reinforce each other.
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const ev = axes ?? FALLBACK;

  const headerOpacity = interpolate(frame, [0, fps * 0.3], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Each exhibit enters ~1.5s after the last — evidence stacking up.
  const aStart = Math.round(fps * 0.4);
  const bStart = Math.round(fps * 1.9);
  const cStart = Math.round(fps * 3.4);

  return (
    <AbsoluteFill
      style={{
        background: COLORS.bg,
        display: "flex",
        flexDirection: "column",
        padding: "90px 60px",
      }}
    >
      {/* Header */}
      <div
        style={{
          opacity: headerOpacity,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          borderBottom: `1px solid ${COLORS.border}`,
          paddingBottom: 24,
          marginBottom: 48,
        }}
      >
        <span
          style={{
            fontFamily: FONTS.mono,
            fontSize: 26,
            color: COLORS.accent,
            letterSpacing: 6,
            textTransform: "uppercase",
          }}
        >
          The Evidence
        </span>
        {/* "Evidence" is the section label in V3 — framework is supporting proof */}
        <span style={{ fontFamily: FONTS.mono, fontSize: 20, color: COLORS.textDim, letterSpacing: 3 }}>
          3-AXIS SCAN
        </span>
      </div>

      {/* Evidence stack */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", gap: 56 }}>
        <EvidenceRow
          exhibit="A"
          label="Instinct"
          score={scores.instinct}
          evidence={ev.instinct.evidence}
          percentile={ev.instinct.percentile}
          startFrame={aStart}
          color={COLORS.scoreBar}
        />
        <EvidenceRow
          exhibit="B"
          label="Football IQ"
          score={scores.iq}
          evidence={ev.iq.evidence}
          percentile={ev.iq.percentile}
          startFrame={bStart}
          color={COLORS.scoreBar}
        />
        <EvidenceRow
          exhibit="C"
          label="Gravity"
          score={scores.gravity}
          evidence={ev.gravity.evidence}
          percentile={ev.gravity.percentile}
          startFrame={cStart}
          color={COLORS.gravity}
        />
      </div>
    </AbsoluteFill>
  );
};
