# Luna, Qwen and Nemotron 3.5 Lightning: full CDS-bench evaluation

Nemotron 3.5 Lightning: 3260/3,260 fresh attempts (complete). Luna and Qwen: 3,260 matched completed attempts each.

Download [report.html](report.html) and open it in a browser. It is self-contained.

[Summary](summary.json) · [Per-task metrics](by-task.csv) · [Final predictions](results.json) · [Settings](config.json)

[84-task radar figure](task-radar.svg) · [PNG](task-radar.png) · [Task order and scores](task-radar.json). The report includes clickable task codes and a full-name/ID key.

[30-task model/provider pilot](../model-pilot-20261029/README.md). Raw requests, reasoning, and Python traces remain local and untracked. The original Luna evaluation is preserved in `../luna-high-20261029/`.

Failed Qwen request counts, timeout flags, usage, and charges are reconstructed from saved response metadata where the collector omitted them. Raw files and scores are unchanged; no requests are retried.
