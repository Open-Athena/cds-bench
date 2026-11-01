"""Paired easy-condition family comparisons from the published predictions.

This is descriptive analysis of fixed benchmark cases. A second test swaps model
labels for whole task types, so ten examples do not count as ten task types.
Neither test changes scoring or selects new inference attempts.
"""

import csv
import hashlib
import html
import json
from collections import Counter, defaultdict
from math import comb

from cds_bench.catalog import TASKS
from .radar import FAMILIES

CONDITIONS = {'easy-no-tools': 'Easy, no tools', 'easy-tools': 'Easy, Python'}
ALPHA = 0.01
EXAMPLES = ['pipeline.variant_peptides/03', 'design.insert_dna_motif/01', 'rna.apply_edits/01']
EXAMPLE_NOTE = 'The three prompts below are Easy/Python examples that Nemotron answered correctly and Snowball failed.'


def exact_mcnemar(nemotron_only, snowball_only):
    """Two-sided exact binomial test of the discordant matched examples."""
    n = nemotron_only + snowball_only
    if not n:
        return 1.0
    return min(1.0, 2 * sum(comb(n, k) for k in range(min(nemotron_only, snowball_only) + 1)) / 2**n)


def task_swap_p(differences):
    """Exact two-sided sign-flip test, keeping all examples of a task together."""
    distribution = Counter({0: 1})
    for difference in differences:
        following = Counter()
        for value, count in distribution.items():
            following[value + difference] += count
            following[value - difference] += count
        distribution = following
    observed = abs(sum(differences))
    return sum(count for value, count in distribution.items() if abs(value) >= observed) / 2**len(differences)


def holm(pvalues):
    """Holm step-down adjustment over every family in both easy conditions."""
    adjusted = [1.0] * len(pvalues)
    previous = 0.0
    for rank, index in enumerate(sorted(range(len(pvalues)), key=pvalues.__getitem__)):
        previous = max(previous, min(1.0, (len(pvalues) - rank) * pvalues[index]))
        adjusted[index] = previous
    return adjusted


def analyze(rows):
    lookup = {(r['condition'], r['instance_id']): r for r in rows
              if r['model'] == 'deepinfra' and r['condition'] in CONDITIONS}
    snowball = [r for r in rows if r['model'] == 'snowball-v01' and r['condition'] in CONDITIONS]
    assert len(lookup) == len(snowball) == 1680
    assert len({(r['condition'], r['instance_id']) for r in snowball}) == len(snowball)
    groups = defaultdict(list)
    for b in snowball:
        a = lookup[b['condition'], b['instance_id']]
        assert a['task_id'] == b['task_id'] and a['expected_answer'] == b['expected_answer']
        assert not a.get('request_timeout') and not b.get('request_timeout')
        groups[b['condition'], TASKS[b['task_id']].get('family', 'composition')].append((a, b))
    result = []
    for condition in CONDITIONS:
        for family, (name, _) in FAMILIES.items():
            pairs = groups[condition, family]
            tasks = defaultdict(list)
            for a, b in pairs:
                tasks[a['task_id']].append((a, b))
            assert pairs and all(len(p) == 10 for p in tasks.values())
            task_rows = []
            for task_id, task_pairs in sorted(tasks.items()):
                task_rows.append({'task_id': task_id, 'title': TASKS[task_id]['title'],
                                  **_metrics(task_pairs)})
            differences = [t['nemotron_correct'] - t['snowball_correct'] for t in task_rows]
            metrics = _metrics(pairs)
            result.append({'condition': condition, 'family': family, 'name': name,
                           'task_count': len(tasks), **metrics,
                           'nemotron_task_wins': sum(d > 0 for d in differences),
                           'snowball_task_wins': sum(d < 0 for d in differences),
                           'task_ties': sum(d == 0 for d in differences),
                           'example_p': exact_mcnemar(metrics['nemotron_only'], metrics['snowball_only']),
                           'task_p': task_swap_p(differences), 'tasks': task_rows})
    assert len(result) == 20
    for name in ('example_p', 'task_p'):
        for row, p in zip(result, holm([r[name] for r in result])):
            row[name + '_holm'] = p
    for row in result:
        row['large_example_gap'] = abs(row['difference_pp']) >= 10 and row['example_p_holm'] < ALPHA
        row['large_task_gap'] = abs(row['difference_pp']) >= 10 and row['task_p_holm'] < ALPHA
    return {'models': ['deepinfra', 'snowball-v01'], 'conditions': list(CONDITIONS),
            'methods': {'example_test': 'Exact two-sided McNemar',
                        'task_test': 'Exact two-sided permutation of model labels within each whole task type',
                        'adjustment': 'Holm, separately over all 20 example tests and all 20 task-type tests',
                        'threshold': ALPHA, 'minimum_highlighted_gap_pp': 10,
                        'scope': 'Post-hoc fixed-benchmark comparison; no new scoring or inference.'},
            'comparisons': result}


def _metrics(pairs):
    n = len(pairs)
    x, y = (sum(a['passed'] for a, b in pairs), sum(b['passed'] for a, b in pairs))
    result = {'examples_per_model': n, 'nemotron_correct': x, 'snowball_correct': y,
              'difference_pp': 100 * (x - y) / n,
              'nemotron_only': sum(a['passed'] and not b['passed'] for a, b in pairs),
              'snowball_only': sum(b['passed'] and not a['passed'] for a, b in pairs)}
    for model, index in [('nemotron', 0), ('snowball', 1)]:
        values = [p[index] for p in pairs]
        result[model + '_outcomes'] = dict(sorted(Counter(r['outcome'] for r in values).items()))
        result[model + '_tool_users'] = sum(r['tool_calls'] > 0 for r in values)
    return result


def export(output, rows, cases):
    analysis = analyze(rows)
    analysis['predictions_sha256'] = hashlib.sha256((output / 'results.json').read_bytes()).hexdigest()
    (output / 'nemotron-snowball-families.json').write_text(json.dumps(analysis, indent=2) + '\n')
    fields = ['condition', 'family', 'name', 'task_count', 'examples_per_model', 'nemotron_correct',
              'snowball_correct', 'difference_pp', 'nemotron_only', 'snowball_only',
              'nemotron_task_wins', 'snowball_task_wins', 'task_ties', 'example_p',
              'example_p_holm', 'task_p', 'task_p_holm', 'nemotron_tool_users', 'snowball_tool_users']
    with (output / 'nemotron-snowball-families.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore', lineterminator='\n')
        writer.writeheader()
        writer.writerows(analysis['comparisons'])
    examples = []
    for instance_id in EXAMPLES:
        case = cases[instance_id, 'easy']
        task_id = case['task_id']
        family = TASKS[task_id].get('family', 'composition')
        paired = {model: next(r for r in rows if r['model'] == model and
                             r['instance_id'] == instance_id and r['condition'] == 'easy-tools')
                  for model in ['deepinfra', 'snowball-v01']}
        assert paired['deepinfra']['passed'] and not paired['snowball-v01']['passed']
        assert all(r['expected_answer'] == case['answer'] for r in paired.values())
        task_metrics = next(t for r in analysis['comparisons']
                            if r['condition'] == 'easy-tools' and r['family'] == family
                            for t in r['tasks'] if t['task_id'] == task_id)
        examples.append({'instance_id': instance_id, 'task_id': task_id,
                         'title': TASKS[task_id]['title'], 'family': FAMILIES[family][0],
                         'condition': 'easy-tools', 'prompt': case['prompt'], 'answer': case['answer'],
                         'prompt_sha256': hashlib.sha256(case['prompt'].encode()).hexdigest(),
                         'nemotron_correct': task_metrics['nemotron_correct'],
                         'snowball_correct': task_metrics['snowball_correct'],
                         'examples_per_model': task_metrics['examples_per_model'],
                         'nemotron_outcome': paired['deepinfra']['outcome'],
                         'snowball_outcome': paired['snowball-v01']['outcome']})
    (output / 'nemotron-snowball-example-prompts.json').write_text(json.dumps(examples, indent=2, ensure_ascii=False) + '\n')
    # Per-task diagnostics live in the dedicated export, rather than duplicating
    # them inside the main report summary.
    return {**analysis, 'comparisons': [{k: v for k, v in row.items() if k != 'tasks'}
                                      for row in analysis['comparisons']]}


def ptext(p):
    return f'{p:.2g}' if p < 0.001 else f'{p:.3f}'


def table_rows(analysis, condition, significant_only=False):
    for r in analysis['comparisons']:
        if r['condition'] == condition and (not significant_only or r['large_example_gap']):
            n = r['examples_per_model']
            yield [r['name'], f"{r['nemotron_correct']}/{n} ({r['nemotron_correct']/n:.1%})",
                   f"{r['snowball_correct']}/{n} ({r['snowball_correct']/n:.1%})",
                   f"{r['difference_pp']:+.1f}", ptext(r['example_p_holm']), ptext(r['task_p_holm'])]


HEADERS = ['Family', 'Nemotron', 'Snowball', 'Δ (pp)', 'p: examples', 'p: task types']
METHODS = (
    'Δ is Nemotron’s accuracy minus Snowball’s, in percentage points; positive values favor Nemotron.\n\n'
    'The “p: examples” column uses the exact McNemar test. It considers questions where only '
    'one model is correct and asks whether the split of wins is more uneven than expected '
    'if neither model had an advantage.\n\n'
    'The “p: task types” column swaps the models’ results for whole task types, keeping each '
    'task’s ten examples together. Its p-value is the fraction of all possible swaps that '
    'produce a gap at least as large in either direction as the observed gap. This accounts '
    'for examples of the same task behaving similarly.\n\n'
    'Both tests are two-sided. We test ten families in two easy conditions '
    '(20 comparisons per method). Holm’s correction adjusts the p-values for the increased '
    'risk of chance findings when many comparisons are made. We apply it separately to the '
    'example-level and task-type tests. Using adjusted p < 0.01 limits the chance of one or '
    'more false positives within each set of 20 comparisons to at most 1%, under the tests’ assumptions.'
)
METHODS_REFERENCE = 'The tables below use the statistical tests and correction described above.'


def overview_text(analysis):
    assert not any(r['difference_pp'] < 0 and r['example_p_holm'] < ALPHA
                   for r in analysis['comparisons'])
    assert not any(r['example_p_holm'] < ALPHA for r in analysis['comparisons']
                   if r['condition'] == 'easy-no-tools')
    return ('Easy/Python families favoring Nemotron with adjusted paired-example p < 0.01:',
            'No family favors Snowball at that threshold in either easy condition. '
            'Without tools, no family difference in either direction meets the threshold.')


def markdown_overview(analysis):
    from .tables import markdown_table
    intro, ending = overview_text(analysis)
    rows = [[f'**{value}**' for value in row] if row[0] == 'Composition tasks' else row
            for row in table_rows(analysis, 'easy-tools', True)]
    explanation = ('<details>\n<summary>Statistical tests and interpretation</summary>\n\n'
                   + METHODS + '\n\n' + ending + '\n\n</details>')
    return '\n\n'.join([intro, markdown_table(HEADERS, rows), explanation])


def open_weight_context(summary):
    pooled = []
    for family, (name, _) in FAMILIES.items():
        metrics = [metric for model in ['deepinfra', 'qwen', 'snowball-v01']
                   for metric in summary['by_family'][family][model].values()]
        correct = sum(m['correct'] for m in metrics)
        attempted = sum(m['attempted'] for m in metrics)
        pooled.append((correct / attempted, family, name, correct, attempted))
    ranked = sorted(pooled)
    assert [r[1] for r in ranked[:3]] == ['composition', 'assay', 'redesign']
    comparison = next(r for r in summary['easy_family_comparison']['comparisons']
                      if r['family'] == 'composition' and r['condition'] == 'easy-tools')
    assert comparison['task_p_holm'] == min(r['task_p_holm'] for r in summary['easy_family_comparison']['comparisons'])
    def score(row):
        return f'{row[0]:.1%} ({row[3]:,}/{row[4]:,})'
    n = comparison['examples_per_model']
    return ('Composition tasks are the hardest family on average for Nemotron, Qwen and Snowball: '
            f'{score(ranked[0])}, pooling all four conditions. They also show the strongest '
            'evidence of a Nemotron–Snowball gap across task types on Easy/Python: '
            f"{comparison['nemotron_correct']/n:.1%} ({comparison['nemotron_correct']}/{n}) versus "
            f"{comparison['snowball_correct']/n:.1%} ({comparison['snowball_correct']}/{n}), "
            f"a {comparison['difference_pp']:.1f}-percentage-point difference "
            f"(adjusted task-type p = {comparison['task_p_holm']:.5f}). "
            f"Nemotron leads on {comparison['nemotron_task_wins']}/{comparison['task_count']} task types. "
            'The next-lowest pooled family accuracies are '
            f'assay design at {score(ranked[1])} and synonymous design at {score(ranked[2])}.')


def markdown_examples(examples, base):
    parts = [EXAMPLE_NOTE]
    for e in examples:
        outcome = {'format': 'format failure', 'token_cap': 'token cap', 'wrong': 'wrong answer'}[e['snowball_outcome']]
        parts.append(f"<details>\n<summary>{e['family']}: {e['title']}</summary>\n\n"
                     f"[{e['instance_id']}]({base}/report.html#task-{e['task_id']}) · Easy/Python. "
                     f"Task scores: Nemotron {e['nemotron_correct']}/{e['examples_per_model']}; "
                     f"Snowball {e['snowball_correct']}/{e['examples_per_model']}. "
                     f"This example: Nemotron correct; Snowball {outcome}.\n\n"
                     'Exact benchmark user prompt:\n\n````text\n' + e['prompt'] + '\n````\n\n'
                     'Expected answer:\n\n```text\n' + e['answer'] + '\n```\n\n</details>')
    return '\n\n'.join(parts)


def markdown_details(analysis, base):
    from .tables import markdown_table
    parts = ['<details>\n<summary>All family comparisons</summary>\n', METHODS_REFERENCE]
    for condition, label in CONDITIONS.items():
        parts.extend(['\n' + label + '\n', markdown_table(HEADERS, table_rows(analysis, condition))])
    parts.append(f'\n[JSON]({base}/nemotron-snowball-families.json) · '
                 f'[CSV]({base}/nemotron-snowball-families.csv)\n\n</details>')
    return '\n\n'.join(parts)


def html_section(analysis, examples, composition_html='', family_context=''):
    esc = html.escape
    intro, ending = overview_text(analysis)
    def table(condition, significant_only=False):
        def render_row(row):
            emphasized = significant_only and row[0] == 'Composition tasks'
            style = ' style="background:#f3f1fa"' if emphasized else ''
            cells = ['<strong>' + esc(v) + '</strong>' if emphasized else esc(v) for v in row]
            return '<tr' + style + '>' + ''.join('<td>' + v + '</td>' for v in cells) + '</tr>'
        return ('<div class="scroll"><table><thead><tr>' +
                ''.join('<th>' + esc(h) + '</th>' for h in HEADERS) + '</tr></thead><tbody>' +
                ''.join(render_row(row)
                        for row in table_rows(analysis, condition, significant_only)) + '</tbody></table></div>')
    explanation = ('<details><summary>Statistical tests and interpretation</summary>'
                   + ''.join('<p>' + esc(p) + '</p>' for p in METHODS.split('\n\n'))
                   + '<p>' + esc(ending) + '</p></details>')
    parts = ['<section id="easy-family-comparison"><h3>Nemotron versus Snowball on easy questions: task families</h3>',
             '<p>' + esc(family_context) + '</p>' if family_context else '',
             '<p>' + esc(intro) + '</p>', table('easy-tools', True), explanation, composition_html]
    parts.append('<p>' + esc(EXAMPLE_NOTE) + '</p>')
    for e in examples:
        outcome = {'format': 'format failure', 'token_cap': 'token cap', 'wrong': 'wrong answer'}[e['snowball_outcome']]
        parts.append('<details><summary>' + esc(e['family'] + ': ' + e['title']) + '</summary>' +
                     f'<p><a href="#task-{e["task_id"]}">{esc(e["instance_id"])}</a> · Easy/Python. '
                     f'Task scores: Nemotron {e["nemotron_correct"]}/{e["examples_per_model"]}; '
                     f'Snowball {e["snowball_correct"]}/{e["examples_per_model"]}. '
                     f'This example: Nemotron correct; Snowball {outcome}.</p>' +
                     '<p>Exact benchmark user prompt:</p><pre>' + esc(e['prompt']) + '</pre>' +
                     '<p>Expected answer:</p><pre>' + esc(e['answer']) + '</pre></details>')
    parts.append('<details><summary>All family comparisons</summary><p>' + esc(METHODS_REFERENCE) + '</p>')
    for condition, label in CONDITIONS.items():
        parts.extend(['<h4>' + esc(label) + '</h4>', table(condition)])
    parts.append('<p><a href="nemotron-snowball-families.json">JSON</a> · '
                 '<a href="nemotron-snowball-families.csv">CSV</a></p></details></section>')
    return ''.join(parts)
