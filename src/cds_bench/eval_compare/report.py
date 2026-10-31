"""Self-contained matched Luna/Qwen report; raw reasoning remains untracked."""

import argparse
import csv
import fcntl
import html
import json
import os
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from cds_bench.catalog import TASKS
from cds_bench.eval_luna.io import save
from cds_bench.eval_luna.report import aggregate, public_record
from cds_bench.eval_luna.score import score_result

from .run import CONDITIONS, LUNA_RAW, LUNA_RESULTS, OUTPUT, PLANNED, RAW, ROOT
from .collector import records
from .lightning_run import RAW as LIGHTNING_RAW
from .deepinfra_run import RAW as DEEPINFRA_RAW
from .lightning_supervise import latest_failure_was_rate_limit
from .tables import html_results

LABELS = ["Easy, no tools", "Hard, no tools", "Easy, Python", "Hard, Python"]
MODELS = {"luna": "Luna high", "qwen": "Qwen3.7 Flash high", "deepinfra": "Nemotron Lightning (DeepInfra)"}
BRANCH = "eval/luna-high-baseline"
REPOSITORY = "Open-Athena/cds-bench"
PR_TITLE = "CDS-bench: model pilot and full Luna/Qwen/Nemotron evaluation"
REPORT_PATH = str(OUTPUT.relative_to(ROOT))


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def formatting_diagnostic(row, case, raw):
    """Only relocate an inline marker and remove one outer JSON fence."""
    if row["outcome"] != "format":
        return False
    if row.get("trace_directory"):
        directory = Path(row["trace_directory"])
    else:
        number = row["instance_id"].rsplit("/", 1)[1]
        matches = list((raw / "traces" / row["condition"]).glob(f"*-{row['task_id']}-{number}"))
        assert len(matches) == 1
        directory = matches[0]
    text = (directory / "answer.txt").read_text()
    markers = list(re.finditer(r"(?m)^Final answer:[ \t]*", text))
    if not markers:
        return False
    final = text[markers[-1].end():].strip()
    if case["output_format"] == "json":
        match = re.fullmatch(r"```(?:json)?[ \t]*\n(.*?)\n```", final, re.DOTALL)
        if match:
            final = match[1]
    return bool(score_result(case, "Final answer:\n" + final, row["finish_reason"])["passed"])


def build(raw=RAW, output=OUTPUT, lightning_raw=LIGHTNING_RAW, deepinfra_raw=DEEPINFRA_RAW):
    output.mkdir(parents=True, exist_ok=True)
    with (raw / "report.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _build(raw, output, lightning_raw, deepinfra_raw)


def _build(raw, output, lightning_raw, deepinfra_raw):
    config = read(raw / "config.json")
    deepinfra_config = read(deepinfra_raw / "config.json")
    data = read(raw / "dataset.json")
    cases = {(r["instance_id"], v): r for v, rows in data.items() for r in rows}
    all_rows = []
    for model, source, source_rows in [
        ("luna", LUNA_RAW, read(LUNA_RESULTS)), ("qwen", raw, records(raw)),
        ("deepinfra", deepinfra_raw, records(deepinfra_raw)),
    ]:
        for original in source_rows:
            key = original["instance_id"], original["variant"]
            if key not in cases:
                continue
            row = dict(original, model=model)
            assert row["expected_answer"] == cases[key]["answer"]
            row["format_diagnostic_exact"] = formatting_diagnostic(row, cases[key], source)
            all_rows.append(row)
    assert len({(r["model"], r["instance_id"], r["condition"]) for r in all_rows}) == len(all_rows)
    condition_names = list(PLANNED)
    summaries = {m: {c: aggregate([r for r in all_rows if r["model"] == m and r["condition"] == c]) for c in condition_names} for m in MODELS}
    totals = {m: aggregate([r for r in all_rows if r["model"] == m]) for m in MODELS}
    assert totals["luna"]["attempted"] == 3260
    by_task = {t: {m: {c: aggregate([r for r in all_rows if r["task_id"] == t and r["model"] == m and r["condition"] == c]) for c in condition_names} for m in MODELS} for t in TASKS}
    families = sorted({v.get("family", "composition") for v in TASKS.values()})
    by_family = {f: {m: {c: aggregate([r for r in all_rows if TASKS[r["task_id"]].get("family", "composition") == f and r["model"] == m and r["condition"] == c]) for c in condition_names} for m in MODELS} for f in families}
    diagnostics = {m: {c: sum(r["format_diagnostic_exact"] for r in all_rows if r["model"] == m and r["condition"] == c) for c in condition_names} for m in MODELS}
    luna_lookup = {(r["instance_id"], r["condition"]): r for r in all_rows if r["model"] == "luna"}
    paired = {}
    for c in condition_names:
        pairs = [(luna_lookup[r["instance_id"], c], r) for r in all_rows if r["model"] == "qwen" and r["condition"] == c]
        paired[c] = {"completed_pairs": len(pairs), "both_correct": sum(a["passed"] and b["passed"] for a, b in pairs),
                     "luna_only": sum(a["passed"] and not b["passed"] for a, b in pairs),
                     "qwen_only": sum(b["passed"] and not a["passed"] for a, b in pairs),
                     "both_failed": sum(not a["passed"] and not b["passed"] for a, b in pairs)}
    paired_deepinfra = {}
    for c in condition_names:
        pairs = [(luna_lookup[r["instance_id"], c], r) for r in all_rows if r["model"] == "deepinfra" and r["condition"] == c]
        paired_deepinfra[c] = {"completed_pairs": len(pairs), "both_correct": sum(a["passed"] and b["passed"] for a, b in pairs),
                              "luna_only": sum(a["passed"] and not b["passed"] for a, b in pairs),
                              "deepinfra_only": sum(b["passed"] and not a["passed"] for a, b in pairs),
                              "both_failed": sum(not a["passed"] and not b["passed"] for a, b in pairs)}
    qwen_job = read(raw / "job-status.json", {"state": "prepared", "completed": 0})
    job = read(deepinfra_raw / "job-status.json", {"state": "prepared", "completed": 0})
    summary = {"generated_at": datetime.now(UTC).isoformat(), "state": job["state"], "qwen_completed": totals["qwen"]["attempted"], "qwen_planned": 3260,
               "deepinfra_completed": totals["deepinfra"]["attempted"], "deepinfra_planned": 3260, "active_model": "deepinfra",
               "deepinfra_completion_audit": "passed" if read(deepinfra_raw / "audit.json", {}).get("complete") else "pending" if job["state"] == "complete" else "not due",
               "model_states": {"luna": "complete", "qwen": qwen_job["state"], "deepinfra": job["state"]},
               "models": MODELS, "planned_per_condition": PLANNED, "totals": totals,
               "conditions": summaries, "by_task": by_task, "by_family": by_family,
               "paired_models": paired, "paired_deepinfra": paired_deepinfra, "format_diagnostic_additional_exact": diagnostics,
               "luna_original_attempts": 3360, "luna_retained_attempts": 3260,
               "luna_original_results_sha256": config["luna_comparison"]["published_results_sha256"],
               "billing": {"luna_original_run": read(LUNA_RAW / "billing-summary.json", {}), "qwen": read(raw / "billing-summary.json", {}), "deepinfra": read(deepinfra_raw / "billing-summary.json", {})},
               "preflight_billing": read(raw / "preflight/billing-summary.json", {}),
               "deepinfra_preflight_billing": read(deepinfra_raw / "preflight/billing-summary.json", {}),
               "request_settings": {"luna": read(LUNA_RAW / "config.json")["parameters_no_tools"], "qwen": config["parameters_no_tools"], "deepinfra": deepinfra_config["parameters_no_tools"] if deepinfra_config else None},
               "job": job, "qwen_job": qwen_job, "recovery": read(deepinfra_raw / "recovery-status.json", {}),
               "stopped_after_provider_rate_limits": job['state'] == 'failed' and any(word in (job.get('error') or '') for word in ['five consecutive API failures', 'rate limits', 'unavailable']) and latest_failure_was_rate_limit(deepinfra_raw)}
    summary["recovered_failed_request_metadata"] = sum(bool(r.get("request_metadata_recovered")) for r in all_rows)
    summary["token_budget"] = {
        "requested_per_example": 32768,
        "qwen_reported_over_budget_attempts": sum(r["completion_tokens"] > 32768 for r in all_rows if r["model"] == "qwen"),
        "qwen_largest_reported_usage": max((r["completion_tokens"] for r in all_rows if r["model"] == "qwen"), default=0),
        "deepinfra_reported_over_budget_attempts": sum(r["completion_tokens"] > 32768 for r in all_rows if r["model"] == "deepinfra"),
        "deepinfra_largest_reported_usage": max((r["completion_tokens"] for r in all_rows if r["model"] == "deepinfra"), default=0),
    }
    public = [dict({k: v for k, v in public_record(r).items() if r["model"] not in {"lightning", "deepinfra"} or k in r}, model=r["model"], format_diagnostic_exact=r["format_diagnostic_exact"], request_metadata_recovered=bool(r.get("request_metadata_recovered"))) for r in all_rows]
    save(output / "summary.json", summary)
    save(output / "results.json", public)
    save(output / "config.json", {"qwen": config, "luna_original": read(LUNA_RAW / "config.json"), "deepinfra": deepinfra_config})
    with (output / "by-task.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=["task_id", "family", "model", "condition", "planned", "attempted", "correct", "accuracy", "wrong", "format", "timeout", "token_cap", "error", "cost_usd", "median_seconds"], lineterminator="\n")
        writer.writeheader()
        for task in TASKS:
            for model in MODELS:
                for condition in condition_names:
                    metric = by_task[task][model][condition]
                    planned = 0 if condition.startswith("hard") and task in config["dataset"]["removed_hard_tasks"] else 10
                    writer.writerow({"task_id": task, "family": TASKS[task].get("family", "composition"), "model": model,
                                     "condition": condition, "planned": planned,
                                     **{k: metric[k] for k in metric if k in writer.fieldnames}})
    plot(output, summaries)
    render(output, summary, config, data, public)
    (output / "pr-body.md").write_text(pr_body(summary, config))
    (output / "README.md").write_text(
        f"# Luna, Qwen and Nemotron Lightning: full CDS-bench evaluation\n\nLightning / DeepInfra: {totals['deepinfra']['attempted']}/3,260 fresh attempts ({job['state']}). Luna and Qwen: 3,260 matched completed attempts each.\n\n"
        "Download [report.html](report.html) and open it in a browser. It is self-contained.\n\n"
        "[Summary](summary.json) · [Per-task metrics](by-task.csv) · [Final predictions](results.json) · [Settings](config.json)\n\n"
        "[30-task model/provider pilot](../model-pilot-20261029/README.md). Raw requests, reasoning, and Python traces remain local and untracked. The original Luna evaluation is preserved in `../luna-high-20261029/`.\n\n"
        "Failed Qwen request counts, timeout flags, usage, and charges are reconstructed from saved response metadata where the collector omitted them. Raw files and scores are unchanged; no requests are retried.\n"
    )
    print(json.dumps({"state": job["state"], "deepinfra_completed": totals["deepinfra"]["attempted"], "deepinfra_cost_usd": totals["deepinfra"]["cost_usd"]}), flush=True)
    return summary


def plot(output, summaries):
    cache = ROOT / "build/eval-comparison-cache"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache / "matplotlib"))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    fig, ax = plt.subplots(figsize=(8.8, 3.5), layout="constrained")
    for offset, (model, name), color in zip([-0.24, 0, 0.24], MODELS.items(), ["#466784", "#688775", "#786b94"]):
        values = [100 * (summaries[model][c]["accuracy"] or 0) for c in PLANNED]
        bars = ax.bar(np.arange(4) + offset, values, width=0.22, label=name, color=color)
        for bar, c in zip(bars, PLANNED):
            r = summaries[model][c]
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height()+1, f"{r['correct']}/{r['attempted']}", ha="center", fontsize=8)
    ax.set_xticks(range(4), LABELS)
    ax.set_ylim(0, 108)
    ax.set_ylabel("Correct answers (%) among finished attempts")
    ax.legend(frameon=False, loc="upper right")
    ax.grid(axis="y", color="#e1e5e8")
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(output / "overall.png", dpi=160)
    plt.close(fig)


def pr_body(summary, config):
    from .pilot import MODELS as PILOT_MODELS, OUTPUT as PILOT_OUTPUT
    from .tables import markdown_results, markdown_table

    base = f"https://github.com/{REPOSITORY}/blob/{BRANCH}/{REPORT_PATH}"
    pilot_base = f"https://github.com/{REPOSITORY}/blob/{BRANCH}/{PILOT_OUTPUT.relative_to(ROOT)}"
    q, luna, deepinfra = (summary["totals"][m] for m in ["qwen", "luna", "deepinfra"])
    full_names = {"luna": "Luna", "qwen": "Qwen Flash", "deepinfra": "Lightning DI"}
    pilot_names = {
        "luna": "Luna", "beam": "Beam 501B A23B", "deepseek": "DeepSeek Flash",
        "nemotron": "Nemotron Ultra", "qwen-flash": "Qwen Flash",
        "nemotron-lightning": "Lightning io.net", "nemotron-lightning-coreweave": "Lightning CoreWeave",
        "north-mini-code": "North Mini Code", "gpt-oss-20b": "GPT-OSS 20B",
        "gemma": "Gemma 31B", "gemma-moe": "Gemma 26B A4B", "liquid": "LFM 24B A2B",
    }
    lines = [
        "Evaluate CDS-bench without tools and with offline Python, first in a **30-task model/provider pilot**, then in a **full matched Luna/Qwen/Nemotron evaluation**. This is an evaluation-only PR; **do not merge**.",
        f"\n**Nemotron Lightning / DeepInfra: {deepinfra['attempted']:,}/3,260 fresh attempts ({summary['state'].replace('waiting-provider', 'waiting for DeepInfra')})**. Luna and Qwen each have 3,260 completed matching attempts. Each condition has ten examples per task: 840 easy and 790 hard. Pilot responses are not reused.",
        f"\n[Full evaluation report (HTML)]({base}/report.html) · [Pilot report (HTML)]({pilot_base}/report.html) · [Full per-task results]({base}/by-task.csv) · [Pilot per-task results]({pilot_base}/by-task.csv)",
        "\nThe HTML reports are self-contained; download and open them in a browser.",
        "\n**Full evaluation results**",
        "\n" + markdown_results([
            ((full_names[model], label), summary["conditions"][model][c], 32768)
            for model, name in MODELS.items() for c, label in zip(PLANNED, LABELS)
        ]),
        "\nLuna and Qwen request `high` reasoning. Lightning uses reasoning enabled without an advertised effort selector, on DeepInfra BF16 with seed omitted, with no provider fallback. All runs request 32,768 generated tokens per example and a 300-second deadline per API request. All failures remain in the denominator. Median time includes tool round trips and failures; cost covers the scored attempts. **Truncated** counts token-cap failures. Incomplete Lightning conditions include only finished attempts.",
        "\n<details>\n<summary>Full-evaluation failures, billing and token-budget exceptions</summary>\n",
        markdown_table(
            ["Model", "Condition", "Wrong", "Format", "Timeout", "Cap", "API"],
            [[full_names[model], label, *[summary["conditions"][model][c][k]
                for k in ["wrong", "format", "timeout", "token_cap", "error"]]]
             for model in MODELS for c, label in zip(PLANNED, LABELS)],
        ),
    ]
    lines += [
        f"\nRecorded charges: **${deepinfra['cost_usd']:.5f} Lightning / DeepInfra**, **${q['cost_usd']:.5f} Qwen**, **${luna['cost_usd']:.5f} retained Luna**. Billing is incomplete for {deepinfra['unreconciled_examples']} DeepInfra, {q['unreconciled_examples']} Qwen and {luna['unreconciled_examples']} retained Luna attempts. Unknown charges are not assumed to be zero.",
        f"\nQwen reports usage beyond the requested 32,768-token budget for {summary['token_budget']['qwen_reported_over_budget_attempts']} attempts, up to {summary['token_budget']['qwen_largest_reported_usage']:,} tokens. The [audit]({base}/audit.json) lists these exceptions. Actual provider-reported usage is not strictly matched to Luna’s requested cap.",
        "\n</details>",
        "\n**30-task pilot**",
        "\nOne judgment-selected instance per task, each in easy/hard form and with/without Python. Two duplicate hard variants are omitted, leaving **30 easy + 28 hard prompts and 116 attempts per complete model**. The pilot checks accuracy, cost, latency and tool compatibility. It is too small for a definitive model ranking.",
        f"\nThe [pilot HTML report]({pilot_base}/report.html) gives four-condition scores, per-task predictions, provider/reasoning settings, failure categories, timing definitions and GPT-OSS compatibility checks. Partial runs, the lower LFM token budget and tool-protocol failures are kept explicit.",
    ]
    pilot = read(PILOT_OUTPUT / "summary.json")
    if pilot:
        rows = []
        for model, name in PILOT_MODELS.items():
            settings = pilot["configurations"][model]
            condition = "All four" if settings["state"] in {"complete", "prior pilot"} else "Running" if settings["state"] == "running" else "Partial"
            rows.append(((pilot_names[model], condition), pilot["totals"][model], settings["aggregate_completion_token_budget"]))
        extension = pilot.get("coreweave_extension")
        if extension:
            rows.append((("Lightning CoreWeave extra", "Easy, no tools"), extension["totals"], 32768))
        lines += [
            f"\n<details>\n<summary>Pilot results: {len(PILOT_MODELS)} model/provider runs, with accuracy, timing and costs</summary>\n",
            markdown_results(rows),
            "\n**All four** pools easy/hard with/without Python. **Partial** means the run was stopped early and pools only completed attempts across the conditions reached. These subsets are not directly comparable to complete runs. North and Gemma 31B never reached a scored Python condition. The CoreWeave extra row retains all 353 completed attempts from the stopped expansion, separately from its original 116-attempt pilot. Ten interrupted attempts are excluded. [Inspect the additional samples](" + pilot_base + "/report.html#coreweave-extra). Full model names, provider routing and failure counts are in the pilot report.",
            "\nLFM used the approved **8,192-token** budget and exhausted it on 99/116 attempts. GPT-OSS/Bedrock’s tool scores include **24 API/protocol failures**; separate CoreWeave/Groq checks did not establish a reliable OpenRouter tool setup. Gemma, North, LFM and Nemotron Lightning enable reasoning without an effort selector; the other models request `high`. Lightning’s io.net run was stopped at the user’s request because it was slow; a separate fresh CoreWeave BF16 run uses the same prompts and settings. Both routes have no fallback and remain separate. io.net initially used concurrency ten, then continued only unissued cases at concurrency three with five-second request spacing; all completed failures are retained.",
            "\nCosts cover these scored subsets, excluding compatibility checks, removed duplicate-hard cases, interrupted requests and follow-up diagnostics. Missing charges remain explicit. The reports separate incorrect values, formatting failures, timeouts, token caps and API/protocol errors. Earlier ten-example GLM/Luna checks are a separate report appendix, not pooled here.",
            "\n</details>",
        ]
    lines += [
        "\n**Request and execution settings**",
        "\n| Setting | Value |\n|---|---|",
        "| Full models / providers | `openai/gpt-6-luna` / OpenAI; `qwen/qwen3.7-flash` / `alibaba/us-east-1`; `nvidia/nemotron-3.5-lightning` / `deepinfra/bf16`; no fallback |",
        '| Full reasoning | Luna/Qwen: `{"effort":"high","exclude":false}`. Lightning: `{"enabled":true,"exclude":false}`; no effort selector |',
        "| Output / timeout | 32,768 aggregate generated tokens/example (8,192 for LFM); **300 seconds/API request** |",
        '| Tools / web | One local Python function, `auto`; no-tools uses `tools=[]`, `tool_choice="none"`; web plugin disabled |',
        "| Executor | **`/usr/bin/sandbox-exec`**, `(deny network*)`; Python 3.12.9 + NumPy 2.5.4; **no Biopython** |",
        "| Tool limits | Eight calls/example; 30 seconds/call; fresh interpreter; files persist within example |",
        "| Sampling | Full runs use ten concurrent examples and provider-default temperature. Seed 20261029 for Luna/Qwen, omitted for Lightning. Pilot scheduling exceptions are in its report |",
        "\n<details>\n<summary>Exact Python function supplied to OpenRouter</summary>\n\n```json\n" + json.dumps(config["tools_condition"]["tools"], indent=2) + "\n```\n\nThe no-tools condition sends an empty tools array. No hosted shell or web tool is registered. Separate GPT-OSS compatibility experiments are described in the pilot report.\n\n</details>",
        "\n<details>\n<summary>Exact full-evaluation request settings</summary>\n\n```json\n" + json.dumps(summary["request_settings"], indent=2) + "\n```\n\nThe tools condition adds the function above and uses `auto`, then `none` after the call limit. Each round receives the remaining token budget. Returned reasoning records are preserved between turns. Pilot-specific routing and settings are in its report.\n\n</details>",
        "\n<details>\n<summary>Local Python execution and network isolation</summary>\n\nThe controller executes returned Python programs locally and sends stdout/stderr, exit code and timeout status back as tool results. Network isolation is an OS policy, not an OpenRouter parameter; the controller retains API access.\n\n```sh\n/usr/bin/sandbox-exec -f \"$workdir/sandbox.sb\" \\\n  \"$runtime/bin/python\" -I -B -c \"$launcher\"\n```\n\nThe policy denies `network*` and `process-fork`, restricts reads to runtime/system paths and the current example workdir, and restricts writes to that workdir. Benchmark answers and credentials are inaccessible. Startup checks verify these restrictions.\n\n</details>",
        "\n<details>\n<summary>Dataset matching, scoring and saved artifacts</summary>\n",
        f"Full-evaluation dataset revision: `{config['dataset']['revision']}`. Five duplicated hard variants were removed after the original Luna run. Its original 3,360-attempt artifacts remain intact; the combined comparison excludes only those 100 historical attempts. Retained prompts and reference answers match byte for byte. The pilot’s 30 task types contain two of those duplicated hard variants, so its comparison retains 116 attempts/model.",
        "\nThe deterministic scorer and benchmark definitions are unchanged. No scored inference requests are retried. A separate formatting diagnostic accepts an inline final-answer marker and removes one outer JSON fence; it never changes primary scores. GPT-OSS exploratory compatibility checks are separate from scored pilot attempts.",
        "\nFailed Qwen request metadata omitted by the legacy trial is reconstructed from saved response and billing files for reporting. Raw traces, final answers and scores are unchanged. Public artifacts include prompts, final predictions, settings and metrics. Raw API requests, reasoning and tool programs/results remain local and untracked.",
        "\n</details>",
    ]
    return "\n".join(lines) + "\n"

def render(output, summary, config, data, rows):
    import base64
    esc = html.escape
    parts = ["""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CDS-bench: Luna, Qwen and Nemotron full evaluation</title><style>
body{font:15px/1.5 system-ui,sans-serif;color:#25313c;margin:0;background:white}main{max-width:1320px;margin:auto;padding:24px}h1{font-size:26px}h2{font-size:20px}a{color:#205d89}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:8px;border-bottom:1px solid #dce2e7;text-align:left;vertical-align:top}th{background:#f4f6f8}small,.muted{color:#64727e}small{display:block}.scroll{overflow-x:auto}details{border-top:1px solid #dce2e7;padding:10px 0}summary,.task-row{cursor:pointer}.task-row:hover{background:#f4f7f9}.task-detail{display:none}.task-detail.open{display:table-row}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:420px;overflow:auto;background:#f5f7f9;padding:12px;font:12px/1.5 ui-monospace,monospace;border:1px solid #dce2e7}input,select{font:inherit;padding:6px;margin:10px 0}img{max-width:100%;height:auto}[hidden]{display:none!important}nav{margin:12px 0 20px}.good{background:#e5efe8}.bad{background:#f3e8e9}</style><main><h1>CDS-bench: Luna, Qwen and Nemotron Lightning</h1><nav><a href="#overview">Overview</a> · <a href="#families">By family</a> · <a href="#tasks">By task</a> · <a href="#settings">Settings and data</a></nav>"""]
    q, deepinfra = (summary["totals"][m] for m in ["qwen", "deepinfra"])
    parts.append(f"<p>Full evaluation: <b>Lightning / DeepInfra {deepinfra['attempted']}/3,260 ({esc(summary['state'].replace('waiting-provider', 'waiting for DeepInfra'))})</b>. Luna and Qwen each have 3,260 matching completed attempts. Each condition includes ten examples per task: 84 easy task types and 79 hard task types. All retained prompts and reference answers match byte for byte. Pilot responses are excluded.</p>")
    if summary['state'] == 'complete':
        parts.append('<p>DeepInfra completion audit: <b>'+esc(summary['deepinfra_completion_audit'])+'</b>.</p>')
    if summary['state'] == 'failed':
        cause = 'DeepInfra upstream rate limits (HTTP 429).' if summary['stopped_after_provider_rate_limits'] else 'The evaluator stopped after an operational failure.'
        parts.append('<p role="status"><b>Requests stopped.</b> '+cause+' Completed attempts, including failures, are retained.</p>')
    if summary['state'] == 'waiting-provider':
        next_check = summary.get('recovery', {}).get('next_check_at') or 'pending'
        parts.append('<p role="status"><b>Waiting for DeepInfra.</b> Upstream shared-pool rate limit (HTTP 429). Next availability check: <time id="next-provider-check" datetime="'+esc(next_check)+'">'+esc(next_check)+'</time>. No scored request is retried.</p>')
    if summary.get('recovery'):
        parts.append('<p class="muted">Rate-limit recovery resumes only unissued examples after separate availability checks. Ten-way parallelism and model settings are unchanged; earlier failed attempts remain counted.</p>')
    parts.append(f'<p class="muted">Updated <time id="last-update" datetime="{esc(summary["generated_at"])}">{esc(summary["generated_at"])}</time>. <span id="update-status">Saved snapshot.</span> <button id="refresh-now" type="button">Refresh now</button></p>')
    parts.append('<h2 id="overview">Overview</h2>')
    parts.append(html_results([
        (f"{name}: {label}", summary["conditions"][model][c], 32768)
        for model, name in MODELS.items() for c, label in zip(PLANNED, LABELS)
    ]))
    parts.append('<p class="muted">All failures remain in the denominator. Original Luna artifacts are preserved separately. The <a href="../model-pilot-20261029/report.html">30-task model/provider pilot</a> is a separate report; its responses are not reused here.</p>')
    parts.append(f"<p class=muted>Billing is incomplete for {deepinfra['unreconciled_examples']} DeepInfra, {q['unreconciled_examples']} Qwen and {summary['totals']['luna']['unreconciled_examples']} retained Luna attempts. Charges are provisional where only streaming usage is available; unknown charges are not assumed to be zero.</p>")
    image = base64.b64encode((output / "overall.png").read_bytes()).decode()
    parts.append(f'<img alt="Accuracy by model and condition" src="data:image/png;base64,{image}">')
    parts.append('<details><summary>Failure categories, token usage, and costs</summary><div class="scroll"><table><tr><th>Model / condition</th><th>Incorrect</th><th>Format</th><th>Timeout</th><th>Token cap</th><th>API error</th><th>Used Python</th><th>Reported generated tokens</th></tr>')
    for m, name in MODELS.items():
        for c, label in zip(PLANNED, LABELS):
            r = summary["conditions"][m][c]
            parts.append(f'<tr><td>{name}<small>{label}</small></td>'+''.join(f'<td>{r[k]}</td>' for k in ['wrong','format','timeout','token_cap','error','examples_using_python','completion_tokens'])+'</tr>')
    budget = summary["token_budget"]
    parts.append('</table></div><p>Timeouts are the 300-second API deadline. Token caps exhaust the aggregate generated-token budget. Provider/connection failures remain separate. Timed-out responses may omit usage; reconciled generation charges are retained when available.</p>')
    parts.append(f"<p>Failed-request bookkeeping is reconstructed from saved response metadata for {summary['recovered_failed_request_metadata']} attempts. Raw traces, answers, and scores are unchanged.</p>")
    parts.append(f"<p>The controller requests at most 32,768 generated tokens per example. Qwen reports usage above that allowance for {budget['qwen_reported_over_budget_attempts']} attempts, with a maximum of {budget['qwen_largest_reported_usage']:,} tokens. The audit lists these exceptions; actual provider-reported usage is not strictly matched to Luna's requested cap.</p></details>")
    parts.append('<details><summary>Paired comparisons with Luna on completed cases</summary><table><tr><th>Model / condition</th><th>Pairs</th><th>Both correct</th><th>Luna only</th><th>Other model only</th><th>Both failed</th></tr>')
    for model, metrics, only in [('qwen', summary['paired_models'], 'qwen_only'), ('deepinfra', summary['paired_deepinfra'], 'deepinfra_only')]:
        for c, label in zip(PLANNED, LABELS):
            r = metrics[c]
            parts.append(f'<tr><td>{esc(MODELS[model])}<small>{label}</small></td>'+''.join(f'<td>{r[k]}</td>' for k in ['completed_pairs','both_correct','luna_only',only,'both_failed'])+'</tr>')
    parts.append('</table></details><details><summary>Formatting diagnostic: original scores unchanged</summary><p>This only accepts an inline <code>Final answer:</code> marker and removes one outer Markdown JSON fence. It applies the same exact-value comparison afterward. It does not repair the answer or recover missing markers.</p><table><tr><th>Model / condition</th><th>Original correct</th><th>Additional exact values</th><th>Diagnostic total</th></tr>')
    for m, name in MODELS.items():
        for c, label in zip(PLANNED, LABELS):
            r = summary["conditions"][m][c]; extra = summary["format_diagnostic_additional_exact"][m][c]
            parts.append(f'<tr><td>{name}<small>{label}</small></td><td>{r["correct"]}/{r["attempted"]}</td><td>{extra}</td><td>{r["correct"]+extra}/{r["attempted"]}</td></tr>')
    parts.append('</table></details><h2 id="families">By family</h2><div class="scroll"><table><tr><th>Family / model</th>'+''.join(f'<th>{label}</th>' for label in LABELS)+'</tr>')
    for family, metrics in summary["by_family"].items():
        for m, name in MODELS.items():
            parts.append(f'<tr><td>{esc(family)}<small>{name}</small></td>'+''.join(f'<td>{metrics[m][c]["correct"]}/{metrics[m][c]["attempted"]}</td>' for c in PLANNED)+'</tr>')
    parts.append('</table></div><h2 id="tasks">By task</h2><p>Expand a row to inspect all ten instances, actual prompts, expected answers, and each model’s final prediction. Counts are correct / finished; — means that hard variant was removed.</p><input id="filter" placeholder="Filter task names or families"><div class="scroll"><table><thead><tr><th rowspan="2">Task</th>'+''.join(f'<th colspan="{len(MODELS)}">{label}</th>' for label in LABELS)+'</tr><tr>'+''.join('<th>Luna</th><th>Qwen</th><th>Lightning DI</th>' for _ in LABELS)+'</tr></thead><tbody>')
    for task, definition in TASKS.items():
        title = definition["title"]
        parts.append(f'<tr class="task-row" id="task-{task}" data-task="{task}" data-search="{esc((task+" "+title+" "+definition.get("family", "composition")).lower())}" tabindex="0" aria-expanded="false"><td><a href="#task-{task}">{esc(title)}</a><small>{task}</small></td>')
        for c in PLANNED:
            for m in MODELS:
                r = summary["by_task"][task][m][c]
                text = '—' if c.startswith('hard') and task in config['dataset']['removed_hard_tasks'] else f'{r["correct"]}/{r["attempted"]}'
                parts.append(f'<td>{text}</td>')
        parts.append(f'</tr><tr class="task-detail"><td colspan="{1+len(MODELS)*len(LABELS)}"></td></tr>')
    parts.append('</tbody></table></div><h2 id="settings">Settings and data</h2><p>Luna and Qwen request <code>high</code> reasoning. Lightning uses <code>nvidia/nemotron-3.5-lightning</code> on <code>deepinfra/bf16</code>, with reasoning enabled and no effort selector. Seed is omitted, matching its pilot. Qwen uses <code>alibaba/us-east-1</code>; Luna used the standard OpenAI endpoint. No provider fallback. The limit is 32,768 generated tokens across all turns, 300 seconds per API request, and eight Python calls per example.</p><p>Python 3.12.9 + NumPy 2.5.4; no Biopython. Local <code>/usr/bin/sandbox-exec</code> denies networking and process forks and restricts filesystem access. Network denial is not an OpenRouter parameter. Web plugins are disabled and no web tool is registered. Raw requests, reasoning, and tool traces remain untracked.</p>')
    parts.append('<details><summary>Exact Python tool definition</summary><pre>'+esc(json.dumps(config['tools_condition']['tools'],indent=2))+'</pre></details>')
    parts.append('<details><summary>Dataset version, exact request settings, and billing metadata</summary><p>The current dataset removes five duplicated hard variants. The 100 corresponding historical Luna attempts are excluded only from this comparison. Its original 3,360-attempt report is preserved. Every retained prompt and answer was verified against the old traces.</p><pre>'+esc(json.dumps({'request_settings':summary['request_settings'],'dataset':config['dataset'],'billing':summary['billing'],'qwen_preflight_billing':summary['preflight_billing'],'deepinfra_preflight_billing':summary['deepinfra_preflight_billing']},indent=2))+'</pre></details>')
    parts.append('<p><a href="summary.json">Summary</a> · <a href="by-task.csv">Per-task CSV</a> · <a href="results.json">Predictions</a> · <a href="config.json">Configurations</a></p>')
    payload = {'snapshot':{k:summary[k] for k in ['generated_at','state','qwen_completed','deepinfra_completed']},
               'models':MODELS,'conditions':list(PLANNED),'labels':LABELS,'records':rows,
               'cases':{v:rs for v,rs in data.items()}}
    parts.append('<script id="data" type="application/json">'+json.dumps(payload,ensure_ascii=False).replace('<','\\u003c')+'</script>')
    parts.append("""<script>
const d=JSON.parse(document.getElementById('data').textContent),caseMap=new Map(),recordMap=new Map();for(const [v,rows]of Object.entries(d.cases))for(const r of rows)caseMap.set(r.instance_id+'|'+v,r);for(const r of d.records)recordMap.set(r.model+'|'+r.condition+'|'+r.instance_id,r);function node(tag,text){const x=document.createElement(tag);if(text!==undefined)x.textContent=text;return x}function details(title,text){const x=node('details');x.append(node('summary',title),node('pre',text));return x}
function expand(row,force){const child=row.nextElementSibling,open=force===undefined?!child.classList.contains('open'):force;child.classList.toggle('open',open);row.setAttribute('aria-expanded',open);if(!open||child.dataset.loaded)return;child.dataset.loaded='1';const cell=child.firstElementChild,select=node('select'),view=node('div'),ids=d.cases.easy.filter(x=>x.task_id===row.dataset.task).map(x=>x.instance_id);for(const id of ids){const o=node('option',id);o.value=id;select.append(o)}const label=node('label','Instance ');label.append(select);cell.append(label,view);function show(){view.replaceChildren();const id=select.value;for(const variant of ['easy','hard']){const c=caseMap.get(id+'|'+variant);if(!c)continue;view.append(details(variant+' prompt',c.prompt));view.append(details(variant+' expected answer',c.answer));for(const tools of [false,true]){const condition=variant+(tools?'-tools':'-no-tools');for(const [m,name]of Object.entries(d.models)){const r=recordMap.get(m+'|'+condition+'|'+id);let text='Not completed';if(r)text=(r.final_answer??r.error??'No final answer')+'\\n\\n'+r.elapsed_seconds.toFixed(1)+'s; '+r.tool_calls+' Python calls; $'+r.cost_usd.toFixed(6);view.append(details(name+' · '+condition+' · '+(r?r.outcome:'pending'),text))}}}}select.addEventListener('change',show);show()}
for(const row of document.querySelectorAll('.task-row')){row.addEventListener('click',e=>expand(row,e.target.closest('a')?true:undefined));row.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();expand(row)}})}document.getElementById('filter').addEventListener('input',e=>{for(const row of document.querySelectorAll('.task-row')){row.hidden=!row.dataset.search.includes(e.target.value.toLowerCase());row.nextElementSibling.hidden=row.hidden}});function anchor(){const row=document.getElementById(decodeURIComponent(location.hash.slice(1)));if(row?.classList.contains('task-row'))expand(row,true)}addEventListener('hashchange',anchor);anchor();
const viewKey='cds-report-view:'+location.pathname;
function refreshReport(){
  const view={scroll:scrollY,filter:document.getElementById('filter').value,
    sections:[...document.querySelectorAll('main > details')].map(x=>x.open),
    tasks:[...document.querySelectorAll('.task-row[aria-expanded="true"]')].map(row=>({
      id:row.id,instance:row.nextElementSibling.querySelector('select')?.value,
      sections:[...row.nextElementSibling.querySelectorAll('details')].map(x=>x.open)}))};
  try{sessionStorage.setItem(viewKey,JSON.stringify(view))}catch{}
  const url=new URL(location.href);url.searchParams.set('updated',Date.now());location.replace(url);
}
try{
  const saved=sessionStorage.getItem(viewKey);sessionStorage.removeItem(viewKey);
  if(saved){const view=JSON.parse(saved),filter=document.getElementById('filter');
    filter.value=view.filter||'';filter.dispatchEvent(new Event('input'));
    for(const task of view.tasks||[]){const row=document.getElementById(task.id);if(!row)continue;
      expand(row,true);const select=row.nextElementSibling.querySelector('select');
      if(select&&task.instance){select.value=task.instance;select.dispatchEvent(new Event('change'))}
      [...row.nextElementSibling.querySelectorAll('details')].forEach((x,i)=>x.open=!!task.sections[i]);}
    [...document.querySelectorAll('main > details')].forEach((x,i)=>x.open=!!view.sections[i]);
    requestAnimationFrame(()=>scrollTo(0,view.scroll||0));}
}catch{}
document.getElementById('last-update').textContent=new Date(d.snapshot.generated_at).toLocaleString();
const nextCheck=document.getElementById('next-provider-check');if(nextCheck&&nextCheck.dateTime!=='pending')nextCheck.textContent=new Date(nextCheck.dateTime).toLocaleString();
document.getElementById('refresh-now').addEventListener('click',refreshReport);
if(/^https?:$/.test(location.protocol)){
  const status=document.getElementById('update-status');status.textContent='Checks for updates every 30 seconds.';
  let checking=false;
  async function checkUpdates(){
    if(checking||document.hidden||document.activeElement?.matches('input,select,textarea'))return;
    checking=true;
    try{const reply=await fetch('summary.json?updated='+Date.now(),{cache:'no-store'});
      if(!reply.ok)throw Error('Report unavailable');const latest=await reply.json();
      if(latest.generated_at&&latest.generated_at!==d.snapshot.generated_at)refreshReport();
      else status.textContent='Checks for updates every 30 seconds.';
    }catch{status.textContent='Update check failed; showing the timestamped snapshot.'}
    finally{checking=false}
  }
  setInterval(checkUpdates,30000);addEventListener('focus',checkUpdates);
}
</script></main></html>""")
    temporary = output / "report.html.tmp"
    temporary.write_text('\n'.join(parts))
    temporary.replace(output / "report.html")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=RAW)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    build(args.raw_root.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
