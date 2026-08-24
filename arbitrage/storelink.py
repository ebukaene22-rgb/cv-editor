#!/usr/bin/env python3
"""
Independent evidence that an eBay handle belongs to a brand.

`exitvenue.py` resolves handles by NAME. Name morphology is evidence, not
identity: a brand appends to its own name (`gymshark-store`), but so can a
reseller. An exact handle can equally be coincidence, an abandoned
registration, or an unrelated seller. Nothing eBay's Browse API exposes
settles it -- feedback, category mix and brand-heavy titles are all just as
consistent with a dedicated reseller as with the brand itself.

One source can settle it: **the brand's own website linking to its eBay
store**. That is the source asserting ownership, not us inferring it.

    ebay.co.uk/str/<handle>          storefront link
    ebay.com/usr/<handle>            seller link
    ebay.*/sch/i.html?_ssn=<handle>  "see our other items"

The asymmetry that makes this worth building (the loss functions differ):

    comp filtering     false positive -> discard a valid comp -> a
                       CONSERVATIVE profit estimate. Cheap error.
    presence detection false positive -> conclude the source competes in
                       the exit venue -> can invalidate a whole sourcing
                       strategy. Expensive error.

So presence needs materially higher precision than comp exclusion, and only
link-confirmed handles may be called confirmed.

Absence of a link is NOT evidence of absence: plenty of brands run an eBay
outlet without linking it from the shop front. A handle with listings and no
link is `candidate`, never `not present`.

## Measured: the link route is nearly empty for this population

Tested against the four sources whose exit-venue status matters most:

    gymshark.com         4 pages fetched, 0 eBay links
    rokform.com          7 pages fetched, 0 eBay links
    fromourplace.co.uk   4 pages fetched, 0 eBay links
    www.itinstock.com    5 pages fetched, 0 eBay links

itinstock runs an 18,839-listing eBay store, so this is a fourth
known-positive failure -- except the parser is fine and the sites simply do
not link. itinstock's only "ebay" strings are product image filenames
(`product_13546_ebay_*.png`), which suggest a shared eBay/Shopify image
pipeline but assert nothing about ownership.

So confirmation leans on the second route below.

## Route two: legal business identity

UK/EU law requires business sellers to publish trading name, address and
company/VAT number on their eBay listings, and UK retailers publish the same
on their own terms pages. A match is genuine independent identity evidence.
Harvested from the source side already:

    www.itinstock.com    company 12704142   VAT GB483890250
    www.tier1online.com  company 03708416
    reboxed.co.uk        none found on probed pages

The eBay side (Browse getItem seller legal info) is untested -- the account
was rate-limited when this was written. Until it is verified, NO handle can
reach `confirmed`, and every active row stands at `candidate`.
"""
import gzip
import re
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (compatible; arbitrage-research/1.0; "
      "+contact via repository owner)")

# Pages a brand plausibly links its marketplace storefronts from.
PATHS = ("", "/", "/pages/contact", "/pages/about", "/pages/about-us",
         "/pages/faq", "/pages/stockists", "/contact", "/about")

EBAY_HOST = r"ebay\.(?:com|co\.uk|de|ca|com\.au|ie|fr|it|es)"
PATTERNS = (
    re.compile(EBAY_HOST + r"/str/([A-Za-z0-9_.-]{3,64})", re.I),
    re.compile(EBAY_HOST + r"/usr/([A-Za-z0-9_.-]{3,64})", re.I),
    re.compile(EBAY_HOST + r"/sch/[^\"'\s]*_ssn=([A-Za-z0-9_.-]{3,64})", re.I),
    re.compile(EBAY_HOST + r"/[a-z]{0,3}/?stores?/([A-Za-z0-9_.-]{3,64})", re.I),
)

# /str/ slugs are display names, not usernames, and these are never handles.
STOPWORDS = {"itm", "sch", "usr", "str", "b", "p", "e", "help", "deals",
             "myb", "signin", "rpp", "n", "sl", "gsr", "motors", "stores"}


def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "text/html,*/*",
        "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(1_500_000)
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return raw.decode("utf-8", "replace")


def handles_in(html):
    """-> set of eBay handles/store slugs referenced by this page."""
    out = set()
    for pat in PATTERNS:
        for m in pat.findall(html or ""):
            h = m.strip(".-_")
            if h and h.lower() not in STOPWORDS and not h.isdigit():
                out.add(h)
    return out


def brand_ebay_handles(domain, paths=PATHS, verbose=False):
    """
    Fetch a brand's own pages and collect every eBay handle it links to.

    -> (handles, pages_fetched, errors). An empty set means "no link found",
    which is NOT evidence the brand has no eBay store.
    """
    found, ok, errs = set(), 0, []
    seen = set()
    for path in paths:
        for scheme in ("https://",):
            url = f"{scheme}{domain}{path}"
            if url in seen:
                continue
            seen.add(url)
            try:
                html = fetch(url)
                ok += 1
                found |= handles_in(html)
            except urllib.error.HTTPError as e:
                if e.code not in (404, 403, 410):
                    errs.append(f"{path}:{e.code}")
            except Exception as e:
                errs.append(f"{path}:{type(e).__name__}")
        if found:                       # one confirming page is enough
            break
    if verbose:
        print(f"  {domain}: {sorted(found) or '-'} "
              f"({ok} pages, {len(errs)} errors)")
    return found, ok, errs


def confirms(domain, handle, linked=None):
    """
    -> (bool, reason). True when the brand's own site links to `handle`.

    Comparison is on the normalised core so 'gymshark-store' matches a link
    to 'gymsharkstore'; eBay store SLUGS differ from usernames in
    punctuation and case.
    """
    if linked is None:
        linked, _, _ = brand_ebay_handles(domain)
    want = re.sub(r"[^a-z0-9]", "", (handle or "").lower())
    for cand in linked:
        if re.sub(r"[^a-z0-9]", "", cand.lower()) == want:
            return True, f"{domain} links to eBay handle '{cand}'"
    return False, ("no eBay link found on the brand's own pages "
                   "(absence of a link is not absence of a store)")
