"""Self-contained full model comparison; raw reasoning remains untracked."""

import argparse
import csv
import fcntl
import hashlib
import html
import json
import os
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from cds_bench.catalog import TASKS
from cds_bench.eval_luna.io import save
from cds_bench.eval_luna.report import aggregate as standard_aggregate, public_record
from cds_bench.eval_luna.score import score_result

from .run import CONDITIONS, LUNA_RAW, LUNA_RESULTS, OUTPUT, PLANNED, RAW, ROOT
from .collector import records
from .lightning_run import RAW as LIGHTNING_RAW
from .deepinfra_run import RAW as DEEPINFRA_RAW
from .lightning_supervise import latest_failure_was_rate_limit
from .tables import HEADERS, cells, html_grouped_table, models_by_task_accuracy
from . import radar, scatter, family_analysis, composition_example
from . import snowball_full, snowball_tools, snowball_one_shot
from . import timeout_results
from . import carbon_pilot

LABELS = ["Easy, no tools", "Hard, no tools", "Easy, Python", "Hard, Python"]
MODELS = {"luna": "GPT-6 Luna (high)", "deepinfra": "Nemotron 3.5 Lightning",
          "qwen": "Qwen 3.7 Flash (high)", "snowball-v01": "Snowball v0.1"}
MODEL_COLORS = {'luna':'#466784', 'qwen':'#688775', 'deepinfra':'#786b94', 'snowball-v01':'#b47f5e'}
BRANCH = "eval/luna-high-baseline"
REPOSITORY = "Open-Athena/cds-bench"
PR_TITLE = "Baseline evaluation and model pilot results"
REPORT_PATH = str(OUTPUT.relative_to(ROOT))


def aggregate(rows, model=None):
    result = standard_aggregate(rows)
    if model == 'snowball-v01':
        result['cost_usd'] = None
        result['reasoning_tokens'] = None
    return result


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
    global MODELS
    config = read(raw / "config.json")
    deepinfra_config = read(deepinfra_raw / "config.json")
    data = read(raw / "dataset.json")
    cases = {(r["instance_id"], v): r for v, rows in data.items() for r in rows}
    all_rows = []
    for model, source, source_rows in [
        ("luna", LUNA_RAW, read(LUNA_RESULTS)), ("qwen", raw, records(raw)),
        ("deepinfra", deepinfra_raw, records(deepinfra_raw)),
        ("snowball-v01", snowball_full.RAW, snowball_full.records()),
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
    recovery = timeout_results.load()
    all_rows = timeout_results.apply(all_rows, recovery)
    for row in all_rows:
        if row.get('retry_attempts'):
            row['format_diagnostic_exact'] = formatting_diagnostic(
                row, cases[row['instance_id'], row['variant']], raw)
    MODELS, model_means = models_by_task_accuracy(MODELS, all_rows)
    condition_names = list(PLANNED)
    summaries = {m: {c: aggregate([r for r in all_rows if r["model"] == m and r["condition"] == c], m) for c in condition_names} for m in MODELS}
    totals = {m: aggregate([r for r in all_rows if r["model"] == m], m) for m in MODELS}
    assert totals["luna"]["attempted"] == 3260
    by_task = {t: {m: {c: aggregate([r for r in all_rows if r["task_id"] == t and r["model"] == m and r["condition"] == c], m) for c in condition_names} for m in MODELS} for t in TASKS}
    families = sorted({v.get("family", "composition") for v in TASKS.values()})
    by_family = {f: {m: {c: aggregate([r for r in all_rows if TASKS[r["task_id"]].get("family", "composition") == f and r["model"] == m and r["condition"] == c], m) for c in condition_names} for m in MODELS} for f in families}
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
               "models": MODELS, "model_mean_task_accuracy":model_means,
               "model_order_metric":"Descending pooled mean task accuracy, weighting each available task equally; the same order is used in every condition.",
               "planned_per_condition": PLANNED, "totals": totals,
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
    snowball_config = snowball_full.public_config()
    snowball_job = read(snowball_full.RAW / 'job-status.json', {'state':'prepared','completed':0})
    snowball_job = dict(snowball_job)
    if snowball_job.get('error'):
        snowball_job['error'] = 'Operational failure; detailed diagnostics remain in the private execution log.'
    snowball_audit = read(snowball_full.RAW / 'audit.json', {})
    summary.update(snowball_completed=totals['snowball-v01']['attempted'], snowball_planned=3260,
                   snowball_completion_audit='passed' if snowball_audit.get('complete') else 'pending',
                   active_model='snowball-v01', snowball_job=snowball_job, deepinfra_job=job,
                   job=snowball_job, state='auditing' if snowball_job['state']=='complete' and not snowball_audit.get('complete') else snowball_job['state'])
    summary['model_states']['snowball-v01'] = summary['state']
    summary['deepinfra_recovery'] = summary['recovery']
    summary['recovery'] = {}
    summary['stopped_after_provider_rate_limits'] = False
    summary['request_settings']['snowball-v01'] = snowball_config['parameters_no_tools'] if snowball_config else None
    summary['snowball_configuration'] = snowball_config
    summary['paired_snowball'] = {}
    for condition in condition_names:
        pairs = [(luna_lookup[r['instance_id'],condition],r) for r in all_rows if r['model']=='snowball-v01' and r['condition']==condition]
        summary['paired_snowball'][condition] = {
            'completed_pairs':len(pairs), 'both_correct':sum(a['passed'] and b['passed'] for a,b in pairs),
            'luna_only':sum(a['passed'] and not b['passed'] for a,b in pairs),
            'snowball_only':sum(b['passed'] and not a['passed'] for a,b in pairs),
            'both_failed':sum(not a['passed'] and not b['passed'] for a,b in pairs)}
    summary["recovered_failed_request_metadata"] = sum(bool(r.get("request_metadata_recovered")) for r in all_rows)
    summary['timeout_recovery'] = timeout_results.export(output, recovery)
    summary["token_budget"] = {
        "requested_per_attempt": 32768,
        "qwen_reported_over_budget_attempts": sum(r["completion_tokens"] > 32768 for r in all_rows if r["model"] == "qwen"),
        "qwen_largest_reported_usage": max((r["completion_tokens"] for r in all_rows if r["model"] == "qwen"), default=0),
        "deepinfra_reported_over_budget_attempts": sum(r["completion_tokens"] > 32768 for r in all_rows if r["model"] == "deepinfra"),
        "deepinfra_largest_reported_usage": max((r["completion_tokens"] for r in all_rows if r["model"] == "deepinfra"), default=0),
    }
    public = []
    for row in all_rows:
        exported = dict({k:v for k,v in public_record(row).items() if row['model'] not in {'lightning','deepinfra','snowball-v01'} or k in row},
                        model=row['model'], format_diagnostic_exact=row['format_diagnostic_exact'],
                        request_metadata_recovered=bool(row.get('request_metadata_recovered')),
                        **{k: row[k] for k in timeout_results.PUBLIC_FIELDS if k in row})
        public.append(snowball_full.public_row(exported) if row['model']=='snowball-v01' else exported)
    summary['snowball_tool_use'] = snowball_tools.build(output, all_rows, MODELS)
    summary['snowball_one_shot_tools'] = snowball_one_shot.export(output, cases)
    save(output / "results.json", public)
    summary['easy_family_comparison'] = family_analysis.export(output, public, cases)
    summary['composition_example'] = composition_example.export(output, cases, summary)
    save(output / "summary.json", summary)
    save(output / "config.json", {"qwen": config, "luna_original": read(LUNA_RAW / "config.json"), "deepinfra": deepinfra_config, 'snowball-v01':snowball_config,
                                 'timeout_recovery': summary['timeout_recovery']})
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
    plot(output, summaries, summary['snowball_one_shot_tools'])
    radar_views = radar.plot(output, summary, MODELS)
    scatter.plot(output, public, radar_views['all'])
    render(output, summary, config, data, public)
    (output / "pr-body.md").write_text(pr_body(summary, config))
    (output / "README.md").write_text(
        f"# Full CDS-bench model evaluation\n\nSnowball v0.1: {totals['snowball-v01']['attempted']}/3,260 fresh attempts ({summary['state']}). GPT-6 Luna, Nemotron 3.5 Lightning and Qwen 3.7 Flash each have 3,260 matched completed attempts.\n\n"
        "Download [report.html](report.html) and open it in a browser. It is self-contained.\n\n"
        "[Summary](summary.json) · [Per-task metrics](by-task.csv) · [Final predictions](results.json) · [Settings](config.json)\n\n"
        f"{'[Snowball completion audit](snowball-v01-full-audit.json)' if summary['snowball_completion_audit']=='passed' else 'Snowball completion audit pending.'}\n\n"
        "Snowball v0.1 is a 67B MoE model with 2B active parameters per token. The full run uses 32,768 aggregate generated tokens, a 1,800-second API request deadline, temperature 0.7 and concurrency 60. Its native thinking/tool transport and private access configuration match the validated pilot.\n\n"
        "Checkpoint: [open-athena/Marin-Snowball-67B-A2B-v0.1](https://huggingface.co/open-athena/Marin-Snowball-67B-A2B-v0.1/tree/adc0078a19a4383bc998fcdb43867b3360baf5f3), revision `adc0078a19a4383bc998fcdb43867b3360baf5f3`.\n\n"
        "Accuracy by condition: [PNG](overall.png) · [SVG](overall.svg).\n\n"
        + (snowball_one_shot.description(summary['snowball_one_shot_tools']) + "\n\n"
           if summary['snowball_one_shot_tools'] else "") +
        "[Pooled task radar](task-radar.svg) · [PNG](task-radar.png) · [Task order and scores](task-radar.json). The report selector also shows each of the four evaluation conditions. Task codes and group colors stay fixed across views, with links to the full-name/ID key and existing details.\n\n"
        "Nemotron versus Snowball, Easy conditions: [PNG](nemotron-snowball-easy.png) · [SVG](nemotron-snowball-easy.svg). The two panels share a legend and axes. Each point compares the same completed examples for one task; all failures count. The interactive report includes all five condition views and links points to task details.\n\n"
        "[30-task model/provider pilot](../model-pilot-20261029/README.md). Sanitized requests, reasoning and Python traces are in the [public HF trace archive](https://huggingface.co/datasets/eczech/cds-bench-pr-2-traces); originals remain untracked locally. The original Luna evaluation is preserved in `../luna-high-20261029/`.\n\n"
        "Failed Qwen request counts, timeout flags, usage, and charges are reconstructed from saved response metadata where the collector omitted them. Original traces are unchanged. [Timeout recovery](timeout-recovery.json) selects the first non-timeout result for each of the 217 retried cases and includes every attempt in costs and elapsed time.\n"
    )
    print(json.dumps({'state':summary['state'], 'snowball_completed':totals['snowball-v01']['attempted'], 'planned':3260}), flush=True)
    return summary


def plot(output, summaries, one_shot=None, carbon=None):
    cache = ROOT / "build/eval-comparison-cache"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache / "matplotlib"))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    import numpy as np
    fig, ax = plt.subplots(figsize=(15 if carbon else 12, 5.5 if carbon and one_shot else 5.2 if carbon else 5.0 if one_shot else 4.2), layout="constrained")
    for index, condition in enumerate(PLANNED):
        entries = [(summaries[model][condition], MODEL_COLORS[model], None)
                   for model in MODELS]
        if one_shot and condition in one_shot['conditions']:
            follow_up = one_shot['conditions'][condition]
            entries.append((dict(follow_up, attempted=follow_up['n']),
                            MODEL_COLORS['snowball-v01'], '///'))
        if carbon:
            entries.append((carbon['conditions'][condition], '#a5a19b', '..'))
        offsets = (np.arange(len(entries)) - (len(entries)-1)/2) * (0.14 if carbon else 0.17)
        for offset, (r, color, hatch) in zip(offsets, entries, strict=True):
            bar = ax.bar(index + offset, 100 * (r['accuracy'] or 0), width=0.12 if carbon else 0.15,
                         color=color, hatch=hatch,
                         edgecolor='#474440' if hatch == '..' else '#684732' if hatch else color,
                         linewidth=0.5 if hatch else 0)[0]
            percent = f"{100 * r['accuracy']:.1f}%" if r['attempted'] else "n/a"
            ax.annotate(
                f"{percent}\n{r['correct']}/{r['attempted']}",
                (bar.get_x() + bar.get_width()/2, bar.get_height()),
                xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                fontsize=8, linespacing=1.15,
            )
    ax.set_xticks(range(4), LABELS)
    ax.set_ylim(0, 108)
    ax.set_ylabel("Correct answers (%) among finished attempts")
    handles = [Patch(facecolor=MODEL_COLORS[model], label=name) for model, name in MODELS.items()]
    if one_shot:
        handles.append(Patch(facecolor=MODEL_COLORS['snowball-v01'], edgecolor='#684732',
                             linewidth=0.5, hatch='///', label=r'Snowball v0.1$^{\ddagger}$ (1-shot tools)'))
    if carbon:
        handles.append(Patch(facecolor='#a5a19b', edgecolor='#474440', hatch='..',
                             label=r'Carbon-X$^{\dagger}$ (error compensation)'))
    footnotes = []
    if carbon:
        footnotes.append(r'$^{\dagger}$ Carbon-X: custom answer parsing compensates for instruction-following errors.')
    if one_shot:
        footnotes.append(r'$^{\ddagger}$ Snowball v0.1 (1-shot tools): a demonstration and required Python execution compensate for low tool use.')
    if footnotes:
        fig.supxlabel('\n'.join(footnotes), x=0.04, ha='left', fontsize=9.5, linespacing=1.5)
    if one_shot or carbon:
        # Matplotlib fills legend columns; reorder to read left to right by row.
        handles = [handles[i] for column in range(3) for i in [column, column + 3]
                   if i < len(handles)]
    fig.legend(handles=handles, frameon=False, loc="outside upper center",
               ncol=3 if one_shot or carbon else 4, columnspacing=1.5, handlelength=1.8)
    ax.grid(axis="y", color="#e1e5e8")
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(output / "overall.png", dpi=160)
    with matplotlib.rc_context({"svg.fonttype": "none", "svg.hashsalt": "cds-bench-overview"}):
        fig.savefig(output / "overall.svg", metadata={"Date": None})
    svg = output / 'overall.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)


def pr_body(summary, config):
    """Fill the reviewed PR prose with the audited evaluation results."""
    from .tables import markdown_results, markdown_table

    recovery = summary.get('timeout_recovery')
    if not recovery or recovery['pending_timeouts']:
        raise RuntimeError('Complete and audit timeout recovery before publishing the PR')
    for model in ['luna', 'deepinfra', 'qwen']:
        assert summary['totals'][model]['timeout'] == 0
    full_rows = [((name, label), summary['conditions'][model][condition], 32768)
                 for model, name in MODELS.items()
                 for condition, label in zip(PLANNED, LABELS)]
    results_table = markdown_results(full_rows, include_timeout=False)
    failures_table = markdown_table(
        ['Model', 'Condition', 'Wrong answer', 'Format', 'Request timeout', 'Token cap', 'API/protocol'],
        [[name, label, *[summary['conditions'][model][condition][key]
                        for key in ['wrong', 'format', 'timeout', 'token_cap', 'error']]]
         for model, name in MODELS.items() for condition, label in zip(PLANNED, LABELS)])
    uptake = summary['snowball_tool_use']['tool_invocation']['deepinfra']
    snowball_uptake = summary['snowball_tool_use']['tool_invocation']['snowball-v01']
    base = f'https://github.com/{REPOSITORY}/blob/{BRANCH}/{REPORT_PATH}'
    cost_names = {'luna': 'Luna', 'deepinfra': 'Nemotron', 'qwen': 'Qwen'}
    costs = ', '.join(f"${summary['totals'][m]['cost_usd']:.5f} for {name}"
                      for m, name in cost_names.items())
    incomplete = ', '.join(f"{summary['totals'][m]['unreconciled_examples']} {name} cases"
                           for m, name in cost_names.items())
    def pooled_accuracy(model, conditions):
        rows = [summary['conditions'][model][condition] for condition in conditions]
        return sum(row['correct'] for row in rows) / sum(row['attempted'] for row in rows)

    open_models = ['deepinfra', 'qwen', 'snowball-v01']
    no_tools = [pooled_accuracy(model, ['easy-no-tools', 'hard-no-tools'])
                for model in open_models]
    python = {model: pooled_accuracy(model, ['easy-tools', 'hard-tools'])
              for model in open_models}
    interpretation = (
        'A frontier model like GPT-6 Luna approaches saturation on easy '
        f"questions with Python ({summary['conditions']['luna']['easy-tools']['accuracy']:.1%}) "
        f"and scores {summary['totals']['luna']['accuracy']:.1%} overall. "
        'The three open-weight general-purpose LLMs, including [Snowball v0.1](https://openathena.ai/blog/post-training-in-the-open/), perform similarly without tools '
        f'({min(no_tools):.1%}–{max(no_tools):.1%} across easy and hard questions), '
        'but differ sharply when Python is available: '
        f"{python['deepinfra']:.1%} for Nemotron, {python['qwen']:.1%} for Qwen and "
        f"{python['snowball-v01']:.1%} for Snowball.")
    if carbon := summary.get('carbon_x'):
        interpretation += (
            f" Carbon-X reaches only {carbon['totals']['accuracy']:.1%}, despite custom answer "
            'parsing that compensates for its instruction-following errors.')
    pilot = read(ROOT / 'evaluations/model-pilot-20261029/summary.json')
    short_names = {
        'luna': MODELS['luna'], 'deepseek': 'DeepSeek Flash', 'beam': 'Beam 501B A23B',
        'nemotron': 'Nemotron Ultra', 'qwen-flash': MODELS['qwen'],
        'nemotron-lightning': 'Nemotron 3.5 Lightning',
        'nemotron-lightning-coreweave': 'Nemotron 3.5 Lightning',
        'north-mini-code': 'North Mini Code', 'gpt-oss-20b': 'GPT-OSS 20B',
        'snowball-v01': 'Snowball v0.1', 'snowball': 'Snowball RC (2026.09.21)',
        'gemma': 'Gemma 31B', 'gemma-moe': 'Gemma 26B A4B', 'liquid': 'LFM 24B A2B',
    }
    providers = {
        'openai': 'OpenAI', 'morph/fp8': 'Morph/FP8', 'nebius/fp4': 'Nebius/FP4',
        'nvidia': 'NVIDIA', 'coreweave/bf16': 'CoreWeave/BF16',
        'alibaba/us-east-1': 'Alibaba/US', 'cohere': 'Cohere',
        'amazon-bedrock': 'Amazon Bedrock', 'io-net': 'io.net',
        'Marin internal API': 'Marin (internal)', 'novita/bf16': 'Novita/BF16',
        'liquid/fp8': 'Liquid/FP8', 'nextbit/bf16': 'NextBit/BF16',
    }
    pilot_rows = []
    for model, name in pilot['models'].items():
        settings = pilot['configurations'][model]
        partial = settings['state'] not in {'complete', 'prior pilot'}
        metric = pilot['totals'][model]
        provider = ', '.join(providers.get(p, p) for p in settings['provider']['only'])
        pilot_rows.append([short_names.get(model, name) + (' †' if partial else ''), provider,
                           *cells('', metric, settings['aggregate_completion_token_budget'])[1:5],
                           metric['timeout'], metric['token_cap']])
    extension = pilot.get('coreweave_extension')
    if extension:
        metric = extension['totals']
        pilot_rows.append(['Nemotron 3.5 Lightning ‡', 'CoreWeave/BF16',
                           *cells('', metric, 32768)[1:5], metric['timeout'], metric['token_cap']])
    values = {
        'FULL_RESULT_INTERPRETATION': interpretation,
        'EASY_FAMILY_INTERPRETATION': family_analysis.markdown_overview(summary['easy_family_comparison']),
        'OPEN_WEIGHT_FAMILY_CONTEXT': family_analysis.open_weight_context(summary),
        'EASY_FAMILY_EXAMPLES': family_analysis.markdown_examples(read(OUTPUT / 'nemotron-snowball-example-prompts.json'), base),
        'COMPOSITION_EXAMPLE': composition_example.markdown(summary['composition_example'], base, OUTPUT),
        'EASY_FAMILY_DETAILS': family_analysis.markdown_details(summary['easy_family_comparison'], base),
        'ADDITIONAL_RETRY_ATTEMPTS': str(recovery['additional_attempts']),
        'FULL_RESULTS_ROWS': '\n'.join(results_table.splitlines()[2:]),
        'FULL_FAILURE_ROWS': '\n'.join(failures_table.splitlines()[2:]),
        'LATENCY_ACCOUNTING': 'total recorded attempt time per case, including discarded attempts and retries',
        'RECORDED_CHARGES_BY_MODEL': costs,
        'UNRECONCILED_CASES_BY_MODEL': incomplete,
        'NEMOTRON_TOOL_USERS': f"{uptake['called']:,}",
        'NEMOTRON_TOOL_RATE': f"{uptake['called']/uptake['available']:.1%}",
        'TOOL_USE_GAP_PP': f"{100 * (uptake['called']/uptake['available'] - snowball_uptake['called']/snowball_uptake['available']):.1f}",
        'QWEN_OVER_BUDGET_ATTEMPTS': str(summary['token_budget']['qwen_reported_over_budget_attempts']),
        'QWEN_MAX_REPORTED_TOKENS': f"{summary['token_budget']['qwen_largest_reported_usage']:,}",
        'TIMEOUT_RECOVERY_AUDIT_LINK_AND_COUNTS':
            f"[Recovery audit and attempt counts]({base}/timeout-recovery-audit.json) · [Attempt counts and costs]({base}/timeout-recovery.json). All 217 cases have a selected model response; earlier attempts timed out or returned a transient provider/connection failure. Original attempts remain saved separately.",
        'PYTHON_TOOL_JSON': json.dumps(config['tools_condition']['tools'], indent=2),
        'REQUEST_SETTINGS_JSON': json.dumps(summary['request_settings'], indent=2),
        'SNOWBALL_NATIVE_FIELDS_JSON': json.dumps(summary['snowball_configuration']['native_request_fields'], indent=2),
        'SNOWBALL_CHART_NOTE': '\n'.join(snowball_one_shot.markdown(summary.get('snowball_one_shot_tools'), base)),
        'PILOT_RESULTS_TABLE': markdown_table(
            ['Model', 'Provider', 'Correct', 'Accuracy', 'Median', 'Cost', 'Timeout', 'Truncated'],
            pilot_rows),
        'CARBON_PILOT_NOTE': carbon_pilot.markdown_note(pilot,
            f'https://github.com/{REPOSITORY}/blob/{BRANCH}/evaluations/model-pilot-20261029'),
        'PILOT_MODEL_COUNT': str(len({c.get('full_name', c['model']) for c in pilot['configurations'].values()})),
        'PILOT_RUN_COUNT': str(len(pilot['models'])),
    }
    for file, token in [('overall', 'OVERALL_PNG_HASH'), ('task-radar-hard-tools', 'HARD_PYTHON_RADAR_PNG_HASH'),
                        ('nemotron-snowball-easy', 'NEMOTRON_SNOWBALL_PNG_HASH')]:
        values[token] = hashlib.sha256((OUTPUT / f'{file}.png').read_bytes()).hexdigest()[:12]
    template = Path(__file__).with_name('pr_body_template.md').read_text()
    required = set(re.findall(r'\{\{([A-Z_]+)\}\}', template))
    assert required == values.keys(), (required-values.keys(), values.keys()-required)
    return re.sub(r'\{\{([A-Z_]+)\}\}', lambda match: values[match[1]], template)


def render(output, summary, config, data, rows):
    import base64
    esc = html.escape
    parts = ["""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CDS-bench: full model evaluation</title><style>
body{font:15px/1.5 system-ui,sans-serif;color:#25313c;margin:0;background:white}main{max-width:1320px;margin:auto;padding:24px}h1{font-size:26px}h2{font-size:20px}a{color:#205d89}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:8px;border-bottom:1px solid #dce2e7;text-align:left;vertical-align:top}th{background:#f4f6f8}small,.muted{color:#64727e}small{display:block}.scroll{overflow-x:auto}details{border-top:1px solid #dce2e7;padding:10px 0}summary,.task-row{cursor:pointer}.task-row:hover{background:#f4f7f9}.task-detail{display:none}.task-detail.open{display:table-row}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:420px;overflow:auto;background:#f5f7f9;padding:12px;font:12px/1.5 ui-monospace,monospace;border:1px solid #dce2e7}input,select{font:inherit;padding:6px;margin:10px 0}img{max-width:100%;height:auto}[hidden]{display:none!important}nav{margin:12px 0 20px}.good{background:#e5efe8}.bad{background:#f3e8e9}
.indexed-table tbody+tbody{border-top:2px solid #bfc9d2}.indexed-table tbody th{background:white;font-weight:400}.indexed-table .index-group{vertical-align:middle;font-weight:600;min-width:130px;max-width:210px;border-right:1px solid #dce2e7}.indexed-table .index-item{min-width:100px;max-width:210px}.indexed-table td{white-space:nowrap;font-variant-numeric:tabular-nums;text-align:right}.indexed-table thead th:nth-child(n+3){text-align:right}
.task-radar-svg{display:block;width:100%;height:auto;min-width:1200px}.task-radar-figure{margin:0}.task-radar-figure figcaption{color:#64727e;font-size:13px;margin-top:8px}.radar-swatch{display:inline-block;width:10px;height:10px;margin-right:8px}.radar-key td:last-child{white-space:nowrap;font-variant-numeric:tabular-nums}.radar-key-group th{font-weight:600}
.radar-control select{margin-left:8px}
</style><main><h1>CDS-bench: full model evaluation</h1><nav><a href="#overview">Overview</a> · <a href="#snowball-tools">Snowball tools</a> · <a href="#families">By family</a> · <a href="#task-radar">Task radars</a> · <a href="#task-scatter">Task comparison</a> · <a href="#tasks">By task</a> · <a href="#settings">Settings and data</a></nav>"""]
    parts.append('<p>The benchmark has <a href="https://openathena.ai/cds-bench/#catalogue">65 individual task types</a> and <a href="https://openathena.ai/cds-bench/#compositions">19 composition task types</a>. A composition task combines procedures from individual tasks to solve one question, for example applying a DNA edit, translating both versions and comparing the peptides produced by digestion.</p>')
    q, deepinfra = (summary["totals"][m] for m in ["qwen", "deepinfra"])
    parts.append(f"<p>Full evaluation: <b>Snowball v0.1 {summary['snowball_completed']:,}/3,260 ({esc(summary['state'])})</b>. GPT-6 Luna, Nemotron 3.5 Lightning and Qwen 3.7 Flash each have 3,260 matching completed attempts. Each condition includes ten examples per task: 84 easy task types and 79 hard task types. Retained prompts and reference answers match byte for byte across these four original baselines. Pilot responses are excluded.</p>")
    parts.append('<p class="muted">Snowball uses 32,768 aggregate generated tokens, a 1,800-second API wall deadline, temperature 0.7 and concurrency 60. OpenRouter requests initially used a 300-second deadline; timeout retries use 900 seconds. Concurrency remains ten per OpenRouter model.</p>')
    if summary.get('timeout_recovery'):
        recovery = summary['timeout_recovery']
        parts.append(f"<p>All 217 initially timed-out examples now have a completed model response, after {recovery['additional_attempts']} additional attempts. Scores use the first completed model response. Completed wrong answers, formatting failures and token caps were not retried. <a href='timeout-recovery.json'>Retry counts and policy</a>.</p>")
    parts.append('<p><a href="https://huggingface.co/datasets/eczech/cds-bench-pr-2-traces">Public request, reasoning and tool traces</a> cover the saved full runs, pilots, retries, interrupted attempts and provider diagnostics. Credentials and private endpoints are redacted.</p>')
    if summary['state'] == 'complete':
        parts.append('<p>Snowball completion audit: <b>'+esc(summary['snowball_completion_audit'])+'</b>. <a href="snowball-v01-full-audit.json">Inspect audit</a>.</p>')
    elif summary['state'] == 'auditing':
        parts.append('<p><b>Inference finished; completion audit pending.</b></p>')
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
    parts.append(html_grouped_table(["Model", "Condition", *HEADERS[1:]], [
        (name, [[label, *cells("", summary["conditions"][model][c], 32768)[1:]]
                for c, label in zip(PLANNED, LABELS)])
        for model, name in MODELS.items()
    ]))
    parts.append('<p class="muted">The four original baselines are ordered by pooled mean task accuracy, giving each task equal weight. The same order is used in all condition views, tables and radar panels. In the main chart, the tools-only follow-up is placed beside the original Snowball bars.</p>')
    parts.append('<p class="muted">All failures remain in the denominator. Original Luna artifacts are preserved separately. The <a href="../model-pilot-20261029/report.html">30-task model/provider pilot</a> is a separate report; its responses are not reused here.</p>')
    parts.append(f"<p class=muted>Billing is incomplete for {deepinfra['unreconciled_examples']} Nemotron 3.5 Lightning, {q['unreconciled_examples']} Qwen and {summary['totals']['luna']['unreconciled_examples']} retained Luna attempts. Charges are provisional where only streaming usage is available; unknown charges are not assumed to be zero.</p>")
    image = base64.b64encode((output / "overall.png").read_bytes()).decode()
    parts.append(f'<img alt="Accuracy by model and condition" src="data:image/png;base64,{image}">')
    parts.append(snowball_one_shot.html_description(summary.get('snowball_one_shot_tools')))
    parts.append('<details><summary>Failure categories, token usage, and costs</summary><div class="scroll"><table><tr><th>Model / condition</th><th>Incorrect</th><th>Format</th><th>Timeout</th><th>Token cap</th><th>API error</th><th>Used Python</th><th>Reported generated tokens</th></tr>')
    for m, name in MODELS.items():
        for c, label in zip(PLANNED, LABELS):
            r = summary["conditions"][m][c]
            parts.append(f'<tr><td>{name}<small>{label}</small></td>'+''.join(f'<td>{r[k]}</td>' for k in ['wrong','format','timeout','token_cap','error','examples_using_python','completion_tokens'])+'</tr>')
    budget = summary["token_budget"]
    parts.append('</table></div><p>OpenRouter timeout retries use a 900-second request deadline, increased from 300 seconds. Request timeouts are unscored and retried with backoff; unresolved cases remain pending. Snowball uses a 1,800-second deadline. Token caps exhaust the per-attempt generated-token budget and are scored failures. API/protocol errors remain separate. Costs and elapsed times include every attempt.</p>')
    parts.append(f"<p>Failed-request bookkeeping is reconstructed from saved response metadata for {summary['recovered_failed_request_metadata']} attempts. Raw traces, answers, and scores are unchanged.</p>")
    parts.append(f"<p>The controller requests at most 32,768 generated tokens per example. Qwen reports usage above that allowance for {budget['qwen_reported_over_budget_attempts']} attempts, with a maximum of {budget['qwen_largest_reported_usage']:,} tokens. The audit lists these exceptions; actual provider-reported usage is not strictly matched to Luna's requested cap.</p></details>")
    parts.append('<details><summary>Paired comparisons with Luna on completed cases</summary><table><tr><th>Model / condition</th><th>Pairs</th><th>Both correct</th><th>Luna only</th><th>Other model only</th><th>Both failed</th></tr>')
    comparisons = {'qwen':(summary['paired_models'],'qwen_only'), 'deepinfra':(summary['paired_deepinfra'],'deepinfra_only'), 'snowball-v01':(summary['paired_snowball'],'snowball_only')}
    for model in (m for m in MODELS if m!='luna'):
        metrics, only = comparisons[model]
        for c, label in zip(PLANNED, LABELS):
            r = metrics[c]
            parts.append(f'<tr><td>{esc(MODELS[model])}<small>{label}</small></td>'+''.join(f'<td>{r[k]}</td>' for k in ['completed_pairs','both_correct','luna_only',only,'both_failed'])+'</tr>')
    parts.append('</table></details><details><summary>Formatting diagnostic: original scores unchanged</summary><p>This only accepts an inline <code>Final answer:</code> marker and removes one outer Markdown JSON fence. It applies the same exact-value comparison afterward. It does not repair the answer or recover missing markers.</p><table><tr><th>Model / condition</th><th>Original correct</th><th>Additional exact values</th><th>Diagnostic total</th></tr>')
    for m, name in MODELS.items():
        for c, label in zip(PLANNED, LABELS):
            r = summary["conditions"][m][c]; extra = summary["format_diagnostic_additional_exact"][m][c]
            parts.append(f'<tr><td>{name}<small>{label}</small></td><td>{r["correct"]}/{r["attempted"]}</td><td>{extra}</td><td>{r["correct"]+extra}/{r["attempted"]}</td></tr>')
    parts.append('</table></details>')
    parts.append(snowball_tools.html_section(summary['snowball_tool_use']))
    parts.append('<h2 id="families">By family</h2>')
    parts.append(html_grouped_table(["Family", "Model", *LABELS], [
        (family, [[name, *[f'{metrics[m][c]["correct"]}/{metrics[m][c]["attempted"]}' for c in PLANNED]]
                  for m, name in MODELS.items()])
        for family, metrics in summary["by_family"].items()
    ]))
    parts.append(radar.section(output, summary, MODELS))
    parts.append(scatter.section(output))
    parts.append(family_analysis.html_section(summary['easy_family_comparison'], read(output / 'nemotron-snowball-example-prompts.json'),
                                            composition_example.html_section(output, summary['composition_example']),
                                            family_analysis.open_weight_context(summary)))
    parts.append('<h2 id="tasks">By task</h2><p>Expand a row to inspect all ten instances, actual prompts, expected answers, and each model’s final prediction. Counts are correct / finished; — means that hard variant was removed.</p><input id="filter" placeholder="Filter task names or families"><div class="scroll"><table><thead><tr><th rowspan="2">Task</th>'+''.join(f'<th colspan="{len(MODELS)}">{label}</th>' for label in LABELS)+'</tr><tr>'+''.join(f'<th>{esc(name)}</th>' for _ in LABELS for name in MODELS.values())+'</tr></thead><tbody>')
    for task, definition in TASKS.items():
        title = definition["title"]
        parts.append(f'<tr class="task-row" id="task-{task}" data-task="{task}" data-search="{esc((task+" "+title+" "+definition.get("family", "composition")).lower())}" tabindex="0" aria-expanded="false"><td><a href="#task-{task}">{esc(title)}</a><small>{task}</small></td>')
        for c in PLANNED:
            for m in MODELS:
                r = summary["by_task"][task][m][c]
                text = '—' if c.startswith('hard') and task in config['dataset']['removed_hard_tasks'] else f'{r["correct"]}/{r["attempted"]}'
                parts.append(f'<td>{text}</td>')
        parts.append(f'</tr><tr class="task-detail"><td colspan="{1+len(MODELS)*len(LABELS)}"></td></tr>')
    parts.append('</tbody></table></div><h2 id="settings">Settings and data</h2><p>Luna and Qwen request <code>high</code> reasoning. Nemotron 3.5 Lightning uses <code>nvidia/nemotron-3.5-lightning</code> on <code>deepinfra/bf16</code>, with reasoning enabled and no effort selector. Seed is omitted, matching its pilot. Qwen uses <code>alibaba/us-east-1</code>; Luna used the standard OpenAI endpoint. No provider fallback. Each attempt allows 32,768 generated tokens across its turns and eight Python calls. OpenRouter timeout retries have a 900-second deadline, increased from 300 seconds; Snowball requests have a 1,800-second wall deadline. Snowball uses native thinking, temperature 0.7, seed 20261029 and concurrency 60.</p><p>Python 3.12.9 + NumPy 2.5.4; no Biopython. Local <code>/usr/bin/sandbox-exec</code> denies networking and process forks and restricts filesystem access. Network denial is not an OpenRouter parameter. Web plugins are disabled and no web tool is registered. Raw requests, reasoning, and tool traces remain untracked.</p>')
    parts.append('<details><summary>Exact Python tool definition</summary><pre>'+esc(json.dumps(config['tools_condition']['tools'],indent=2))+'</pre></details>')
    native = summary.get('snowball_configuration')
    if native:
        p = native['provenance']
        parts.append('<details><summary>Snowball v0.1 checkpoint and native API</summary><p>67B total parameters and 2B active per token. Checkpoint: <a href="'+esc(p['url'])+'">'+esc(native['full_name'])+'</a>, <code>'+esc(p['repo'])+'</code>, revision <code>'+esc(p['revision'])+'</code>.</p>'+''.join('<p>'+esc(text)+'</p>' for text in snowball_tools.native_explanation(summary['snowball_tool_use']).split('\n\n'))+'<pre>'+esc(json.dumps(native['native_request_fields'],indent=2))+'</pre></details>')
    parts.append('<details><summary>Dataset version, exact request settings, and billing metadata</summary><p>The current dataset removes five duplicated hard variants. The 100 corresponding historical Luna attempts are excluded only from this comparison. Its original 3,360-attempt report is preserved. Every retained prompt and answer was verified against the old traces.</p><pre>'+esc(json.dumps({'request_settings':summary['request_settings'],'dataset':config['dataset'],'billing':summary['billing'],'qwen_preflight_billing':summary['preflight_billing'],'deepinfra_preflight_billing':summary['deepinfra_preflight_billing']},indent=2))+'</pre></details>')
    parts.append('<p><a href="summary.json">Summary</a> · <a href="by-task.csv">Per-task CSV</a> · <a href="results.json">Predictions</a> · <a href="config.json">Configurations</a></p>')
    payload = {'snapshot':{k:summary[k] for k in ['generated_at','state','qwen_completed','deepinfra_completed','snowball_completed']},
               'models':MODELS,'conditions':list(PLANNED),'labels':LABELS,'records':rows,
               'cases':{v:rs for v,rs in data.items()}}
    parts.append('<script id="data" type="application/json">'+json.dumps(payload,ensure_ascii=False).replace('<','\\u003c')+'</script>')
    parts.append("""<script>
const d=JSON.parse(document.getElementById('data').textContent),caseMap=new Map(),recordMap=new Map();for(const [v,rows]of Object.entries(d.cases))for(const r of rows)caseMap.set(r.instance_id+'|'+v,r);for(const r of d.records)recordMap.set(r.model+'|'+r.condition+'|'+r.instance_id,r);function node(tag,text){const x=document.createElement(tag);if(text!==undefined)x.textContent=text;return x}function details(title,text){const x=node('details');x.append(node('summary',title),node('pre',text));return x}
function expand(row,force){const child=row.nextElementSibling,open=force===undefined?!child.classList.contains('open'):force;child.classList.toggle('open',open);row.setAttribute('aria-expanded',open);if(!open||child.dataset.loaded)return;child.dataset.loaded='1';const cell=child.firstElementChild,select=node('select'),view=node('div'),ids=d.cases.easy.filter(x=>x.task_id===row.dataset.task).map(x=>x.instance_id);for(const id of ids){const o=node('option',id);o.value=id;select.append(o)}const label=node('label','Instance ');label.append(select);cell.append(label,view);function show(){view.replaceChildren();const id=select.value;for(const variant of ['easy','hard']){const c=caseMap.get(id+'|'+variant);if(!c)continue;view.append(details(variant+' prompt',c.prompt));view.append(details(variant+' expected answer',c.answer));for(const tools of [false,true]){const condition=variant+(tools?'-tools':'-no-tools');for(const [m,name]of Object.entries(d.models)){const r=recordMap.get(m+'|'+condition+'|'+id);let text='Not completed';if(r)text=(r.final_answer??r.error??'No final answer')+'\\n\\n'+r.elapsed_seconds.toFixed(1)+'s; '+r.tool_calls+' Python calls; '+(r.cost_usd===null?'cost unavailable':'$'+r.cost_usd.toFixed(6));view.append(details(name+' · '+condition+' · '+(r?r.outcome:'pending'),text))}}}}select.addEventListener('change',show);show()}
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
