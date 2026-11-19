# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/docintel_telemetry.py
# ---------------------------------------------------------------------------

def _reconciliation_signal_counts(reconciliation_artifact):
    monetary = 0
    exclusions = 0

    try:
        for bucket in reconciliation_artifact.get("buckets", []):
            stype = bucket.get("signal_type")

            if stype == "base_bid":
                monetary += len(bucket.get("facts") or [])

            if stype == "exclusions":
                exclusions += len(bucket.get("facts") or [])

    except Exception:
        pass

    return monetary, exclusions