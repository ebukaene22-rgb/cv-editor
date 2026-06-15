import { Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS } from "../theme";

interface Props {
  imageKey: string;
  mode: "hero" | "ghost" | "medium";
  // hero:   35-40% of frame, high opacity, prominent entrance — ClaimScene
  // medium: 25% of frame, 50% opacity, parallax — TensionScene
  // ghost:  18% opacity, full bleed background — evidence scenes
}

// Animated player cutout that adapts per scene.
// hero mode: the player dominates first 5 seconds — instant recognition.
// All modes add parallax motion so a static image never sits dead on screen.
export const PlayerCutout: React.FC<Props> = ({ imageKey, mode }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();

  // Subtle ambient drift — even in ghost mode nothing is truly static.
  const drift = Math.sin(frame / (fps * 3)) * 8;
  const driftX = Math.cos(frame / (fps * 4.5)) * 5;

  if (mode === "hero") {
    // Slam in from bottom-right with overshoot, then settle.
    const enterProgress = interpolate(frame, [0, fps * 0.5, fps * 0.7], [0, 1.05, 1], {
      extrapolateRight: "clamp",
    });
    const opacity = interpolate(frame, [0, fps * 0.25], [0, 1], {
      extrapolateRight: "clamp",
    });
    // Subtle Ken Burns — slow zoom into the player over the clip duration.
    const zoom = interpolate(frame, [0, fps * 5], [1, 1.04], {
      extrapolateRight: "clamp",
    });

    return (
      <div
        style={{
          position: "absolute",
          right: 0,
          bottom: 0,
          width: "55%",
          height: "75%",
          opacity: opacity * enterProgress,
          transform: `translateY(${(1 - enterProgress) * 80}px) translateX(${driftX}px) scale(${zoom})`,
          transformOrigin: "bottom right",
        }}
      >
        <Img
          src={staticFile(imageKey)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "contain",
            objectPosition: "bottom right",
          }}
        />
      </div>
    );
  }

  if (mode === "medium") {
    const opacity = interpolate(frame, [0, fps * 0.4], [0, 0.5], {
      extrapolateRight: "clamp",
    });
    return (
      <div
        style={{
          position: "absolute",
          right: -20,
          bottom: 0,
          width: "45%",
          height: "60%",
          opacity,
          transform: `translateY(${drift}px) translateX(${driftX}px)`,
          mixBlendMode: "luminosity",
        }}
      >
        <Img
          src={staticFile(imageKey)}
          style={{ width: "100%", height: "100%", objectFit: "contain", objectPosition: "bottom right" }}
        />
      </div>
    );
  }

  // ghost
  const opacity = interpolate(frame, [0, fps * 0.5], [0, 0.14], {
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        position: "absolute",
        right: 0,
        bottom: 0,
        width: "60%",
        height: "70%",
        opacity,
        transform: `translateY(${drift * 0.5}px) translateX(${driftX * 0.5}px)`,
        mixBlendMode: "luminosity",
      }}
    >
      <Img
        src={staticFile(imageKey)}
        style={{ width: "100%", height: "100%", objectFit: "contain", objectPosition: "bottom right" }}
      />
    </div>
  );
};
