"""Stream standard vLLM chat replies and retain complete request/tool traces."""

import asyncio
import copy
import json
import time
from pathlib import Path

from cds_bench.eval_luna.io import save

ACCESS_FILE = None
REQUEST_TIMEOUT = 900


def configure_access(path):
    global ACCESS_FILE
    ACCESS_FILE = Path(path)


class RequestFailure(Exception):
    def __init__(self, message, response):
        super().__init__(message)
        self.response = response


async def api_call(client, directory, number, body, key):
    if ACCESS_FILE is None:
        raise RuntimeError('Configure the private Carbon-X access file before inference')
    access = json.loads(ACCESS_FILE.read_text())
    base = access['base_url'].rstrip('/')
    payload = copy.deepcopy(body)
    payload['model'] = access['model_id']
    if not payload.get('tools'):
        payload.pop('tools', None)
        payload.pop('tool_choice', None)
    else:
        # xgrammar rejects this release's slow HybridDNATokenizer. Preserve
        # the function and argument schema, using native unconstrained calls.
        for tool in payload['tools']:
            tool['function'].pop('strict', None)
    save(directory / f'request-{number:02}.json', payload)
    meta = {'request_number': number, 'request_max_tokens': payload['max_tokens']}
    started = time.monotonic()
    text, reasoning, calls = [], [], {}
    done = False
    error = None

    def redact(value):
        return value.replace(base, '[PRIVATE_API]')

    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):
            async with client.stream('POST', base + '/chat/completions', json=payload) as stream:
                meta['http_status'] = stream.status_code
                if stream.status_code != 200:
                    raise RuntimeError(f'HTTP {stream.status_code}: ' + redact((await stream.aread()).decode(errors='replace')))
                with (directory / f'response-{number:02}.sse').open('w') as log:
                    async for line in stream.aiter_lines():
                        line = redact(line)
                        log.write(line + '\n')
                        log.flush()
                        if not line.startswith('data:'):
                            continue
                        value = line[5:].strip()
                        if value == '[DONE]':
                            done = True
                            break
                        if not value:
                            continue
                        event = json.loads(value)
                        if event.get('error'):
                            raise RuntimeError(str(event['error']))
                        for name in ['id', 'model', 'usage']:
                            if event.get(name) is not None:
                                meta[name] = event[name]
                        for choice in event.get('choices', []):
                            if choice.get('error') or choice.get('finish_reason') == 'error':
                                raise RuntimeError(str(choice.get('error') or 'Serving error'))
                            if choice.get('finish_reason'):
                                meta['finish_reason'] = choice['finish_reason']
                            delta = choice.get('delta') or {}
                            text.append(delta.get('content') or '')
                            reasoning.append(delta.get('reasoning_content') or delta.get('reasoning') or '')
                            for piece in delta.get('tool_calls') or []:
                                call = calls.setdefault(piece['index'], {'id': '', 'type': 'function', 'function': {'name': '', 'arguments': ''}})
                                call['id'] += piece.get('id') or ''
                                for field in ['name', 'arguments']:
                                    call['function'][field] += (piece.get('function') or {}).get(field) or ''
        if not done or not meta.get('finish_reason') or not meta.get('usage'):
            raise RuntimeError('Stream ended without DONE, terminal finish reason and usage')
        if meta.get('model') != access['model_id']:
            raise RuntimeError('Unexpected served model ID')
    except TimeoutError:
        meta['request_timeout'] = True
        error = '900-second API transaction deadline exceeded'
    except Exception as exc:
        error = redact(f'{type(exc).__name__}: {exc}')
    message = {'role': 'assistant', 'content': ''.join(text) or None, 'tool_calls': [calls[i] for i in sorted(calls)]}
    if any(reasoning):
        message['reasoning_content'] = ''.join(reasoning)
    meta.update(message=message, reasoning_summary=''.join(reasoning),
                elapsed_seconds=time.monotonic() - started, stream_done=done, error=error)
    save(directory / f'response-{number:02}.json', meta)
    if error:
        raise RequestFailure(error, meta)
    return meta
