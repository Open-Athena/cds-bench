# CDS-bench

CDS-bench evaluates procedural reasoning and constrained design on coding DNA
sequences: 65 individual task types and 19 composition task types (84 total),
covering translation, edits, RNA and protein operations, and sequence design.

The [benchmark specification](https://openathena.ai/cds-bench/) contains task
definitions, examples, and scoring rules. The
[open-athena/cds-bench](https://huggingface.co/datasets/open-athena/cds-bench)
dataset has `easy` and `hard` splits: easy prompts supply biological reference
material; hard prompts assume that knowledge for the same question and answer.
Five task types are easy-only.

## Scoring

The [strict scorer](src/cds_bench/scoring.py) was introduced for the model
evaluations documented in
[Baseline evaluation results](https://github.com/Open-Athena/cds-bench/pull/2).

Install with `uv sync --locked`. The scorer accepts a dataset record and a
complete assistant response with a standalone `Final answer:` marker. It applies
the specification's formatting normalizations and counts token-limit completions
as incorrect.

```python
from cds_bench.scoring import score_result

case = {"answer": "AUGGCU", "output_format": "scalar"}  # Or a complete dataset record.
assert score_result(case, "Final answer:\nAUG GCU", finish="stop")["passed"]
```
