# CDS-bench

CDS-bench evaluates procedural reasoning and constrained design on coding DNA
sequences: 65 individual task types and 19 composition task types covering
translation, edits, RNA and protein operations, and sequence design. Inputs
supply the coding strand and boundaries; gene discovery is outside the scope.

Easy prompts supply biological reference material; hard prompts assume that
knowledge while keeping the question inputs and answer fixed. Five task types
have only an easy variant.

See the [benchmark specification](https://openathena.ai/cds-bench/) for task
definitions, examples and scoring. The
[open-athena/cds-bench](https://huggingface.co/datasets/open-athena/cds-bench)
dataset provides `easy` and `hard` splits.

## Scoring

The [strict scorer](src/cds_bench/scoring.py) was introduced for the model
evaluations described in
[Baseline evaluation results](https://github.com/Open-Athena/cds-bench/pull/2)
(PR #2). Install with `uv sync --locked`.

It accepts a dataset row and a complete assistant response, including the
standalone `Final answer:` marker. It applies the specification's formatting
normalizations; token-limit completions fail.

```python
from cds_bench.scoring import score_result

case = {"answer": "AUGGCU", "output_format": "scalar"}  # Or a complete dataset row.
assert score_result(case, "Final answer:\nAUG GCU", finish="stop")["passed"]
```
