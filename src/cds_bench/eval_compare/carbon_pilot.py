"""Publish the saved Carbon-X pilot with its original strict scores."""

import copy
import hashlib
import json
import statistics
from pathlib import Path

from cds_bench.eval_luna.io import save
from cds_bench.eval_luna.report import aggregate, outcome, public_record
from cds_bench.eval_luna.score import score_result

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / 'scratch/carbon-x-pilot-20261101-01'
KEY = 'carbon-x'
NOTE = (
    'Self-hosted upstream vLLM 0.25.1 on CoreWeave H100x8, BF16, with the native '
    'DNA tokenizer and chat template. Thinking is disabled; temperature 0.6, '
    'top-p 0.95, top-k 20 and min-p 0. The aggregate output budget is 32,768 '
    'tokens, the request deadline is 900 seconds, and concurrency is 32. '
    'This pilot retains strict scoring, unlike the error-compensated full-run '
    'scores. It has 104 answer-format failures. All three scored Python call '
    'attempts had malformed JSON arguments and failed before execution; '
    'a separate preflight verified real execution and result delivery. '
    'The API strict-JSON flag is omitted because the decoder does not support '
    'the custom tokenizer. No scored request is rerun or repaired.'
)


def read(path):
    return json.loads(path.read_text())


def build(output, cases, format_diagnostic):
    if not (RAW / 'summary.json').exists():
        return None
    config, status, audit = [read(RAW / name) for name in ['config.json', 'summary.json', 'audit.json']]
    assert status['state'] == 'complete' and status['completed'] == 116 and audit['passed']
    rows, durations = [], []
    originals = read(RAW / 'results.json')
    assert len({(row['instance_id'], row['condition']) for row in originals}) == 116
    for original in originals:
        directory = Path(original['trace_directory'])
        case = read(directory / 'case.json')
        expected = cases[original['instance_id'], original['variant']]
        assert all(case[key] == expected[key] for key in ['prompt', 'answer', 'task_id', 'output_format'])
        text = (directory / 'answer.txt').read_text()
        assert not original.get('request_timeout') and original['completion_tokens'] <= 32768
        if original.get('api_error'):
            assert not original['passed']
            responses = sorted(directory.glob('response-*.json'))
            assert read(responses[-1])['http_status'] == 400
            assert any(read(path)['result'].get('error') for path in directory.glob('tool-*.json'))
        else:
            assert score_result(case, text, original['finish_reason'])['passed'] == original['passed']
        durations.extend(read(path)['elapsed_seconds'] for path in directory.glob('response-*.json'))
        row = dict(original, expected_answer=case['answer'], output_format=case['output_format'],
                   cost_usd=0, billing_complete=False)
        row['outcome'] = outcome(row)
        exported = {key: value for key, value in public_record(row).items() if key in row}
        if exported.get('error'):
            exported['error'] = {
                'error': 'Malformed native tool call', 'timeout': 'API deadline exceeded',
                'token_cap': 'Generated-token budget exhausted',
                'format': 'Final answer does not satisfy the required format',
                'wrong': 'Incorrect value',
            }[row['outcome']]
        exported['cost_usd'] = None
        rows.append(dict(exported, model=KEY,
                         format_diagnostic_exact=format_diagnostic(case, row, text)))

    def metrics(subset):
        result = aggregate([dict(row, cost_usd=0) for row in subset])
        result['cost_usd'] = None
        return result

    totals = metrics(rows)
    assert totals == status['totals']
    conditions = {condition: metrics([row for row in rows if row['condition'] == condition])
                  for condition in status['conditions']}
    assert conditions == status['conditions']
    totals['median_api_request_seconds'] = statistics.median(durations)
    totals['format_diagnostic_additional_exact'] = sum(row['format_diagnostic_exact'] for row in rows)
    tools = copy.deepcopy(config['tools'])
    for tool in tools:
        tool['function'].pop('strict', None)
    settings = {
        'name': 'Carbon-X', 'model': config['model'], 'full_name': 'Carbon-X',
        'provenance': {'repo': config['model'], 'revision': config['model_revision'],
            'url': f"https://huggingface.co/{config['model']}/tree/{config['model_revision']}"},
        'provider': {'only': ['CoreWeave/vLLM'], 'allow_fallbacks': False},
        'reasoning': config['reasoning'], 'parameters_no_tools': config['parameters_no_tools'],
        'tools': tools, 'backend': config['backend'], 'aggregate_completion_token_budget': 32768,
        'request_timeout_seconds': config['request_timeout_seconds'], 'concurrency': config['concurrency'],
        'dataset_revision': config['dataset_revision'], 'state': 'complete', 'stop_reason': None,
        'scoring': 'Original strict scorer; no error compensation applied to primary pilot scores.',
        'tool_audit': {'preflight_passed': audit['python_tool_round_trip_verified'],
                       'malformed_scored_calls': audit['malformed_model_calls_rejected_on_replay'],
                       'scored_python_executions': 0},
        'raw_traces': read(RAW / 'trace-publication.json'),
    }
    save(output / 'carbon-x-audit.json', {**audit, 'original_strict_scores_verified': True,
        'raw_traces': settings['raw_traces'],
        'source_sha256': {name: hashlib.sha256((RAW / name).read_bytes()).hexdigest()
                          for name in ['config.json', 'results.json', 'selected.json']}})
    return rows, totals, conditions, settings


def markdown_note(summary, base):
    if KEY not in summary['models']:
        return ''
    metric = summary['totals'][KEY]
    return (
        f"Carbon-X is shown with strict pilot scoring ({metric['correct']}/{metric['attempted']}), "
        'unlike its error-compensated full-run scores. It had '
        f"{metric['format']} answer-format failures and three malformed Python call attempts; "
        'a separate preflight verified the tool round trip. It used thinking off and a '
        '900-second request deadline on self-hosted CoreWeave/vLLM. '
        f'[Pilot audit and traces]({base}/carbon-x-audit.json).'
    )
