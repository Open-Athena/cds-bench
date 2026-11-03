"""Executor checks; integration tests use an explicitly supplied tool runtime."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cds_bench import python_executor as executor


class AvailabilityTests(unittest.TestCase):
    def test_no_unsandboxed_fallback(self):
        with patch.object(executor, "SANDBOX_EXEC", Path("/nonexistent/sandbox-exec")):
            with self.assertRaisesRegex(RuntimeError, "requires macOS"):
                executor.execute("print(42)", "unused", python=sys.executable)


@unittest.skipUnless(
    sys.platform == "darwin" and os.environ.get("CDS_BENCH_TEST_PYTHON"),
    "Set CDS_BENCH_TEST_PYTHON to a dedicated macOS Python + NumPy interpreter",
)
class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.work = self.root / "example"
        self.python = Path(os.environ["CDS_BENCH_TEST_PYTHON"]).absolute()

    def run_code(self, code, **kwargs):
        return executor.execute(code, self.work, python=self.python, **kwargs)

    def test_numpy_is_available(self):
        result = self.run_code("import numpy as np; print(np.arange(5).sum())")
        self.assertEqual(result["exit_code"], 0, result)
        self.assertEqual(result["stdout"], "10\n")

    def test_restrictions(self):
        healthy = self.run_code("pass")
        self.assertEqual(healthy["exit_code"], 0, healthy)
        private = self.root / "private.txt"
        private.write_text("outside the example")
        checks = {
            "network": "import socket; socket.socket().bind(('127.0.0.1', 0))",
            "fork": "import os; pid = os.fork(); os._exit(0) if pid == 0 else os.waitpid(pid, 0)",
            "subprocess": "import subprocess; subprocess.run(['/bin/echo', 'unexpected'], check=True)",
            "private_read": f"open({str(private)!r}).read()",
            "outside_write": f"open({str(private)!r}, 'w').write('unexpected')",
            "repository_read": f"open({str(Path(__file__).resolve())!r}).read()",
            "biopython": "import Bio",
        }
        for name, code in checks.items():
            with self.subTest(name=name):
                result = self.run_code(code)
                self.assertNotEqual(result["exit_code"], 0, result)
                self.assertTrue(result["stderr"], result)
        self.assertEqual(private.read_text(), "outside the example")

    def test_fresh_interpreter_with_persistent_example_files(self):
        result = self.run_code("value = 42; open('saved.txt', 'w').write('42')")
        self.assertEqual(result["exit_code"], 0, result)
        result = self.run_code("print(open('saved.txt').read()); print('value' in globals())")
        self.assertEqual(result["stdout"], "42\nFalse\n")

    def test_parent_credentials_are_not_inherited(self):
        with patch.dict(os.environ, {"CDS_BENCH_TEST_SECRET": "should-not-be-inherited"}):
            result = self.run_code("import os; print(os.environ.get('CDS_BENCH_TEST_SECRET'))")
        self.assertEqual(result["exit_code"], 0, result)
        self.assertEqual(result["stdout"], "None\n")

    def test_wall_timeout(self):
        result = self.run_code("import time; time.sleep(10)", timeout=0.2)
        self.assertTrue(result["timed_out"], result)
        self.assertNotEqual(result["exit_code"], 0, result)

    def test_output_limits_and_execution_errors(self):
        result = self.run_code("import sys; print('x' * 20000); print('y' * 20000, file=sys.stderr)")
        self.assertEqual(result["exit_code"], 0, result)
        self.assertTrue(result["output_truncated"], result)
        self.assertEqual(len(result["stdout"]), executor.OUTPUT_LIMIT)
        self.assertEqual(len(result["stderr"]), executor.OUTPUT_LIMIT)
        result = self.run_code("raise ValueError('test error')")
        self.assertNotEqual(result["exit_code"], 0, result)
        self.assertIn("ValueError: test error", result["stderr"])


if __name__ == "__main__":
    unittest.main()
