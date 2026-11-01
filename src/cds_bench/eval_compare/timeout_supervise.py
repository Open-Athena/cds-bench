"""Continue pending timeout recovery with backoff and no total attempt limit."""

import fcntl
import json
import os
import subprocess
import sys
import time

from cds_bench.eval_luna.io import save
from cds_bench.eval_luna.run import now

from .retry_timeouts import RAW, ROOT, EXPECTED, prepare, retryable_request_failure


def read(path):
    return json.loads(path.read_text())


def alive(launch):
    process = subprocess.run(["ps", "-p", str(launch['pid']), "-o", "command="],
                             capture_output=True, text=True)
    return process.returncode == 0 and 'cds_bench.eval_compare.retry_timeouts' in process.stdout


def launch_worker(model, ceiling, pending):
    directory = RAW / model
    directory.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-m', 'cds_bench.eval_compare.retry_timeouts',
               '--model', model, '--max-attempts', str(ceiling)]
    with (directory / 'execution.log').open('ab') as log:
        child = subprocess.Popen(command, cwd=ROOT,
            env=dict(os.environ, PYTHONPATH=str(ROOT/'src')),
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    event = {'pid':child.pid,'command':command,'started_at':now(),'previous_pending':pending}
    save(directory / 'current-launch.json', event)
    with (directory / 'launch-history.jsonl').open('a') as history:
        history.write(json.dumps(event)+'\n')


def main():
    prepare()
    with (RAW / 'supervisor.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        save(RAW / 'retry-policy.json', {
            'recorded_at': now(), 'overall_attempt_limit': None,
            'request_deadline_seconds': 900, 'resume_backoff_seconds': 60,
            'policy': 'Timeouts and transient transport/provider failures in the selected recovery cases are unscored. Bounded worker batches do not limit total retries. Resume pending cases after backoff; never turn repeated timeouts into failures. Completed answers are final. Keep the same provider.',
        })
        next_resume = {}
        while True:
            states = {}
            for model in EXPECTED:
                directory = RAW / model
                if not (directory / 'job-status.json').exists():
                    launch = directory / 'current-launch.json'
                    if not launch.exists() or not alive(read(launch)):
                        launch_worker(model, 3, EXPECTED[model])
                    states[model] = {'state':'starting'}
                    continue
                status = read(directory / 'job-status.json')
                states[model] = status
                if status['state'] == 'complete':
                    failures = [r for r in read(directory/'selected.json') if retryable_request_failure(r)]
                    if not failures:
                        continue
                    status = dict(status, state='pending-timeouts',
                                  selected=status['selected']-len(failures))
                    save(directory/'job-status.json', status)
                    states[model] = status
                launch_path = directory / 'current-launch.json'
                launch = read(launch_path if launch_path.exists() else directory / 'launch.json')
                if alive(launch):
                    continue
                if status['state'] != 'pending-timeouts':
                    save(RAW / 'supervisor-status.json', {'state':'needs-review','updated_at':now(),
                         'model':model,'reason':'Worker ended unexpectedly; preserve interrupted requests for review.',
                         'models':states})
                    return
                next_resume.setdefault(model, time.monotonic() + 60)
                if time.monotonic() < next_resume[model]:
                    continue
                ceiling = status['max_attempts'] + 3
                launch_worker(model, ceiling, status['planned']-status['selected'])
                next_resume.pop(model, None)
            complete = all(s['state']=='complete' for s in states.values())
            save(RAW / 'supervisor-status.json', {'state':'complete' if complete else 'watching',
                 'updated_at':now(),'models':states,'overall_attempt_limit':None})
            if complete:
                return
            time.sleep(20)


if __name__ == '__main__':
    main()
