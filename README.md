# CDS-bench

CDS-bench evaluates procedural reasoning and constrained design on coding DNA
sequences: 65 individual task types and 19 composition task types covering
translation, edits, RNA and protein operations, and sequence design. Inputs
supply the coding strand and boundaries; gene discovery is outside the scope.

Easy prompts supply biological reference material; hard prompts assume that
knowledge while keeping the question inputs and answer fixed. Five task types
have only an easy variant.

See the [benchmark specification](https://openathena.ai/cds-bench/) for task
definitions, examples and scoring, the
[Hugging Face dataset](https://huggingface.co/datasets/open-athena/cds-bench) for
`easy` and `hard` splits, and [data generation](generation/README.md) for provenance.

## Evaluation utilities

The [strict scorer](src/cds_bench/scoring.py) and
[Python executor](src/cds_bench/python_executor.py) were introduced for the
30-task pilot described in
[Baseline evaluation and model pilot results](https://github.com/Open-Athena/cds-bench/pull/2)
(PR #2), then reused for the full evaluations. Both are independent of the
inference API. Install with `uv sync --locked`.

The scorer is platform independent. It accepts a dataset row and a complete
assistant response, including the standalone `Final answer:` marker. It applies
the specification's formatting normalizations; token-limit completions fail.

```python
from cds_bench.scoring import score_result

case = {"answer": "AUGGCU", "output_format": "scalar"}  # Or a complete dataset row.
assert score_result(case, "Final answer:\nAUG GCU", finish="stop")["passed"]
```

The executor reproduces PR #2's local macOS tool environment. It requires
`/usr/bin/sandbox-exec`, a macOS-specific utility, and does not run on Linux or
Windows. The sandbox denies networking and process forks, and restricts file
access. Each call uses a fresh interpreter; use a separate working directory per
example. Recreate that environment with:

```sh
uv venv --python 3.12.9 build/python-runtime
uv pip install --python build/python-runtime/bin/python numpy==2.5.4
```

```python
from cds_bench.python_executor import execute

result = execute("print(6 * 7)", "build/tool-work/example-01",
                 python="build/python-runtime/bin/python")
assert result["stdout"] == "42\n"
```

The executor returns stdout, stderr, exit code, timeout and output-truncation
status. Calls have a 30-second CPU and default wall limit, with 16,384 bytes per
returned output stream. The caller manages model messages and tool-call limits.
