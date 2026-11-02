"""Reproduce the mass-constant revision locally; this script never uploads.

Download this script and 2026-11-02-mass-constants.json into one directory.
Use pyarrow==26.0.0 for byte-identical Parquet output:

    python apply_mass_constants.py --output ./reproduced

--source DIRECTORY uses previously downloaded data/{easy,hard}.parquet offline.
"""

import argparse
import hashlib
import json
import re
import urllib.request
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from itertools import product
from pathlib import Path


TASKS = {
    "protein.monoisotopic_mass",
    "pipeline.protein_properties",
    "pipeline.tag_cleave_mass",
}
CODE = dict(zip(map("".join, product("TCAG", repeat=3)),
    "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"))
STARTS = {"TTG", "CTG", "ATT", "ATC", "ATA", "ATG", "GTG"}


def constants_text(patch):
    labels = {"C": "12C", "H": "1H", "N": "14N", "O": "16O", "S": "32S"}
    atoms = "\n".join(f"{labels[a]} = {v}" for a, v in patch["isotope_masses"].items())
    return (
        "## Mass constants\n\n"
        "Use these isotope masses in Da as exact decimal constants:\n\n"
        "```text\n" + atoms + "\n```\n\n"
        "For a neutral, unmodified linear peptide, sum the neutral free-amino-acid "
        "molecular formulas and subtract one H2O for each peptide bond. "
        "Equivalently, sum the incorporated residue masses and add one H2O "
        "for the complete peptide. Do not round intermediate values.\n\n"
    )


def residue_table(patch):
    entries = list(patch["residue_masses"].items())
    return "\n".join("  ".join(f"{a}={v}" for a, v in entries[i:i+4])
                     for i in range(0, len(entries), 4))


def residue_text(patch):
    return (
        "### Monoisotopic residue masses\n\n"
        "Use these incorporated residue masses in Da as exact decimal constants. "
        "Each is the corresponding neutral free amino acid minus one H2O.\n\n"
        "```text\n" + residue_table(patch) + "\n```\n\n"
        "Add one H2O = " + patch["water_mass"] + " Da for the complete free linear peptide.\n\n"
    )


def revise_prompt(prompt, variant, patch):
    assert "## Mass constants" not in prompt
    if variant == "easy":
        prompt, count = re.subn(
            r"### Monoisotopic residue masses\n.*?(?=\n### |\n## |\Z)",
            lambda _: residue_text(patch).rstrip() + "\n",
            prompt, flags=re.S,
        )
        assert count == 1
    marker = "## Reference material\n" if "## Reference material\n" in prompt else "## Answer\n"
    prompt = prompt.replace(marker, constants_text(patch) + marker, 1)
    prompt = prompt.replace(
        "- Use the monoisotopic residue masses and include one water molecule for the complete peptide.",
        "- Use the mass constants below, including the complete peptide's free termini.",
    )
    assert not re.search(r"https?://|Snapshot accessed|NIST", prompt)
    return prompt


def translate(sequence):
    sequence = "".join(sequence.split()).upper()
    amino_acids = []
    for i in range(0, len(sequence)-2, 3):
        codon = sequence[i:i+3]
        aa = "M" if i == 0 and codon in STARTS else CODE[codon]
        if aa == "*": break
        amino_acids.append(aa)
    return "".join(amino_acids)


def peptide_mass(peptide, patch):
    value = sum(Decimal(patch["residue_masses"][a]) for a in peptide)
    return (value + Decimal(patch["water_mass"])).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )


def revise_answer(row, patch):
    if row["task_id"] == "protein.monoisotopic_mass":
        peptide = translate(json.loads(row["inputs_json"])["cds"])
        value = peptide_mass(peptide, patch)
        return row["answer"] if Decimal(row["answer"]) == value else str(value)
    before = json.loads(row["answer"])
    after = json.loads(row["answer"])
    if row["task_id"] == "pipeline.protein_properties":
        peptide = translate(json.loads(row["inputs_json"])["cds"])
        after["mass_da"] = float(peptide_mass(peptide, patch))
    elif row["task_id"] == "pipeline.tag_cleave_mass":
        for fragment in after["fragments"]:
            fragment["mass_da"] = float(peptide_mass(fragment["peptide"], patch))
    else: raise ValueError(row["task_id"])
    return row["answer"] if after == before else json.dumps(after, sort_keys=True, separators=(",", ":"))


def revise_records(rows, patch):
    changed_prompts, changed_answers = [], []
    for row in rows:
        if row["task_id"] not in TASKS: continue
        before = row["answer"]
        row["prompt"] = revise_prompt(row["prompt"], row["variant"], patch)
        row["answer"] = revise_answer(row, patch)
        changed_prompts.append(row["id"])
        if before != row["answer"]:
            changed_answers.append({"id": row["id"], "before": before, "after": row["answer"]})
    return changed_prompts, changed_answers


def main():
    import pyarrow as pa
    import pyarrow.parquet as pq

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patch", type=Path, default=Path(__file__).with_name("2026-11-02-mass-constants.json"))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    patch = json.loads(args.patch.read_text())
    out = args.output / "data"
    out.mkdir(parents=True, exist_ok=True)
    summary = {"rows": {}, "changed_prompts": [], "changed_answers": [], "sha256": {}}
    for split in ["easy", "hard"]:
        if args.source:
            raw = (args.source / "data" / f"{split}.parquet").read_bytes()
        else:
            url = (f'https://huggingface.co/datasets/{patch["source_dataset"]}/resolve/'
                   f'{patch["source_revision"]}/data/{split}.parquet')
            raw = urllib.request.urlopen(url, timeout=120).read()
        assert hashlib.sha256(raw).hexdigest() == patch["source_parquet_sha256"][split]
        table = pq.read_table(pa.BufferReader(raw))
        rows = table.to_pylist()
        prompts, answers = revise_records(rows, patch)
        pq.write_table(pa.Table.from_pylist(rows, schema=table.schema), out/f"{split}.parquet", compression="zstd")
        digest = hashlib.sha256((out/f"{split}.parquet").read_bytes()).hexdigest()
        if patch.get("output_parquet_sha256"):
            assert digest == patch["output_parquet_sha256"][split]
        summary["rows"][split] = len(rows)
        summary["changed_prompts"].extend(prompts)
        summary["changed_answers"].extend(answers)
        summary["sha256"][split] = digest
    assert len(summary["changed_prompts"]) == 60
    assert len(summary["changed_answers"]) == 2
    (args.output/"mass-update-summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "changed_prompts"}, indent=2))


if __name__ == "__main__": main()
