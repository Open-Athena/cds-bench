# Synthetic evaluation data

The task definitions and exact prompt templates are read from `index.html`.
The generator does not modify the benchmark specification. Python source is in
`src/cds_bench/`; `uv sync` installs the package so the commands below work
from the repository root.

```sh
uv sync --locked
uv run python -m cds_bench.acquire
uv run python -m cds_bench.generate
```

The acquisition command downloads the 24 versioned RefSeq assemblies in
[`sources.json`](sources.json), extracts their CDS FASTA content, and verifies
SHA-256 checksums. If NCBI changes an annotation, the command fails rather than
silently changing the data. The release retains the original FASTA files:

```sh
uv run python -m cds_bench.acquire \
  --mirror https://huggingface.co/datasets/open-athena/cds-bench/resolve/main/sources
```

Each assembly supplies a first-order codon Markov model fitted to complete,
unambiguous code-11 CDSs without internal stops or annotated translation
exceptions. Codon-pair counts stay within genes. A pseudocount of 20 backs each
pair row off to the empirical codon distribution; unigram pseudocounts are 0.01.
Starts and stops are sampled jointly from accepted CDSs. Task lengths are set
explicitly, rather than inheriting the natural gene-length distribution.

The sampled sequences approximate bacterial coding composition. They do not
claim to encode functional proteins. Task-specific generation inserts required
sites, constructs comparison sequences, or rejects unsuitable substrates.
Three-pair RNA stems have complementary arms and at least three unpaired loop
bases. Weakening starts with a canonical stem; repair starts with a synonymous
disruption that has a feasible repair. These are supplied pairing annotations,
not thermodynamic predictions of the whole RNA.

Design problems use six internal codons and at most 15,000 synonymous encodings
before any task-specific insertions. Exact enumeration certifies feasibility,
the objective, and the specified tie-break. A failed search causes resampling;
timeouts and empty candidate sets never become an `IMPOSSIBLE` answer.

The default seed is 20261029. Each task/example has an independent PCG64 stream
derived from that seed and its identifier. The output contains ten instances
per task, with paired easy/hard prompts: 840 instances and 1,680 rows in two
evaluation splits, `easy` and `hard`, with 840 rows each. Row IDs and fields
are identical to those in the original combined release. Changing `--count`
or `--seed` generates another release. Re-running the locked environment
reproduces `records.jsonl`, `data/easy.parquet`, and `data/hard.parquet` byte
for byte. Generation reports and individual solved instances are under `build/`.

## Dataset schema

All fields are strings. `answer` contains the final answer payload without its
marker or an explanation. For JSON outputs it is canonical JSON text. For
scalar outputs it is the value's text representation, including JSON syntax for
simple lists and booleans where the task requires them. Numeric spelling and
sequence-spacing normalization follow the benchmark's existing rules.

| Field | Meaning |
|---|---|
| `id` | Unique prompt identifier, including its variant. |
| `instance_id` | Question identifier shared by its easy and hard variants. |
| `task_id` | Published individual or composition task identifier. |
| `variant` | `easy` or `hard`, indicating supplied reference support. |
| `prompt` | Complete model-visible prompt rendered from the site template. |
| `answer` | Canonical final answer payload. |
| `output_format` | `scalar` or `json`, as defined by the task. |
| `inputs_json` | The task's complete input object serialized as JSON. |

To publish after reviewing the generated release:

```sh
uv run python -m cds_bench.publish
```
