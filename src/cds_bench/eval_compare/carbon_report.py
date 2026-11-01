"""Add Carbon-X to the overview only, preserving all existing task figures."""

import argparse
import base64
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from cds_bench.eval_luna.io import save
from cds_bench.eval_luna.report import aggregate

from . import report, snowball_one_shot
from .carbon_run import RAW, now, read, saved_results, scorable
from .carbon_score import score_normalized
from .run import OUTPUT, PLANNED, ROOT
from .tables import HEADERS, cells, html_grouped_table, markdown_results

NAME = 'Carbon-X† (relaxed formatting)'
REPOSITORY_URL = ('https://github.com/Open-Athena/cds-bench/blob/'
                  'eval/luna-high-baseline/evaluations/luna-qwen-high-20261029')
MODEL_CARD = ('https://huggingface.co/HuggingFaceBio/Carbon-X/blob/'
              '17de89165e25c49e7de4f845d0e5d464469de359/README.md')
FOOTNOTE_SUMMARY = '† Carbon-X uses customizations to compensate for instruction-following errors'
FOOTNOTE = (
    'Carbon-X repeatedly ignored the benchmark’s required answer format in the pilot, '
    'even with the settings recommended by the model authors '
    '(thinking off, temperature 0.6, top-p 0.95 and top-k 20). '
    'The error compensation targets those recurring failures: we accept '
    '`Final answer: ATGC` on one line or a bare answer, remove surrounding Markdown '
    'and `<dna>…</dna>` tags, and parse Python-style lists and dictionaries as JSON '
    'without running code. This recovers 222/3,260 correct answers (6.8%), compared '
    'with 3/3,260 (0.1%) under strict scoring. These model-specific scores are not '
    'directly comparable to the other models’ strict scores. Sequence contents, '
    'numerical values, field names and list order must still match; truncated answers '
    'and malformed tool calls still fail. The parsing rules were fixed before the '
    'full run. The server cannot force valid JSON during tool-call generation '
    'with this tokenizer.'
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_protected(raw, output):
    manifest = read(raw / 'preparation/protected-artifacts.json')
    assert manifest, 'Missing pre-run artifact manifest'
    for name, expected in manifest.items():
        relative = Path(name).relative_to(OUTPUT.relative_to(ROOT))
        assert digest(output / relative) == expected, f'Unrelated artifact changed: {name}'


def collect(raw, *, require_complete):
    config = read(raw / 'config.json')
    data = read(raw / 'dataset.json')
    assert config['planned_per_condition'] == PLANNED
    for name, expected in config['source_sha256'].items():
        assert digest(ROOT / name) == expected, f'Frozen inference/scoring source changed: {name}'
    cases = {(row['instance_id'], row['variant']): row
             for rows in data.values() for row in rows}
    attempts = defaultdict(list)
    for path in sorted(raw.glob('attempt-*/traces/*/*/result.json')):
        row = read(path)
        attempts[row['instance_id'], row['condition']].append(row)
    chosen = saved_results(raw) if require_complete else {
        (row['instance_id'], row['condition']): row for row in read(raw / 'results.json', [])
    }
    rows = []
    for identity, saved in sorted(chosen.items()):
        row = dict(saved)
        row.setdefault('strict_passed', False)
        directory = Path(row['trace_directory'])
        case = cases[row['instance_id'], row['variant']]
        assert read(directory / 'case.json') == case
        assert scorable(row) and not row.get('request_timeout')
        answer = (directory / 'answer.txt').read_text()
        score = score_normalized(case, answer, 'length' if row.get('truncated') else row['finish_reason'])
        assert score['passed'] == row['passed']
        assert score['strict_passed'] == row.get('strict_passed', False)
        if not row.get('model_tool_protocol_failure') and not row.get('truncated'):
            assert row['normalization_version'] == config['normalization']['version']
        assert row['completion_tokens'] <= config['aggregate_completion_token_budget']
        tools = [read(path) for path in sorted(directory.glob('tool-*.json'))]
        assert sum('exit_code' in tool['result'] for tool in tools) <= config['max_tool_calls']
        assert all(tool['result'].get('error', '').startswith('Maximum of 8 Python calls')
                   for tool in tools[config['max_tool_calls']:])
        row.update(cost_usd=0, billing_complete=False)
        row['elapsed_seconds'] = sum(attempt['elapsed_seconds'] for attempt in attempts[identity])
        rows.append(row)
    counts = Counter(row['condition'] for row in rows)
    complete = dict(counts) == PLANNED
    if require_complete:
        assert complete and read(raw / 'job-status.json')['state'] == 'complete'
    conditions = {}
    for condition in PLANNED:
        subset = [row for row in rows if row['condition'] == condition]
        metric = aggregate(subset)
        metric.update(cost_usd=None, strict_correct=sum(row['strict_passed'] for row in subset))
        conditions[condition] = metric
    total = aggregate(rows)
    total.update(cost_usd=None, strict_correct=sum(row['strict_passed'] for row in rows))
    metric = {'model': NAME, 'state': 'complete' if complete else 'running',
              'generated_at': now(), 'planned': 3260, 'completed': len(rows),
              'conditions': conditions, 'totals': total, 'configuration': config}
    audit = {'passed': complete, 'selected_cases': len(rows), 'planned_cases': 3260,
             'condition_counts': dict(counts), 'attempts': sum(map(len, attempts.values())),
             'unscored_attempts': sum(not scorable(row) for group in attempts.values() for row in group),
             'strict_correct': total['strict_correct'], 'relaxed_correct': total['correct'],
             'checks': ['Frozen source hashes', 'Dataset prompt and reference-answer equality',
                        'One first completed answer per case; no pilot reuse',
                        'Independent strict and relaxed rescoring', 'Token and Python-call budgets',
                        'No unresolved transport failure scored as an incorrect answer']}
    tokenizer = read(raw / 'tokenizer-audit.json', {})
    if tokenizer:
        affected = Counter(row['id'].rsplit('/', 2)[0] for row in tokenizer['native_oov_prompts'])
        audit['native_tokenizer'] = {'checked_prompts': tokenizer['prompt_count'],
            'prompts_with_unknown_tokens': len(tokenizer['native_oov_prompts']),
            'affected_task_types': dict(affected),
            'served_request_token_counts_checked': len(tokenizer['request_checks']),
            'served_request_token_counts_all_match': tokenizer['request_token_counts_all_match'],
            'note': 'The released native tokenizer replaces DNA chunks containing ambiguity codes with an unknown token. Inputs were not altered to avoid this behavior.'}
    metric['audit'] = audit
    publication = read(raw / 'trace-publication.json')
    if publication:
        assert publication['verified']
        metric['trace_archive'] = publication
    return metric


def strict_note(carbon):
    values = '; '.join(f"{label}: {carbon['conditions'][condition]['strict_correct']}/"
                       f"{carbon['conditions'][condition]['attempted']}"
                       for condition, label in zip(PLANNED, report.LABELS, strict=True))
    return f'Strict-format correct counts: {values}.'


def markdown_explanation():
    paragraph = FOOTNOTE.replace('model authors', f'[model authors]({MODEL_CARD})')
    paragraph += f' [Configuration and strict counts]({REPOSITORY_URL}/carbon-x.json).'
    return f'<details>\n<summary>{FOOTNOTE_SUMMARY}</summary>\n\n{paragraph}\n\n</details>'


def html_explanation(carbon):
    paragraph = html.escape(FOOTNOTE).replace('`', '')
    paragraph = paragraph.replace('model authors', f'<a href="{MODEL_CARD}">model authors</a>')
    return ('<aside class="chart-exception" id="carbon-x-formatting"><details><summary>'
            + html.escape(FOOTNOTE_SUMMARY) + '</summary><p>' + paragraph
            + '</p><p class="muted">' + html.escape(strict_note(carbon))
            + ' <a href="carbon-x.json">Configuration and audit</a>.</p></details></aside>')


def replace_table(body, replacement):
    pattern = r'(<summary>Full results:[^<]*</summary>\s*)\| Model \|.*?(?=\n\n)'
    def replace(match):
        original = match[0][len(match[1]):].splitlines()
        return match[1] + '\n'.join(original[:2] + replacement.splitlines()[2:])
    value, count = re.subn(pattern, replace, body, count=1, flags=re.DOTALL)
    assert count == 1, 'Main PR table not found'
    return value


def update(raw, output, *, require_complete=True):
    verify_protected(raw, output)
    carbon = collect(raw, require_complete=require_complete)
    if require_complete:
        save(raw / 'audit.json', carbon['audit'])
    summary = read(output / 'summary.json')
    assert set(summary['models']) == set(report.MODELS)
    report.MODELS = {model: summary['models'][model] for model in summary['models']}
    report.plot(output, summary['conditions'], summary.get('snowball_one_shot_tools'), carbon=carbon)
    save(output / 'carbon-x.json', carbon)

    # Preserve the current OP, including later pilot additions. Replace only
    # the overview chart, table and Carbon-X explanation.
    current_body = output / 'pr-body.md'
    body = current_body.read_text() if current_body.exists() else (raw / 'preparation/pr-before.md').read_text()
    body = re.sub(r'<details>\s*<summary>† Carbon-X uses.*?</summary>.*?</details>\s*',
                  '', body, count=1, flags=re.DOTALL)
    body = re.sub(r'<details>\s*<summary>‡ Snowball v0\.1.*?</summary>.*?</details>\s*',
                  '', body, count=1, flags=re.DOTALL)
    main_rows = [((name, label), summary['conditions'][model][condition], 32768)
                 for model, name in report.MODELS.items()
                 for condition, label in zip(PLANNED, report.LABELS, strict=True)]
    main_rows += [(('Carbon-X†', label), carbon['conditions'][condition], 32768)
                  for condition, label in zip(PLANNED, report.LABELS, strict=True)]
    body = replace_table(body, markdown_results(main_rows, include_timeout=False))
    body = re.sub(r'(overall\.png\?v=)[a-f0-9]+',
                  lambda match: match[1] + digest(output / 'overall.png')[:12], body)
    footnote = markdown_explanation()
    if summary.get('snowball_one_shot_tools'):
        footnote += '\n\n' + '\n'.join(snowball_one_shot.markdown(summary['snowball_one_shot_tools'], REPOSITORY_URL)).strip()
    image_end = re.search(r'!\[CDS-bench accuracy by model and evaluation condition\]\([^\n]+\)', body).end()
    body = body[:image_end] + '\n\n' + footnote + body[image_end:]
    (output / 'pr-body.md').write_text(body.rstrip() + '\n')

    document = (output / 'report.html').read_text()
    start = document.index('<h2 id="overview">')
    table_start = document.index('<div class="scroll"><table class="indexed-table">', start)
    table_end = document.index('</table></div>', table_start) + len('</table></div>')
    groups = [(name, [cells(label, summary['conditions'][model][condition], 32768)
                      for condition, label in zip(PLANNED, report.LABELS, strict=True)])
              for model, name in report.MODELS.items()]
    carbon_table = html_grouped_table(['Model', 'Condition', *HEADERS[1:]],
                                     [(NAME, [cells(label, carbon['conditions'][condition], 32768)
                                              for condition, label in zip(PLANNED, report.LABELS, strict=True)])])
    carbon_body = re.search(r'<tbody>.*</tbody>', carbon_table).group()
    carbon_body = carbon_body.replace('<tbody>', '<tbody class="relaxed-model">', 1)
    main_table = html_grouped_table(['Model', 'Condition', *HEADERS[1:]], groups)
    main_table = main_table.replace('</table>', carbon_body + '</table>')
    document = document[:table_start] + main_table + document[table_end:]
    encoded = base64.b64encode((output / 'overall.png').read_bytes()).decode()
    document, count = re.subn(r'(<img alt="Accuracy by model and condition" src=")[^"]+("[^>]*>)',
                             lambda match: match[1] + 'data:image/png;base64,' + encoded + match[2], document, count=1)
    assert count == 1
    document = re.sub(r'<aside(?: class="chart-exception")? id="carbon-x-formatting">.*?</aside>', '', document, flags=re.DOTALL)
    aside = html_explanation(carbon)
    document = re.sub(r'(<img alt="Accuracy by model and condition"[^>]*>)',
                      lambda match: match[0] + aside, document, count=1)
    style = '<style id="carbon-overview-style">.relaxed-model{background:#f4f1e9}.relaxed-model .index-group{border-left:4px dotted #6b655b}.chart-exception{border-left:3px solid #c4cbd3;padding-left:1em;margin:12px 0}</style>'
    if 'id="carbon-overview-style"' in document:
        document = re.sub(r'<style id="carbon-overview-style">.*?</style>', lambda match: style, document, count=1, flags=re.DOTALL)
    else:
        document = document.replace('</head>', style + '</head>') if '</head>' in document else document.replace('</style>', '</style>' + style, 1)
    (output / 'report.html').write_text(document)
    summary['carbon_x'] = carbon
    save(output / 'summary.json', summary)
    verify_protected(raw, output)
    save(raw / 'publication-audit.json', {'passed': carbon['audit']['passed'], 'updated_at': now(),
        'protected_artifacts_unchanged': True, 'changed_views': ['Overview bar chart', 'Main results table'],
        'relaxed_score_label': NAME, 'strict_counts': strict_note(carbon)})
    return carbon


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-root', type=Path, default=RAW)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    result = update(args.raw_root, args.output, require_complete=not args.allow_partial)
    print(json.dumps({'completed': result['completed'], 'conditions': result['conditions']}, indent=2))


if __name__ == '__main__':
    main()
