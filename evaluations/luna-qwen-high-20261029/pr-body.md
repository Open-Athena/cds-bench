Results for four general-purpose LLMs: GPT-6 Luna (high), Nemotron 3.5 Lightning, Qwen 3.7 Flash (high) and Snowball v0.1. Carbon-X is a separate biology-specialist comparison. The PR also includes a broader model pilot and Snowball tool-use experiments.

## Full evaluation

The benchmark has [65 individual task types](https://openathena.ai/cds-bench/#catalogue) and [19 composition task types](https://openathena.ai/cds-bench/#compositions). A composition task combines procedures from individual tasks to solve one question, for example applying a DNA edit, translating both versions and comparing the peptides produced by digestion.

Each model receives the same questions and reference answers: ten examples for each of 84 easy and 79 hard task types, tested without tools and with optional offline Python (3,260 cases per model). The Snowball "1-shot tools" follow-up repeats only the 1,630 cases with Python available and requires its use. Timed-out requests are retried until the model returns a response or reaches the output token limit. The first completed response is scored; truncation counts as a failure.

A frontier model like GPT-6 Luna approaches saturation on easy questions with Python (94.4%) and scores 89.6% overall. The three open-weight general-purpose LLMs, including [Snowball v0.1](https://openathena.ai/blog/post-training-in-the-open/), perform similarly without tools (20.7%–26.7% across easy and hard questions), but differ sharply when Python is available: 57.4% for Nemotron, 44.3% for Qwen and 24.6% for Snowball. Carbon-X reaches only 6.8%, despite custom answer parsing that compensates for its instruction-following errors.

Notably, Snowball uses Python on only **177/1,630 examples (10.9%)**, versus **1,545/1,630 (94.8%)** for Nemotron. This 83.9-percentage-point gap motivates the Snowball v0.1 (1-shot tools) follow-up, which adds a tool-use demonstration and requires an initial Python program.

[Full report (HTML)](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/report.html) · [Per-task results (CSV)](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/by-task.csv) · [Final predictions (JSON)](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/results.json) · [Traces (HF)](https://huggingface.co/datasets/eczech/cds-bench-pr-2-traces)

### Accuracy by condition

![CDS-bench accuracy by model and evaluation condition](https://raw.githubusercontent.com/Open-Athena/cds-bench/refs/heads/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/overall.png?v=d11dad349730)

<details>
<summary>† Carbon-X uses customizations to compensate for instruction-following errors</summary>

Carbon-X repeatedly ignored the benchmark’s required answer format in the pilot, even with the settings recommended by the [model authors](https://huggingface.co/HuggingFaceBio/Carbon-X/blob/17de89165e25c49e7de4f845d0e5d464469de359/README.md) (thinking off, temperature 0.6, top-p 0.95 and top-k 20). The error compensation targets those recurring failures: we accept `Final answer: ATGC` on one line or a bare answer, remove surrounding Markdown and `<dna>…</dna>` tags, and parse Python-style lists and dictionaries as JSON without running code. This recovers 222/3,260 correct answers (6.8%), compared with 3/3,260 (0.1%) under strict scoring. These model-specific scores are not directly comparable to the other models’ strict scores. Sequence contents, numerical values, field names and list order must still match; truncated answers and malformed tool calls still fail. The parsing rules were fixed before the full run. The server cannot force valid JSON during tool-call generation with this tokenizer. [Configuration and strict counts](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/carbon-x.json).

</details>

<details>
<summary>‡ Snowball v0.1 (1-shot tools) uses customizations to compensate for low tool use</summary>


Standard Snowball used Python on only 177/1,630 examples where Python was available (10.9%). This variant compensates with one arithmetic tool-use demonstration and a requirement to run a Python program before answering. The model supplies the program; the controller executes it verbatim and returns the result. Python use rises to 1,563/1,630 (95.9%).

Accuracy rises from 26.3% to 37.6% on Easy/Python and 22.8% to 32.2% on Hard/Python. The question data and strict final-answer scorer are unchanged; the prompting and execution requirements differ from the optional-tool baseline.

[Exact example request](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/snowball-v01-one-shot-tools-example.txt) · [Aggregates, prompt instructions and schema](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/snowball-v01-one-shot-tools.json) · [Completion audit](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/snowball-v01-one-shot-tools-audit.json)

Each benchmark question is preceded by a worked arithmetic example showing a Python call, its output and the final answer. Instructions requiring Python are added before and after the original benchmark prompt. The original sequence inputs, references, answer and scoring rules are unchanged. The first response must contain exactly one `code` string; the controller executes it verbatim and returns the result. If execution fails, the model writes a complete replacement program. The controller does not edit the program or supply reference-answer feedback. The final answer is scored as originally specified.

The sandbox, 32,768 aggregate generated-token budget and eight-execution limit are unchanged.

The full run contains 1,630 fresh attempts, separate from calibration, with no scored retries. Temperature 0.7, seed 20261029, concurrency 60 and a 1,800-second request deadline match the Snowball setup. Its raw traces remain local and are not yet in the linked HF archive.

The protocol was selected using predeclared tool-invocation and successful-execution thresholds on 30 easy and 28 hard calibration attempts, rather than answer accuracy.

Checkpoint, with 67B total / 2B active parameters: [open-athena/Marin-Snowball-67B-A2B-v0.1](https://huggingface.co/open-athena/Marin-Snowball-67B-A2B-v0.1/tree/adc0078a19a4383bc998fcdb43867b3360baf5f3), revision `adc0078a19a4383bc998fcdb43867b3360baf5f3`.

</details>

Exports: [PNG](https://raw.githubusercontent.com/Open-Athena/cds-bench/refs/heads/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/overall.png?v=d11dad349730) · [SVG](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/overall.svg)

<details>
<summary>Full results: accuracy, median time, cost and truncation</summary>

| Model | Condition | Correct | Accuracy | Median | Cost | Truncated |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| GPT-6&nbsp;Luna&nbsp;(high) | Easy,&nbsp;no&nbsp;tools | 738/840 | 87.9% | 8.6s | $0.74795 | 5 |
| GPT-6&nbsp;Luna&nbsp;(high) | Hard,&nbsp;no&nbsp;tools | 679/790 | 85.9% | 9.5s | $0.69396 | 5 |
| GPT-6&nbsp;Luna&nbsp;(high) | Easy,&nbsp;Python | 793/840 | 94.4% | 7.6s | $0.43532 | 0 |
| GPT-6&nbsp;Luna&nbsp;(high) | Hard,&nbsp;Python | 710/790 | 89.9% | 8.0s | $0.39479 | 0 |
| Nemotron&nbsp;3.5&nbsp;Lightning | Easy,&nbsp;no&nbsp;tools | 222/840 | 26.4% | 161.5s | $3.28820 | 146 |
| Nemotron&nbsp;3.5&nbsp;Lightning | Hard,&nbsp;no&nbsp;tools | 192/790 | 24.3% | 157.4s | $3.30568 | 176 |
| Nemotron&nbsp;3.5&nbsp;Lightning | Easy,&nbsp;Python | 538/840 | 64.0% | 28.3s | $1.84583 | 4 |
| Nemotron&nbsp;3.5&nbsp;Lightning | Hard,&nbsp;Python | 398/790 | 50.4% | 40.7s | $2.38756 | 7 |
| Qwen&nbsp;3.7&nbsp;Flash&nbsp;(high) | Easy,&nbsp;no&nbsp;tools | 230/840 | 27.4% | 235.3s | $3.19283 | 302 |
| Qwen&nbsp;3.7&nbsp;Flash&nbsp;(high) | Hard,&nbsp;no&nbsp;tools | 206/790 | 26.1% | 250.8s | $3.18124 | 335 |
| Qwen&nbsp;3.7&nbsp;Flash&nbsp;(high) | Easy,&nbsp;Python | 387/840 | 46.1% | 52.2s | $1.28484 | 13 |
| Qwen&nbsp;3.7&nbsp;Flash&nbsp;(high) | Hard,&nbsp;Python | 335/790 | 42.4% | 70.6s | $1.50354 | 23 |
| Snowball&nbsp;v0.1 | Easy,&nbsp;no&nbsp;tools | 179/840 | 21.3% | 109.6s | Unavailable | 109 |
| Snowball&nbsp;v0.1 | Hard,&nbsp;no&nbsp;tools | 158/790 | 20.0% | 119.5s | Unavailable | 103 |
| Snowball&nbsp;v0.1 | Easy,&nbsp;Python | 221/840 | 26.3% | 110.4s | Unavailable | 91 |
| Snowball&nbsp;v0.1 | Hard,&nbsp;Python | 180/790 | 22.8% | 122.2s | Unavailable | 96 |
| Carbon-X† | Easy,&nbsp;no&nbsp;tools | 71/840 | 8.5% | 3.1s | Unavailable | 8 |
| Carbon-X† | Hard,&nbsp;no&nbsp;tools | 52/790 | 6.6% | 2.9s | Unavailable | 7 |
| Carbon-X† | Easy,&nbsp;Python | 55/840 | 6.5% | 3.1s | Unavailable | 10 |
| Carbon-X† | Hard,&nbsp;Python | 44/790 | 5.6% | 3.3s | Unavailable | 15 |

The four general-purpose models are ordered by pooled mean task accuracy, with each task weighted equally; Carbon-X is shown separately. Median time uses total recorded attempt time per case, including discarded attempts and retries. Truncated counts token-cap failures. Costs include all attempts and exclude the pilot.

Recorded total costs, including timeout attempts and retries: $2.27203 for Luna, $10.82727 for Nemotron, $9.16244 for Qwen. Totals include available charges only; billing is incomplete for 18 Luna cases, 55 Nemotron cases, 30 Qwen cases.

</details>

<details>
<summary>General-purpose models: failure counts by condition</summary>

| Model | Condition | Wrong answer | Format | Request timeout | Token cap | API/protocol |
|---|---|---:|---:|---:|---:|---:|
| GPT-6&nbsp;Luna&nbsp;(high) | Easy,&nbsp;no&nbsp;tools | 94 | 3 | 0 | 5 | 0 |
| GPT-6&nbsp;Luna&nbsp;(high) | Hard,&nbsp;no&nbsp;tools | 104 | 2 | 0 | 5 | 0 |
| GPT-6&nbsp;Luna&nbsp;(high) | Easy,&nbsp;Python | 42 | 4 | 0 | 0 | 1 |
| GPT-6&nbsp;Luna&nbsp;(high) | Hard,&nbsp;Python | 63 | 1 | 0 | 0 | 16 |
| Nemotron&nbsp;3.5&nbsp;Lightning | Easy,&nbsp;no&nbsp;tools | 278 | 157 | 0 | 146 | 37 |
| Nemotron&nbsp;3.5&nbsp;Lightning | Hard,&nbsp;no&nbsp;tools | 269 | 151 | 0 | 176 | 2 |
| Nemotron&nbsp;3.5&nbsp;Lightning | Easy,&nbsp;Python | 87 | 196 | 0 | 4 | 15 |
| Nemotron&nbsp;3.5&nbsp;Lightning | Hard,&nbsp;Python | 147 | 238 | 0 | 7 | 0 |
| Qwen&nbsp;3.7&nbsp;Flash&nbsp;(high) | Easy,&nbsp;no&nbsp;tools | 73 | 202 | 0 | 302 | 33 |
| Qwen&nbsp;3.7&nbsp;Flash&nbsp;(high) | Hard,&nbsp;no&nbsp;tools | 71 | 169 | 0 | 335 | 9 |
| Qwen&nbsp;3.7&nbsp;Flash&nbsp;(high) | Easy,&nbsp;Python | 75 | 361 | 0 | 13 | 4 |
| Qwen&nbsp;3.7&nbsp;Flash&nbsp;(high) | Hard,&nbsp;Python | 112 | 310 | 0 | 23 | 10 |
| Snowball&nbsp;v0.1 | Easy,&nbsp;no&nbsp;tools | 153 | 382 | 0 | 109 | 17 |
| Snowball&nbsp;v0.1 | Hard,&nbsp;no&nbsp;tools | 145 | 384 | 0 | 103 | 0 |
| Snowball&nbsp;v0.1 | Easy,&nbsp;Python | 167 | 355 | 0 | 91 | 6 |
| Snowball&nbsp;v0.1 | Hard,&nbsp;Python | 161 | 351 | 0 | 96 | 2 |

Wrong answers, formatting failures and token caps count against accuracy. API/protocol errors are reported separately and remain included in the denominator.

Qwen reported usage beyond the requested 32,768-token budget on 24 attempts, up to 64,923 tokens. The [audit](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/audit.json) lists these exceptions. Actual provider-reported usage was therefore not strictly matched to Luna’s requested cap.

</details>

### Task performance

![Hard/Python task accuracy for the four general-purpose models (79 evaluated task types)](https://raw.githubusercontent.com/Open-Athena/cds-bench/refs/heads/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/task-radar-hard-tools.png?v=c756e5610ef0)

Exports: [PNG](https://raw.githubusercontent.com/Open-Athena/cds-bench/refs/heads/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/task-radar-hard-tools.png?v=c756e5610ef0) · [SVG](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/task-radar-hard-tools.svg)

The radar plots above show Hard/Python results for the four general-purpose models under the same strict scoring criteria. Snowball v0.1 uses the standard optional-tool setup, without answer-format compensation or the “1-shot tools” modifications. Each spoke shows accuracy on one task’s ten hard examples, with Python available. Subtitles report mean accuracy across the 79 task types with hard variants; the five easy-only task types are omitted.

Results for the other evaluation conditions are available in the [HTML report](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/report.html#task-radar).

### Nemotron versus Snowball on easy questions

Composition tasks are the hardest family on average for Nemotron, Qwen and Snowball: 19.1% (436/2,280), pooling all four conditions. They also show the strongest evidence of a Nemotron–Snowball gap across task types on Easy/Python: 50.0% (95/190) versus 14.2% (27/190), a 35.8-percentage-point difference (adjusted task-type p = 0.00053). Nemotron leads on 18/19 task types. The next-lowest pooled family accuracies are assay design at 21.1% (76/360) and synonymous design at 28.1% (505/1,800).

![Task accuracy for Nemotron and Snowball: Easy without tools and Easy with Python](https://raw.githubusercontent.com/Open-Athena/cds-bench/refs/heads/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/nemotron-snowball-easy.png?v=851a5cb12f0a)

Exports: [PNG](https://raw.githubusercontent.com/Open-Athena/cds-bench/refs/heads/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/nemotron-snowball-easy.png?v=851a5cb12f0a) · [SVG](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/nemotron-snowball-easy.svg)

Each point shows one task’s accuracy for both models on the same examples. Colors identify the task groups used in the radar plots above. Snowball scores higher above the equality line; Nemotron scores higher below it. Numbered markers combine overlapping tasks.

Easy/Python families favoring Nemotron with adjusted paired-example p < 0.01:

| Family | Nemotron | Snowball | Δ (pp) | p: examples | p: task types |
|---|---|---:|---:|---:|---:|
| Sequence&nbsp;operations | 51/60&nbsp;(85.0%) | 25/60&nbsp;(41.7%) | +43.3 | 3.8e-05 | 0.875 |
| Protein&nbsp;operations | 63/90&nbsp;(70.0%) | 24/90&nbsp;(26.7%) | +43.3 | 3.1e-07 | 0.070 |
| RNA&nbsp;operations | 69/90&nbsp;(76.7%) | 24/90&nbsp;(26.7%) | +50.0 | 3.7e-10 | 0.070 |
| Synonymous&nbsp;design | 82/150&nbsp;(54.7%) | 33/150&nbsp;(22.0%) | +32.7 | 5.7e-09 | 0.007 |
| Construct&nbsp;design | 63/90&nbsp;(70.0%) | 25/90&nbsp;(27.8%) | +42.2 | 5.2e-07 | 0.234 |
| **Composition&nbsp;tasks** | **95/190&nbsp;(50.0%)** | **27/190&nbsp;(14.2%)** | **+35.8** | **1.6e-12** | **0.00053** |

<details>
<summary>Statistical tests and interpretation</summary>

Δ is Nemotron’s accuracy minus Snowball’s, in percentage points; positive values favor Nemotron.

The “p: examples” column uses the exact McNemar test. It considers questions where only one model is correct and asks whether the split of wins is more uneven than expected if neither model had an advantage.

The “p: task types” column swaps the models’ results for whole task types, keeping each task’s ten examples together. Its p-value is the fraction of all possible swaps that produce a gap at least as large in either direction as the observed gap. This accounts for examples of the same task behaving similarly.

Both tests are two-sided. We test ten families in two easy conditions (20 comparisons per method). Holm’s correction adjusts the p-values for the increased risk of chance findings when many comparisons are made. We apply it separately to the example-level and task-type tests. Using adjusted p < 0.01 limits the chance of one or more false positives within each set of 20 comparisons to at most 1%, under the tests’ assumptions.

No family favors Snowball at that threshold in either easy condition. Without tools, no family difference in either direction meets the threshold.

</details>

[Example composition task: From DNA edits to changed peptide readouts](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/report.html#task-pipeline.variant_peptides). In this task, the model applies a DNA edit, translates the original and edited CDSs, digests both proteins with trypsin, and reports the peptides lost or gained. In the illustrated example, R4 → A removes a cleavage site and merges two peptides.

Components: [variant.apply](https://openathena.ai/cds-bench/#task-variant.apply) → [cds.translate](https://openathena.ai/cds-bench/#task-cds.translate) → [protein.trypsin_digest](https://openathena.ai/cds-bench/#task-protein.trypsin_digest).

![Worked composition task: DNA edit, translation, digestion and peptide comparison](https://raw.githubusercontent.com/Open-Athena/cds-bench/refs/heads/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/composition-example.png?v=f57eab3a6199)

[PNG](https://raw.githubusercontent.com/Open-Athena/cds-bench/refs/heads/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/composition-example.png?v=f57eab3a6199) · [SVG](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/composition-example.svg)

For the illustrated task on Easy/Python, Nemotron scores 60.0% (6/10) versus 10.0% (1/10) for Snowball.

The three prompts below are Easy/Python examples that Nemotron answered correctly and Snowball failed.

<details>
<summary>Composition tasks: From DNA edits to changed peptide readouts</summary>

[pipeline.variant_peptides/03](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/report.html#task-pipeline.variant_peptides) · Easy/Python. Task scores: Nemotron 6/10; Snowball 1/10. This example: Nemotron correct; Snowball wrong answer.

Exact benchmark user prompt:

````text
## Task

Apply the DNA edits and report which complete tryptic peptide sequences are lost and gained relative to the original CDS.

## Inputs

DNA inputs are 5′→3′ coding strands. Ignore whitespace between bases.

Coordinates and intervals are 1-based and inclusive unless a rule states otherwise.

In an edit object, `replace` is `[first_base, last_base, new_text]`; an empty `new_text` deletes that interval. `insert_after` gives an original base boundary and `sequence` gives the inserted text. Apply all edits to the original coordinates, simultaneously.

```json
{
  "cds": "ATGGTGGGCCGGGTCTCCCAGACCGCTCTGGTAGGGGATGTGCTCATCCGTATCCTGCTGGCGGATTAG",
  "edits": [
    {
      "replace": [
        10,
        12,
        "GCA"
      ]
    }
  ]
}
```

## Rules

- Use NCBI genetic code 11 with first-stop termination.
- Apply the supplied edits simultaneously to the original DNA coordinates.
- Translate and completely digest both versions under `trypsin_KR_notP_v1`, with zero missed cleavages.
- Compare peptide sequence sets, ignoring copy number.

## Reference material

### Initiation after DNA editing

At the first DNA codon, TTG, CTG, ATT, ATC, ATA, ATG, and GTG encode initiating M under NCBI genetic code 11. If the first edited codon is not one of these initiators, use its ordinary internal assignment.

### NCBI genetic code 11: internal DNA codons

Each internal DNA codon is an aligned group of three bases. The table gives its one-letter amino-acid assignment; STOP marks a stop signal.

```text
TTT=F  TTC=F  TTA=L  TTG=L
TCT=S  TCC=S  TCA=S  TCG=S
TAT=Y  TAC=Y  TAA=STOP  TAG=STOP
TGT=C  TGC=C  TGA=STOP  TGG=W
CTT=L  CTC=L  CTA=L  CTG=L
CCT=P  CCC=P  CCA=P  CCG=P
CAT=H  CAC=H  CAA=Q  CAG=Q
CGT=R  CGC=R  CGA=R  CGG=R
ATT=I  ATC=I  ATA=I  ATG=M
ACT=T  ACC=T  ACA=T  ACG=T
AAT=N  AAC=N  AAA=K  AAG=K
AGT=S  AGC=S  AGA=R  AGG=R
GTT=V  GTC=V  GTA=V  GTG=V
GCT=A  GCC=A  GCA=A  GCG=A
GAT=D  GAC=D  GAA=E  GAG=E
GGT=G  GGC=G  GGA=G  GGG=G
```

### Trypsin cleavage specificity

Trypsin cleaves after K or R, except when the next residue is P. The K or R remains on the upstream peptide.

## Answer

- `lost` lists distinct peptide sequences present in the original tryptic digest and absent from the edited digest. `gained` lists those present only in the edited digest.
- Sort each list in ASCII order. Each sequence appears once; an empty difference is [].

Use exactly this structure. `<…>` marks a typed value; array items and map entries repeat as needed.

### Output structure

```text
{
  "lost": [<amino-acid string>],
  "gained": [<amino-acid string>]
}
```

After any explanation, write `Final answer:` on its own line. Begin the raw JSON on the next line; it may span multiple lines and ends your response.
````

Expected answer:

```text
{"gained":["MVGAVSQTALVGDVLIR"],"lost":["MVGR","VSQTALVGDVLIR"]}
```

</details>

<details>
<summary>Synonymous design: Introduce a DNA recognition site</summary>

[design.insert_dna_motif/01](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/report.html#task-design.insert_dna_motif) · Easy/Python. Task scores: Nemotron 6/10; Snowball 0/10. This example: Nemotron correct; Snowball token cap.

Exact benchmark user prompt:

````text
## Task

Introduce the specified DNA pattern at position `start` through synonymous changes to the CDS.

## Inputs

DNA inputs are 5′→3′ coding strands. Ignore whitespace between bases.

Coordinates and intervals are 1-based and inclusive unless a rule states otherwise.

```json
{
  "cds": "ATGTATGAGTTCATCATTTCGTAG",
  "pattern": "GAATTC",
  "start": 7
}
```

## Rules

- Use NCBI genetic code 11 for codon interpretation.
- Keep the DNA length, complete encoded protein, original first codon, and terminal stop codon unchanged.
- The literal DNA string `pattern` must begin at the supplied 1-based position `start` on the forward coding strand.
- Other copies of that pattern elsewhere in the final CDS are allowed.

## Selection

Among all sequences satisfying every condition, return the lexicographically smallest full DNA string, comparing bases in the order A<C<G<T. This is a tie-break among feasible sequences, not a minimum-edit objective.

## Reference material

### Synonymous codons

Synonymous codons encode the same amino acid. Replacing a codon with a synonymous codon preserves that residue in the protein.

### NCBI genetic code 11: internal DNA codons

Each internal DNA codon is an aligned group of three bases. The table gives its one-letter amino-acid assignment; STOP marks a stop signal.

```text
TTT=F  TTC=F  TTA=L  TTG=L
TCT=S  TCC=S  TCA=S  TCG=S
TAT=Y  TAC=Y  TAA=STOP  TAG=STOP
TGT=C  TGC=C  TGA=STOP  TGG=W
CTT=L  CTC=L  CTA=L  CTG=L
CCT=P  CCC=P  CCA=P  CCG=P
CAT=H  CAC=H  CAA=Q  CAG=Q
CGT=R  CGC=R  CGA=R  CGG=R
ATT=I  ATC=I  ATA=I  ATG=M
ACT=T  ACC=T  ACA=T  ACG=T
AAT=N  AAC=N  AAA=K  AAG=K
AGT=S  AGC=S  AGA=R  AGG=R
GTT=V  GTC=V  GTA=V  GTG=V
GCT=A  GCC=A  GCA=A  GCG=A
GAT=D  GAC=D  GAA=E  GAG=E
GGT=G  GGC=G  GGA=G  GGG=G
```

## Answer

- Return one continuous uppercase DNA sequence.

If no valid result exists, return:

```text
IMPOSSIBLE
```

After any explanation, write `Final answer:` on its own line. Put the required value or list on the next line to finish your response.
````

Expected answer:

```text
ATGTACGAATTCATAATAAGCTAG
```

</details>

<details>
<summary>RNA operations: Apply specified RNA edits</summary>

[rna.apply_edits/01](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/report.html#task-rna.apply_edits) · Easy/Python. Task scores: Nemotron 10/10; Snowball 0/10. This example: Nemotron correct; Snowball wrong answer.

Exact benchmark user prompt:

````text
## Task

Apply the supplied edits to the CDS’s coding RNA and return the edited RNA sequence.

## Inputs

DNA inputs are 5′→3′ coding strands. Ignore whitespace between bases.

Coordinates and intervals are 1-based and inclusive unless a rule states otherwise.

In an edit object, `replace` is `[first_base, last_base, new_text]`; an empty `new_text` deletes that interval. `insert_after` gives an original base boundary and `sequence` gives the inserted text. Apply all edits to the original coordinates, simultaneously.

```json
{
  "cds": "ATGATCAAGCAAGGCGGCACCGACCTCGTGCTCGAACTCTGA",
  "rna_edits": [
    {
      "replace": [
        10,
        10,
        "U"
      ]
    }
  ]
}
```

## Rules

- Transcribe the original CDS and apply the edit objects to that RNA, using original RNA coordinates.
- Use the U alphabet in inserted or replacement RNA text. Do not translate the edited RNA.

## Reference material

### Coding DNA to RNA

The supplied DNA is the coding strand, written 5′→3′. Copy its bases in the same order, replacing each T with U to obtain the coding RNA.

## Answer

- Return one continuous uppercase 5′→3′ RNA sequence.
- An empty sequence is the token EMPTY_SEQUENCE.

After any explanation, write `Final answer:` on its own line. Put the required value or list on the next line to finish your response.
````

Expected answer:

```text
AUGAUCAAGUAAGGCGGCACCGACCUCGUGCUCGAACUCUGA
```

</details>

<details>
<summary>All family comparisons</summary>


The tables below use the statistical tests and correction described above.


Easy, no tools


| Family | Nemotron | Snowball | Δ (pp) | p: examples | p: task types |
|---|---|---:|---:|---:|---:|
| Sequence&nbsp;operations | 21/60&nbsp;(35.0%) | 22/60&nbsp;(36.7%) | -1.7 | 1.000 | 1.000 |
| Variant&nbsp;effects | 29/60&nbsp;(48.3%) | 30/60&nbsp;(50.0%) | -1.7 | 1.000 | 1.000 |
| Sequence&nbsp;statistics | 21/60&nbsp;(35.0%) | 14/60&nbsp;(23.3%) | +11.7 | 1.000 | 1.000 |
| Protein&nbsp;operations | 21/90&nbsp;(23.3%) | 29/90&nbsp;(32.2%) | -8.9 | 1.000 | 1.000 |
| RNA&nbsp;operations | 23/90&nbsp;(25.6%) | 19/90&nbsp;(21.1%) | +4.4 | 1.000 | 1.000 |
| Synonymous&nbsp;design | 26/150&nbsp;(17.3%) | 18/150&nbsp;(12.0%) | +5.3 | 1.000 | 1.000 |
| Construct&nbsp;design | 31/90&nbsp;(34.4%) | 19/90&nbsp;(21.1%) | +13.3 | 0.501 | 1.000 |
| Assay&nbsp;design | 2/30&nbsp;(6.7%) | 2/30&nbsp;(6.7%) | +0.0 | 1.000 | 1.000 |
| Overlapping&nbsp;frames | 12/20&nbsp;(60.0%) | 6/20&nbsp;(30.0%) | +30.0 | 1.000 | 1.000 |
| Composition&nbsp;tasks | 36/190&nbsp;(18.9%) | 20/190&nbsp;(10.5%) | +8.4 | 0.057 | 0.156 |


Easy, Python


| Family | Nemotron | Snowball | Δ (pp) | p: examples | p: task types |
|---|---|---:|---:|---:|---:|
| Sequence&nbsp;operations | 51/60&nbsp;(85.0%) | 25/60&nbsp;(41.7%) | +43.3 | 3.8e-05 | 0.875 |
| Variant&nbsp;effects | 46/60&nbsp;(76.7%) | 26/60&nbsp;(43.3%) | +33.3 | 0.011 | 1.000 |
| Sequence&nbsp;statistics | 41/60&nbsp;(68.3%) | 24/60&nbsp;(40.0%) | +28.3 | 0.020 | 1.000 |
| Protein&nbsp;operations | 63/90&nbsp;(70.0%) | 24/90&nbsp;(26.7%) | +43.3 | 3.1e-07 | 0.070 |
| RNA&nbsp;operations | 69/90&nbsp;(76.7%) | 24/90&nbsp;(26.7%) | +50.0 | 3.7e-10 | 0.070 |
| Synonymous&nbsp;design | 82/150&nbsp;(54.7%) | 33/150&nbsp;(22.0%) | +32.7 | 5.7e-09 | 0.007 |
| Construct&nbsp;design | 63/90&nbsp;(70.0%) | 25/90&nbsp;(27.8%) | +42.2 | 5.2e-07 | 0.234 |
| Assay&nbsp;design | 14/30&nbsp;(46.7%) | 3/30&nbsp;(10.0%) | +36.7 | 0.041 | 1.000 |
| Overlapping&nbsp;frames | 14/20&nbsp;(70.0%) | 10/20&nbsp;(50.0%) | +20.0 | 1.000 | 1.000 |
| Composition&nbsp;tasks | 95/190&nbsp;(50.0%) | 27/190&nbsp;(14.2%) | +35.8 | 1.6e-12 | 0.00053 |


[JSON](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/nemotron-snowball-families.json) · [CSV](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/nemotron-snowball-families.csv)

</details>

## Snowball tool use

### Optional Python

Snowball used the available Python tool on only **177/1,630 examples (10.9%)**, compared with **1,545/1,630 (94.8%)** for Nemotron, an 83.9-percentage-point gap.

For Snowball Easy/Python, 33 task types have at least two examples with a call and two without. Giving each of these task types equal weight, Snowball scores 54.8% with calls versus 23.2% without, a 31.6 percentage-point difference. [Per-task breakdown](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/report.html#snowball-tools).

<details>
<summary>Demonstration-only pilot: matched results, context and settings</summary>

In the [demonstration-only pilot](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/report.html#snowball-oneshot), 7 of 22 final responses missing the required final-answer marker still ended with the correct answer. Two also prefixed it with the demonstration’s arithmetic result. These responses remain failures under the primary scorer.

Adding one arithmetic tool-use demonstration to the matched 58-question pilot increased Python use from 5/58 to 10/58, while accuracy changed from 15/58 (25.9%) to 12/58 (20.7%). Accuracy did not improve in this pilot.

| Condition | Original correct | With demo | Original tool users | With demo |
|---|---:|---:|---:|---:|
| Easy, Python | 7/30 (23.3%) | 8/30 (26.7%) | 3/30 | 7/30 |
| Hard, Python | 8/28 (28.6%) | 4/28 (14.3%) | 2/28 | 3/28 |

The 30 easy and 28 hard benchmark user messages are unchanged byte for byte. Four messages precede each question: an arithmetic question, an assistant Python call, the tool result and an assistant answer. The demonstration covers both tool use and final-answer formatting, so the comparison does not isolate these effects.

The native XML request transformation, response parser and scorer are unchanged. Settings are optional Python, 32,768 aggregate generated tokens, temperature 0.7, seed 20261029, concurrency 60 and a 1,800-second API deadline. The demonstration is the only change to the prompts or model settings. Its Python call is excluded from the tool-use counts.

The client adds error-stage metadata and a 15-second connection-setup timeout, replacing the original pilot’s generic 1,800-second timeout for connection setup. No connection failures occurred in this follow-up.

[Follow-up results and exact demonstration](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/report.html#snowball-oneshot). All 58 fresh attempts passed the source/prompt/budget/scoring audit; none were retried.

</details>

## 30-task model pilot

The pilot covers 14 models across 15 model/provider runs, including DeepSeek V4.1 Flash 1017, Beam 1.0 501B A23B, Gemma 4 31B and GPT-OSS 20B. It uses one manually selected example per task, with easy and hard prompt variants, each tested with and without Python. Removing two duplicate hard variants leaves 30 easy + 28 hard questions and 116 attempts per complete model.

Luna scored 107/116 (92.2%) and Beam 99/116 (85.3%) across all four conditions. DeepSeek scored 93/101 (92.1%) on a partial run. The small sample, incomplete runs and differing token budgets limit model ranking; the pilot also exposes substantial tool and provider compatibility differences. **Pilot scores count request timeouts as failures; the full evaluation retries them.**

[Pilot report (HTML)](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/model-pilot-20261029/report.html) · [Pilot per-task results (CSV)](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/model-pilot-20261029/by-task.csv). The report includes provider behavior, tool compatibility, timing and failure categories.

### Pilot results

| Model | Provider | Correct | Accuracy | Median | Cost | Timeout | Truncated |
|---|---|---:|---:|---:|---:|---:|---:|
| GPT-6&nbsp;Luna&nbsp;(high) | OpenAI | 107/116 | 92.2% | 8.6s | $0.07805 | 1 | 0 |
| DeepSeek&nbsp;Flash&nbsp;† | Morph/FP8 | 93/101 | 92.1% | 13.5s | $0.12730 | 0 | 2 |
| Beam&nbsp;501B&nbsp;A23B | Nebius/FP4 | 99/116 | 85.3% | 6.9s | $0.62241 | 0 | 5 |
| Nemotron&nbsp;Ultra&nbsp;† | NVIDIA | 69/100 | 69.0% | 130.3s | $0.00000 | 12 | 0 |
| Nemotron&nbsp;3.5&nbsp;Lightning | CoreWeave/BF16 | 45/116 | 38.8% | 45.9s | $0.46213 | 0 | 35 |
| Qwen&nbsp;3.7&nbsp;Flash&nbsp;(high) | Alibaba/US | 47/116 | 40.5% | 143.0s | $0.30059 | 6 | 16 |
| North&nbsp;Mini&nbsp;Code&nbsp;† | Cohere | 13/33 | 39.4% | 159.4s | $0.00000 | 13 | 1 |
| GPT-OSS&nbsp;20B | Amazon&nbsp;Bedrock | 37/116 | 31.9% | 26.7s | $0.35233 | 0 | 19 |
| Nemotron&nbsp;3.5&nbsp;Lightning&nbsp;† | io.net | 21/81 | 25.9% | 154.7s | $0.12087 | 25 | 2 |
| Snowball&nbsp;v0.1 | Marin&nbsp;(internal) | 27/116 | 23.3% | 110.3s | Unavailable | 0 | 11 |
| Gemma&nbsp;31B&nbsp;† | Novita/BF16 | 5/24 | 20.8% | 300.0s | $0.04795 | 13 | 0 |
| Snowball&nbsp;RC&nbsp;(2026.09.21) | Marin&nbsp;(internal) | 16/116 | 13.8% | 154.8s | Unavailable | 0 | 61 |
| LFM&nbsp;24B&nbsp;A2B | Liquid/FP8 | 9/116 | 7.8% | 20.8s | $0.65148 | 0 | 99 |
| Gemma&nbsp;26B&nbsp;A4B&nbsp;† | NextBit/BF16 | 8/100 | 8.0% | 220.2s | $0.35711 | 34 | 6 |
| Carbon-X | CoreWeave/vLLM | 0/116 | 0.0% | 3.5s | Unavailable | 0 | 1 |
| Nemotron&nbsp;3.5&nbsp;Lightning&nbsp;‡ | CoreWeave/BF16 | 75/353 | 21.2% | 95.5s | $1.50838 | 0 | 134 |

Scores pool the available conditions. † Partial run. ‡ [353 additional Easy/no-tools cases](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/model-pilot-20261029/report.html#coreweave-extra), outside the pilot. Costs cover the displayed cases.

Output caps are 32,768 tokens, except Snowball RC (16,384) and LFM (8,192). GPT-OSS includes 24 API/tool-protocol failures; provider diagnostics are in the linked pilot report.

Carbon-X is shown with strict pilot scoring (0/116), unlike its error-compensated full-run scores. It had 104 answer-format failures and three malformed Python call attempts; a separate preflight verified the tool round trip. It used thinking off and a 900-second request deadline on self-hosted CoreWeave/vLLM. [Pilot audit and traces](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/model-pilot-20261029/carbon-x-audit.json).

Both Snowball checkpoints have 67B total / 2B active parameters and use the internal Marin/vLLM API.

- Snowball RC (2026.09.21), the release candidate: [open-athena/Grug-67B-A2B-Datakit-SFT-262K-2026.09.21](https://huggingface.co/open-athena/Grug-67B-A2B-Datakit-SFT-262K-2026.09.21/tree/b8c07f7df1df65525abbfdbcd1572318ba11c42f), revision `b8c07f7df1df65525abbfdbcd1572318ba11c42f`.
- Snowball v0.1: [open-athena/Marin-Snowball-67B-A2B-v0.1](https://huggingface.co/open-athena/Marin-Snowball-67B-A2B-v0.1/tree/adc0078a19a4383bc998fcdb43867b3360baf5f3), revision `adc0078a19a4383bc998fcdb43867b3360baf5f3`.

## Settings and provenance

<details>
<summary>Request deadlines, retries and scoring</summary>

Timeouts and transient provider or connection failures during retries, such as HTTP 429, trigger backoff and another attempt with no overall retry limit. Cases remain pending while the provider is unavailable. The first response that ends normally or at the token limit is scored; completed wrong answers, formatting failures and token-cap completions are not resampled.

Initial OpenRouter requests used a five-minute deadline; retries use 15 minutes. Snowball uses 30 minutes. Deadlines guard against stuck or intermittently slow requests, rather than setting a time budget for a scored answer. Retries use the same provider, prompt and token budget.

Request accounting: 217 cases required retries (14 Luna, 135 Nemotron and 68 Qwen), using 218 additional attempts. All attempts are saved and included in costs and elapsed times. Non-timeout API errors outside these cases were not retried and remain reported in the failure table.

[Recovery audit and attempt counts](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/timeout-recovery-audit.json) · [Attempt counts and costs](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/timeout-recovery.json). All 217 cases have a selected model response; earlier attempts timed out or returned a transient provider/connection failure. Original attempts remain saved separately.

The report’s separate formatting diagnostic accepts an inline `Final answer:` marker and removes one outer JSON fence. Timeout-retry traces are not yet in the linked HF archive.

</details>

<details>
<summary>General-purpose model settings and provider routes</summary>

| Setting | Value |
|---|---|
| Dataset | [open-athena/cds-bench](https://huggingface.co/datasets/open-athena/cds-bench/tree/26f63e8e488022bed14e12af0f1e44d87a28e14f), revision `26f63e8e488022bed14e12af0f1e44d87a28e14f` |
| Scoring | [Deterministic scorer](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/src/cds_bench/eval_luna/score.py) · [Snowball completion audit](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/snowball-v01-full-audit.json) |
| Full models / providers | Luna / OpenAI; Qwen / `alibaba/us-east-1`; Nemotron / `deepinfra/bf16`; Snowball v0.1 / internal Marin API. Exact model identifiers are below; no fallback |
| Full reasoning | Luna/Qwen: `high`; Nemotron: reasoning enabled; Snowball: native `enable_thinking=true`. No effort selector is verified for Nemotron or Snowball |
| Full output / timeout | 32,768 generated tokens per attempt, across its tool turns. OpenRouter: 300 seconds for first attempts, 900 seconds for retries; Snowball: 1,800 seconds/API request |
| Tools / web | One local Python function; no web tools. OpenRouter uses `auto` or an empty tools array with `none`. Snowball uses its native tool-call format |
| Executor | `/usr/bin/sandbox-exec`, `(deny network*)`; Python 3.12.9 + NumPy 2.5.4; no Biopython |
| Tool limits | Eight calls/attempt; 30 seconds/call; fresh interpreter; files persist within example |
| Sampling | OpenRouter: concurrency 10, provider-default temperature. Snowball: concurrency 60, temperature 0.7. Seed 20261029 for Luna/Qwen/Snowball; omitted for Nemotron |

Snowball uses the same native API and deployment tested in the pilot, with new responses for the full evaluation.

</details>

<details>
<summary>Exact Python function supplied to the models</summary>

```json
[
  {
    "type": "function",
    "function": {
      "name": "python",
      "description": "Execute Python 3.12.9 code with the standard library and NumPy 2.5.4. Biopython is not installed. Networking and subprocesses are disabled; only runtime files and this example's working directory are readable. Use print() to return results. Each call starts a fresh interpreter; files in the working directory persist within this example. Limits: 30 seconds per call, 16384 characters each of stdout/stderr, and at most 8 calls per example. Returns stdout, stderr, exit_code, timed_out, and output_truncated.",
      "strict": true,
      "parameters": {
        "type": "object",
        "properties": {
          "code": {
            "type": "string",
            "description": "Python code to execute."
          }
        },
        "required": [
          "code"
        ],
        "additionalProperties": false
      }
    }
  }
]
```

For no-tools conditions, OpenRouter receives an empty tools array and Snowball omits the function definitions from its chat template. No shell or web tool is registered.

</details>

<details>
<summary>Exact general-purpose model request settings</summary>

```json
{
  "luna": {
    "model": "openai/gpt-6-luna",
    "max_tokens": 32768,
    "seed": 20261029,
    "reasoning": {
      "effort": "high",
      "exclude": false
    },
    "tool_choice": "none",
    "tools": [],
    "plugins": [
      {
        "id": "web",
        "enabled": false
      },
      {
        "id": "response-healing",
        "enabled": false
      },
      {
        "id": "file-parser",
        "enabled": false
      }
    ],
    "provider": {
      "only": [
        "openai"
      ],
      "ignore": [
        "openai/flex",
        "openai/fast"
      ],
      "allow_fallbacks": false,
      "require_parameters": true
    },
    "stream": true,
    "stream_options": {
      "include_usage": true
    }
  },
  "qwen": {
    "model": "qwen/qwen3.7-flash",
    "max_tokens": 32768,
    "seed": 20261029,
    "reasoning": {
      "effort": "high",
      "exclude": false
    },
    "tool_choice": "none",
    "tools": [],
    "plugins": [
      {
        "id": "web",
        "enabled": false
      },
      {
        "id": "response-healing",
        "enabled": false
      },
      {
        "id": "file-parser",
        "enabled": false
      }
    ],
    "provider": {
      "only": [
        "alibaba/us-east-1"
      ],
      "allow_fallbacks": false,
      "require_parameters": true
    },
    "stream": true,
    "stream_options": {
      "include_usage": true
    }
  },
  "deepinfra": {
    "model": "nvidia/nemotron-3.5-lightning",
    "max_tokens": 32768,
    "reasoning": {
      "enabled": true,
      "exclude": false
    },
    "tool_choice": "none",
    "tools": [],
    "plugins": [
      {
        "id": "web",
        "enabled": false
      },
      {
        "id": "response-healing",
        "enabled": false
      },
      {
        "id": "file-parser",
        "enabled": false
      }
    ],
    "provider": {
      "only": [
        "deepinfra/bf16"
      ],
      "allow_fallbacks": false,
      "require_parameters": true
    },
    "stream": true,
    "stream_options": {
      "include_usage": true
    }
  },
  "snowball-v01": {
    "model": "[private serving model ID]",
    "max_tokens": 32768,
    "temperature": 0.7,
    "seed": 20261029,
    "stream": true,
    "stream_options": {
      "include_usage": true
    },
    "skip_special_tokens": false,
    "chat_template_kwargs": {
      "enable_thinking": true
    }
  }
}
```

For Python conditions, OpenRouter adds the function above with `auto`, then `none` at the call limit. Snowball supplies the function through its native chat template. Each turn receives the remaining token budget. Private Snowball access identifiers are redacted.

</details>

<details>
<summary>Snowball native tool API and adapter limitations</summary>

The service did not support standard automatic function parsing: the initial auto-tool probe returned HTTP 400. The controller instead supplies the function through `chat_template_kwargs.xml_tools`, with `enable_thinking=true` and `skip_special_tokens=false`. The checkpoint template encodes calls as JSON objects with `name` and `arguments` fields inside `<tool_call>` tags. Generation stops at `</tool_call>`, including the delimiter; the client parses the call, executes its code verbatim and returns a tool-role message containing stdout, stderr, exit code, timeout and truncation status.

In the standard Snowball evaluation, tool use is optional. Although the function definition contains `strict:true`, this native route does not enforce a decoding grammar. Definitions are omitted at eight calls.

The standard full run recorded 240 successful program executions and 14 program failures. A zero exit code does not establish that the program or final answer was correct.

The checkpoint template also describes a direct Python-code channel using `python_tag` and `eom_id`, with `ipython` replies. That channel was not tested. It describes a stateful notebook; this evaluation instead starts a fresh interpreter per call. Server-side parsing was not used. The required first program belongs to the separate experiment described above.

Exact native tool-related fields:

```json
{
  "skip_special_tokens": false,
  "chat_template_kwargs": {
    "enable_thinking": true,
    "xml_tools": [
      {
        "type": "function",
        "function": {
          "name": "python",
          "description": "Execute Python 3.12.9 code with the standard library and NumPy 2.5.4. Biopython is not installed. Networking and subprocesses are disabled; only runtime files and this example's working directory are readable. Use print() to return results. Each call starts a fresh interpreter; files in the working directory persist within this example. Limits: 30 seconds per call, 16384 characters each of stdout/stderr, and at most 8 calls per example. Returns stdout, stderr, exit_code, timed_out, and output_truncated.",
          "strict": true,
          "parameters": {
            "type": "object",
            "properties": {
              "code": {
                "type": "string",
                "description": "Python code to execute."
              }
            },
            "required": [
              "code"
            ],
            "additionalProperties": false
          }
        }
      }
    ]
  },
  "stop": [
    "</tool_call>"
  ],
  "include_stop_str_in_output": true
}
```

Snowball’s full run also has a 15-second connection-setup limit. After a burst of connection timeouts, the run continued with examples that had not yet been submitted, using unchanged settings. Earlier failures still count against accuracy. A preflight check verified that the model could call Python and receive its output. Private serving identifiers are omitted.

</details>

<details>
<summary>Local Python execution and network isolation</summary>

The controller returns program stdout/stderr, exit code and timeout status. Network isolation is enforced by the local OS sandbox; the controller retains API access.

```sh
/usr/bin/sandbox-exec -f "$workdir/sandbox.sb" \
  "$runtime/bin/python" -I -B -c "$launcher"
```

The policy denies `network*` and `process-fork`, restricts reads to runtime/system paths and the current example’s working directory, and restricts writes to that directory. Benchmark answers and credentials are inaccessible. Startup checks verify these restrictions.

</details>
