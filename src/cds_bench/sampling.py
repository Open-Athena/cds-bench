"""Fit and sample a first-order codon Markov model per bacterial assembly.

Counts never span gene boundaries. Pair rows back off to the empirical codon
distribution with a pseudocount of 20. Only sense codons are sampled internally;
the empirical start/stop distribution supplies complete code-11 boundaries.
These sequences model coding composition, not functional proteins.
"""

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
from Bio import SeqIO
from Bio.Data import CodonTable

from .catalog import ROOT

CODE = CodonTable.unambiguous_dna_by_id[11]
CODONS = sorted(CODE.forward_table)
CODON_INDEX = {c: i for i, c in enumerate(CODONS)}


def fit(directory: Path) -> list[dict]:
    models = []
    for source in json.loads((ROOT / "generation/sources.json").read_text()):
        path = directory / (source["accession"] + ".fna.gz")
        raw = gzip.decompress(path.read_bytes())
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise ValueError(f"Source checksum mismatch: {path}")
        counts = np.zeros(61, dtype=np.int64)
        pairs = np.zeros((61, 61), dtype=np.int64)
        boundaries = Counter()
        lengths = Counter()
        accepted = 0
        with gzip.open(path, "rt") as handle:
            for record in SeqIO.parse(handle, "fasta"):
                seq = str(record.seq).upper()
                # These annotation cases require biology outside the benchmark's
                # complete, unexceptional, spliced CDS convention.
                if any(
                    t in record.description.lower()
                    for t in ("partial=", "transl_except=", "pseudo=true")
                ):
                    continue
                if len(seq) < 9 or len(seq) % 3 or set(seq) - set("ACGT"):
                    continue
                if seq[:3] not in CODE.start_codons or seq[-3:] not in CODE.stop_codons:
                    continue
                internal = [seq[i : i + 3] for i in range(3, len(seq) - 3, 3)]
                if any(c not in CODON_INDEX for c in internal):
                    continue
                encoded = np.array([CODON_INDEX[c] for c in internal])
                counts += np.bincount(encoded, minlength=61)
                np.add.at(pairs, (encoded[:-1], encoded[1:]), 1)
                boundaries[seq[:3] + seq[-3:]] += 1
                lengths[len(internal)] += 1
                accepted += 1
        models.append(
            {
                "accession": source["accession"],
                "accepted_cds": accepted,
                "codon_counts": counts.tolist(),
                "pair_counts": pairs.tolist(),
                "boundaries": dict(sorted(boundaries.items())),
                "internal_lengths": dict(sorted(lengths.items())),
            }
        )
    return models


class Sampler:
    def __init__(self, models: list[dict], rng: np.random.Generator):
        self.models = models
        self.rng = rng
        self.probabilities = []
        for model in models:
            counts = np.array(model["codon_counts"], dtype=float)
            unigram = (counts + 0.01) / (counts.sum() + 0.61)
            pairs = np.array(model["pair_counts"], dtype=float)
            conditional = (pairs + 20 * unigram) / (pairs.sum(axis=1)[:, None] + 20)
            self.probabilities.append((unigram, conditional))

    def cds(self, internal_codons: int, assembly_index: int | None = None) -> str:
        index = (
            int(self.rng.integers(len(self.models))) if assembly_index is None else assembly_index
        )
        model = self.models[index]
        p0, p1 = self.probabilities[index]
        keys = list(model["boundaries"])
        weights = np.array(list(model["boundaries"].values()), dtype=float)
        start_stop = keys[int(self.rng.choice(len(keys), p=weights / weights.sum()))]
        codon = int(self.rng.choice(61, p=p0))
        result = [CODONS[codon]]
        for _ in range(internal_codons - 1):
            codon = int(self.rng.choice(61, p=p1[codon]))
            result.append(CODONS[codon])
        return start_stop[:3] + "".join(result) + start_stop[3:]
