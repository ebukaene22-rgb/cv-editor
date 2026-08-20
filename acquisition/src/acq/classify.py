"""Listing-text classification for the two rules arithmetic can't reach.

`CHANNEL_RISK` and the narrative half of `SELF_CONTRADICTORY` live in prose, not
in numbers. Two implementations:

  HeuristicClassifier — phrase matching. Deterministic, offline, free. This is
    what the Appendix A regression suite runs against, so an acceptance run
    never depends on a network call or on model sampling.
  ClaudeClassifier   — an Anthropic API call returning a strict boolean plus the
    sentence that triggered it, per §6 of the brief. Falls back to the heuristic
    on any API failure, because a screening run that dies on a 429 is worse than
    one that degrades to keyword matching and says so.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

MODEL = "claude-opus-5"

# Phrases that mean "the channel is a person, not an asset". Stage 6 of the
# playbook: only an account or a ranking transfers — a person does not.
CHANNEL_RISK_PHRASES = (
    "my audience", "my following", "my twitter", "my x account", "my linkedin",
    "my newsletter", "my youtube", "my tiktok", "my instagram", "my community",
    "my personal", "personal brand", "personal account", "founder's audience",
    "my subscribers", "my list", "build in public", "buildinpublic",
    "product hunt launch", "launched on product hunt", "hacker news front page",
    "went viral", "viral tweet", "viral launch", "launch spike", "featured on",
    "my followers", "i promoted", "i posted", "from my own channels",
    "own channels", "indie hackers post", "reddit post drove",
)

# Prose that contradicts arithmetic: a stated multiple or payback claim the
# computed figures don't support.
CONTRADICTION_PHRASES = (
    "2x revenue", "3x revenue", "2x multiple", "3x multiple",
    "priced at 2x", "priced at 3x", "a steal at", "conservative multiple",
    "pays for itself in", "roi in", "payback in",
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?\n])\s+")


@dataclass
class Classification:
    triggered: bool
    evidence: str = ""
    method: str = "heuristic"       # "heuristic" | "claude" | "heuristic-fallback"


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text or "") if s.strip()]


class HeuristicClassifier:
    """Deterministic phrase matching. Returns the offending sentence as evidence."""

    name = "heuristic"

    def channel_risk(self, text: str) -> Classification:
        return self._match(text, CHANNEL_RISK_PHRASES)

    def stated_claim_contradiction(self, text: str) -> Classification:
        return self._match(text, CONTRADICTION_PHRASES)

    @staticmethod
    def _match(text: str, phrases: tuple[str, ...]) -> Classification:
        lowered = (text or "").lower()
        for phrase in phrases:
            if phrase in lowered:
                for sentence in _sentences(text):
                    if phrase in sentence.lower():
                        return Classification(True, sentence[:300], "heuristic")
                return Classification(True, phrase, "heuristic")
        return Classification(False, "", "heuristic")


CHANNEL_RISK_SYSTEM = """\
You screen micro-SaaS acquisition listings for channel risk.

Channel risk means the product's customer acquisition depends on something that
does NOT transfer to a new owner: the founder's personal audience, their personal
social or newsletter accounts, a one-off launch spike (Product Hunt, Hacker News,
a viral post), or word of mouth from the founder personally.

It is NOT channel risk when acquisition is organic search, an app-store or
directory listing, paid ads, SEO content, or an integration marketplace — those
transfer with the asset.

Judge only what the listing text says. If the text does not describe how
customers are acquired, that is not evidence of risk: answer false.
Quote the single sentence that decided it, verbatim, in `evidence`.
"""

_SCHEMA = {
    "type": "object",
    "properties": {
        "channel_risk": {"type": "boolean"},
        "evidence": {"type": "string"},
    },
    "required": ["channel_risk", "evidence"],
    "additionalProperties": False,
}


class ClaudeClassifier:
    """LLM classification with a hard heuristic fallback."""

    name = "claude"

    def __init__(self, model: str = MODEL, fallback: HeuristicClassifier | None = None) -> None:
        self.model = model
        self.fallback = fallback or HeuristicClassifier()
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic  # imported lazily: the offline path must not need the SDK

            self._client = anthropic.Anthropic()
        return self._client

    def available(self) -> bool:
        if os.environ.get("ACQ_NO_LLM"):
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def channel_risk(self, text: str) -> Classification:
        if not (text or "").strip():
            return Classification(False, "", "heuristic")
        if not self.available():
            return self._degrade(text, "LLM disabled or SDK missing")
        try:
            import anthropic

            resp = self._get_client().messages.create(
                model=self.model,
                max_tokens=2000,
                system=CHANNEL_RISK_SYSTEM,
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": _SCHEMA},
                },
                messages=[{"role": "user", "content": f"<listing>\n{text}\n</listing>"}],
            )
            if resp.stop_reason == "refusal":
                return self._degrade(text, "model declined to classify")
            body = next(b.text for b in resp.content if b.type == "text")
            data = json.loads(body)
            return Classification(bool(data["channel_risk"]), str(data.get("evidence", "")), "claude")
        except anthropic.RateLimitError:
            return self._degrade(text, "rate limited")
        except anthropic.APIStatusError as exc:
            return self._degrade(text, f"API error {exc.status_code}")
        except anthropic.APIConnectionError:
            return self._degrade(text, "network error")
        except Exception as exc:  # parse errors, auth resolution, anything else
            return self._degrade(text, f"{type(exc).__name__}: {exc}")

    def stated_claim_contradiction(self, text: str) -> Classification:
        return self.fallback.stated_claim_contradiction(text)

    def _degrade(self, text: str, why: str) -> Classification:
        # Fail loudly, not silently — §10 of the brief.
        print(f"WARN classify: falling back to heuristic ({why})")
        result = self.fallback.channel_risk(text)
        result.method = "heuristic-fallback"
        return result


def get_classifier(use_llm: bool = False):
    return ClaudeClassifier() if use_llm else HeuristicClassifier()
