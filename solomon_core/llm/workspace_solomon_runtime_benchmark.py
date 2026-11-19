# ---------------------------------------------------------------------------
# FILE: workspace_solomon_runtime_benchmark.py
# DIRECTORY: solomon_core/llm/
# ---------------------------------------------------------------------------
# Isolated benchmark for portable SolomonAI source-operation runtime profiles.
# Production routes, queues, prompts, settings, and records are not modified.
# ---------------------------------------------------------------------------

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .direct_model_runner import (
    run_direct_generation,
    warm_direct_model,
)

_CALL_SITE = (
    "workspace_solomon_source_operation_runtime_benchmark"
)
_PROFILES = (
    "default",
    "static_cache",
    "static_cache_compile",
)
_PROMPT = """
You are SolomonAI, a professional construction-document assistant.

ACTION
Summarize the bounded source preview below. The visible answer must be written
by you from the supplied evidence. Do not claim access beyond the preview.

OUTPUT CONTRACT
- Begin with: Summary — Riverside Office Renovation Bid
- Write exactly three concise paragraphs after the heading.
- Target 120 to 180 words.
- Paragraph 1: identify the document, purpose, price, and date.
- Paragraph 2: synthesize the principal scope and commercial obligations.
- Paragraph 3: state additional qualifications, omissions, and review cautions.
- Preserve factual distinctions. Do not invent missing information.
- When evidence is absent, say the available preview does not show it.

BOUNDED SOURCE PREVIEW
Document: Riverside Office Renovation Bid
Bid date: April 3, 2025
Base bid: $111,110
Project area: Level 1, Wings A and B
Purpose: selective demolition and preparation for renovation

Wing A includes removal of VCT flooring, carpet transitions, millwork, toilet
partitions, plumbing fixtures, storefront, selected doors and frames, a steel
stair, tech booths, drywall partitions, and identified CMU partitions. Protect
adjacent occupied areas, coordinate temporary barriers, include four
mobilizations, and include ordinary debris handling and haul-off.

Wing B includes removal of carpet, VCT, ceramic tile, millwork, bathroom
accessories, plumbing fixtures, handrail, selected doors and frames, storefront,
drywall partitions, identified CMU partitions, and six-inch slab-on-grade only
where shown. Ordinary debris handling and haul-off are included.

Commercial qualifications:
- Additional mobilizations are $4,500 each.
- Work below two feet beneath grade is excluded unless specifically identified.
- Concealed conditions and hazardous-material testing or abatement are excluded.
- Pricing remains valid for 30 days.
- Salvageable materials remain the contractor's property unless directed
  otherwise before removal.
- Catch-deck protection and ground-penetrating radar scanning are included only
  where described.
- Work is based on the available drawings and listed clarifications.

The preview shows no detailed schedule, unit-price breakdown, accepted
alternates, or final contract terms.
""".strip()


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark isolated SolomonAI source-operation "
            "runtime profiles."
        )
    )
    parser.add_argument(
        "--profiles",
        default=",".join(_PROFILES),
    )
    parser.add_argument(
        "--warmup-runs",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--measured-runs",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=256,
    )
    parser.add_argument(
        "--output",
        default="",
    )

    return parser.parse_args()


def _selected_profiles(
    value: str,
) -> tuple[str, ...]:
    selected = tuple(
        item.strip().lower()
        for item in str(
            value or ""
        ).split(",")
        if item.strip()
    )
    unsupported = sorted(
        set(selected) - set(_PROFILES)
    )

    if not selected:
        raise ValueError(
            "At least one runtime profile is required."
        )

    if unsupported:
        raise ValueError(
            "Unsupported runtime profiles: "
            + ", ".join(unsupported)
        )

    return selected


def _validated_count(
    name: str,
    value: int,
    *,
    allow_zero: bool = False,
) -> int:
    minimum = 0 if allow_zero else 1

    if (
        isinstance(value, bool)
        or value < minimum
    ):
        raise ValueError(
            f"{name} must be at least {minimum}."
        )

    return value


def _report_path(
    value: str,
) -> Path:
    if value:
        return Path(
            value
        ).expanduser().resolve()

    stamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    return (
        Path.cwd()
        / (
            "workspace_solomon_runtime_benchmark_"
            f"{stamp}.json"
        )
    )


def _run(
    profile: str,
    kind: str,
    number: int,
    max_new_tokens: int,
) -> dict[str, Any]:
    print(
        (
            f"[BENCHMARK] profile={profile} "
            f"kind={kind} run={number}"
        ),
        flush=True,
    )

    result = run_direct_generation(
        prompt=_PROMPT,
        call_site=_CALL_SITE,
        response_format="text",
        max_new_tokens=max_new_tokens,
        runtime_profile=profile,
    )
    metrics = result.metrics or {}
    record = {
        "profile": profile,
        "run_kind": kind,
        "run_number": number,
        "ok": result.ok,
        "error": result.error,
        "output_chars": len(
            result.text
        ),
        "output_sha256": (
            hashlib.sha256(
                result.text.encode(
                    "utf-8"
                )
            ).hexdigest()
            if result.text
            else ""
        ),
        "metrics": metrics,
    }

    print(
        (
            "[BENCHMARK] "
            f"ok={result.ok} "
            f"generate_ms={metrics.get('generate_ms')} "
            f"tps={metrics.get('generated_tps')} "
            f"compiled={metrics.get('compiled')} "
            "static_cache="
            f"{metrics.get('static_cache_effective')}"
        ),
        flush=True,
    )

    return record


def _mean(
    records: list[dict[str, Any]],
    key: str,
) -> float:
    values = [
        float(
            record["metrics"][key]
        )
        for record in records
        if (
            record["ok"]
            and key in record["metrics"]
        )
    ]

    return (
        round(
            statistics.fmean(values),
            2,
        )
        if values
        else 0.0
    )


def _summary(
    profile: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    measured = [
        record
        for record in records
        if (
            record["profile"] == profile
            and record["run_kind"] == "measured"
        )
    ]
    successful = [
        record
        for record in measured
        if record["ok"]
    ]

    return {
        "profile": profile,
        "measured_runs": len(
            measured
        ),
        "successful_runs": len(
            successful
        ),
        "average_generate_ms": _mean(
            successful,
            "generate_ms",
        ),
        "average_total_ms": _mean(
            successful,
            "total_ms",
        ),
        "average_generated_tps": _mean(
            successful,
            "generated_tps",
        ),
        "average_input_tokens": _mean(
            successful,
            "input_tokens",
        ),
        "average_generated_tokens": _mean(
            successful,
            "generated_tokens",
        ),
        "compiled_observed": any(
            bool(
                record["metrics"].get(
                    "compiled"
                )
            )
            for record in successful
        ),
        "static_cache_effective_observed": any(
            bool(
                record["metrics"].get(
                    "static_cache_effective"
                )
            )
            for record in successful
        ),
        "unique_output_hashes": sorted({
            record["output_sha256"]
            for record in successful
            if record["output_sha256"]
        }),
    }


def main() -> int:
    args = _arguments()

    try:
        profiles = _selected_profiles(
            args.profiles
        )
        warmups = _validated_count(
            "warmup-runs",
            args.warmup_runs,
            allow_zero=True,
        )
        measured = _validated_count(
            "measured-runs",
            args.measured_runs,
        )
        tokens = _validated_count(
            "max-new-tokens",
            args.max_new_tokens,
        )
    except ValueError as exc:
        print(
            (
                "[BENCHMARK] configuration error: "
                f"{exc}"
            ),
            file=sys.stderr,
        )
        return 2

    print(
        "[BENCHMARK] loading and priming model",
        flush=True,
    )

    warmup = warm_direct_model(
        call_site=(
            "workspace_solomon_source_operation_"
            "runtime_benchmark_boot"
        )
    )

    if not warmup.ok:
        print(
            (
                "[BENCHMARK] model warmup failed: "
                f"{warmup.error}"
            ),
            file=sys.stderr,
        )
        return 1

    records: list[dict[str, Any]] = []

    for profile in profiles:
        for number in range(
            1,
            warmups + 1,
        ):
            records.append(
                _run(
                    profile,
                    "warmup",
                    number,
                    tokens,
                )
            )

        for number in range(
            1,
            measured + 1,
        ):
            records.append(
                _run(
                    profile,
                    "measured",
                    number,
                    tokens,
                )
            )

    report = {
        "benchmark": (
            "workspace_solomon_source_operation_runtime_profiles"
        ),
        "created_at": (
            datetime.now()
            .astimezone()
            .isoformat()
        ),
        "call_site": _CALL_SITE,
        "max_new_tokens": tokens,
        "warmup_runs_per_profile": warmups,
        "measured_runs_per_profile": measured,
        "profiles": list(
            profiles
        ),
        "prompt_chars": len(
            _PROMPT
        ),
        "summaries": [
            _summary(
                profile,
                records,
            )
            for profile in profiles
        ],
        "records": records,
    }
    destination = _report_path(
        args.output
    )
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    destination.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        "\n[BENCHMARK] profile summary",
        flush=True,
    )

    for item in report["summaries"]:
        print(
            (
                f"  {item['profile']}: "
                f"generate_ms={item['average_generate_ms']} "
                f"tps={item['average_generated_tps']} "
                f"compiled={item['compiled_observed']} "
                "static_cache="
                f"{item['static_cache_effective_observed']} "
                f"success={item['successful_runs']}/"
                f"{item['measured_runs']}"
            ),
            flush=True,
        )

    print(
        f"\n[BENCHMARK] report={destination}",
        flush=True,
    )

    return (
        0
        if all(
            record["ok"]
            for record in records
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )