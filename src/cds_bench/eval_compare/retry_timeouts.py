"""Recover timed-out main-evaluation examples without resampling scored answers.

Each attempt has its own trace directory. Select the first non-timeout result;
timeouts remain unscored. Historical attempts and scores are never overwritten.
"""

import argparse
import asyncio
import copy
import fcntl
import hashlib
import importlib
import json
import subprocess
from collections import Counter
from pathlib import Path

import httpx

from cds_bench.eval_luna import sandbox
from cds_bench.eval_luna.billing import reconcile
from cds_bench.eval_luna.io import api_key, save
from cds_bench.eval_luna.run import now, validate_sandbox

from .run import ROOT, REVISION

RAW = ROOT / "scratch/timeout-recovery-20261101-01"
DEADLINE = 900
SOURCES = {
    "luna": ("luna-high-full-20261029-01", "cds_bench.eval_luna.client"),
    "deepinfra": ("nemotron-lightning-deepinfra-full-20261030-01", "cds_bench.eval_compare.lightning_client"),
    "qwen": ("qwen37-flash-high-full-20261029-01", "cds_bench.eval_compare.client"),
}
EXPECTED = {"luna": 14, "deepinfra": 135, "qwen": 68}


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    RAW.mkdir(parents=True, exist_ok=True)
    with (RAW / "prepare.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _prepare()


def _prepare():
    baseline = RAW / "baseline-results.json"
    if not baseline.exists():
        baseline.write_bytes((ROOT / "evaluations/luna-qwen-high-20261029/results.json").read_bytes())
    rows = read(baseline)
    chosen = {m: [r for r in rows if r["model"] == m and r.get("request_timeout")]
              for m in SOURCES}
    assert {m: len(rs) for m, rs in chosen.items()} == EXPECTED
    config = {
        "dataset_revision": REVISION, "selected_examples": EXPECTED,
        "baseline_sha256": digest(baseline), "request_timeout_seconds": DEADLINE,
        "concurrency_per_model": 10,
        "policy": "Retry timeout-selected cases; first non-timeout result is final. Never retry a completed wrong, malformed or token-capped answer. Unresolved timeouts are unscored. Preserve every attempt. Providers, prompts, sampling, 32768-token per-attempt budget and Python tool are unchanged.",
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in
            [Path(__file__), ROOT / "src/cds_bench/eval_luna/trial.py",
             ROOT / "src/cds_bench/eval_luna/score.py", ROOT / "src/cds_bench/eval_luna/sandbox.py"]},
    }
    path = RAW / "config.json"
    if path.exists():
        previous = read(path)
        for field in config:
            if field == 'source_commit':
                continue
            if field != 'source_sha256':
                assert previous[field] == config[field], field
                continue
            revision_path = RAW / 'operational-source-revisions.json'
            revisions = read(revision_path) if revision_path.exists() else {}
            for name, current in config[field].items():
                if previous[field][name] != current:
                    change = revisions[name]
                    assert change['original_sha256'] == previous[field][name]
                    assert current in change['accepted_sha256']
    else:
        save(path, config)
    save(RAW / "selected-timeouts.json", chosen)
    return chosen


def retryable_request_failure(result):
    """A transport failure has no model answer; completed answers are final."""
    if result.get('request_timeout'):
        return True
    if not result.get('api_error'):
        return False
    files = sorted(Path(result['trace_directory']).glob('response-*.json'))
    last = read(files[-1]) if files else {}
    status = last.get('http_status')
    return (status is None or status in {408, 425, 429} or status >= 500
            or status == 200 and not last.get('finish_reason') and not last.get('usage'))


async def recover_case(attempt, start=1, stop=3):
    """Retry missing responses; never retry a completed scored answer."""
    for number in range(start, stop + 1):
        result = await attempt(number)
        if not retryable_request_failure(result):
            return number, result
        if number < stop:
            await asyncio.sleep(min(2 ** number, 30))
    return None


async def evaluate(model, maximum_attempts):
    chosen = prepare()[model]
    directory = RAW / model
    directory.mkdir(exist_ok=True)
    source, module_name = SOURCES[model]
    original_config = read(ROOT / "scratch" / source / "config.json")
    config = copy.deepcopy(original_config["parameters_no_tools"])
    runtime = importlib.import_module("cds_bench.eval_luna.trial")
    client_module = importlib.import_module(module_name)
    client_module.REQUEST_TIMEOUT = DEADLINE
    runtime.PARAMETERS = config
    runtime.RequestFailure = client_module.RequestFailure
    runtime.api_call = client_module.api_call
    sandbox.WORK_ROOT = ROOT / "build/luna-tool-work" / RAW.name / model
    cases = read(ROOT / "scratch/qwen37-flash-high-full-20261029-01/dataset.json")
    case_map = {(r["instance_id"], v): r for v, rs in cases.items() for r in rs}
    selected_path = directory / "selected.json"
    selected = read(selected_path) if selected_path.exists() else []
    if any(retryable_request_failure(r) for r in selected):
        archive = directory / 'selected-before-provider-recovery.json'
        if not archive.exists():
            save(archive, selected)
        selected = [r for r in selected if not retryable_request_failure(r)]
    completed = {(r["instance_id"], r["condition"]) for r in selected}
    assert len(completed) == len(selected)
    active = set()

    def refresh(state="running", error=None):
        files = list(directory.glob("attempt-*/traces/*/*/result.json"))
        attempts = [read(p) for p in files]
        save(selected_path, selected)
        save(directory / "job-status.json", {
            "state": state, "updated_at": now(), "model": model,
            "selected": len(selected), "planned": len(chosen),
            "attempts": len(attempts), "additional_timeouts": sum(bool(r.get("request_timeout")) for r in attempts),
            "correct": sum(bool(r.get("passed")) for r in selected),
            "active": len(active), "max_attempts": maximum_attempts, "error": error,
        })

    key = api_key()
    gate = asyncio.Semaphore(10)
    refresh()
    async with httpx.AsyncClient(timeout=DEADLINE, trust_env=False,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=10)) as client:
        async def one(index, original):
            identity = original["instance_id"], original["condition"]
            if identity in completed:
                return
            case = case_map[original["instance_id"], original["variant"]]
            assert case["answer"] == original["expected_answer"]
            async with gate:
                active.add(identity)
                history = []
                async def attempt(number):
                    result = await runtime.trial(client, asyncio.Semaphore(1), index,
                        case, original["tools_enabled"], key, directory / f"attempt-{number:02}")
                    # No timeout enters the scored result set. Preserve its raw output.
                    history.append(result)
                    if retryable_request_failure(result):
                        save(Path(result["trace_directory"]) / "unscored.json",
                             {"scorable": False, "reason": "Request timeout or transient provider/connection failure", "retry_required": True})
                    refresh()
                    return result
                outcome = await recover_case(attempt, stop=maximum_attempts)
                if outcome:
                    number, result = outcome
                    selected.append(dict(result, selected_attempt=number, model=model,
                                         scorable=True, prior_timeout_count=1+sum(bool(r.get('request_timeout')) for r in history)))
                    completed.add(identity)
                active.remove(identity)
                refresh()
        await asyncio.gather(*(one(i, r) for i, r in enumerate(chosen, 1)))
    for attempt_root in sorted(directory.glob("attempt-*")):
        await reconcile(attempt_root)
    refresh("complete" if len(selected) == len(chosen) else "pending-timeouts")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=SOURCES)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args()
    if args.prepare:
        prepare()
        print(json.dumps(EXPECTED))
        return
    if not args.model:
        parser.error("--model is required")
    directory = RAW / args.model
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "driver.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        validate_sandbox(directory)
        asyncio.run(evaluate(args.model, args.max_attempts))


if __name__ == "__main__":
    main()
