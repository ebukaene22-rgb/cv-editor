import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { PlayerCutout } from "../components/PlayerCutout";
import { TacticalBoard } from "../components/TacticalBoard";
import { COLORS, FONTS } from "../theme";
import { deriveVerdict } from "../verdict";

interface Props {
  player: string;
  claim: string;
  transferability: number;
  verdictHook?: string;
  verdictLabel?: string;
  playerImageKey?: string;
  durationFrames: number;
}

// V3: The claim IS the hook. A single punchy sentence that poses the case.
// The viewer must feel "I need to know if this is true" within 5 seconds.
// Framework doesn't exist here. Verdict stamp is tiny, supporting, not hero.
export const ClaimScene: React.FC<Props> = ({
  player,
  claim,
  transferability,
  verdictHook,
  verdictLabel,
  playerImageKey,
  durationFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const verdict = deriveVerdict(transferability, verdictHook, verdictLabel);

  // Words in the claim enter sequentially — each word slams in, forcing the
  // viewer to read along and feel the accusation build word by word.
  const words = claim.split(" ");
  const totalRevealFrames = Math.round(fps * 3.0);
  const framesPerWord = totalRevealFrames / words.length;

  // Small stamp badge fades in only AFTER the claim is done being read.
  const stampOpacity = interpolate(
    frame,
    [totalRevealFrames, totalRevealFrames + fps * 0.4],
    [0, 0.7],
    { extrapolateRight: "clamp" }
  );

  // Subtle scanline flicker on entry.
  const scanOpacity = interpolate(frame, [0, 3, 6, 10, 14], [0, 0.15, 0, 0.06, 0], {
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
      {/* File header strip — minimal, doesn't distract from claim */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontFamily: FONTS.mono,
          fontSize: 20,
          color: COLORS.textDim,
          letterSpacing: 4,
          marginBottom: 80,
        }}
      >
        <span>FILE #IQ-001</span>
        <span>CLASSIFIED</span>
      </div>

      {/* THE CLAIM — takes up the full middle of the screen. */}
      {/* Each word slams in individually so the viewer reads at our pace. */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            fontFamily: FONTS.sans,
            fontSize: 88,
            fontWeight: "bold",
            color: COLORS.text,
            lineHeight: 1.1,
            textTransform: "uppercase",
            letterSpacing: 1,
          }}
        >
          {words.map((word, i) => {
            const wordFrame = Math.round(i * framesPerWord);
            const wOpacity = interpolate(
              frame,
              [wordFrame, wordFrame + Math.round(fps * 0.1)],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
            // Accent words (numbers, key nouns) flash red briefly then settle white.
            const isAccent = /[£€$\d%]/.test(word) || word.length > 6;
            const accentProgress = interpolate(
              frame,
              [wordFrame, wordFrame + Math.round(fps * 0.4)],
              [1, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
            const wordColor = isAccent
              ? `rgba(${200 - Math.round(accentProgress * (200 - 240))}, ${Math.round(accentProgress * 16)}, ${Math.round(accentProgress * 46)}, 1)`
              : COLORS.text;

            return (
              <span
                key={i}
                style={{
                  opacity: wOpacity,
                  display: "inline-block",
                  color: wordColor,
                  marginRight: "0.28em",
                }}
              >
                {word}
              </span>
            );
          })}
        </div>

        {/* Player name — smaller, underneath, fades in with claim */}
        <div
          style={{
            marginTop: 40,
            fontFamily: FONTS.mono,
            fontSize: 32,
            color: COLORS.textMuted,
            letterSpacing: 8,
            textTransform: "uppercase",
            opacity: interpolate(frame, [fps * 0.5, fps * 1], [0, 1], {
              extrapolateRight: "clamp",
            }),
          }}
        >
          {player.toUpperCase()}
        </div>
      </div>

      {/* Verdict badge — appears AFTER the claim has landed, not before */}
      <div
        style={{
          opacity: stampOpacity,
          alignSelf: "flex-start",
          border: `4px solid ${verdict.color}`,
          padding: "10px 24px",
          transform: "rotate(-5deg)",
        }}
      >
        <span
          style={{
            fontFamily: FONTS.mono,
            fontSize: 30,
            color: verdict.color,
            letterSpacing: 6,
            fontWeight: "bold",
          }}
        >
          {verdict.hook}
        </span>
      </div>

      {/* V5: background tactical flash — immediate visual so mute viewer sees football proof */}
      {/* Fades to near-invisible once the player cutout and claim dominate */}
      <AbsoluteFill style={{ zIndex: 0, pointerEvents: "none", opacity: interpolate(frame, [0, fps * 1.5, fps * 2.5], [0.18, 0.18, 0.06], { extrapolateRight: "clamp" }) }}>
        <TacticalBoard motif="transition" label="" startFrame={0} />
      </AbsoluteFill>

      {/* Hero player cutout — 35-40% of frame, slams in with claim */}
      {playerImageKey && (
        <AbsoluteFill style={{ zIndex: 0, pointerEvents: "none" }}>
          <PlayerCutout imageKey={playerImageKey} mode="hero" />
        </AbsoluteFill>
      )}

      {/* Scanline flicker */}
      <AbsoluteFill
        style={{
          background: `repeating-linear-gradient(
            0deg,
            transparent, transparent 3px,
            rgba(255,255,255,0.025) 3px, rgba(255,255,255,0.025) 4px
          )`,
          opacity: scanOpacity,
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};
