import { AbsoluteFill } from "remotion";
import { ClassificationReveal } from "../components/ClassificationReveal";
import { deriveVerdict } from "../verdict";

interface Props {
  transferability: number;
  reveal: string;
  verdictLabelText?: string;
  durationFrames: number;
}

// The emotional climax: transferability drops in a classified-document reveal.
// The spoken `reveal` text is the narration; visually this is the classification sequence.
export const VerdictScene: React.FC<Props> = ({
  transferability,
  reveal,
  verdictLabelText,
  durationFrames,
}) => {
  const v = deriveVerdict(transferability, undefined, verdictLabelText);

  return (
    <AbsoluteFill>
      <ClassificationReveal
        score={transferability}
        verdictColor={v.color}
        verdictLabel={v.label}
        durationFrames={durationFrames}
      />
    </AbsoluteFill>
  );
};
