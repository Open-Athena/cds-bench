"""Publish the audited tools-only Snowball follow-up in the overview chart."""

import hashlib
import html
import json
from collections import Counter

from cds_bench.eval_luna.io import save

from .run import ROOT

RAW = ROOT / "scratch/snowball-tools-aggressive-20261031-01/full-complete-code-v6"
NAME = "Snowball v0.1 (1-shot tools)"
FOOTNOTE_SUMMARY = '‡ Snowball v0.1 (1-shot tools) uses customizations to compensate for low tool use'
DATA_FILE = "snowball-v01-one-shot-tools.json"
AUDIT_FILE = "snowball-v01-one-shot-tools-audit.json"
EXAMPLE_FILE = "snowball-v01-one-shot-tools-example.txt"


def read(path):
    return json.loads(path.read_text())


def export(output, cases):
    """Keep follow-up data separate from all four original full baselines."""
    audit_path = RAW / "final-audit.json"
    if not audit_path.exists():
        return None
    audit = read(audit_path)
    assert audit["passed"] and audit["attempts"] == 1630
    assert audit["scored_retries"] == 0 and audit["no_no_tools_attempts"]
    comparison = read(RAW / "comparison.json")
    config = read(RAW / "config.json")
    rows = read(RAW / "results.json")
    assert comparison["state"] == "complete" and len(rows) == 1630
    assert Counter(r["condition"] for r in rows) == {"easy-tools": 840, "hard-tools": 790}
    assert len({(r["instance_id"], r["condition"]) for r in rows}) == len(rows)
    originals = {(r["instance_id"], variant): r
                 for variant, entries in read(RAW / "original-cases.json").items()
                 for r in entries}
    assert len(originals) == 1630
    for row in rows:
        key = row["instance_id"], row["variant"]
        assert originals[key] == cases[key]
    for condition, metrics in comparison["conditions"].items():
        selected = [r for r in rows if r["condition"] == condition]
        assert metrics["n"] == len(selected)
        assert metrics["correct"] == sum(bool(r["passed"]) for r in selected)
        assert metrics["tool_users"] == sum(r["tool_calls"] > 0 for r in selected)

    request = read(RAW / "traces/hard-tools/0021-cds.translate-01/request-01.json")
    original = cases["cds.translate/01", "hard"]["prompt"]
    profile = config["profile"]
    assert request["messages"][-1]["content"] == (
        profile["question_prefix"] + original + profile["question_suffix"]
    )
    public = {
        "name": NAME,
        "display_scope": "Overview bar chart only; no no-tools observations or pooled ranking.",
        "provenance": config["provenance"],
        "total_parameters": config["total_parameters"],
        "active_parameters_per_token": config["active_parameters_per_token"],
        "dataset_revision": "26f63e8e488022bed14e12af0f1e44d87a28e14f",
        "conditions": comparison["conditions"],
        "totals": comparison["totals"],
        "original_baseline": {
            condition: {key: metrics[key] for key in
                        ["n", "correct", "accuracy", "tool_users", "tool_use_rate"]}
            for condition, metrics in comparison["matched_baselines"]["original_snowball"].items()
        },
        "failure_categories": comparison["failure_categories_from_raw_metadata"],
        "failure_category_note": comparison["failure_category_note"],
        "method": comparison["method"],
        "selection": (
            "Selected using predeclared tool-invocation and successful-execution thresholds "
            "on fresh 30 easy / 28 hard calibration attempts, not classification accuracy. "
            "Calibration responses are excluded from the full evaluation."
        ),
        "prompt_profile": profile,
        "demonstration_messages": config["demonstration"]["messages"],
        "first_request_fields": {
            "chat_template_kwargs": request["chat_template_kwargs"],
            "response_format": request["response_format"],
        },
        "settings": {
            key: config[key] for key in [
                "aggregate_completion_token_budget", "request_timeout_seconds",
                "connection_timeout_seconds", "max_tool_calls", "concurrency",
                "sampling", "scoring", "cost_note",
            ]
        },
        "sampling_parameters": {
            key: config["parameters"][key] for key in ["temperature", "seed"]
        },
        "audit": {key: value for key, value in audit.items() if key != "publication"},
        "raw_audit_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
        "raw_results_sha256": hashlib.sha256((RAW / "results.json").read_bytes()).hexdigest(),
        "source_sha256": config["source_sha256"],
        "raw_traces": "Saved locally; this follow-up is not yet in the linked HF archive.",
    }
    save(output / DATA_FILE, public)
    save(output / AUDIT_FILE, public["audit"])
    example = [
        "Actual first request: Hard, Python; cds.translate/01",
        "Custom instructions (chat_template_kwargs.custom_instructions)",
        request["chat_template_kwargs"]["custom_instructions"],
        "Tool definition (chat_template_kwargs.xml_tools)",
        json.dumps(request["chat_template_kwargs"]["xml_tools"], indent=2),
        "Conversation messages",
        json.dumps(request["messages"], indent=2, ensure_ascii=False),
        "Initial response format",
        json.dumps(request["response_format"], indent=2),
        "Initial enable_thinking: false. Native thinking resumes after successful execution.",
    ]
    (output / EXAMPLE_FILE).write_text("\n\n".join(example) + "\n")
    return public


def description(stats):
    a, b = (stats["conditions"][c] for c in ["easy-tools", "hard-tools"])
    original = stats['original_baseline']
    old_rate = sum(r['tool_users'] for r in original.values()) / sum(r['n'] for r in original.values())
    total = stats["totals"]
    return (
        f"Standard Snowball used Python on only {sum(r['tool_users'] for r in original.values()):,}/"
        f"{sum(r['n'] for r in original.values()):,} examples where Python was available ({old_rate:.1%}). "
        "This variant compensates with one arithmetic tool-use demonstration and a requirement "
        "to run a Python program before answering. The model supplies the program; the controller "
        "executes it verbatim and returns the result. "
        f"Python use rises to {total['tool_users']:,}/{total['n']:,} ({total['tool_use_rate']:.1%}).\n\n"
        "Accuracy rises "
        f"from {original['easy-tools']['accuracy']:.1%} to {a['accuracy']:.1%} on Easy/Python "
        f"and {original['hard-tools']['accuracy']:.1%} to {b['accuracy']:.1%} on Hard/Python. "
        "The question data and strict final-answer scorer are unchanged; the prompting and "
        "execution requirements differ from the optional-tool baseline."
    )


def markdown(stats, base):
    if not stats:
        return []
    return [
        f"\n<details>\n<summary>{FOOTNOTE_SUMMARY}</summary>\n",
        "\n" + description(stats),
        f"\n[Exact example request]({base}/{EXAMPLE_FILE}) · "
        f"[Aggregates, prompt instructions and schema]({base}/{DATA_FILE}) · "
        f"[Completion audit]({base}/{AUDIT_FILE})",
        "\nEach benchmark question is preceded by a worked arithmetic example showing a Python "
        "call, its output and the final answer. Instructions requiring Python are added before and after the original "
        "benchmark prompt. The original sequence inputs, references, answer and scoring rules "
        "are unchanged. The first response must contain exactly one `code` string; the controller "
        "executes it verbatim and returns the result. If execution fails, the model writes a "
        "complete replacement program. The controller does not edit the program or supply reference-answer feedback. "
        "The final answer is scored as originally specified.",
        "\nThe sandbox, 32,768 aggregate generated-token budget and eight-execution limit "
        "are unchanged.",
        "\nThe full run contains 1,630 fresh attempts, separate from calibration, with no scored "
        "retries. Temperature 0.7, seed 20261029, concurrency 60 and a 1,800-second request deadline "
        "match the Snowball setup. "
        "Its raw traces remain local and are not yet in the linked HF archive.",
        "\nThe protocol was selected using predeclared tool-invocation and successful-execution "
        "thresholds on 30 easy and 28 hard calibration attempts, rather than answer accuracy.",
        f"\nCheckpoint, with 67B total / 2B active parameters: "
        f"[{stats['provenance']['repo']}]({stats['provenance']['url']}), "
        f"revision `{stats['provenance']['revision']}`.",
        "\n</details>",
    ]


def html_description(stats):
    if not stats:
        return ""
    return (
        '<aside class="chart-exception" id="snowball-one-shot-tools"><details><summary>'
        + html.escape(FOOTNOTE_SUMMARY) + '</summary>'
        + ''.join('<p>' + html.escape(p) + '</p>' for p in description(stats).split('\n\n'))
        + f'<p><a href="{EXAMPLE_FILE}">Exact example request</a> · '
        f'<a href="{DATA_FILE}">Aggregates, instructions and schema</a> · '
        f'<a href="{AUDIT_FILE}">Completion audit</a>.</p>'
        '<p>Original question inputs, references and expected answers are unchanged. Generic '
        'execution instructions are added around the question, and four demonstration messages '
        'are prepended. Model programs execute verbatim. There is no final-answer grammar or '
        'gold-answer feedback. All 1,630 attempts are fresh; calibration attempts are excluded. '
        'This follow-up’s raw traces remain local and are not yet in the linked HF archive.</p>'
        '<p>Thinking is disabled while generating the required Python program. '
        'The model writes execution-error repairs within the same eight-execution '
        'limit. The offline sandbox, 32,768 aggregate generated-token budget and final scorer '
        'are unchanged.</p>'
        '<p>Added instructions before the question:</p><pre>'
        + html.escape(stats['prompt_profile']['question_prefix'].strip())
        + '</pre><p>Added instructions after the question:</p><pre>'
        + html.escape(stats['prompt_profile']['question_suffix'].strip())
        + '</pre><p>First response format:</p><pre>'
        + html.escape(json.dumps(stats['first_request_fields']['response_format'], indent=2))
        + '</pre></details></aside>'
    )
