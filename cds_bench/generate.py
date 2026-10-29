"""Generate ten solvable instances per task and both exact prompt variants."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .catalog import ROOT, SPEC_SHA256, TASKS, render
from .instances import Reject, make
from .sampling import Sampler, fit
from .solve import clean, solve

SEED = 20261029
FIELDS = [
    "id",
    "instance_id",
    "task_id",
    "variant",
    "prompt",
    "answer",
    "output_format",
    "inputs_json",
]


def canonical(value):
    return (
        value
        if isinstance(value, str)
        else json.dumps(value, sort_keys=True, separators=(",", ":"))
    )


def generate(source_directory: Path, output: Path, count: int = 10, seed: int = SEED):
    output.mkdir(parents=True, exist_ok=True)
    models = fit(source_directory)
    (output / "fitted-models.json").write_text(
        json.dumps(models, sort_keys=True, separators=(",", ":")) + "\n"
    )
    records, report, seen_cds = [], {}, set()
    for task_id, definition in TASKS.items():
        rejected = Counter()
        instances = []
        for index in range(count):
            # Each question has its own RNG stream. Rejections for one task do
            # not change any other task's examples.
            entropy = int.from_bytes(
                hashlib.sha256(f"{seed}/{task_id}/{index}".encode()).digest()[:16], "big"
            )
            rng = np.random.Generator(np.random.PCG64(entropy))
            sampler = Sampler(models, rng)
            for attempt in range(1000):
                try:
                    inputs = make(task_id, sampler, rng, index)
                    if set(inputs) != set(definition["example_inputs"]):
                        raise KeyError(f"Input fields do not match {task_id}: {inputs.keys()}")
                    answer = solve(task_id, inputs)
                    if answer in (None, "IMPOSSIBLE", "NONE"):
                        raise Reject("No positive feasible answer")
                    if answer == [] and task_id not in {"cds.validate", "stats.gc_windows"}:
                        raise Reject("Empty readout")
                    cds = [
                        clean(v)
                        for key, v in inputs.items()
                        if key in {"cds", "cds_a", "target_cds"}
                    ]
                    if any(c in seen_cds for c in cds):
                        raise Reject("Duplicate primary substrate")
                except (Reject, ValueError, StopIteration, AssertionError) as error:
                    # Only known generation/feasibility failures are retried;
                    # implementation errors such as KeyError remain fatal.
                    rejected[str(error) or type(error).__name__] += 1
                    continue
                seen_cds.update(cds)
                instance_id = f"{task_id}/{index + 1:02}"
                instances.append({"instance_id": instance_id, "inputs": inputs, "answer": answer})
                for variant in ["easy", "hard"]:
                    records.append(
                        {
                            "id": f"{instance_id}/{variant}",
                            "instance_id": instance_id,
                            "task_id": task_id,
                            "variant": variant,
                            "prompt": render(task_id, variant, inputs),
                            "answer": canonical(answer),
                            "output_format": definition["output_format"],
                            "inputs_json": json.dumps(
                                inputs, sort_keys=True, separators=(",", ":")
                            ),
                        }
                    )
                break
            else:
                raise RuntimeError(f"Could not generate {task_id}/{index}: {rejected}")
        report[task_id] = {"instances": count, "rejected_draws": dict(sorted(rejected.items()))}
        (output / "instances").mkdir(exist_ok=True)
        (output / "instances" / (task_id + ".json")).write_text(
            json.dumps(instances, indent=2) + "\n"
        )
        print(f"{task_id}: {count} instances; {sum(rejected.values())} rejected draws", flush=True)
    schema = pa.schema([(field, pa.string()) for field in FIELDS])
    table = pa.Table.from_pylist(records, schema=schema)
    (output / "data").mkdir(exist_ok=True)
    pq.write_table(table, output / "data/test.parquet", compression="zstd")
    with (output / "records.jsonl").open("w") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    summary = {
        "seed": seed,
        "spec_sha256": SPEC_SHA256,
        "task_count": len(TASKS),
        "instance_count": len(records) // 2,
        "prompt_count": len(records),
        "tasks": report,
        "records_sha256": hashlib.sha256((output / "records.jsonl").read_bytes()).hexdigest(),
        "parquet_sha256": hashlib.sha256((output / "data/test.parquet").read_bytes()).hexdigest(),
    }
    (output / "generation-report.json").write_text(json.dumps(summary, indent=2) + "\n")
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=ROOT / "build/sources")
    parser.add_argument("--output", type=Path, default=ROOT / "build/dataset")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be positive")
    generate(args.sources, args.output, args.count, args.seed)


if __name__ == "__main__":
    main()
