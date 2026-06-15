import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONTS } from "../theme";

export type Motif = "transition" | "low_block" | "gravity";

interface Props {
  motif: Motif;
  label: string;       // freeze-frame annotation, e.g. "SPACE IN BEHIND"
  startFrame?: number;
}

// Procedurally-generated tactical evidence. No broadcast footage — these are
// reconstructions, like a scout's whiteboard. Each motif animates a movement
// over ~2.5s then freezes with an annotation (the "freeze frame analysis").
//
// Coordinate space: 0-100 wide, 0-56 tall (16:9). Attacking direction is UP
// (toward y=0), so the defensive line sits near the top.
export const TacticalBoard: React.FC<Props> = ({ motif, label, startFrame = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const rel = frame - startFrame;

  // Animation progress 0→1 over 2.5s, then holds (freeze frame).
  const t = interpolate(rel, [0, fps * 2.5], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  // Label + freeze annotations appear once the movement resolves.
  const freeze = interpolate(rel, [fps * 2.2, fps * 2.6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const boardOpacity = interpolate(rel, [0, fps * 0.3], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const pitchGreen = "#0d1f14";
  const lineCol = "rgba(255,255,255,0.12)";

  return (
    <svg
      viewBox="0 0 100 56"
      preserveAspectRatio="xMidYMid meet"
      style={{ width: "100%", height: "100%", opacity: boardOpacity }}
    >
      <defs>
        <marker id="arrow-red" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 1 L 9 5 L 0 9 z" fill={COLORS.accent} />
        </marker>
        <marker id="arrow-dim" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 1 L 9 5 L 0 9 z" fill={COLORS.textMuted} />
        </marker>
      </defs>

      {/* Pitch */}
      <rect x="0" y="0" width="100" height="56" fill={pitchGreen} />
      {/* Mowing stripes */}
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <rect key={i} x={i * 16.67} y="0" width="8.33" height="56" fill="rgba(255,255,255,0.015)" />
      ))}
      {/* Defensive third line + penalty box near top */}
      <line x1="0" y1="20" x2="100" y2="20" stroke={lineCol} strokeWidth="0.3" vectorEffect="non-scaling-stroke" />
      <rect x="30" y="0" width="40" height="14" fill="none" stroke={lineCol} strokeWidth="0.3" vectorEffect="non-scaling-stroke" />

      {motif === "transition" && <TransitionMotif t={t} freeze={freeze} />}
      {motif === "low_block" && <LowBlockMotif t={t} freeze={freeze} />}
      {motif === "gravity" && <GravityMotif t={t} freeze={freeze} />}

      {/* Freeze-frame annotation label */}
      <g opacity={freeze}>
        <rect x="2" y="48" width={label.length * 2.4 + 6} height="6.5" fill="rgba(200,16,46,0.9)" />
        <text x="5" y="52.6" fontFamily={FONTS.mono} fontSize="4" fill="#fff" letterSpacing="0.3">
          {label}
        </text>
      </g>
    </svg>
  );
};

// ── Motifs ──────────────────────────────────────────────────────────────────

const Defender: React.FC<{ x: number; y: number }> = ({ x, y }) => (
  <circle cx={x} cy={y} r="2.2" fill="#2b3a44" stroke="rgba(255,255,255,0.3)" strokeWidth="0.3" vectorEffect="non-scaling-stroke" />
);

// Instinct: a runner bursts through a gap in the defensive line in transition.
const TransitionMotif: React.FC<{ t: number; freeze: number }> = ({ t, freeze }) => {
  const startX = 50, startY = 48;
  const endX = 50, endY = 6;
  const px = startX, py = startY + (endY - startY) * t;

  return (
    <g>
      {/* Back line with a gap between x=40 and x=60 */}
      <Defender x={18} y={18} />
      <Defender x={32} y={18} />
      <Defender x={68} y={18} />
      <Defender x={82} y={18} />

      {/* Run path */}
      <line x1={startX} y1={startY} x2={px} y2={py} stroke={COLORS.accent} strokeWidth="0.8"
        strokeDasharray="2 1.5" vectorEffect="non-scaling-stroke" markerEnd="url(#arrow-red)" />

      {/* Runner */}
      <circle cx={px} cy={py} r="2.6" fill={COLORS.accent} />

      {/* Highlighted space behind the line */}
      <ellipse cx={50} cy={10} rx={11} ry={6} fill="none" stroke={COLORS.accent}
        strokeWidth="0.5" strokeDasharray="1.5 1.5" opacity={freeze} vectorEffect="non-scaling-stroke" />
    </g>
  );
};

// IQ: in a settled low block, the passing lane is closed — the move stalls.
const LowBlockMotif: React.FC<{ t: number; freeze: number }> = ({ t, freeze }) => {
  const playerX = 50, playerY = 44;
  // Attempted pass extends then gets blocked at the wall.
  const targetX = 50, targetY = 30;
  const px = playerX + (targetX - playerX) * Math.min(t * 1.5, 1);
  const py = playerY + (targetY - playerY) * Math.min(t * 1.5, 1);

  return (
    <g>
      {/* Two compact banks of defenders */}
      <Defender x={26} y={14} />
      <Defender x={42} y={14} />
      <Defender x={58} y={14} />
      <Defender x={74} y={14} />
      <Defender x={34} y={26} />
      <Defender x={50} y={26} />
      <Defender x={66} y={26} />

      {/* Blocked pass attempt */}
      <line x1={playerX} y1={playerY} x2={px} y2={py} stroke={COLORS.textMuted} strokeWidth="0.8"
        strokeDasharray="2 1.5" vectorEffect="non-scaling-stroke" markerEnd="url(#arrow-dim)" />

      {/* Player in possession */}
      <circle cx={playerX} cy={playerY} r="2.6" fill={COLORS.accent} />

      {/* Blocked marker — red X where the lane dies */}
      <g opacity={freeze} stroke={COLORS.accent} strokeWidth="0.9" vectorEffect="non-scaling-stroke">
        <line x1={targetX - 2.5} y1={targetY - 2.5} x2={targetX + 2.5} y2={targetY + 2.5} />
        <line x1={targetX + 2.5} y1={targetY - 2.5} x2={targetX - 2.5} y2={targetY + 2.5} />
      </g>
    </g>
  );
};

// Gravity: defenders collapse toward the player, opening the weak side.
const GravityMotif: React.FC<{ t: number; freeze: number }> = ({ t, freeze }) => {
  const playerX = 34, playerY = 34;
  // Two defenders drift toward the player.
  const d1 = { x: 52 - 10 * t, y: 24 + 6 * t };
  const d2 = { x: 64 - 14 * t, y: 30 + 3 * t };
  // Weak-side attacker becomes free as space opens.
  const freeMate = { x: 82, y: 22 };

  return (
    <g>
      {/* Defensive line */}
      <Defender x={20} y={16} />
      <Defender x={44} y={16} />
      <Defender x={72} y={16} />

      {/* Drifting defenders + pull arrows */}
      <line x1={52} y1={24} x2={d1.x} y2={d1.y} stroke={COLORS.textMuted} strokeWidth="0.6"
        strokeDasharray="1.5 1.5" vectorEffect="non-scaling-stroke" markerEnd="url(#arrow-dim)" />
      <line x1={64} y1={30} x2={d2.x} y2={d2.y} stroke={COLORS.textMuted} strokeWidth="0.6"
        strokeDasharray="1.5 1.5" vectorEffect="non-scaling-stroke" markerEnd="url(#arrow-dim)" />
      <Defender x={d1.x} y={d1.y} />
      <Defender x={d2.x} y={d2.y} />

      {/* Player exerting gravity */}
      <circle cx={playerX} cy={playerY} r="2.8" fill={COLORS.accent} />
      <circle cx={playerX} cy={playerY} r={4 + Math.sin(t * Math.PI) * 3} fill="none"
        stroke={COLORS.accent} strokeWidth="0.4" opacity="0.5" vectorEffect="non-scaling-stroke" />

      {/* Freed weak-side attacker + space */}
      <ellipse cx={freeMate.x} cy={freeMate.y} rx={10} ry={7} fill="none" stroke="#4a90d9"
        strokeWidth="0.5" strokeDasharray="1.5 1.5" opacity={freeze} vectorEffect="non-scaling-stroke" />
      <circle cx={freeMate.x} cy={freeMate.y} r="2.4" fill="#4a90d9" opacity={freeze} />
    </g>
  );
};
