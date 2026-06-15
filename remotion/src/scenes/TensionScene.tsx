import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Caption } from "../components/Caption";
import { ClipEvidence } from "../components/ClipEvidence";
import { PlayerCutout } from "../components/PlayerCutout";
import { ScoutNote } from "../components/ScoutNote";
import { TacticalBoard } from "../components/TacticalBoard";
import { COLORS, FONTS } from "../theme";
import { ClipSpec } from "../types";

interface Props {
  tension: string;
  playerImageKey?: string;
  scoutNote?: string;
  durationFrames: number;
  clip?: ClipSpec;
}

// V4: Why the popular take is wrong. 5-15s.
// "Everyone sees X. Nobody sees Y." The tactical board shows the problem
// directly — a settled low block where the player's game stops working.
export const TensionScene: React.FC<Props> = ({ tension, playerImageKey, scoutNote, durationFrames, clip }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const headerOpacity = interpolate(frame, [0, fps * 0.25], [0, 1], {
    extrapolateRight: "clamp",
  });

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
          marginBottom: 40,
          zIndex: 2,
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

      {/* The problem shown — real clip if available, tactical reconstruction otherwise */}
      <div style={{ flex: 1, minHeight: 0, border: `1px solid ${COLORS.border}`, position: "relative", marginBottom: 36, zIndex: 2, overflow: "hidden" }}>
        {clip ? (
          <ClipEvidence src={clip.src} freezeAt={clip.freezeAt} annotations={clip.annotations} zoom={clip.zoom} />
        ) : (
          <TacticalBoard motif="low_block" label="SETTLED POSSESSION" startFrame={Math.round(fps * 0.4)} />
        )}
      </div>

      {/* Tension caption — word by word, investigative */}
      <div style={{ zIndex: 2 }}>
        <Caption
          text={tension}
          startFrame={Math.round(fps * 0.5)}
          endFrame={durationFrames - Math.round(fps * 0.4)}
        />
      </div>

      {/* Medium player cutout — fades in at 50% opacity for recognition without dominating */}
      {playerImageKey && (
        <AbsoluteFill style={{ zIndex: 0, pointerEvents: "none" }}>
          <PlayerCutout imageKey={playerImageKey} mode="medium" />
        </AbsoluteFill>
      )}

      {/* Optional scout note — analyst annotation that slides in mid-scene */}
      {scoutNote && <ScoutNote text={scoutNote} startFrame={Math.round(fps * 1.2)} position="top-right" accent />}
    </AbsoluteFill>
  );
};
