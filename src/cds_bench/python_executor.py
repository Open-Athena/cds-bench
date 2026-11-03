"""Run Python under the macOS sandbox used for the PR #2 evaluations.

The caller supplies a dedicated Python environment and an example workdir.
Each call starts a fresh interpreter; files persist within that workdir.
"""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

SANDBOX_EXEC = Path("/usr/bin/sandbox-exec")
TIMEOUT_SECONDS = 30
OUTPUT_LIMIT = 16384
LAUNCHER = """import resource,sys
resource.setrlimit(resource.RLIMIT_CPU,(30,30))
resource.setrlimit(resource.RLIMIT_FSIZE,(1048576,1048576))
resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
code=sys.stdin.read()
exec(compile(code,"<python-tool>","exec"),{"__name__":"__main__"})
"""


def profile(directory, python):
    """Allow runtime and workdir reads; deny network access and process forks."""
    runtime = python.parent.parent
    readable = [
        python.resolve().parents[1],
        runtime,
        directory,
        "/System",
        "/usr/lib",
        "/usr/share",
        "/System/Volumes/Preboot/Cryptexes/OS/usr/lib",
        "/private/var/db/dyld",
        "/dev",
    ]
    q = lambda p: json.dumps(str(Path(p).resolve()))
    exclusions = "\n".join("(require-not (subpath " + q(p) + "))" for p in readable)
    return f"""(version 1)
(allow default)
(deny network*)
(deny process-fork)
(deny file-read-data (require-all (require-not (literal "/")) {exclusions}))
(deny file-write* (require-all
    (require-not (subpath {q(directory)}))
    (require-not (literal "/dev/null"))))
"""


def execute(code, directory, *, python, timeout=TIMEOUT_SECONDS):
    """Execute code with a 30-second CPU limit and a configurable wall deadline.

    ``python`` is the executable inside a dedicated virtual environment. Only
    that environment, its base runtime, system paths and ``directory`` are
    readable. The subprocess receives a minimal environment without caller
    credentials. Writes are restricted to the example directory and /dev/null.

    Returns stdout, stderr, exit_code, timed_out and output_truncated. Each
    output stream is limited to 16,384 bytes in the returned result. A missing
    sandbox raises an error; execution never falls back to unsandboxed Python.
    """
    if sys.platform != "darwin" or not SANDBOX_EXEC.is_file():
        raise RuntimeError("Python execution requires macOS /usr/bin/sandbox-exec")
    python = Path(python).absolute()
    if not python.is_file():
        raise FileNotFoundError(f"Python interpreter not found: {python}")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "sandbox.sb"
    path.write_text(profile(directory, python))
    environment = {
        "PATH": str(python.parent) + ":/usr/bin:/bin",
        "HOME": str(directory),
        "TMPDIR": str(directory),
        "LANG": "C.UTF-8",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
    }
    stdout_path = directory / "stdout.log"
    stderr_path = directory / "stderr.log"
    timed_out = False
    with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
        child = subprocess.Popen(
            [str(SANDBOX_EXEC), "-f", str(path), str(python), "-I", "-B", "-c", LAUNCHER],
            cwd=directory,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=out,
            stderr=err,
            start_new_session=True,
        )
        try:
            child.communicate(code.encode(), timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
    output = stdout_path.read_bytes()
    errors = stderr_path.read_bytes()
    return {
        "stdout": output[:OUTPUT_LIMIT].decode(errors="replace"),
        "stderr": errors[:OUTPUT_LIMIT].decode(errors="replace"),
        "exit_code": child.returncode,
        "timed_out": timed_out,
        "output_truncated": len(output) > OUTPUT_LIMIT or len(errors) > OUTPUT_LIMIT,
    }
