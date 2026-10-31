Compare **Luna high** and **Qwen3.7 Flash high** on the full CDS-bench dataset, with and without offline Python. Qwen uses Alibaba’s US endpoint. This is an evaluation-only branch; **do not merge**.

**Qwen: 3260/3,260 attempts (complete).** Recorded Qwen charges: **$8.883549**. Luna contributes 3,260 matching historical attempts. No pilot responses are reused.

Billing is incomplete for 29 completed Qwen attempts and 16 retained Luna attempts. Unverified charges are not assumed to be zero.

[Combined HTML report](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/report.html) · [Per-task results](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/by-task.csv) · [Predictions](https://github.com/Open-Athena/cds-bench/blob/eval/luna-high-baseline/evaluations/luna-qwen-high-20261029/results.json)

| Model / condition | Correct / finished | Median | Recorded cost |
|---|---:|---:|---:|
| Luna high: Easy, no tools | 738/840 | 8.6s | $0.636581 |
| Luna high: Hard, no tools | 679/790 | 9.5s | $0.598893 |
| Luna high: Easy, Python | 793/840 | 7.6s | $0.435323 |
| Luna high: Hard, Python | 710/790 | 8.0s | $0.394795 |
| Qwen3.7 Flash high: Easy, no tools | 227/840 | 235.3s | $3.124152 |
| Qwen3.7 Flash high: Hard, no tools | 199/790 | 250.8s | $2.993657 |
| Qwen3.7 Flash high: Easy, Python | 386/840 | 52.2s | $1.274086 |
| Qwen3.7 Flash high: Hard, Python | 332/790 | 70.6s | $1.491654 |

All failures remain in the denominator. In-progress Qwen results are a partial subset. Incorrect values, answer-format failures, five-minute timeouts, token caps, and provider/connection errors are separated below.

| Model / condition | Incorrect | Format | Timeout | Token cap | API error |
|---|---:|---:|---:|---:|---:|
| Luna high: Easy, no tools | 90 | 3 | 8 | 1 | 0 |
| Luna high: Hard, no tools | 103 | 2 | 6 | 0 | 0 |
| Luna high: Easy, Python | 42 | 4 | 0 | 0 | 1 |
| Luna high: Hard, Python | 63 | 1 | 0 | 0 | 16 |
| Qwen3.7 Flash high: Easy, no tools | 72 | 198 | 17 | 293 | 33 |
| Qwen3.7 Flash high: Hard, no tools | 65 | 163 | 44 | 310 | 9 |
| Qwen3.7 Flash high: Easy, Python | 75 | 359 | 3 | 13 | 4 |
| Qwen3.7 Flash high: Hard, Python | 112 | 309 | 4 | 23 | 10 |

| Request / execution setting | Value |
|---|---|
| Models / providers | `openai/gpt-6-luna` / OpenAI; `qwen/qwen3.7-flash` / `alibaba/us-east-1`; no fallback |
| Reasoning | `{"effort":"high","exclude":false}` |
| Output / timeout | 32,768 total generated tokens/example; 300 seconds/API request |
| Tools / web | One Python function, `auto`; no-tools uses `tools=[]`, `tool_choice="none"`; web plugin disabled |
| Executor | `/usr/bin/sandbox-exec`, `(deny network*)`; Python 3.12.9 + NumPy 2.5.4; no Biopython |
| Tool limits | Eight calls/example; 30 seconds/call; fresh interpreter; files persist within example |
| Sampling | Seed 20261029; provider defaults; ten concurrent examples |

<details>
<summary>Matched dataset and historical Luna results</summary>

Pinned dataset revision: `26f63e8e488022bed14e12af0f1e44d87a28e14f`. There are 840 easy and 790 hard prompts. Five duplicated hard variants were removed after the original Luna run. Every retained prompt, input, and answer was checked against Luna’s saved cases. The original 3,360-attempt Luna report remains intact; only the 100 duplicate-hard attempts are omitted from the combined comparison. No model responses were rescored or retried. Qwen makes fresh requests for every case, including the cases previously used in its model-selection pilot.

</details>

<details>
<summary>Exact tools JSON supplied to OpenRouter</summary>

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

The no-tools condition sends an empty tools array. No hosted shell or web tool is registered.

</details>

<details>
<summary>Python execution and macOS sandbox</summary>

The controller executes returned Python programs locally and sends stdout/stderr, exit code, and timeout status back as tool results. Networking is blocked by the operating system, not an OpenRouter parameter. The controller retains API access.

```sh
/usr/bin/sandbox-exec -f "$workdir/sandbox.sb" \
  "$runtime/bin/python" -I -B -c "$launcher"
```

The policy denies `network*` and `process-fork`, restricts content reads to runtime/system paths and the current example workdir, and restricts writes to that workdir. Credentials and benchmark answers are inaccessible. Startup checks verify these restrictions.

</details>

<details>
<summary>Request settings, scoring, costs, and traces</summary>

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

The tools condition adds the function above and uses `auto`, then `none` once the call limit is reached. Every round receives the remaining token budget. Reasoning records are preserved between rounds. The original deterministic scorer is unchanged. A separately labeled formatting diagnostic only relocates inline final-answer markers and removes outer JSON fences; it never changes the primary scores.

Costs are reconciled against generation metadata. Missing billing records remain explicit. Raw requests, SSE responses, reasoning, and tool programs/results stay untracked. Only final predictions and metrics are published.

</details>

<details>
<summary>Failed-request bookkeeping</summary>

The Qwen client and legacy trial use different exception classes. The trial records these requests as failures but omits failed-response metadata from its bookkeeping. The report reconstructs request counts, timeout flags, usage, and charges from the saved response files and billing records. No raw files, final answers, or scores are changed, and no requests are retried. The inference source remains frozen throughout the run.

</details>

<details>
<summary>Provider-reported token-budget exceptions</summary>

The controller requests at most 32,768 generated tokens per example, reducing the allowance after each tool round. Qwen's response metadata reports more than this allowance for 24 attempts, with a maximum of 64,923 tokens. These exceptions remain visible in the audit. Requests and scores are unchanged; actual provider-reported usage is not strictly matched to Luna's requested cap.

</details>
