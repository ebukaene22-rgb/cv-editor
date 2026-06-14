import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Caption } from "../components/Caption";
import { COLORS, FONTS } from "../theme";
import { deriveVerdict } from "../verdict";

interface Props {
  transferability: number;
  verdict: string;
  verdictLabelText?: string;
  durationFrames: number;
}

export const VerdictScene: React.FC<Props> = ({
  transferability,
  verdict,
  verdictLabelText,
  durationFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const v = deriveVerdict(transferability, undefined, verdictLabelText);
  const verdictColor = v.color;
  const verdictLabel = v.label;

  const labelOpacity = interpolate(frame, [0, fps * 0.35], [0, 1], {
    extrapolateRight: "clamp",
  });

  const scoreProgress = interpolate(
    frame,
    [Math.round(fps * 0.4), Math.round(fps * 1.2)],
    [0, transferability],
    { extrapolateRight: "clamp" }
  );

  const scoreOpacity = interpolate(frame, [Math.round(fps * 0.4), Math.round(fps * 0.7)], [0, 1], {
    extrapolateRight: "clamp",
  });

  const captionStart = Math.round(fps * 1.4);

  return (
    <AbsoluteFill
      style={{
        background: COLORS.bg,
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: "120px 60px 100px",
      }}
    >
      {/* Verdict classification banner */}
      <div
        style={{
          opacity: labelOpacity,
          borderLeft: `6px solid ${verdictColor}`,
          paddingLeft: 32,
          marginBottom: 60,
        }}
      >
        <div
          style={{
            fontFamily: FONTS.mono,
            fontSize: 22,
            color: COLORS.textMuted,
            letterSpacing: 4,
            marginBottom: 10,
          }}
        >
          SYSTEM VERDICT
        </div>
        <div
          style={{
            fontFamily: FONTS.mono,
            fontSize: 34,
            color: verdictColor,
            fontWeight: "bold",
            letterSpacing: 2,
            lineHeight: 1.2,
          }}
        >
          {verdictLabel}
        </div>
      </div>

      {/* Transferability score — big animated number */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          opacity: scoreOpacity,
        }}
      >
        <div
          style={{
            fontFamily: FONTS.mono,
            fontSize: 22,
            color: COLORS.textMuted,
            letterSpacing: 6,
            marginBottom: 16,
          }}
        >
          TRANSFERABILITY SCORE
        </div>
        <div
          style={{
            fontFamily: FONTS.mono,
            fontSize: 200,
            fontWeight: "bold",
            color: verdictColor,
            lineHeight: 1,
          }}
        >
          {Math.round(scoreProgress)}
        </div>
        <div
          style={{
            fontFamily: FONTS.mono,
            fontSize: 56,
            color: verdictColor,
            letterSpacing: 4,
            marginTop: -10,
          }}
        >
          %
        </div>

        {/* Arc gauge underneath the number */}
        <div
          style={{
            width: 360,
            height: 8,
            background: COLORS.scoreBarBg,
            borderRadius: 4,
            overflow: "hidden",
            marginTop: 30,
          }}
        >
          <div
            style={{
              width: `${scoreProgress}%`,
              height: "100%",
              background: verdictColor,
              borderRadius: 4,
            }}
          />
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            width: 360,
            marginTop: 8,
            fontFamily: FONTS.mono,
            fontSize: 20,
            color: COLORS.textDim,
          }}
        >
          <span>0</span>
          <span>100%</span>
        </div>
      </div>

      {/* Divider */}
      <div style={{ height: 1, background: COLORS.border, margin: "40px 0" }} />

      {/* Verdict caption */}
      <Caption
        text={verdict}
        startFrame={captionStart}
        endFrame={durationFrames - Math.round(fps * 0.3)}
      />
    </AbsoluteFill>
  );
};
