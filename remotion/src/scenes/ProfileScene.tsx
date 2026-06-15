import { AbsoluteFill, interpolate, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import { ClipEvidence } from "../components/ClipEvidence";
import { PlayerCutout } from "../components/PlayerCutout";
import { TacticalBoard, Motif } from "../components/TacticalBoard";
import { COLORS, FONTS } from "../theme";
import { EpisodeClips, ScriptAxes, ScriptScores } from "../types";

interface Props {
  scores: ScriptScores;
  axes?: ScriptAxes;
  evidence: string;
  playerImageKey?: string;
  durationFrames: number;
  clips?: EpisodeClips;
}

const FALLBACK: ScriptAxes = {
  instinct: { evidence: "Reads danger before it forms.", percentile: "ELITE TRAIT" },
  iq: { evidence: "Solves moments, not structures.", percentile: "ROLE-DEPENDENT" },
  gravity: { evidence: "Defenders react before he touches it.", percentile: "HIGH PULL" },
};

// Each axis is shown as a self-contained EXHIBIT.
// V6: When CI has fetched evidence clips, ClipEvidence plays real footage → freeze → annotations.
// Without clips, falls back to the procedural TacticalBoard (V4 mode).
// Score reveals only AFTER the evidence is frozen on screen (V5 timing preserved).
export const ProfileScene: React.FC<Props> = ({ scores, axes, playerImageKey, durationFrames, clips }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const ev = axes ?? FALLBACK;
  const sub = Math.floor(durationFrames / 3);

  const headerOpacity = interpolate(frame, [0, fps * 0.3], [0, 1], { extrapolateRight: "clamp" });

  const exhibits: {
    key: keyof EpisodeClips; exhibit: string; label: string; score: number;
    evidence: string; percentile: string; motif: Motif; motifLabel: string;
    scoutNote?: string; color: string;
  }[] = [
    {
      key: "instinct", exhibit: "A", label: "Instinct", score: scores.instinct,
      evidence: ev.instinct.evidence, percentile: ev.instinct.percentile,
      motif: "transition", motifLabel: "SPACE IN BEHIND",
      scoutNote: scores.instinct >= 8 ? "Elite Trait" : scores.instinct <= 4 ? "High Collapse Risk" : undefined,
      color: COLORS.scoreBar,
    },
    {
      key: "iq", exhibit: "B", label: "Football IQ", score: scores.iq,
      evidence: ev.iq.evidence, percentile: ev.iq.percentile,
      motif: "low_block", motifLabel: "NO PASSING LANE",
      scoutNote: scores.iq <= 5 ? "System Dependency" : scores.iq >= 8 ? "Tactical Outlier" : undefined,
      color: COLORS.scoreBar,
    },
    {
      key: "gravity", exhibit: "C", label: "Gravity", score: scores.gravity,
      evidence: ev.gravity.evidence, percentile: ev.gravity.percentile,
      motif: "gravity", motifLabel: "SPACE CREATED",
      scoutNote: scores.gravity >= 8 ? "Portable Gravity" : undefined,
      color: COLORS.gravity,
    },
  ];

  return (
    <AbsoluteFill style={{ background: COLORS.bg, display: "flex", flexDirection: "column", padding: "90px 60px" }}>
      {/* Ghost cutout — identity anchor, persists across all exhibits */}
      {playerImageKey && (
        <AbsoluteFill style={{ zIndex: 0, pointerEvents: "none" }}>
          <PlayerCutout imageKey={playerImageKey} mode="ghost" />
        </AbsoluteFill>
      )}

      {/* Header — persists */}
      <div
        style={{
          opacity: headerOpacity,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          borderBottom: `1px solid ${COLORS.border}`,
          paddingBottom: 24,
          marginBottom: 32,
          zIndex: 2,
        }}
      >
        <span style={{ fontFamily: FONTS.mono, fontSize: 26, color: COLORS.accent, letterSpacing: 6, textTransform: "uppercase" }}>
          The Evidence
        </span>
        <span style={{ fontFamily: FONTS.mono, fontSize: 20, color: COLORS.textDim, letterSpacing: 3 }}>
          3-AXIS SCAN
        </span>
      </div>

      {/* One exhibit at a time — footage (or diagram) dominant, score last */}
      {exhibits.map((ex, i) => {
        const clipSpec = clips?.[ex.key];
        return (
          <Sequence key={ex.key} from={i * sub} durationInFrames={sub} name={`Exhibit-${ex.exhibit}`} layout="none">
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 28 }}>
              {/* Exhibit tag */}
              <span style={{ fontFamily: FONTS.mono, fontSize: 22, color: COLORS.textDim, letterSpacing: 4 }}>
                EXHIBIT {ex.exhibit}
              </span>

              {/* Evidence layer — real clip (V6) or procedural diagram (fallback) */}
              <div style={{ flex: 1, minHeight: 0, border: `1px solid ${COLORS.border}`, position: "relative", overflow: "hidden" }}>
                {clipSpec ? (
                  <ClipEvidence
                    src={clipSpec.src}
                    freezeAt={clipSpec.freezeAt}
                    annotations={clipSpec.annotations}
                  />
                ) : (
                  <TacticalBoard motif={ex.motif} label={ex.motifLabel} startFrame={0} />
                )}
              </div>

              {/* Score + evidence — delayed to fps*2.8 so it reveals AFTER freeze annotation (V5) */}
              <ExhibitReadout
                label={ex.label}
                score={ex.score}
                evidence={ex.evidence}
                percentile={ex.percentile}
                scoutNote={ex.scoutNote}
                color={ex.color}
              />
            </div>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

// V5: Score appears AFTER the tactical board has frozen with its annotation.
// Evidence is proven first; the score is a verdict ON that evidence.
// Board phase: 0-2.5s animation → 2.5-2.8s freeze annotation visible.
// Score phase: slides in at 2.8s, so the viewer reads the annotation first.
const ExhibitReadout: React.FC<{
  label: string; score: number; evidence: string; percentile: string;
  scoutNote?: string; color: string;
}> = ({ label, score, evidence, percentile, color }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Wait for board to freeze before revealing score (V5: evidence → verdict order)
  const revealStart = fps * 2.8;
  const opacity = interpolate(frame, [revealStart, revealStart + fps * 0.25], [0, 1], { extrapolateRight: "clamp" });
  const scoreCount = interpolate(frame, [revealStart, revealStart + fps * 0.5], [0, score], { extrapolateRight: "clamp" });
  // Thin divider line sweeps in right as the score reveals — signals transition from evidence to verdict
  const dividerWidth = interpolate(frame, [revealStart - fps * 0.1, revealStart + fps * 0.2], [0, 100], { extrapolateRight: "clamp" });

  return (
    <div style={{ fontFamily: FONTS.mono, zIndex: 2 }}>
      {/* Sweep line: visual signal that evidence phase is done, verdict phase begins */}
      <div style={{ width: `${dividerWidth}%`, height: 1, background: color, marginBottom: 16, opacity: 0.6 }} />
      <div style={{ opacity, display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontSize: 30, color: COLORS.textMuted, letterSpacing: 4, textTransform: "uppercase" }}>
          {label}
        </span>
        <span style={{ fontSize: 80, fontWeight: "bold", color, lineHeight: 1 }}>
          {Math.round(scoreCount)}
        </span>
      </div>
      <div style={{ opacity, fontFamily: FONTS.sans, fontSize: 32, fontWeight: "bold", color: COLORS.text, lineHeight: 1.25, margin: "12px 0" }}>
        {evidence}
      </div>
      <div style={{ opacity, display: "inline-block", border: `1px solid ${color}`, padding: "6px 18px", fontSize: 22, color, letterSpacing: 3, textTransform: "uppercase" }}>
        {percentile}
      </div>
    </div>
  );
};
