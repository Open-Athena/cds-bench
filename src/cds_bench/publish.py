"""Publish the reviewed Parquet dataset and checksum-verifiable source snapshot."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import HfApi

from .catalog import ROOT, SPEC_SHA256, TASKS, variants


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="open-athena/cds-bench")
    parser.add_argument("--dataset", type=Path, default=ROOT / "build/dataset")
    parser.add_argument("--sources", type=Path, default=ROOT / "build/sources")
    args = parser.parse_args()
    report = json.loads((args.dataset / "generation-report.json").read_text())
    if report["spec_sha256"] != SPEC_SHA256 or set(report["tasks"]) != set(TASKS):
        raise ValueError("Regenerate the dataset from the current task specification")
    expected = {variant: 0 for variant in ["easy", "hard"]}
    for task_id, task in report["tasks"].items():
        if task["variants"] != list(variants(task_id)):
            raise ValueError(f"Outdated prompt variants for {task_id}")
        for variant in task["variants"]:
            expected[variant] += task["instances"]
    if report["instance_count"] != sum(
        task["instances"] for task in report["tasks"].values()
    ) or report["prompt_count"] != sum(expected.values()):
        raise ValueError("Generation counts do not match the task inventory")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    staging = ROOT / "build/hub"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "data").mkdir(exist_ok=True)
    (staging / "sources").mkdir(exist_ok=True)
    for variant in ["easy", "hard"]:
        path = args.dataset / f"data/{variant}.parquet"
        split = report["splits"][variant]
        if (
            split["num_rows"] != expected[variant]
            or pq.read_metadata(path).num_rows != expected[variant]
            or hashlib.sha256(path.read_bytes()).hexdigest() != split["parquet_sha256"]
        ):
            raise ValueError(f"Unverified {variant} split")
        shutil.copyfile(path, staging / f"data/{variant}.parquet")
    (staging / "data/test.parquet").unlink(missing_ok=True)
    for path in sorted(args.sources.glob("*.fna.gz")):
        shutil.copyfile(path, staging / "sources" / path.name)
    schema = (
        (ROOT / "generation/README.md")
        .read_text()
        .split("| Field | Meaning |", 1)[1]
        .split("\n\n", 1)[0]
    )
    card = f"""---
language:
- en
configs:
- config_name: default
  data_files:
  - split: easy
    path: data/easy.parquet
  - split: hard
    path: data/hard.parquet
---

# CDS-bench

Synthetic evaluation data for [CDS-bench](https://openathena.ai/cds-bench/).
See the benchmark site for task definitions, prompt variants, and scoring.

This release has {report["instance_count"]:,} instances across {report["task_count"]}
task types: {expected["easy"]:,} rows in `easy` and {expected["hard"]:,} rows in `hard`.
Easy and hard differ in supplied biological reference material, with the same
inputs and answer. When those prompts would be identical, only the `easy` copy
is retained. Paired easy/hard comparisons should use the
{report["paired_task_count"]} task types present in both splits.

All fields are strings. `answer` is the final answer payload, without the
`Final answer:` marker or an explanation. Structured answers are JSON text.
`inputs_json` contains the complete task input object.

| Field | Meaning |{schema}

[Acquisition and generation code](https://github.com/Open-Athena/cds-bench/tree/{revision}/generation)
records the source accessions, checksums, sampling rules, and fixed seed. The
`sources/` directory preserves the original CDS FASTA snapshot for regeneration.
"""
    (staging / "README.md").write_text(card)
    token = os.environ.get("HUGGING_FACE_HUB_TOKEN") or os.environ.get("HF_TOKEN")
    api = HfApi(token=token)
    api.create_repo(args.repo, repo_type="dataset", private=False, exist_ok=True)
    commit = api.upload_folder(
        repo_id=args.repo,
        repo_type="dataset",
        folder_path=staging,
        delete_patterns=["data/test.parquet"],
        commit_message="Remove redundant hard prompt variants",
    )
    print(commit.commit_url)


if __name__ == "__main__":
    main()
