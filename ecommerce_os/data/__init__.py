"""Fee-book fixtures built from verified public sources.

Each module here states, per rule, where the number came from and when it was
collected. Rates gathered by web search are marked as such and must be
confirmed against the marketplace's own fee page (or fee-estimate API) before
production listing decisions rely on them — see
``docs/ecommerce-os/verification/`` for the collection log.
"""

from ecommerce_os.data.fees_uk_2026 import uk_fee_book_2026

__all__ = ["uk_fee_book_2026"]
