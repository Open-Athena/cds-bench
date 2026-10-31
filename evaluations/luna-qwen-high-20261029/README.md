# Full CDS-bench model evaluation

Snowball v0.1: 684/3,260 fresh attempts (running). GPT-6 Luna, Qwen 3.7 Flash and Nemotron 3.5 Lightning each have 3,260 matched completed attempts.

Download [report.html](report.html) and open it in a browser. It is self-contained.

[Summary](summary.json) · [Per-task metrics](by-task.csv) · [Final predictions](results.json) · [Settings](config.json)

Snowball v0.1 is a 67B MoE model with 2B active parameters per token. The full run uses 32,768 aggregate generated tokens, a 1,800-second API request deadline, temperature 0.7 and concurrency 60. Its native thinking/tool transport and private access configuration match the validated pilot. No per-request monetary price is exposed.

Checkpoint: [open-athena/Marin-Snowball-67B-A2B-v0.1](https://huggingface.co/open-athena/Marin-Snowball-67B-A2B-v0.1/tree/adc0078a19a4383bc998fcdb43867b3360baf5f3), revision `adc0078a19a4383bc998fcdb43867b3360baf5f3`.

Accuracy by condition: [PNG](overall.png) · [SVG](overall.svg).

[Pooled task radar](task-radar.svg) · [PNG](task-radar.png) · [Task order and scores](task-radar.json). The report selector also shows each of the four evaluation conditions. Task codes and group colors stay fixed across views, with links to the full-name/ID key and existing details.

[30-task model/provider pilot](../model-pilot-20261029/README.md). Raw requests, reasoning, and Python traces remain local and untracked. The original Luna evaluation is preserved in `../luna-high-20261029/`.

Failed Qwen request counts, timeout flags, usage, and charges are reconstructed from saved response metadata where the collector omitted them. Raw files and scores are unchanged; no requests are retried.
