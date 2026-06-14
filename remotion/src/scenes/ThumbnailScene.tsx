import { AbsoluteFill, Img, staticFile } from "remotion";
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
  // Player image
  player_image_key?: string;      // relative to remotion/public/, e.g. "players/pedri.png"
  player_image_position?: "right" | "left" | "centre" | "behind_text";
  player_image_scale?: number;
  player_image_opacity?: number;
  player_image_rotation?: number;
}

const ACCENT: Record<string, string> = {
  red: COLORS.accent,
  green: "#22c55e",
};

// ── Sub-components ───────────────────────────────────────────────────────────

const VerdictStamp: React.FC<{
  label: string;
  color: string;
  angle?: number;
  fontSize?: number;
}> = ({ label, color, angle = -14, fontSize = 54 }) => (
  <div
    style={{
      display: "inline-block",
      border: `7px solid ${color}`,
      padding: "10px 22px",
      transform: `rotate(${angle}deg)`,
      background: "rgba(0,0,0,0.35)",
      backdropFilter: "blur(2px)",
    }}
  >
    <span
      style={{
        fontFamily: FONTS.mono,
        fontSize,
        fontWeight: "bold",
        color,
        letterSpacing: 4,
        textTransform: "uppercase",
        lineHeight: 1,
        display: "block",
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </span>
  </div>
);

const MiniMetric: React.FC<{ label: string; value: number }> = ({ label, value }) => (
  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}>
    <span style={{ fontFamily: FONTS.mono, fontSize: 18, color: COLORS.textMuted, letterSpacing: 2, textTransform: "uppercase" }}>
      {label}
    </span>
    <span style={{ fontFamily: FONTS.mono, fontSize: 32, fontWeight: "bold", color: COLORS.text, lineHeight: 1 }}>
      {value}
    </span>
  </div>
);

const TransferabilityBar: React.FC<{ value: number; color: string }> = ({ value, color }) => (
  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
    <span style={{ fontFamily: FONTS.mono, fontSize: 20, color: COLORS.textMuted, letterSpacing: 3, textTransform: "uppercase", whiteSpace: "nowrap" }}>
      Transferability
    </span>
    <span style={{ fontFamily: FONTS.mono, fontSize: 44, fontWeight: "bold", color, lineHeight: 1 }}>
      {value}%
    </span>
  </div>
);

const MetricRow: React.FC<{ scores: ThumbnailProps["scores"] }> = ({ scores }) => (
  <div
    style={{
      display: "flex",
      justifyContent: "space-around",
      borderTop: `1px solid ${COLORS.border}`,
      paddingTop: 16,
    }}
  >
    <MiniMetric label="Instinct" value={scores.instinct} />
    <div style={{ width: 1, background: COLORS.border }} />
    <MiniMetric label="IQ" value={scores.iq} />
    <div style={{ width: 1, background: COLORS.border }} />
    <MiniMetric label="Gravity" value={scores.gravity} />
  </div>
);

// ── Player image layer ───────────────────────────────────────────────────────

const PlayerImage: React.FC<{
  src: string;
  position: string;
  scale: number;
  opacity: number;
  rotation: number;
}> = ({ src, position, scale, opacity, rotation }) => {
  const baseImg: React.CSSProperties = {
    position: "absolute",
    objectFit: "contain",
    opacity,
    transform: `rotate(${rotation}deg) scale(${scale})`,
    transformOrigin: "bottom center",
    userSelect: "none",
    pointerEvents: "none",
  };

  switch (position) {
    case "right":
      return (
        <img
          src={src}
          style={{
            ...baseImg,
            right: -30,
            bottom: 0,
            height: "88%",
            width: "58%",
            objectPosition: "top center",
          }}
          crossOrigin="anonymous"
        />
      );
    case "left":
      return (
        <img
          src={src}
          style={{
            ...baseImg,
            left: -30,
            bottom: 0,
            height: "88%",
            width: "58%",
            objectPosition: "top center",
          }}
          crossOrigin="anonymous"
        />
      );
    case "centre":
      return (
        <img
          src={src}
          style={{
            ...baseImg,
            left: "50%",
            bottom: 0,
            transform: `translateX(-50%) rotate(${rotation}deg) scale(${scale})`,
            height: "72%",
            width: "80%",
            objectPosition: "top center",
          }}
          crossOrigin="anonymous"
        />
      );
    case "behind_text":
      return (
        <img
          src={src}
          style={{
            ...baseImg,
            left: 0,
            top: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
            opacity: opacity * 0.35,
          }}
          crossOrigin="anonymous"
        />
      );
    default:
      return null;
  }
};

// Gradient that protects text legibility when the image is near text
const TextProtectionGradient: React.FC<{ position: string }> = ({ position }) => {
  const gradients: Record<string, string> = {
    right: `linear-gradient(to right, rgba(10,10,10,0.98) 38%, rgba(10,10,10,0.6) 62%, rgba(10,10,10,0.05) 100%)`,
    left: `linear-gradient(to left, rgba(10,10,10,0.98) 38%, rgba(10,10,10,0.6) 62%, rgba(10,10,10,0.05) 100%)`,
    centre: `linear-gradient(to bottom, rgba(10,10,10,0.95) 0%, rgba(10,10,10,0.3) 30%, rgba(10,10,10,0.3) 70%, rgba(10,10,10,0.95) 100%)`,
    behind_text: `linear-gradient(to bottom, rgba(10,10,10,0.7) 0%, rgba(10,10,10,0.4) 40%, rgba(10,10,10,0.7) 100%)`,
  };

  if (!gradients[position]) return null;

  return (
    <AbsoluteFill
      style={{
        background: gradients[position],
        pointerEvents: "none",
      }}
    />
  );
};

// ── Layout renderers ─────────────────────────────────────────────────────────

// Shared bottom data strip
const DataStrip: React.FC<{
  transferability: number;
  scores: ThumbnailProps["scores"];
  color: string;
}> = ({ transferability, scores, color }) => (
  <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
    <TransferabilityBar value={transferability} color={color} />
    <MetricRow scores={scores} />
  </div>
);

const LayoutRight: React.FC<ThumbnailProps & { color: string }> = (props) => {
  const isTransferTrap = props.variant === "transfer_trap";
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between", padding: "60px 56px 60px 56px", zIndex: 2, position: "relative" }}>
      {/* Top: CASE FILE label */}
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span style={{ fontFamily: FONTS.mono, fontSize: 22, color: COLORS.textDim, letterSpacing: 5 }}>CASE FILE</span>
        <span style={{ fontFamily: FONTS.mono, fontSize: 18, color: COLORS.textDim, letterSpacing: 3 }}>PFD</span>
      </div>

      {/* Player name + optional club line */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <div style={{
          fontFamily: FONTS.mono,
          fontSize: props.player_name.length > 8 ? 88 : 116,
          fontWeight: "bold",
          color: COLORS.text,
          lineHeight: 0.88,
          textTransform: "uppercase",
          letterSpacing: -3,
          maxWidth: "62%",
        }}>
          {props.player_name}
        </div>
        {isTransferTrap && props.transfer_club && (
          <div style={{ fontFamily: FONTS.mono, fontSize: 38, color: COLORS.textMuted, textTransform: "uppercase", letterSpacing: 2, marginTop: 4 }}>
            TO {props.transfer_club}?
          </div>
        )}
        {props.collapse_risk && props.variant === "system_product" && (
          <div style={{ marginTop: 12, display: "inline-flex", background: props.color, padding: "6px 18px", alignSelf: "flex-start" }}>
            <span style={{ fontFamily: FONTS.mono, fontSize: 20, color: "#fff", fontWeight: "bold", letterSpacing: 4, textTransform: "uppercase" }}>
              COLLAPSE RISK: {props.collapse_risk}
            </span>
          </div>
        )}
      </div>

      {/* Verdict stamp — sits over the name block, angled */}
      <div style={{ alignSelf: "flex-start", marginTop: -10 }}>
        <VerdictStamp label={props.verdict_label} color={props.color} />
      </div>

      {/* Data strip */}
      <DataStrip transferability={props.transferability} scores={props.scores} color={props.color} />
    </div>
  );
};

// Left layout mirrors right, text on right side
const LayoutLeft: React.FC<ThumbnailProps & { color: string }> = (props) => {
  const isTransferTrap = props.variant === "transfer_trap";
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between", padding: "60px 56px 60px 56px", zIndex: 2, position: "relative" }}>
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <span style={{ fontFamily: FONTS.mono, fontSize: 22, color: COLORS.textDim, letterSpacing: 5 }}>CASE FILE</span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end", textAlign: "right" }}>
        <div style={{
          fontFamily: FONTS.mono,
          fontSize: props.player_name.length > 8 ? 88 : 116,
          fontWeight: "bold",
          color: COLORS.text,
          lineHeight: 0.88,
          textTransform: "uppercase",
          letterSpacing: -3,
          maxWidth: "62%",
        }}>
          {props.player_name}
        </div>
        {isTransferTrap && props.transfer_club && (
          <div style={{ fontFamily: FONTS.mono, fontSize: 38, color: COLORS.textMuted, textTransform: "uppercase", letterSpacing: 2 }}>
            TO {props.transfer_club}?
          </div>
        )}
      </div>

      <div style={{ alignSelf: "flex-end" }}>
        <VerdictStamp label={props.verdict_label} color={props.color} angle={14} />
      </div>

      <DataStrip transferability={props.transferability} scores={props.scores} color={props.color} />
    </div>
  );
};

// Centre: player behind, text top and bottom
const LayoutCentre: React.FC<ThumbnailProps & { color: string }> = (props) => (
  <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between", padding: "60px 56px 60px 56px", zIndex: 2, position: "relative" }}>
    <div style={{ display: "flex", justifyContent: "space-between" }}>
      <span style={{ fontFamily: FONTS.mono, fontSize: 22, color: COLORS.textDim, letterSpacing: 5 }}>CASE FILE</span>
      <span style={{ fontFamily: FONTS.mono, fontSize: 18, color: COLORS.textDim, letterSpacing: 3 }}>PFD</span>
    </div>
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 24 }}>
      <div style={{ fontFamily: FONTS.mono, fontSize: 112, fontWeight: "bold", color: COLORS.text, lineHeight: 0.9, textTransform: "uppercase", letterSpacing: -3, textAlign: "center" }}>
        {props.player_name}
      </div>
      <VerdictStamp label={props.verdict_label} color={props.color} />
    </div>
    <DataStrip transferability={props.transferability} scores={props.scores} color={props.color} />
  </div>
);

// Behind text: full-frame image, all text overlaid
const LayoutBehindText: React.FC<ThumbnailProps & { color: string }> = (props) => (
  <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between", padding: "60px 56px 60px 56px", zIndex: 2, position: "relative" }}>
    <span style={{ fontFamily: FONTS.mono, fontSize: 22, color: COLORS.textDim, letterSpacing: 5 }}>CASE FILE</span>
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ fontFamily: FONTS.mono, fontSize: 120, fontWeight: "bold", color: COLORS.text, lineHeight: 0.88, textTransform: "uppercase", letterSpacing: -3 }}>
        {props.player_name}
      </div>
      <VerdictStamp label={props.verdict_label} color={props.color} />
    </div>
    <DataStrip transferability={props.transferability} scores={props.scores} color={props.color} />
  </div>
);

// ── Main composition ──────────────────────────────────────────────────────────

export const ThumbnailScene: React.FC<ThumbnailProps> = (props) => {
  const color = ACCENT[props.verdict_color] ?? COLORS.accent;
  const position = props.player_image_position ?? "right";
  const scale = props.player_image_scale ?? 1.0;
  const opacity = props.player_image_opacity ?? 1.0;
  const rotation = props.player_image_rotation ?? 0;
  const imageKey = props.player_image_key ?? "players/placeholder.svg";
  const hasImage = true; // always render image layer; falls back to placeholder automatically

  const imageSrc = staticFile(imageKey);

  const layoutProps = { ...props, color };

  return (
    <AbsoluteFill style={{ background: COLORS.bg, overflow: "hidden" }}>
      {/* Grunge diagonal texture */}
      <AbsoluteFill
        style={{
          background: `repeating-linear-gradient(-55deg, transparent, transparent 8px, rgba(255,255,255,0.012) 8px, rgba(255,255,255,0.013) 9px)`,
          pointerEvents: "none",
        }}
      />

      {/* Player image layer */}
      {hasImage && (
        <PlayerImage
          src={imageSrc}
          position={position}
          scale={scale}
          opacity={opacity}
          rotation={rotation}
        />
      )}

      {/* Text protection gradient */}
      <TextProtectionGradient position={position} />

      {/* Text content — switches by position */}
      {position === "right" && <LayoutRight {...layoutProps} />}
      {position === "left" && <LayoutLeft {...layoutProps} />}
      {position === "centre" && <LayoutCentre {...layoutProps} />}
      {position === "behind_text" && <LayoutBehindText {...layoutProps} />}

      {/* Accent border edge line */}
      <AbsoluteFill
        style={{
          borderLeft: `4px solid ${color}`,
          opacity: 0.6,
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};
