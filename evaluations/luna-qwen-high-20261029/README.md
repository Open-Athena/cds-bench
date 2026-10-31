# Luna and Qwen3.7 Flash: full CDS-bench evaluation

Qwen: 3260/3,260 attempts (complete). Luna: 3,260 matched historical attempts.

Download [report.html](report.html) and open it in a browser. It is self-contained.

[Summary](summary.json) · [Per-task metrics](by-task.csv) · [Final predictions](results.json) · [Settings](config.json)

Raw requests, reasoning, and Python traces remain local and untracked. The original Luna evaluation is preserved in `../luna-high-20261029/`.

Failed Qwen request counts, timeout flags, usage, and charges are reconstructed from saved response metadata where the collector omitted them. Raw files and scores are unchanged; no requests are retried.
