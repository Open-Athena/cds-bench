"""Select recovered timeout cases and account for every preserved attempt."""

import hashlib
import json
from collections import Counter

from cds_bench.eval_luna.io import save

from .collector import records
from .retry_timeouts import RAW, EXPECTED, DEADLINE, retryable_request_failure

PUBLIC_FIELDS = [
    "scorable", "retry_attempts", "prior_timeout_count", "selected_elapsed_seconds",
    "selected_request_count",
    "retry_elapsed_seconds", "retry_prompt_tokens", "retry_completion_tokens",
    "retry_api_requests", "retry_recorded_cost_usd", "retry_history",
]


def read(path):
    return json.loads(path.read_text())


def load():
    if not (RAW / "config.json").exists():
        return None
    original = read(RAW / "baseline-results.json")
    expected = {(r["model"], r["instance_id"], r["condition"]): r
                for r in original if r["model"] in EXPECTED and r.get("request_timeout")}
    assert len(expected) == 217
    selected, histories = {}, {}
    for model, count in EXPECTED.items():
        directory = RAW / model
        status = read(directory / "job-status.json")
        if status["state"] != "complete" or status["selected"] != count:
            raise RuntimeError(f"Timeout recovery for {model} is not complete; do not publish old timeout failures")
        chosen = read(directory / "selected.json")
        assert len(chosen) == count
        attempts = {}
        for root in sorted(directory.glob("attempt-*")):
            number = int(root.name.split("-")[1])
            for row in records(root):
                key = model, row["instance_id"], row["condition"]
                attempts[key, number] = row
        for entry in chosen:
            key = model, entry["instance_id"], entry["condition"]
            assert key in expected and key not in selected
            number = entry["selected_attempt"]
            chain = [attempts[key, n] for n in range(1, number + 1)]
            assert all(retryable_request_failure(r) for r in chain[:-1])
            assert not retryable_request_failure(chain[-1])
            assert not chain[-1].get('api_error'), 'A provider/protocol error is not a recovered model response'
            selected[key] = chain[-1]
            histories[key] = chain
    assert selected.keys() == expected.keys()
    return {"selected": selected, "histories": histories, "original": expected}


def apply(rows, recovery):
    if recovery is None:
        return rows
    output = []
    replaced = set()
    for original in rows:
        key = original["model"], original["instance_id"], original["condition"]
        if key not in recovery["selected"]:
            output.append(original)
            continue
        assert original.get("request_timeout")
        assert original["expected_answer"] == recovery["selected"][key]["expected_answer"]
        extra = recovery["histories"][key]
        chain = [original, *extra]
        final = dict(recovery["selected"][key], model=original["model"], scorable=True)
        final.update(
            request_timeout=False,
            retry_attempts=len(extra),
            prior_timeout_count=sum(bool(r.get("request_timeout")) for r in chain),
            selected_elapsed_seconds=final["elapsed_seconds"],
            selected_request_count=final["request_count"],
            retry_elapsed_seconds=sum(r["elapsed_seconds"] for r in chain[:-1]),
            elapsed_seconds=sum(r["elapsed_seconds"] for r in chain),
            retry_prompt_tokens=sum(r["prompt_tokens"] for r in chain),
            retry_completion_tokens=sum(r["completion_tokens"] for r in chain),
            retry_api_requests=sum(r["request_count"] for r in chain),
            request_count=sum(r["request_count"] for r in chain),
            retry_recorded_cost_usd=sum(r["cost_usd"] for r in extra),
            cost_usd=sum(r["cost_usd"] for r in chain),
            billing_complete=all(r["billing_complete"] for r in chain),
            retry_history=[{
                "attempt": n, "selected": n == len(chain) - 1,
                "request_timeout": bool(r.get("request_timeout")),
                "outcome": r["outcome"], "elapsed_seconds": r["elapsed_seconds"],
                "cost_usd": r["cost_usd"], "billing_complete": r["billing_complete"],
                "request_timeout_seconds": 300 if n == 0 else DEADLINE,
            } for n, r in enumerate(chain)],
        )
        output.append(final)
        replaced.add(key)
    assert replaced == recovery["selected"].keys()
    assert not any(r.get("request_timeout") for r in output if r["model"] in EXPECTED)
    return output


def export(output, recovery):
    if recovery is None:
        return None
    models = {}
    for model in EXPECTED:
        keys = [k for k in recovery["selected"] if k[0] == model]
        extra = [r for k in keys for r in recovery["histories"][k]]
        chosen = [recovery["selected"][k] for k in keys]
        models[model] = {
            "recovered_examples": len(keys), "additional_attempts": len(extra),
            "additional_timeouts": sum(bool(r.get("request_timeout")) for r in extra),
            "additional_transient_provider_failures": sum(retryable_request_failure(r) and not r.get('request_timeout') for r in extra),
            "correct_replacements": sum(bool(r["passed"]) for r in chosen),
            "replacement_outcomes": dict(Counter(r["outcome"] for r in chosen)),
            "recorded_retry_cost_usd": sum(r["cost_usd"] for r in extra),
            "retry_attempts_with_incomplete_billing": sum(not r["billing_complete"] for r in extra),
        }
    value = {
        "models": models, "recovered_examples": 217,
        "additional_attempts": sum(r["additional_attempts"] for r in models.values()),
        "pending_timeouts": 0, "request_timeout_seconds": DEADLINE,
        "selection": "First completed model response in each timeout-selected case. Transient transport/provider failures during recovery are unscored and retried. Completed wrong, malformed and token-capped responses are not retried.",
        "latency": "Per-example elapsed time includes the original timed-out attempt and every retry, excluding backoff and queue waiting.",
        "costs": "Include original attempts and every retry; incomplete billing remains flagged.",
        "budget": "32768 generated tokens per attempt across its tool turns; retry token totals are recorded separately.",
        "baseline_results_sha256": hashlib.sha256((RAW / "baseline-results.json").read_bytes()).hexdigest(),
        "audit": "All 217 timeout-selected cases have exactly one selected model response. Earlier attempts timed out or had a transient provider/connection failure. Non-selected cases are unchanged.",
    }
    save(output / "timeout-recovery.json", value)
    return value
