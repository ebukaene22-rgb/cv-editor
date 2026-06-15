import { AbsoluteFill, Freeze, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { ClipAnnotation, ClipZoom } from "../types";
import { COLORS, FONTS } from "../theme";

interface Props {
  src: string;
  freezeAt: number;
  annotations: ClipAnnotation[];
  zoom?: ClipZoom;
}

// V6 Path A: Real footage as primary evidence. Plays clip → optionally Ken Burns
// zooms toward the evidence point → freezes → SVG annotations animate in on the
// frozen frame. The score reveals only after this (handled by parent timing).
export const ClipEvidence: React.FC<Props> = ({ src, freezeAt, annotations, zoom }) => {
  const { fps } = useVideoConfig();
  const freezeFrame = Math.round(freezeAt * fps);

  return (
    <AbsoluteFill>
      {/* Phase 1: clip plays live with optional Ken Burns zoom (0 → freezeFrame) */}
      <Sequence from={0} durationInFrames={freezeFrame} layout="none">
        <LiveClip src={src} freezeFrame={freezeFrame} zoom={zoom} />
      </Sequence>

      {/* Phase 2: frozen frame at the zoomed-in state + annotations (freezeFrame → end) */}
      <Sequence from={freezeFrame} layout="none">
        <FrozenFrame src={src} freezeFrame={freezeFrame} annotations={annotations} zoom={zoom} />
      </Sequence>
    </AbsoluteFill>
  );
};

const LiveClip: React.FC<{ src: string; freezeFrame: number; zoom?: ClipZoom }> = ({ src, freezeFrame, zoom }) => {
  const frame = useCurrentFrame();

  // Ken Burns: scale 1.0 → zoom.scale over the clip's live phase, focused on (x, y).
  const scale = zoom
    ? interpolate(frame, [0, freezeFrame], [1, zoom.scale], { extrapolateRight: "clamp" })
    : 1;
  const originX = zoom?.x ?? 50;
  const originY = zoom?.y ?? 50;

  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <OffthreadVideo
        src={staticFile(src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale})`,
          transformOrigin: `${originX}% ${originY}%`,
        }}
      />
    </AbsoluteFill>
  );
};

const FrozenFrame: React.FC<{
  src: string;
  freezeFrame: number;
  annotations: ClipAnnotation[];
  zoom?: ClipZoom;
}> = ({ src, freezeFrame, annotations, zoom }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const annotationOpacity = interpolate(frame, [0, fps * 0.35], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const freezeTagOpacity = interpolate(frame, [0, fps * 0.2], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Frozen state holds the final zoomed scale; annotations live on top in the same coord space.
  const scale = zoom?.scale ?? 1;
  const originX = zoom?.x ?? 50;
  const originY = zoom?.y ?? 50;

  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <Freeze frame={freezeFrame}>
        <OffthreadVideo
          src={staticFile(src)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: `scale(${scale})`,
            transformOrigin: `${originX}% ${originY}%`,
          }}
        />
      </Freeze>

      {/* SVG annotation overlay — coords are in 0-100 wide, 0-177 tall (9:16) */}
      <svg
        viewBox="0 0 100 177"
        preserveAspectRatio="xMidYMid slice"
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
        opacity={annotationOpacity}
      >
        <defs>
          <marker id="ann-arrow" viewBox="0 0 10 10" refX="7" refY="5"
            markerWidth="4" markerHeight="4" orient="auto-start-reverse">
            <path d="M 0 1 L 9 5 L 0 9 z" fill={COLORS.accent} />
          </marker>
        </defs>
        {annotations.map((ann, i) => <AnnotationShape key={i} ann={ann} />)}
      </svg>

      {/* FREEZE tag — signals analysis moment to mute viewer */}
      <div style={{
        position: "absolute",
        top: 16,
        right: 16,
        fontFamily: FONTS.mono,
        fontSize: 13,
        color: COLORS.accent,
        letterSpacing: 3,
        border: `1px solid ${COLORS.accent}`,
        padding: "3px 10px",
        background: "rgba(0,0,0,0.6)",
        opacity: freezeTagOpacity,
      }}>
        ■ FREEZE
      </div>
    </AbsoluteFill>
  );
};

const AnnotationShape: React.FC<{ ann: ClipAnnotation }> = ({ ann }) => {
  const color = ann.color ?? COLORS.accent;

  if (ann.type === "circle") {
    const r = ann.r ?? 6;
    return (
      <g>
        <circle cx={ann.x} cy={ann.y} r={r} fill="none" stroke={color}
          strokeWidth="0.9" strokeDasharray="2 1.5" vectorEffect="non-scaling-stroke" />
        {ann.label && (
          <g>
            <rect x={ann.x - ann.label.length * 1.3} y={ann.y - r - 7}
              width={ann.label.length * 2.6} height="5.5"
              fill="rgba(0,0,0,0.7)" />
            <text x={ann.x} y={ann.y - r - 3} fontFamily={FONTS.mono} fontSize="4"
              fill={color} textAnchor="middle" letterSpacing="0.3">
              {ann.label}
            </text>
          </g>
        )}
      </g>
    );
  }

  if (ann.type === "arrow") {
    return (
      <line x1={ann.x} y1={ann.y} x2={ann.x2 ?? ann.x} y2={ann.y2 ?? ann.y}
        stroke={color} strokeWidth="0.9"
        markerEnd="url(#ann-arrow)" vectorEffect="non-scaling-stroke" />
    );
  }

  if (ann.type === "zone") {
    const w = ann.w ?? 20;
    const h = ann.h ?? 15;
    return (
      <g>
        <rect x={ann.x} y={ann.y} width={w} height={h}
          fill={`${color}18`} stroke={color} strokeWidth="0.6"
          strokeDasharray="2 1.5" vectorEffect="non-scaling-stroke" />
        {ann.label && (
          <g>
            <rect x={ann.x} y={ann.y - 6} width={ann.label.length * 2.5} height="5.5"
              fill="rgba(200,16,46,0.85)" />
            <text x={ann.x + 1.5} y={ann.y - 2} fontFamily={FONTS.mono} fontSize="3.8"
              fill="#fff" letterSpacing="0.3">
              {ann.label}
            </text>
          </g>
        )}
      </g>
    );
  }

  return null;
};
