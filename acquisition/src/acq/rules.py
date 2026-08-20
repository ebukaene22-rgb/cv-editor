"""D5 — the rule engine. Phase 1 of the build order and the acceptance gate.

Two dispositions:

  reject — one or more hard rules fired. Dropped from the shortlist, but the
    reason is logged and the flags are still computed, so a rejection can be
    audited later ("why did we never see this one?") without a re-run.
  review — no hard reject. Goes to the human with every flag attached.

Design rules, both learned from the listings in Appendix A:

  1. Missing data never causes a hard reject. A rule that fires on `None`
     rejects an incomplete listing and a bad one identically, and the incomplete
     one might be the good deal. Missing data raises DATA_INCOMPLETE instead.
  2. Every rule that fires records the arithmetic that made it fire. A flag
     without its evidence is an opinion, and the human can't triage opinions.
"""
from __future__ import annotations

from .classify import HeuristicClassifier
from .config import Config
from .models import Candidate

# --- flag identifiers (the brief's §6 table, plus three additions) -----------
DECLINING = "DECLINING"
TREND_MISMATCH = "TREND_MISMATCH"                # addition — see rule_trend
LTV_IMPLAUSIBLE = "LTV_IMPLAUSIBLE"
CUSTOMER_COUNT_INFLATED = "CUSTOMER_COUNT_INFLATED"
SELF_CONTRADICTORY = "SELF_CONTRADICTORY"
COSTS_AMBIGUOUS = "COSTS_AMBIGUOUS"
UNVERIFIED = "UNVERIFIED"
CHANNEL_RISK = "CHANNEL_RISK"
DATA_INCOMPLETE = "DATA_INCOMPLETE"              # addition — see design rule 1
LOSS_MAKING = "LOSS_MAKING"                      # addition — negative profit

# Product shapes whose stated costs are almost always understated because the
# marginal cost scales with usage. §6: "AI/inference product with implausibly
# low costs".
INFERENCE_HINTS = (
    "ai", "gpt", "llm", "openai", "anthropic", "claude", "video", "image",
    "transcription", "speech", "voice", "render", "generation", "generator",
    "inference", "diffusion", "avatar",
)


def _pct(a: float, b: float) -> str:
    return f"{a:.4g} vs {b:.4g}"


class RuleEngine:
    def __init__(self, config: Config, classifier=None) -> None:
        self.cfg = config
        self.classifier = classifier or HeuristicClassifier()

    # ------------------------------------------------------------------ entry
    def screen(self, c: Candidate) -> Candidate:
        c.rejects = []
        c.flags = []
        self._hard_rejects(c)
        self._flags(c)
        c.disposition = "reject" if c.rejects else "review"
        self.score(c)
        return c

    def screen_all(self, candidates: list[Candidate]) -> list[Candidate]:
        return [self.screen(c) for c in candidates]

    # ---------------------------------------------------------- hard rejects
    def _reject(self, c: Candidate, rule: str, detail: str) -> None:
        c.rejects.append({"rule": rule, "detail": detail})

    def _hard_rejects(self, c: Candidate) -> None:
        cfg = self.cfg

        min_arpu = cfg["targets.min_arpu_gbp"]
        if c.arpu is not None and c.arpu < min_arpu:
            self._reject(c, "ARPU_BELOW_FLOOR",
                         f"arpu £{c.arpu:.2f} < £{min_arpu} — no paid channel is solvent here")

        max_ptr = cfg["thresholds.max_price_to_revenue"]
        if c.price_to_revenue is not None and c.price_to_revenue > max_ptr:
            self._reject(c, "PRICE_TO_REVENUE_TOO_HIGH",
                         f"price/revenue {c.price_to_revenue:.2f}x > {max_ptr}x")

        max_payback = cfg["thresholds.max_payback_months"]
        if c.monthly_profit is not None and c.monthly_profit <= 0:
            self._reject(c, "NOT_PROFITABLE",
                         f"monthly profit £{c.monthly_profit:.2f} — payback never arrives")
        elif c.payback_months is not None and c.payback_months > max_payback:
            self._reject(c, "PAYBACK_TOO_LONG",
                         f"payback {c.payback_months:.1f} months > {max_payback}")

        min_age = cfg["targets.min_age_months"]
        if c.age_months is not None and c.age_months < min_age:
            self._reject(c, "TOO_YOUNG",
                         f"{c.age_months:.0f} months live < {min_age} — no ranking history")

        if c.category and c.category in cfg.excluded_categories():
            self._reject(c, "CATEGORY_EXCLUDED", f"category '{c.category}' fails the thesis")

        if c.revenue_model and c.revenue_model in cfg.excluded_revenue_models():
            self._reject(c, "REVENUE_MODEL_EXCLUDED",
                         f"'{c.revenue_model}' is an acquisition engine, not a revenue book")

        if c.platform and c.platform in cfg.excluded_platforms():
            self._reject(c, "PLATFORM_EXCLUDED", f"platform '{c.platform}' excluded")

        lo, hi = cfg["budget.min_price_gbp"], cfg["budget.max_price_gbp"]
        if c.asking_price is not None and not (lo <= c.asking_price <= hi):
            self._reject(c, "PRICE_OUT_OF_BAND",
                         f"£{c.asking_price:,.0f} outside £{lo:,}–£{hi:,} — wrong tier")

    # ----------------------------------------------------------------- flags
    def _flag(self, c: Candidate, flag: str, trigger: str, evidence: str = "") -> None:
        """Record a flag once, but keep every trigger that fired it — the
        diligence pack has to show all the evidence, not the first piece."""
        for existing in c.flags:
            if existing["flag"] == flag:
                if trigger not in existing["trigger"]:
                    existing["trigger"] += f"; {trigger}"
                if evidence and evidence not in existing["evidence"]:
                    existing["evidence"] += f"; {evidence}"
                return
        c.flags.append({"flag": flag, "trigger": trigger, "evidence": evidence})

    def _flags(self, c: Candidate) -> None:
        self.rule_trend(c)
        self.rule_ltv(c)
        self.rule_customer_count(c)
        self.rule_self_contradictory(c)
        self.rule_costs(c)
        self.rule_verification(c)
        self.rule_channel(c)
        self.rule_completeness(c)
        self.rule_loss_making(c)

    def rule_trend(self, c: Candidate) -> None:
        """Run-rate against trailing, checked in both directions.

        Below the floor is the brief's DECLINING: the listing will quote the
        higher trailing figure and call it current. Far above the ceiling is the
        same lie inverted — a run-rate or "ARR" that trailing revenue does not
        support (Appendix A case 2: $5,753 "ARR" on $1,178 TTM). Real growth
        that steep in a 24-month-old product is possible but is not a figure to
        take on trust, which is why both directions flag rather than reject.
        """
        if c.trend_ratio is None:
            return
        lo = self.cfg["thresholds.min_trend_ratio"]
        hi = self.cfg.get("thresholds.max_trend_ratio", None)
        if c.trend_ratio < lo:
            self._flag(c, DECLINING, f"trend_ratio {c.trend_ratio:.2f} < {lo}",
                       f"run-rate £{c.run_rate_arr:,.0f} below TTM £{c.ttm_revenue:,.0f}")
        elif hi is not None and c.trend_ratio > hi:
            self._flag(c, TREND_MISMATCH, f"trend_ratio {c.trend_ratio:.2f} > {hi}",
                       f"claimed run-rate £{c.run_rate_arr:,.0f} against TTM "
                       f"£{c.ttm_revenue:,.0f} — the ARR figure is not in the trailing revenue")

    def rule_ltv(self, c: Candidate) -> None:
        """Does the seller's LTV survive arpu / churn?"""
        if c.stated_ltv is None or c.implied_lifetime is None:
            return
        tol = self.cfg["thresholds.ltv_tolerance"]

        if c.implied_ltv is not None:
            deviation = abs(c.implied_ltv - c.stated_ltv) / c.stated_ltv if c.stated_ltv else None
            if deviation is not None and deviation > tol:
                self._flag(c, LTV_IMPLAUSIBLE,
                           f"|implied {c.implied_ltv:,.0f} - stated {c.stated_ltv:,.0f}| "
                           f"/ stated = {deviation:.2f} > {tol}",
                           "usually a portfolio figure mislabelled as per-customer")
            return

        # No customer count, so implied_ltv can't be computed directly. Back the
        # ARPU out of the seller's own LTV instead: stated_ltv / lifetime. If
        # that exceeds total MRR, the LTV describes fewer than one customer.
        implied_arpu = c.stated_ltv / c.implied_lifetime
        if c.mrr is not None and implied_arpu > c.mrr:
            self._flag(c, LTV_IMPLAUSIBLE,
                       f"stated LTV £{c.stated_ltv:,.0f} / {c.implied_lifetime:.1f}mo lifetime "
                       f"implies ARPU £{implied_arpu:,.0f} against total MRR £{c.mrr:,.0f}",
                       "the stated LTV describes fewer than one paying customer")

    def rule_customer_count(self, c: Candidate) -> None:
        """Can the stated customers all be paying?"""
        ratio_floor = self.cfg["thresholds.customer_inflation_ratio"]
        min_price = c.min_customer_price or self.cfg["thresholds.min_customer_price_gbp"]

        if c.mrr is not None and c.active_customers and min_price:
            ratio = c.mrr / (c.active_customers * min_price)
            if ratio < ratio_floor:
                self._flag(c, CUSTOMER_COUNT_INFLATED,
                           f"mrr / (customers × min_price) = {ratio:.3f} < {ratio_floor}",
                           f"£{c.mrr:,.0f} MRR cannot cover {c.active_customers:,.0f} customers "
                           f"at £{min_price:,.2f} — signups or free users")

        if c.paying_customers is not None and c.active_customers:
            conversion = c.paying_customers / c.active_customers
            if conversion < ratio_floor:
                self._flag(c, CUSTOMER_COUNT_INFLATED,
                           f"paying / stated customers = {conversion:.4f} < {ratio_floor}",
                           f"{c.paying_customers:,.0f} payers against {c.active_customers:,.0f} "
                           f"stated — the headline count is users, not customers")

    def rule_self_contradictory(self, c: Candidate) -> None:
        """The listing's own numbers disagree with each other."""
        tol = self.cfg["thresholds.ltv_tolerance"]

        if c.stated_multiple is not None and c.price_to_revenue:
            deviation = abs(c.stated_multiple - c.price_to_revenue) / c.price_to_revenue
            if deviation > tol:
                self._flag(c, SELF_CONTRADICTORY,
                           f"stated multiple {c.stated_multiple:.2g}x vs computed "
                           f"{c.price_to_revenue:.2f}x",
                           "treat every other figure on the page as unverified")

        if c.monthly_profit is not None and c.annual_revenue is not None:
            if c.monthly_profit * 12 > c.annual_revenue:
                self._flag(c, SELF_CONTRADICTORY,
                           f"stated monthly profit × 12 = £{c.monthly_profit * 12:,.0f} exceeds "
                           f"annual revenue £{c.annual_revenue:,.0f}",
                           "profit cannot exceed revenue")

        if c.listing_text:
            hit = self.classifier.stated_claim_contradiction(c.listing_text)
            if hit.triggered and c.price_to_revenue is not None and c.price_to_revenue > 5:
                self._flag(c, SELF_CONTRADICTORY,
                           f"listing states a cheap multiple; computed {c.price_to_revenue:.2f}x",
                           hit.evidence)

    def rule_costs(self, c: Candidate) -> None:
        """A single cost figure, no cost figure, or a margin inference won't survive."""
        if c.ttm_costs is None and c.annual_revenue is not None:
            self._flag(c, COSTS_AMBIGUOUS, "no cost figure stated",
                       "margin is unknown; ask for 3 months of hosting/API invoices")
            return

        blob = f"{c.name} {c.category} {c.listing_text}".lower()
        if any(hint in blob for hint in INFERENCE_HINTS):
            if c.annual_revenue and c.ttm_costs is not None:
                margin = (c.annual_revenue - c.ttm_costs) / c.annual_revenue
                if margin > 0.9:
                    self._flag(c, COSTS_AMBIGUOUS,
                               f"{margin:.0%} margin on an inference-shaped product",
                               "API/inference cost scales with usage; this margin will not "
                               "survive growth")

    def rule_verification(self, c: Candidate) -> None:
        """Flippa does not verify below $50k. Assume nothing."""
        if c.has_verified_revenue or c.trustmrr_match == "agrees":
            return
        detail = ("processor-verified figure disagrees with the listing"
                  if c.trustmrr_match == "disagrees"
                  else "no verified revenue and no TrustMRR match")
        self._flag(c, UNVERIFIED, "has_verified_revenue == false", detail)

    def rule_channel(self, c: Candidate) -> None:
        """Is the acquisition channel an account, a ranking, or a person?"""
        if not c.listing_text:
            return
        hit = self.classifier.channel_risk(c.listing_text)
        if hit.triggered:
            self._flag(c, CHANNEL_RISK, f"listing text ({hit.method})", hit.evidence)

    def rule_completeness(self, c: Candidate) -> None:
        """Nothing was rejected for these — but their absence is the finding."""
        missing = [name for name in ("asking_price", "annual_revenue", "mrr", "age_months")
                   if getattr(c, name) is None]
        if not missing:
            return
        self._flag(c, DATA_INCOMPLETE, f"missing: {', '.join(missing)}",
                   "screened on partial data — treat the score as provisional")

    def rule_loss_making(self, c: Candidate) -> None:
        if c.annual_profit is not None and c.annual_profit < 0:
            self._flag(c, LOSS_MAKING, f"annual profit £{c.annual_profit:,.0f}",
                       "costs exceed revenue on the seller's own figures")

    # ----------------------------------------------------------------- score
    def fit(self, c: Candidate) -> float:
        """Positive signal only. Flags are subtracted afterwards, so a product
        that scores well on fundamentals and badly on honesty still sorts below
        a plainer one that checks out."""
        s = self.cfg["scoring.fit.base"]

        if c.trend_ratio is not None:
            s += self.cfg["scoring.fit.trend_weight"] * max(0.0, min(1.0, c.trend_ratio))
        if c.payback_months is not None and c.payback_months > 0:
            cap = self.cfg["thresholds.max_payback_months"]
            s += self.cfg["scoring.fit.payback_weight"] * max(0.0, 1 - c.payback_months / cap)
        if c.price_to_revenue is not None and c.price_to_revenue > 0:
            cap = self.cfg["thresholds.max_price_to_revenue"]
            s += self.cfg["scoring.fit.multiple_weight"] * max(0.0, 1 - c.price_to_revenue / cap)
        if c.age_months is not None:
            floor = self.cfg["targets.min_age_months"]
            s += self.cfg["scoring.fit.age_weight"] * max(0.0, min(1.0, (c.age_months - floor) / 36))

        keywords = [k.lower() for k in self.cfg.get("audience.keywords", []) if k]
        if keywords:
            blob = f"{c.name} {c.category} {c.listing_text}".lower()
            if any(k in blob for k in keywords):
                s += self.cfg["scoring.fit.vertical_match_bonus"]
        return s

    def score(self, c: Candidate) -> float:
        c.fit_score = self.fit(c)
        penalty = self.cfg["scoring.flag_penalty"] * len(c.flags)
        bonus = (self.cfg["scoring.verification_bonus"]
                 if (c.has_verified_revenue or c.trustmrr_match == "agrees") else 0)
        c.score = round(c.fit_score - penalty + bonus, 2)
        return c.score
