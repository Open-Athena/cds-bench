Evaluate CDS-bench without tools and with offline Python, first in a **30-task model/provider pilot**, then in a **full matched Luna/Qwen evaluation**. This is an evaluation-only PR; **do not merge**.

**Full evaluation: 3,260/3,260 Qwen attempts (complete)**, compared with 3,260 matching historical Luna attempts. Each condition has ten examples per task: 840 easy and 790 hard. All Qwen requests are fresh; pilot responses are not reused.

[Full evaluation report (HTML)](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/report.html) · [Pilot report (HTML)](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/model-pilot-20261029/report.html) · [Full per-task results](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/by-task.csv) · [Pilot per-task results](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/model-pilot-20261029/by-task.csv)

The HTML reports are self-contained; download and open them in a browser.

**Full evaluation results**

| Model | Condition | Correct | Accuracy | Median | Cost | Truncated |
|---|---|---:|---:|---:|---:|---:|
| Luna | Easy,&nbsp;no&nbsp;tools | 738/840 | 87.9% | 8.6s | $0.63658 | 1 |
| Luna | Hard,&nbsp;no&nbsp;tools | 679/790 | 85.9% | 9.5s | $0.59889 | 0 |
| Luna | Easy,&nbsp;Python | 793/840 | 94.4% | 7.6s | $0.43532 | 0 |
| Luna | Hard,&nbsp;Python | 710/790 | 89.9% | 8.0s | $0.39479 | 0 |
| Qwen&nbsp;Flash | Easy,&nbsp;no&nbsp;tools | 227/840 | 27.0% | 235.3s | $3.12415 | 293 |
| Qwen&nbsp;Flash | Hard,&nbsp;no&nbsp;tools | 199/790 | 25.2% | 250.8s | $2.99366 | 310 |
| Qwen&nbsp;Flash | Easy,&nbsp;Python | 386/840 | 46.0% | 52.2s | $1.27409 | 13 |
| Qwen&nbsp;Flash | Hard,&nbsp;Python | 332/790 | 42.0% | 70.6s | $1.49165 | 23 |

Both full-evaluation models use `high` reasoning, a requested 32,768-token budget per example and a 300-second deadline per API request. All failures remain in the denominator. Median time includes tool round trips and failures; cost covers the scored attempts. **Truncated** counts token-cap failures.

<details>
<summary>Full-evaluation failures, billing and token-budget exceptions</summary>

| Model | Condition | Wrong | Format | Timeout | Cap | API |
|---|---|---:|---:|---:|---:|---:|
| Luna | Easy,&nbsp;no&nbsp;tools | 90 | 3 | 8 | 1 | 0 |
| Luna | Hard,&nbsp;no&nbsp;tools | 103 | 2 | 6 | 0 | 0 |
| Luna | Easy,&nbsp;Python | 42 | 4 | 0 | 0 | 1 |
| Luna | Hard,&nbsp;Python | 63 | 1 | 0 | 0 | 16 |
| Qwen&nbsp;Flash | Easy,&nbsp;no&nbsp;tools | 72 | 198 | 17 | 293 | 33 |
| Qwen&nbsp;Flash | Hard,&nbsp;no&nbsp;tools | 65 | 163 | 44 | 310 | 9 |
| Qwen&nbsp;Flash | Easy,&nbsp;Python | 75 | 359 | 3 | 13 | 4 |
| Qwen&nbsp;Flash | Hard,&nbsp;Python | 112 | 309 | 4 | 23 | 10 |

Recorded charges: **$8.88355 Qwen**, **$2.06559 retained Luna**. Billing is incomplete for 29 Qwen attempts and 16 retained Luna attempts. Unknown charges are not assumed to be zero.

Qwen reports usage beyond the requested 32,768-token budget for 24 attempts, up to 64,923 tokens. The [audit](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/audit.json) lists these exceptions. Actual provider-reported usage is not strictly matched to Luna’s requested cap.

</details>

**30-task pilot**

One judgment-selected instance per task, each in easy/hard form and with/without Python. Two duplicate hard variants are omitted, leaving **30 easy + 28 hard prompts and 116 attempts per complete model**. The pilot checks accuracy, cost, latency and tool compatibility. It is too small for a definitive model ranking.

The [pilot HTML report](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/model-pilot-20261029/report.html) gives four-condition scores, per-task predictions, provider/reasoning settings, failure categories, timing definitions and GPT-OSS compatibility checks. Partial runs, the lower LFM token budget and tool-protocol failures are kept explicit.

<details>
<summary>Pilot results: 12 model/provider runs, with accuracy, timing and costs</summary>

| Model | Condition | Correct | Accuracy | Median | Cost | Truncated |
|---|---|---:|---:|---:|---:|---:|
| Luna | All&nbsp;four | 107/116 | 92.2% | 8.6s | $0.07805 | 0 |
| Beam&nbsp;501B&nbsp;A23B | All&nbsp;four | 99/116 | 85.3% | 6.9s | $0.62241 | 5 |
| DeepSeek&nbsp;Flash | Partial | 93/101 | 92.1% | 13.5s | $0.12730 | 2 |
| Nemotron&nbsp;Ultra | Partial | 69/100 | 69.0% | 130.3s | $0.00000 | 0 |
| Lightning&nbsp;io.net | Partial | 21/81 | 25.9% | 154.7s | $0.12087 | 2 |
| Lightning&nbsp;CoreWeave | All&nbsp;four | 45/116 | 38.8% | 45.9s | $0.46213 | 35 |
| Qwen&nbsp;Flash | All&nbsp;four | 47/116 | 40.5% | 143.0s | $0.30059 | 16 |
| North&nbsp;Mini&nbsp;Code | Partial | 13/33 | 39.4% | 159.4s | $0.00000 | 1 |
| GPT-OSS&nbsp;20B | All&nbsp;four | 37/116 | 31.9% | 26.7s | $0.35233 | 19 |
| Gemma&nbsp;31B | Partial | 5/24 | 20.8% | 300.0s | $0.04795 | 0 |
| Gemma&nbsp;26B&nbsp;A4B | Partial | 8/100 | 8.0% | 220.2s | $0.35711 | 6 |
| LFM&nbsp;24B&nbsp;A2B | All&nbsp;four | 9/116 | 7.8% | 20.8s | $0.65148 | 99 |

**All four** pools easy/hard with/without Python. **Partial** means the run was stopped early and pools only completed attempts across the conditions reached. These subsets are not directly comparable to complete runs. North and Gemma 31B never reached a scored Python condition. Full model names, provider routing and failure counts are in the pilot report.

LFM used the approved **8,192-token** budget and exhausted it on 99/116 attempts. GPT-OSS/Bedrock’s tool scores include **24 API/protocol failures**; separate CoreWeave/Groq checks did not establish a reliable OpenRouter tool setup. Gemma, North, LFM and Nemotron Lightning enable reasoning without an effort selector; the other models request `high`. Lightning’s io.net run was stopped at the user’s request because it was slow; a separate fresh CoreWeave BF16 run uses the same prompts and settings. Both routes have no fallback and remain separate. io.net initially used concurrency ten, then continued only unissued cases at concurrency three with five-second request spacing; all completed failures are retained.

Costs cover these scored subsets, excluding compatibility checks, removed duplicate-hard cases, interrupted requests and follow-up diagnostics. Missing charges remain explicit. The reports separate incorrect values, formatting failures, timeouts, token caps and API/protocol errors. Earlier ten-example GLM/Luna checks are a separate report appendix, not pooled here.

</details>

**Request and execution settings**

| Setting | Value |
|---|---|
| Full models / providers | `openai/gpt-6-luna` / OpenAI; `qwen/qwen3.7-flash` / `alibaba/us-east-1`; no fallback |
| Full reasoning | `{"effort":"high","exclude":false}`; pilot exceptions are documented above |
| Output / timeout | 32,768 aggregate generated tokens/example (8,192 for LFM); **300 seconds/API request** |
| Tools / web | One local Python function, `auto`; no-tools uses `tools=[]`, `tool_choice="none"`; web plugin disabled |
| Executor | **`/usr/bin/sandbox-exec`**, `(deny network*)`; Python 3.12.9 + NumPy 2.5.4; **no Biopython** |
| Tool limits | Eight calls/example; 30 seconds/call; fresh interpreter; files persist within example |
| Sampling | Seed 20261029 where supported, omitted on Bedrock and both Lightning runs; provider-default temperature; initially ten concurrent examples, with free-endpoint pacing. io.net continued only unissued cases at concurrency three |

<details>
<summary>Exact Python function supplied to OpenRouter</summary>

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

The no-tools condition sends an empty tools array. No hosted shell or web tool is registered. Separate GPT-OSS compatibility experiments are described in the pilot report.

</details>

<details>
<summary>Exact full-evaluation request settings</summary>

```json
{
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
}
```

The tools condition adds the function above and uses `auto`, then `none` after the call limit. Each round receives the remaining token budget. Returned reasoning records are preserved between turns. Pilot-specific routing and settings are in its report.

</details>

<details>
<summary>Local Python execution and network isolation</summary>

The controller executes returned Python programs locally and sends stdout/stderr, exit code and timeout status back as tool results. Network isolation is an OS policy, not an OpenRouter parameter; the controller retains API access.

```sh
/usr/bin/sandbox-exec -f "$workdir/sandbox.sb" \
  "$runtime/bin/python" -I -B -c "$launcher"
```

The policy denies `network*` and `process-fork`, restricts reads to runtime/system paths and the current example workdir, and restricts writes to that workdir. Benchmark answers and credentials are inaccessible. Startup checks verify these restrictions.

</details>

<details>
<summary>Dataset matching, scoring and saved artifacts</summary>

Full-evaluation dataset revision: `26f63e8e488022bed14e12af0f1e44d87a28e14f`. Five duplicated hard variants were removed after the original Luna run. Its original 3,360-attempt artifacts remain intact; the combined comparison excludes only those 100 historical attempts. Retained prompts and reference answers match byte for byte. The pilot’s 30 task types contain two of those duplicated hard variants, so its comparison retains 116 attempts/model.

The deterministic scorer and benchmark definitions are unchanged. No scored inference requests are retried. A separate formatting diagnostic accepts an inline final-answer marker and removes one outer JSON fence; it never changes primary scores. GPT-OSS exploratory compatibility checks are separate from scored pilot attempts.

Failed Qwen request metadata omitted by the legacy trial is reconstructed from saved response and billing files for reporting. Raw traces, final answers and scores are unchanged. Public artifacts include prompts, final predictions, settings and metrics. Raw API requests, reasoning and tool programs/results remain local and untracked.

</details>
