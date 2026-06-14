import { COLORS } from "./theme";

// The verdict vocabulary is shared between thumbnail and video so the channel
// speaks with one voice. The accusation (hook) and the resolved label (verdict
// scene) are derived from the transferability score when not set explicitly.

export interface Verdict {
  hook: string;   // 0-2s accusation — always ends in "?"
  label: string;  // resolved verdict shown in the verdict scene
  color: string;  // green = validated outlier, red = at risk
  positive: boolean;
}

export const deriveVerdict = (
  transferability: number,
  hook?: string,
  label?: string,
): Verdict => {
  let dHook: string;
  let dLabel: string;
  let positive: boolean;

  if (transferability >= 75) {
    dHook = "OUTLIER?";
    dLabel = "SYSTEM-INDEPENDENT OUTLIER";
    positive = true;
  } else if (transferability >= 60) {
    dHook = "TRANSFER TRAP?";
    dLabel = "TRANSFERABLE — WITH CONDITIONS";
    positive = false;
  } else {
    dHook = "SYSTEM PRODUCT?";
    dLabel = "SYSTEM PRODUCT — AT RISK";
    positive = false;
  }

  return {
    hook: hook ?? dHook,
    label: label ?? dLabel,
    color: positive ? "#22c55e" : COLORS.accent,
    positive,
  };
};
