"""Publish the reviewed Parquet dataset and checksum-verifiable source snapshot."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from huggingface_hub import HfApi

from .catalog import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="open-athena/cds-bench")
    parser.add_argument("--dataset", type=Path, default=ROOT / "build/dataset")
    parser.add_argument("--sources", type=Path, default=ROOT / "build/sources")
    args = parser.parse_args()
    report = json.loads((args.dataset / "generation-report.json").read_text())
    assert report["instance_count"] == 840 and report["prompt_count"] == 1680
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    staging = ROOT / "build/hub"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "data").mkdir(exist_ok=True)
    (staging / "sources").mkdir(exist_ok=True)
    for variant in ["easy", "hard"]:
        assert report["splits"][variant]["num_rows"] == 840
        shutil.copyfile(
            args.dataset / f"data/{variant}.parquet", staging / f"data/{variant}.parquet"
        )
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

This release has 840 instances (10 per task), each rendered as easy and hard
prompts with the same answer: 840 rows in `easy` and 840 rows in `hard`.
The splits are two reference-support conditions for the same questions.

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
        commit_message="Separate easy and hard evaluation splits",
    )
    print(commit.commit_url)


if __name__ == "__main__":
    main()
