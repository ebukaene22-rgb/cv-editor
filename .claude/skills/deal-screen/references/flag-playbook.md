# Flag playbook

Every flag, what it actually means, and the one thing to ask. Flags never
auto-reject — they are what the human is being handed. A flag you can't explain
in one sentence to the seller is a flag you haven't understood yet.

Thresholds live in `acquisition/config.yaml`. Read them there.

---

## `DECLINING`
**Fires when** `trend_ratio` (run-rate ÷ trailing) is below the floor.

Run-rate is under trailing revenue: the business made more over the last twelve
months than it is making now. The listing will present the higher trailing
figure and, often, call it ARR.

Flat or gently declining is acceptable at this size — collapsing is not. The
distinction is the *shape*, which one ratio cannot show you.

**Ask:** monthly revenue for each of the last 12 months, as a processor export.
Look for a step change and find out what happened in that month.

**Stop if:** the decline is a cliff rather than a slope, or it starts the month
the founder stopped working on it.

---

## `TREND_MISMATCH`
**Fires when** run-rate is far *above* trailing revenue.

The inverse lie. A listing quoting "$5,753 ARR" on $1,178 of trailing revenue is
not describing growth — it is annualising its best month, or its best week.
Real growth that steep exists, but it is a claim to verify, never one to price.

**Ask:** the same 12-month export, plus which month the ARR figure was computed
from.

**Stop if:** the "ARR" turns out to be one good month × 12.

---

## `LTV_IMPLAUSIBLE`
**Fires when** the seller's stated LTV doesn't survive `arpu / churn` — or,
where no customer count is given, when the LTV implies an ARPU larger than the
entire MRR (i.e. fewer than one paying customer).

Usually a portfolio figure mislabelled as per-customer value. Occasionally it is
lifetime *revenue* of the whole business divided by nothing in particular.

**Ask:** how the LTV was calculated, in one sentence.

**Stop if:** the answer is a rule of thumb rather than a cohort.

---

## `CUSTOMER_COUNT_INFLATED`
**Fires when** MRR cannot cover the stated customer count at the stated entry
price, or when disclosed payers are a small fraction of the headline count.

The stated customers are not all paying. Usually cumulative signups or free
users, sometimes deliberately blurred by quoting "users" in the headline and
"customers" in the metrics box.

**Ask:** current *active paying* subscriber count from the processor, and the
subscription/one-off split.

**Stop if:** the free-to-paid ratio means the paid product is a rounding error
on a free tool. You would be buying a hosting bill.

---

## `SELF_CONTRADICTORY`
**Fires when** the listing's own numbers disagree: a stated multiple that isn't
the computed one, or a stated profit that exceeds stated revenue.

Treat *everything else on the page* as unverified. This is not a negotiating
point about one figure; it is information about how the whole listing was
written.

**Ask:** nothing yet. Reconcile the two figures yourself first, then ask which
one is right and why the other is there.

**Stop if:** the explanation requires the seller to have misunderstood their own
business.

---

## `COSTS_AMBIGUOUS`
**Fires when** no cost figure is given, or an inference-shaped product reports a
margin above 90%.

AI and video products are the common case: API cost per active user is real,
scales with usage, and is almost always quoted as the current bill rather than
the marginal cost. A margin that only survives at current volume is not a margin.

**Ask:** hosting and API invoices for three months, and the cost per active user.
Then compute what that becomes at 3× volume.

**Stop if:** the product is only profitable because nobody uses it.

---

## `UNVERIFIED`
**Fires when** there is no verified revenue figure and no agreeing TrustMRR match.

Below $50k, Flippa does not verify. This is the **default state**, not an
accusation — nearly every candidate in this tier carries it. What it means is
that nothing on the page has independent support yet.

**Ask:** read-only processor access, or a live screen-share of the dashboard.

**Stop if:** refused with no reason given. Ask once, plainly: *"Is there a reason
you'd rather not share processor data directly?"* A good reason exists
occasionally. Usually the refusal is the answer.

---

## `CHANNEL_RISK`
**Fires when** the listing text points at the founder's own audience, personal
accounts, or a launch spike.

The single most expensive thing to get wrong at this size, because it is
invisible in every financial figure and it transfers to nobody. A product with
perfect numbers and a founder-shaped channel is worth close to nothing to a
buyer who is not that founder.

**Ask:** where the last 20 customers came from. Aggregate traffic figures are
easy to fabricate; twenty specific answers are not.

**Stop if:** the honest answer is "my audience".

---

## `LOSS_MAKING`
**Fires when** annual profit is negative on the seller's own figures.

Rare, and it means the listing is being sold on revenue or on hope. There is no
payback period.

**Stop:** almost always.

---

## `DATA_INCOMPLETE`
**Fires when** price, revenue, MRR or age is missing.

Not a defect in the business — a defect in the listing. The candidate was
screened on partial data and its score is provisional. Nothing was hard-rejected
on the missing fields, deliberately: a rule that fires on absent data rejects an
incomplete listing and a bad one identically, and the incomplete one might be
the good deal.

**Ask:** the missing figures, before anything else.
