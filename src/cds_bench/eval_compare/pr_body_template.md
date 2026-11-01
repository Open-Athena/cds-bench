Results for four general-purpose LLMs: GPT-6 Luna (high), Nemotron 3.5 Lightning, Qwen 3.7 Flash (high) and Snowball v0.1. Carbon-X is a separate biology-specialist comparison. The PR also includes a broader model pilot and Snowball tool-use experiments.

## Full evaluation

The benchmark has [65 individual task types](https://openathena.ai/cds-bench/#catalogue) and [19 composition task types](https://openathena.ai/cds-bench/#compositions). A composition task combines procedures from individual tasks to solve one question, for example applying a DNA edit, translating both versions and comparing the peptides produced by digestion.

Each model receives the same questions and reference answers: ten examples for each of 84 easy and 79 hard task types, tested without tools and with optional offline Python (3,260 cases per model). The Snowball "1-shot tools" follow-up repeats only the 1,630 cases with Python available and requires its use. Timed-out requests are retried until the model returns a response or reaches the output token limit. The first completed response is scored; truncation counts as a failure.

{{FULL_RESULT_INTERPRETATION}}

Notably, Snowball uses Python on only **177/1,630 examples (10.9%)**, versus **{{NEMOTRON_TOOL_USERS}}/1,630 ({{NEMOTRON_TOOL_RATE}})** for Nemotron. This {{TOOL_USE_GAP_PP}}-percentage-point gap motivates the Snowball v0.1 (1-shot tools) follow-up, which adds a tool-use demonstration and requires an initial Python program.

[Full report (HTML)](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/report.html) · [Per-task results (CSV)](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/by-task.csv) · [Final predictions (JSON)](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/results.json) · [Traces (HF)](https://huggingface.co/datasets/eczech/cds-bench-pr-2-traces)

### Accuracy by condition

![CDS-bench accuracy by model and evaluation condition](https://raw.githubusercontent.com/Open-Athena/cds-bench/refs/heads/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/overall.png?v={{OVERALL_PNG_HASH}})

{{SNOWBALL_CHART_NOTE}}

Exports: [PNG](https://raw.githubusercontent.com/Open-Athena/cds-bench/refs/heads/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/overall.png?v={{OVERALL_PNG_HASH}}) · [SVG](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/overall.svg)

<details>
<summary>Full results: accuracy, median time, cost and truncation</summary>

| Model | Condition | Correct | Accuracy | Median | Cost | Truncated |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
{{FULL_RESULTS_ROWS}}

The four general-purpose models are ordered by pooled mean task accuracy, with each task weighted equally; Carbon-X is shown separately. Median time uses {{LATENCY_ACCOUNTING}}. Truncated counts token-cap failures. Costs include all attempts and exclude the pilot.

Recorded total costs, including timeout attempts and retries: {{RECORDED_CHARGES_BY_MODEL}}. Totals include available charges only; billing is incomplete for {{UNRECONCILED_CASES_BY_MODEL}}.

</details>

<details>
<summary>General-purpose models: failure counts by condition</summary>

| Model | Condition | Wrong answer | Format | Request timeout | Token cap | API/protocol |
|---|---|---:|---:|---:|---:|---:|
{{FULL_FAILURE_ROWS}}

Wrong answers, formatting failures and token caps count against accuracy. API/protocol errors are reported separately and remain included in the denominator.

Qwen reported usage beyond the requested 32,768-token budget on {{QWEN_OVER_BUDGET_ATTEMPTS}} attempts, up to {{QWEN_MAX_REPORTED_TOKENS}} tokens. The [audit](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/audit.json) lists these exceptions. Actual provider-reported usage was therefore not strictly matched to Luna’s requested cap.

</details>

### Task performance

![Hard/Python task accuracy for the four general-purpose models (79 evaluated task types)](https://raw.githubusercontent.com/Open-Athena/cds-bench/refs/heads/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/task-radar-hard-tools.png?v={{HARD_PYTHON_RADAR_PNG_HASH}})

Exports: [PNG](https://raw.githubusercontent.com/Open-Athena/cds-bench/refs/heads/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/task-radar-hard-tools.png?v={{HARD_PYTHON_RADAR_PNG_HASH}}) · [SVG](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/task-radar-hard-tools.svg)

The radar plots above show Hard/Python results for the four general-purpose models under the same strict scoring criteria. Snowball v0.1 uses the standard optional-tool setup, without answer-format compensation or the “1-shot tools” modifications. Each spoke shows accuracy on one task’s ten hard examples, with Python available. Subtitles report mean accuracy across the 79 task types with hard variants; the five easy-only task types are omitted.

Results for the other evaluation conditions are available in the [HTML report](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/report.html#task-radar).

### Nemotron versus Snowball on easy questions

{{OPEN_WEIGHT_FAMILY_CONTEXT}}

![Task accuracy for Nemotron and Snowball: Easy without tools and Easy with Python](https://raw.githubusercontent.com/Open-Athena/cds-bench/refs/heads/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/nemotron-snowball-easy.png?v={{NEMOTRON_SNOWBALL_PNG_HASH}})

Exports: [PNG](https://raw.githubusercontent.com/Open-Athena/cds-bench/refs/heads/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/nemotron-snowball-easy.png?v={{NEMOTRON_SNOWBALL_PNG_HASH}}) · [SVG](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/nemotron-snowball-easy.svg)

Each point shows one task’s accuracy for both models on the same examples. Colors identify the task groups used in the radar plots above. Snowball scores higher above the equality line; Nemotron scores higher below it. Numbered markers combine overlapping tasks.

{{EASY_FAMILY_INTERPRETATION}}

{{COMPOSITION_EXAMPLE}}

{{EASY_FAMILY_EXAMPLES}}

{{EASY_FAMILY_DETAILS}}

## Snowball tool use

### Optional Python

Snowball used the available Python tool on only **177/1,630 examples (10.9%)**, compared with **{{NEMOTRON_TOOL_USERS}}/1,630 ({{NEMOTRON_TOOL_RATE}})** for Nemotron, an {{TOOL_USE_GAP_PP}}-percentage-point gap.

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

The pilot covers {{PILOT_MODEL_COUNT}} models across {{PILOT_RUN_COUNT}} model/provider runs, including DeepSeek V4.1 Flash 1017, Beam 1.0 501B A23B, Gemma 4 31B and GPT-OSS 20B. It uses one manually selected example per task, with easy and hard prompt variants, each tested with and without Python. Removing two duplicate hard variants leaves 30 easy + 28 hard questions and 116 attempts per complete model.

Luna scored 107/116 (92.2%) and Beam 99/116 (85.3%) across all four conditions. DeepSeek scored 93/101 (92.1%) on a partial run. The small sample, incomplete runs and differing token budgets limit model ranking; the pilot also exposes substantial tool and provider compatibility differences. **Pilot scores count request timeouts as failures; the full evaluation retries them.**

[Pilot report (HTML)](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/model-pilot-20261029/report.html) · [Pilot per-task results (CSV)](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/model-pilot-20261029/by-task.csv). The report includes provider behavior, tool compatibility, timing and failure categories.

### Pilot results

{{PILOT_RESULTS_TABLE}}

Scores pool the available conditions. † Partial run. ‡ [353 additional Easy/no-tools cases](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/model-pilot-20261029/report.html#coreweave-extra), outside the pilot. Costs cover the displayed cases.

Output caps are 32,768 tokens, except Snowball RC (16,384) and LFM (8,192). GPT-OSS includes 24 API/tool-protocol failures; provider diagnostics are in the linked pilot report.

{{CARBON_PILOT_NOTE}}

Both Snowball checkpoints have 67B total / 2B active parameters and use the internal Marin/vLLM API.

- Snowball RC (2026.09.21), the release candidate: [open-athena/Grug-67B-A2B-Datakit-SFT-262K-2026.09.21](https://huggingface.co/open-athena/Grug-67B-A2B-Datakit-SFT-262K-2026.09.21/tree/b8c07f7df1df65525abbfdbcd1572318ba11c42f), revision `b8c07f7df1df65525abbfdbcd1572318ba11c42f`.
- Snowball v0.1: [open-athena/Marin-Snowball-67B-A2B-v0.1](https://huggingface.co/open-athena/Marin-Snowball-67B-A2B-v0.1/tree/adc0078a19a4383bc998fcdb43867b3360baf5f3), revision `adc0078a19a4383bc998fcdb43867b3360baf5f3`.

## Settings and provenance

<details>
<summary>Request deadlines, retries and scoring</summary>

Timeouts and transient provider or connection failures during retries, such as HTTP 429, trigger backoff and another attempt with no overall retry limit. Cases remain pending while the provider is unavailable. The first response that ends normally or at the token limit is scored; completed wrong answers, formatting failures and token-cap completions are not resampled.

Initial OpenRouter requests used a five-minute deadline; retries use 15 minutes. Snowball uses 30 minutes. Deadlines guard against stuck or intermittently slow requests, rather than setting a time budget for a scored answer. Retries use the same provider, prompt and token budget.

Request accounting: 217 cases required retries (14 Luna, 135 Nemotron and 68 Qwen), using {{ADDITIONAL_RETRY_ATTEMPTS}} additional attempts. All attempts are saved and included in costs and elapsed times. Non-timeout API errors outside these cases were not retried and remain reported in the failure table.

{{TIMEOUT_RECOVERY_AUDIT_LINK_AND_COUNTS}}

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
{{PYTHON_TOOL_JSON}}
```

For no-tools conditions, OpenRouter receives an empty tools array and Snowball omits the function definitions from its chat template. No shell or web tool is registered.

</details>

<details>
<summary>Exact general-purpose model request settings</summary>

```json
{{REQUEST_SETTINGS_JSON}}
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
{{SNOWBALL_NATIVE_FIELDS_JSON}}
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
