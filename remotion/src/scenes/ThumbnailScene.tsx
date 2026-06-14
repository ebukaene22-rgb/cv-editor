import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { COLORS, FONTS, W, H } from "../theme";

export interface ThumbnailProps {
  player_name: string;
  variant: "fraud_watch" | "system_product" | "outlier" | "transfer_trap";
  scores: { instinct: number; iq: number; gravity: number };
  transferability: number;
  verdict_label: string;
  verdict_color: "red" | "green";
  transfer_club?: string;
  collapse_risk?: string;
  subtitle?: string;
}

const VERDICT_COLOR = {
  red: COLORS.accent,
  green: "#22c55e",
};

const MiniMetric: React.FC<{ label: string; value: number }> = ({ label, value }) => (
  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
    <span style={{ fontFamily: FONTS.mono, fontSize: 20, color: COLORS.textMuted, letterSpacing: 2, textTransform: "uppercase" }}>
      {label}
    </span>
    <span style={{ fontFamily: FONTS.mono, fontSize: 36, fontWeight: "bold", color: COLORS.text, lineHeight: 1 }}>
      {value}
    </span>
  </div>
);

export const ThumbnailScene: React.FC<ThumbnailProps> = (props) => {
  const frame = useCurrentFrame();
  const vColor = VERDICT_COLOR[props.verdict_color];

  const isTransferTrap = props.variant === "transfer_trap";
  const isSystemProduct = props.variant === "system_product";

  // Subtle entry animation for studio preview (still render uses frame 0 = clean state)
  const stampOpacity = interpolate(frame, [0, 8], [0.92, 0.92], { extrapolateRight: "clamp" });
  const stampScale = interpolate(frame, [0, 8], [1, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill
      style={{
        background: COLORS.bg,
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: "80px 60px 70px",
        overflow: "hidden",
      }}
    >
      {/* Grunge texture overlay — repeated diagonal lines */}
      <AbsoluteFill
        style={{
          background: `repeating-linear-gradient(
            -55deg,
            transparent,
            transparent 8px,
            rgba(255,255,255,0.012) 8px,
            rgba(255,255,255,0.012) 9px
          )`,
          pointerEvents: "none",
        }}
      />

      {/* Top: CASE FILE header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontFamily: FONTS.mono, fontSize: 22, color: COLORS.textDim, letterSpacing: 5, textTransform: "uppercase" }}>
          Case File
        </span>
        <span style={{ fontFamily: FONTS.mono, fontSize: 18, color: COLORS.textDim, letterSpacing: 4 }}>
          Player Football Fd
        </span>
      </div>

      {/* Player name — dominates the frame */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", gap: 0, position: "relative" }}>

        {/* Transfer trap: show "[PLAYER] TO [CLUB]?" */}
        {isTransferTrap && props.transfer_club ? (
          <>
            <div style={{ fontFamily: FONTS.mono, fontSize: 110, fontWeight: "bold", color: COLORS.text, lineHeight: 0.95, textTransform: "uppercase", letterSpacing: -2 }}>
              {props.player_name}
            </div>
            <div style={{ fontFamily: FONTS.mono, fontSize: 52, fontWeight: "bold", color: COLORS.textMuted, lineHeight: 1.1, textTransform: "uppercase", letterSpacing: 2, marginTop: 8 }}>
              TO {props.transfer_club}?
            </div>
          </>
        ) : (
          <div style={{ fontFamily: FONTS.mono, fontSize: 130, fontWeight: "bold", color: COLORS.text, lineHeight: 0.9, textTransform: "uppercase", letterSpacing: -3 }}>
            {props.player_name}
          </div>
        )}

        {/* System product: collapse risk label */}
        {isSystemProduct && props.collapse_risk && (
          <div style={{
            marginTop: 24,
            display: "inline-flex",
            background: vColor,
            padding: "8px 20px",
            alignSelf: "flex-start",
          }}>
            <span style={{ fontFamily: FONTS.mono, fontSize: 22, color: "#fff", fontWeight: "bold", letterSpacing: 4, textTransform: "uppercase" }}>
              COLLAPSE RISK: {props.collapse_risk}
            </span>
          </div>
        )}

        {/* Verdict stamp — diagonal, bold, ink-worn feel */}
        <div
          style={{
            position: "absolute",
            right: -20,
            top: "30%",
            opacity: stampOpacity,
            transform: `rotate(-15deg) scale(${stampScale})`,
            border: `8px solid ${vColor}`,
            padding: "12px 24px",
            background: "transparent",
          }}
        >
          <span
            style={{
              fontFamily: FONTS.mono,
              fontSize: 52,
              fontWeight: "bold",
              color: vColor,
              letterSpacing: 4,
              textTransform: "uppercase",
              lineHeight: 1,
              display: "block",
              whiteSpace: "nowrap",
            }}
          >
            {props.verdict_label}
          </span>
        </div>
      </div>

      {/* Bottom: transferability + mini metrics */}
      <div style={{ display: "flex", flexDirection: "column", gap: 20, borderTop: `1px solid ${COLORS.border}`, paddingTop: 24 }}>

        {/* Transferability */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontFamily: FONTS.mono, fontSize: 22, color: COLORS.textMuted, letterSpacing: 3, textTransform: "uppercase" }}>
            Transferability
          </span>
          <span style={{ fontFamily: FONTS.mono, fontSize: 40, fontWeight: "bold", color: vColor }}>
            {props.transferability}%
          </span>
        </div>

        {/* Mini score chips */}
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <MiniMetric label="Instinct" value={props.scores.instinct} />
          <div style={{ width: 1, background: COLORS.border }} />
          <MiniMetric label="IQ" value={props.scores.iq} />
          <div style={{ width: 1, background: COLORS.border }} />
          <MiniMetric label="Gravity" value={props.scores.gravity} />
        </div>

        {props.subtitle && (
          <span style={{ fontFamily: FONTS.mono, fontSize: 18, color: COLORS.textDim, letterSpacing: 2, textAlign: "center" }}>
            {props.subtitle}
          </span>
        )}
      </div>
    </AbsoluteFill>
  );
};
