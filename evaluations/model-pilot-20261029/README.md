# CDS-bench: 30-task model pilot

Download [report.html](report.html) and open it in a browser. The report is self-contained and includes model/provider settings, four-condition scores, failure categories, timing, task-level results and GPT-OSS compatibility checks.

Complete runs contain 116 attempts: one instance from 30 task types, easy/hard, without tools/with offline Python, excluding two duplicate hard variants. Partial runs are marked explicitly. Scores and raw traces are unchanged. Earlier ten-example checks and GPT-OSS diagnostics are separate.

[Summary and settings](summary.json) · [Per-task outcomes](by-task.csv) · [Final predictions](results.json) · [Prompt instances](cases.json) · [GPT-OSS diagnostics](gpt-oss-diagnostics.json)

Raw API requests, reasoning and Python programs/results remain untracked. Costs exclude preflight and interrupted requests; unknown charges are not assumed to be zero.

Rebuild from the saved local pilot, with no inference:

```sh
PYTHONPATH=src .venv/bin/python -m cds_bench.eval_compare.pilot
```
