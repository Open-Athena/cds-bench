# Full Luna/Qwen comparison

The Qwen run makes 3,260 fresh attempts over the pinned current release: 840 easy and 790 hard prompts, each without tools and with offline Python. It requests `high` reasoning on `qwen/qwen3.7-flash`, pinned to `alibaba/us-east-1`, using the same budgets, scorer, and Python tool as Luna. Pilot responses are not reused.

The comparison retains 3,260 historical Luna attempts whose full prompt and reference-answer records match the current release. It excludes only the 100 historical attempts corresponding to five removed duplicate hard variants. The original Luna reports and raw responses remain intact.

```sh
PYTHONPATH=src .venv/bin/python -m cds_bench.eval_compare.run --prepare
PYTHONPATH=src .venv/bin/python -m cds_bench.eval_compare.run --preflight-only
PYTHONPATH=src .venv/bin/python -m cds_bench.eval_compare.run
```

Run the watcher separately to refresh the report, reconcile costs at publication checkpoints, and update only the existing evaluation PR's original post:

```sh
PYTHONPATH=src .venv/bin/python -m cds_bench.eval_compare.watch --pr 2
```

The watcher publishes after 250 new completions, phase changes, or termination. Use `--once` for an immediate checkpoint or `--no-publish` to update locally. It refuses to publish if another branch is checked out or unrelated changes are staged. It never creates PR comments or merges the PR.

During inference, the local report refreshes at least once a minute when new attempts complete. The browser checks for newer snapshots every 30 seconds and preserves expanded sections, selected instances, the task filter, and scroll position when refreshing. Each snapshot displays its generation time; downloaded reports still work offline.

Raw requests, streaming responses, reasoning, and Python programs/results remain untracked in `scratch/qwen37-flash-high-full-20261029-01`. Public final predictions, metrics, figures, exact request settings, and a self-contained HTML report go in `evaluations/luna-qwen-high-20261029`.

There are no inference retries. A lock prevents duplicate drivers. Completed results are reused on restart, but interrupted requests without a result require review. Five consecutive non-timeout API errors halt scheduling. Each API request has a 300-second wall deadline; all model turns share 32,768 generated tokens per example. Eight Python executions are allowed, with a fresh interpreter and a 30-second limit per call. The macOS sandbox denies networking, subprocesses, and access to benchmark answers or credentials.

To rebuild the report or audit the finished run without new inference:

```sh
PYTHONPATH=src .venv/bin/python -m cds_bench.eval_compare.report
PYTHONPATH=src .venv/bin/python -m cds_bench.eval_compare.audit
```

The PR also includes the earlier 30-task model/provider pilot. Publish its saved results
before rebuilding the full report, so the PR's original post includes its summary table:

```sh
PYTHONPATH=src .venv/bin/python -m cds_bench.eval_compare.pilot
PYTHONPATH=src .venv/bin/python -m cds_bench.eval_compare.report
```

The pilot publisher reads the saved local comparison and verifies prompts, reference
answers, scores and aggregate metrics before exporting final predictions, settings and a
self-contained report to `evaluations/model-pilot-20261029`. It makes no inference
requests. Interrupted attempts and discarded duplicate-hard cases remain excluded.
Provider diagnostics and earlier ten-example checks stay separate from the pilot scores.
Raw requests, reasoning and Python traces remain local and untracked. `tables.py` defines
the shared result columns used by both reports and the PR original post.

`audit --partial` checks only completed attempts during a run. A separately labeled diagnostic accepts inline final-answer markers and outer JSON fences; it never changes primary scores. The endpoint's quantization and public-weight availability are not established by this evaluation.

The Qwen client and legacy trial have different request-exception classes. Failed requests remain failures, but their raw result files omit some request metadata. `collector.py` reconstructs counts, timeout flags, usage, and charges from saved response files for reporting. It leaves raw traces and scores untouched. The frozen driver's circuit breaker does not recognize these omitted error flags; the completion check monitors operational failures separately.

The controller requests a maximum of 32,768 generated tokens across all turns. Some Qwen responses report usage above that allowance. The audit lists each exception, verifies the requested allowance and that no later request follows exhaustion, and reports `token_budgets_verified=false` when exceptions exist. Actual provider-reported usage is therefore not strictly matched to Luna's requested cap.
