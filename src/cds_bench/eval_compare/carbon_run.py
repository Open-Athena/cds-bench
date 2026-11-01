"""Full Carbon-X evaluation with frozen answer-format normalization rules."""

import argparse
import asyncio
import copy
import fcntl
import hashlib
import importlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx

from cds_bench.eval_luna import sandbox
from cds_bench.eval_luna.io import save
from cds_bench.eval_luna.report import aggregate, outcome
from cds_bench.eval_luna.run import validate_sandbox
from cds_bench.eval_luna.settings import TOOLS

from . import carbon_client
from .carbon_score import VERSION, score_normalized
from .run import HASHES, PLANNED, REVISION, ROOT

RAW = ROOT / 'scratch/carbon-x-full-20261101-01'
CONDITIONS = [('easy', False), ('hard', False), ('easy', True), ('hard', True)]
CONCURRENCY = 32
MODEL = 'HuggingFaceBio/Carbon-X'
MODEL_REVISION = '17de89165e25c49e7de4f845d0e5d464469de359'
runtime = importlib.import_module('cds_bench.eval_luna.trial')


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def parameters():
    return {'model': MODEL, 'max_tokens': 32768, 'temperature': 0.6, 'top_p': 0.95,
            'top_k': 20, 'min_p': 0.0, 'seed': 20261029,
            'chat_template_kwargs': {'enable_thinking': False},
            'stream': True, 'stream_options': {'include_usage': True}}


def prepare(raw, access_file):
    raw.mkdir(parents=True, exist_ok=True)
    rows = read(ROOT / 'scratch/qwen37-flash-high-full-20261029-01/dataset.json')
    assert {variant: len(cases) for variant, cases in rows.items()} == {'easy': 840, 'hard': 790}
    assert all(count == 10 for cases in rows.values() for count in Counter(row['task_id'] for row in cases).values())
    for variant, cases in rows.items():
        assert all(row['variant'] == variant for row in cases)
    tools = copy.deepcopy(TOOLS)
    tools[0]['function'].pop('strict', None)
    source_paths = [Path(__file__), Path(__file__).with_name('carbon_client.py'),
                    Path(__file__).with_name('carbon_score.py'),
                    ROOT / 'src/cds_bench/eval_luna/trial.py',
                    ROOT / 'src/cds_bench/eval_luna/score.py',
                    ROOT / 'src/cds_bench/eval_luna/sandbox.py']
    config = {
        'model': MODEL, 'model_revision': MODEL_REVISION,
        'planned': 3260, 'planned_per_condition': PLANNED,
        'parameters_no_tools': parameters(), 'tools': tools, 'tool_choice': 'auto',
        'aggregate_completion_token_budget': 32768, 'request_timeout_seconds': 900,
        'max_tool_calls': 8, 'concurrency': CONCURRENCY,
        'dataset': {'repo': 'open-athena/cds-bench', 'revision': REVISION,
                    'parquet_sha256': HASHES, 'snapshot_sha256': hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()},
        'normalization': {'version': VERSION, 'strict_scores_also_saved': True,
            'description': 'Read a clearly labeled final answer despite capitalization, Markdown or same-line placement. Without a label, accept a complete response or a final self-contained data/code block. Remove Markdown wrappers and native DNA boundary tags. Convert JSON-shaped Python literals without execution. Preserve sequence content, numerical values, field names and list order; truncation remains failure. No reference answer is used for extraction.'},
        'backend': {'kind': 'vllm', 'version': '0.25.1', 'dtype': 'bfloat16',
                    'gpu': 'H100x8', 'tensor_parallel_size': 1, 'data_parallel_size': 8,
                    'max_model_len': 40960, 'compilation_and_cuda_graphs': True,
                    'tool_parser': 'hermes', 'reasoning_parser': 'qwen3'},
        'tool_compatibility': 'The API strict flag is omitted because xgrammar does not support the custom HybridDNATokenizer. Function, description, argument schema and sandbox match the other evaluations. No demonstration or forced execution.',
        'execution_environment': {'python': '3.12.9', 'numpy': '2.5.4', 'biopython': False,
            'network': 'macOS sandbox deny network*', 'subprocesses': False,
            'tool_wall_seconds': 30, 'max_output_bytes_per_stream': 16384},
        'sampling': 'Fresh attempts on all released cases; no pilot-response reuse, prompt changes, correctness feedback or resampling of completed answers.',
        'transport_policy': 'Incomplete or timed-out transactions are unscored. Retry with backoff or pause for service review; never convert an unresolved transaction to an incorrect answer. Malformed model-generated calls are scored protocol failures.',
        'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths},
    }
    path = raw / 'config.json'
    if path.exists():
        old = read(path)
        assert {key: value for key, value in old.items() if key != 'source_commit'} == {key: value for key, value in config.items() if key != 'source_commit'}, 'Frozen inference or normalization configuration changed'
    else:
        save(path, config)
        save(raw / 'dataset.json', rows)
    carbon_client.configure_access(access_file)
    runtime.PARAMETERS = parameters()
    runtime.api_call = carbon_client.api_call
    runtime.RequestFailure = carbon_client.RequestFailure
    runtime.score_result = score_normalized
    sandbox.WORK_ROOT = ROOT / 'build/luna-tool-work' / raw.name
    return rows


def model_protocol_failure(row):
    if not row.get('api_error'):
        return False
    directory = Path(row['trace_directory'])
    responses = sorted(directory.glob('response-*.json'))
    last = read(responses[-1]) if responses else {}
    tools = [read(path) for path in directory.glob('tool-*.json')]
    return last.get('http_status') == 400 and any(tool['result'].get('error') for tool in tools)


def scorable(row):
    return not row.get('request_timeout') and (not row.get('api_error') or model_protocol_failure(row))


def saved_results(raw):
    chosen = {}
    for path in sorted(raw.glob('attempt-*/traces/*/*/result.json')):
        row = read(path)
        identity = row['instance_id'], row['condition']
        if scorable(row) and identity not in chosen:
            chosen[identity] = row
    for path in raw.glob('attempt-*/traces/*/*/request-01.json'):
        if not (path.parent / 'result.json').exists():
            raise RuntimeError(f'Interrupted transaction needs review before resuming: {path.parent}')
    return chosen


def refresh(raw, results, state, **updates):
    records = [dict(row, cost_usd=0, billing_complete=False) for row in results]
    conditions = {}
    for condition in PLANNED:
        metric = aggregate([row for row in records if row['condition'] == condition])
        metric['strict_correct'] = sum(bool(row.get('strict_passed')) for row in records if row['condition'] == condition)
        metric['cost_usd'] = None
        conditions[condition] = metric
    total = aggregate(records)
    total['cost_usd'] = None
    total['strict_correct'] = sum(bool(row.get('strict_passed')) for row in records)
    summary = {'model': 'Carbon-X†', 'state': state, 'updated_at': now(), 'planned': 3260,
               'completed': len(records), 'conditions': conditions, 'totals': total,
               'normalization_version': VERSION, **updates}
    save(raw / 'results.json', results)
    save(raw / 'summary.json', summary)
    save(raw / 'job-status.json', {key: summary[key] for key in ['model', 'state', 'updated_at', 'planned', 'completed']} | updates)


async def preflight(client, raw):
    if read(raw / 'tool-round-trip-verification.json', {}).get('passed'):
        return
    case = {'id': 'protocol/01/easy', 'instance_id': 'protocol/01', 'task_id': 'protocol',
            'variant': 'easy', 'output_format': 'scalar',
            'prompt': 'Use the python tool to calculate 123456789 * 987654321. You must execute Python before answering. After any explanation, write Final answer: on its own line, then the integer result on the next line.',
            'answer': '121932631112635269'}
    result = await runtime.trial(client, asyncio.Semaphore(1), 1, case, True, 'internal-no-api-key', raw / 'preflight')
    save(raw / 'preflight-result.json', result)
    assert not result.get('api_error') and result['tool_calls'] > 0 and result['tool_failures'] == 0, 'Stop: Python tool round trip did not work'
    directory = Path(result['trace_directory'])
    tools = [read(path) for path in directory.glob('tool-*.json')]
    assert any(tool['result'].get('stdout', '').strip() == case['answer'] for tool in tools)
    requests = [read(path) for path in sorted(directory.glob('request-*.json'))]
    assert any(message['role'] == 'tool' and case['answer'] in message['content'] for request in requests[1:] for message in request['messages'])
    assert case['answer'] in (directory / 'answer.txt').read_text()
    save(raw / 'tool-round-trip-verification.json', {'passed': True, 'executed_python': True, 'result_replayed': True, 'strict_answer_passed': result.get('strict_passed', False)})


async def evaluate(raw, data):
    chosen = saved_results(raw)
    refresh(raw, list(chosen.values()), 'preflight')
    async with httpx.AsyncClient(timeout=httpx.Timeout(900, connect=15), trust_env=False,
            limits=httpx.Limits(max_connections=CONCURRENCY, max_keepalive_connections=CONCURRENCY)) as client:
        await preflight(client, raw)
        for variant, tools in CONDITIONS:
            condition = variant + ('-tools' if tools else '-no-tools')
            stop = asyncio.Event()
            gate = asyncio.Semaphore(CONCURRENCY)
            refresh(raw, list(chosen.values()), 'running', phase=condition, phase_completed=sum(key[1] == condition for key in chosen))

            async def one(index, case):
                identity = case['instance_id'], condition
                if identity in chosen:
                    return None
                async with gate:
                    if stop.is_set():
                        return None
                    directory_name = f"{index:04}-{case['task_id']}-{case['instance_id'].rsplit('/', 1)[1]}"
                    previous = [int(path.name.split('-')[1]) for path in raw.glob('attempt-*') if (path / 'traces' / condition / directory_name).exists()]
                    start = max(previous, default=0) + 1
                    for number in range(start, start + 3):
                        row = await runtime.trial(client, asyncio.Semaphore(1), index, case, tools,
                            'internal-no-api-key', raw / f'attempt-{number:03}')
                        if scorable(row):
                            row.setdefault('strict_passed', False)
                            if model_protocol_failure(row):
                                row['model_tool_protocol_failure'] = True
                                save(Path(row['trace_directory']) / 'result.json', row)
                            return row
                        save(Path(row['trace_directory']) / 'unscored.json', {'scorable': False, 'retry_required': True, 'reason': 'Incomplete transport or operational API failure'})
                        # A disconnected backend may still be running. Pause until
                        # its completion/cancellation is verified before resampling.
                        if row.get('request_timeout') or not row.get('finish_reason'):
                            stop.set()
                            return None
                        await asyncio.sleep(min(2 ** number, 30))
                    stop.set()
                    return None

            for future in asyncio.as_completed([one(index, case) for index, case in enumerate(data[variant], 1)]):
                result = await future
                if result is not None:
                    identity = result['instance_id'], result['condition']
                    assert identity not in chosen
                    chosen[identity] = result
                refresh(raw, list(chosen.values()), 'needs-transport-review' if stop.is_set() else 'running',
                        phase=condition, phase_completed=sum(key[1] == condition for key in chosen))
            if stop.is_set():
                raise RuntimeError('Paused for transaction/service review; unresolved cases are unscored')
            assert sum(key[1] == condition for key in chosen) == PLANNED[condition]
    assert len(chosen) == 3260
    refresh(raw, list(chosen.values()), 'complete', finished_at=now())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-root', type=Path, default=RAW)
    parser.add_argument('--access-file', type=Path, required=True)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    raw = args.raw_root.resolve()
    raw.mkdir(parents=True, exist_ok=True)
    with (raw / 'driver.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            data = prepare(raw, args.access_file)
            if args.prepare:
                refresh(raw, list(saved_results(raw).values()), 'prepared')
                return
            validate_sandbox(raw / 'preparation')
            asyncio.run(evaluate(raw, data))
        except BaseException as exc:
            refresh(raw, list(saved_results(raw).values()), 'needs-review', error=f'{type(exc).__name__}: {exc}')
            raise


if __name__ == '__main__':
    main()
