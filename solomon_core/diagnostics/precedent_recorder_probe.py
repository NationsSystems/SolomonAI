# ---------------------------------------------------------------------------
# Precedent Recorder Probe
# ---------------------------------------------------------------------------

from solomon_core.investigator.precedent_recorder import record_precedent


def run():
    record_precedent(
        fingerprint="TEST::fingerprint",
        resolution="accept_vendor_A",
        case_id="probe_case",
        authority_actor="tester",
    )

    print("✔ precedent write attempted (check DB)")


if __name__ == "__main__":
    run()
