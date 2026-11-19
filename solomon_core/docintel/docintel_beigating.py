# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/docintel_beigating.py
# ---------------------------------------------------------------------------

from solomon_core.logger import get_logger

logger = get_logger("docintel_beigating")


def _bei_applicable(reconciliation_artifact):
    legacy_bid_signals = {"base_bid", "alternates", "addenda", "scope"}

    expanded_indicators = {
        "currency",
        "money",
        "pricing",
        "price",
        "unit_price",
        "extended_price",
        "total",
        "quantity",
        "qty",
        "duration",
        "schedule",
        "line_item",
        "allowance",
    }

    bid_shape_indicators = {
        "exclusions",
        "clarifications",
        "scope",
        "scope_of_work",
        "inclusions",
        "conditions",
        "qualifiers",
        "structural",
    }

    observed = {b.get("signal_type") for b in reconciliation_artifact["buckets"]}

    logger.info(
        "[BEI_GATE] observed signal types",
        extra={"types": sorted(list(observed))},
    )

    if observed.intersection(legacy_bid_signals):
        logger.info("[BEI_GATE] activation via legacy match")
        return True

    if observed.intersection(expanded_indicators):
        logger.info("[BEI_GATE] activation via expanded indicators")
        return True

    scope_like = {"scope", "scope_of_work", "inclusions", "structural"}
    exclusion_like = {"exclusions", "clarifications", "conditions", "qualifiers"}

    has_scope_like = bool(observed.intersection(scope_like))
    has_exclusion_like = bool(observed.intersection(exclusion_like))
    bid_shape_hits = observed.intersection(bid_shape_indicators)

    if (has_scope_like and has_exclusion_like) or (len(bid_shape_hits) >= 2):
        logger.info(
            "[BEI_GATE] activation via bid-shape pattern",
            extra={"bid_shape_hits": sorted(list(bid_shape_hits))},
        )
        return True

    logger.info("[BEI_GATE] BEI not applicable")
    return False