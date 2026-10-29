"""Task-specific sampling. Constraints are instance data, never changed task rules.

Ordinary questions use de novo bacterial codon-Markov CDSs. Design problems use
shorter CDSs so every permitted encoding can be searched. Some substrates need
engineered features (a cleavage site, a recognition site, a broken stem); those
features are inserted explicitly before solving, rather than inferred from a
random sequence that lacks them.
"""

import math
from collections import defaultdict
from itertools import product

from . import solve as bio

PAIR_SCORES = {"AU": 2, "UA": 2, "CG": 3, "GC": 3}
PKA = {
    "N_term": 8.0,
    "C_term": 4.0,
    "K": 10.5,
    "R": 12.5,
    "H": 6.0,
    "D": 3.9,
    "E": 4.1,
    "C": 8.3,
    "Y": 10.1,
}
SIMPLE = {
    "dna.reverse_complement",
    "dna.transcribe",
    "cds.translate",
    "rna.translate",
    "stats.codon_counts",
    "stats.gc_fraction",
    "stats.gc3_fraction",
    "protein.residue_counts",
    "protein.monoisotopic_mass",
    "protein.mean_hydropathy",
    "protein.trypsin_digest",
}


class Reject(ValueError):
    """A sampled substrate cannot support this question; draw a new one."""


def require(condition, reason):
    if not condition:
        raise Reject(reason)


def replace_codon(cds, index, codon):
    """Use a one-based codon index."""
    return cds[: 3 * (index - 1)] + codon + cds[3 * index :]


def encode(peptide, rng):
    return "".join(str(rng.choice(bio.syn[a])) for a in peptide)


def weights_for(cds, rng):
    """Illustrative host preferences, fully supplied as question inputs."""
    result = {}
    for aa in sorted(set(bio.translate(cds)[1:])):
        codons = bio.syn[aa]
        preferred = int(rng.integers(len(codons)))
        for index, codon in enumerate(codons):
            result[codon] = 1.0 if index == preferred else float(rng.choice([0.2, 0.4, 0.6, 0.8]))
    return result


def alternate(cds, rng, *, synonymous=True):
    positions = list(range(2, len(cds) // 3))
    rng.shuffle(positions)
    for index in positions:
        old = cds[3 * (index - 1) : 3 * index]
        choices = (
            [c for c in bio.syn[bio.rawaa(old)] if c != old]
            if synonymous
            else [c for c in bio.codons if bio.rawaa(c) not in ("*", bio.rawaa(old))]
        )
        if choices:
            return replace_codon(cds, index, str(rng.choice(choices))), index
    raise Reject("No eligible codon change")


def stems(cds):
    """Three contiguous canonical pairs enclosing at least three loop bases."""
    rna = bio.RNA(cds)
    result = []
    for left in range(1, len(rna) - 8):
        for right in range(left + 8, len(rna) + 1):
            pairs = [[left + offset, right - offset] for offset in range(3)]
            if bio.allcanonical(cds, pairs):
                result.append(pairs)
    return result


def dotbracket(cds, pairs):
    result = ["."] * len(cds)
    for left, right in pairs:
        result[left - 1], result[right - 1] = "(", ")"
    return "".join(result)


def hairpin_design(cds, rng, task_id):
    candidates = stems(cds)
    rng.shuffle(candidates)
    for pairs in candidates:
        for sequence in bio.synonymous(cds):
            changed = [i for i, (a, b) in enumerate(zip(cds, sequence), 1) if a != b]
            if len(changed) != 1 or changed[0] not in {i for pair in pairs for i in pair}:
                continue
            position = changed[0]
            touching = [pair for pair in pairs if position in pair]
            if bio.allcanonical(sequence, touching):
                continue
            if task_id == "design.expose_rna_window":
                return {
                    "cds": cds,
                    "candidate_pairs": pairs,
                    "target_interval": [position, position],
                    "editable_positions": [position],
                }
            # Reverse that one synonymous disruption to create a repair task.
            return {"cds": sequence, "pairs": pairs, "editable_positions": [position]}
    raise Reject("No synonymously editable three-pair hairpin")


def make(task_id, sampler, rng, example_index):
    short = task_id.startswith(("design.", "joint.", "overlap.")) or task_id in {
        "construct.remove_peptide_motif",
        "construct.edit_aware_encoding",
        "assay.select_rna_probe",
        "pipeline.repair_and_verify",
        "pipeline.target_and_escape",
        "pipeline.controlled_panel",
        "pipeline.edit_dependent_product",
        "pipeline.overlap_edit_verify",
    }
    c = sampler.cds(6 if short else int(rng.integers(9, 22)))
    if short:
        require(
            math.prod(len(bio.syn[bio.rawaa(c[i : i + 3])]) for i in range(3, len(c) - 3, 3))
            <= 15000,
            "Exact synonymous search too large",
        )
    p, r = bio.translate(c), bio.RNA(c)
    x = {"cds": c}
    if task_id in SIMPLE:
        if task_id == "protein.trypsin_digest":
            require(len(bio.digest(p)) >= 2, "No internal trypsin cleavage")
        return x
    if task_id == "cds.validate":
        # Include valid CDSs, individual faults, and combinations, all explicitly
        # within this task's validation domain.
        mode = example_index % 5
        if mode in (1, 4):
            c = "GCT" + c[3:]
        if mode in (2, 4):
            c = replace_codon(c, 4, "TAA")
        if mode in (3, 4):
            c = c[:-3] + "GCA"
        if example_index == 9:
            c += "C"
        return {"cds": c}
    if task_id == "coords.nt_to_codon":
        return dict(x, nt_position=int(rng.integers(1, len(c) - 2)))
    if task_id in {"coords.aa_to_nt", "construct.inframe_deletion"}:
        start = int(rng.integers(2, len(p)))
        return dict(x, aa_interval=[start, min(start + int(rng.integers(1, 4)), len(p))])
    if task_id in {"variant.apply", "variant.frame_status"}:
        return dict(
            x,
            edits=[
                {"insert_after": 6, "sequence": "C" if example_index % 2 else "GGT"},
                {"replace": [12, 12, ""]},
            ],
        )
    if task_id == "variant.protein_effect":
        mode = example_index % 3
        changed, index = alternate(c, rng, synonymous=mode == 0)
        codon = "TGA" if mode == 2 else changed[3 * (index - 1) : 3 * index]
        return dict(x, replacement=[3 * index - 2, 3 * index, codon])
    if task_id == "cds.protein_equivalence":
        changed, _ = alternate(c, rng, synonymous=example_index % 2 == 0)
        return {"cds_a": c, "cds_b": changed}
    if task_id.startswith("ambiguity.") or task_id == "library.codon_products":
        codon = str(rng.choice(["NNK", "TAN", "TAR", "GCN", "ATH", "RAY", "YTN"]))
        index = int(rng.integers(2, len(p)))
        return {"cds": replace_codon(c, index, codon), "codon_index": index}
    if task_id == "stats.gc_windows":
        return dict(x, window=9, gc_bounds=["1/3", "2/3"])
    if task_id == "stats.cai":
        return dict(x, weights=weights_for(c, rng))
    if task_id == "dna.motif_positions":
        start = int(rng.integers(3, len(c) - 5))
        pattern = c[start : start + 3]
        if example_index % 2:
            pattern = bio.rc(pattern)
        return dict(x, pattern=pattern, strand_mode="both")
    if task_id in {"protein.motif_positions", "pipeline.motif_to_dna"}:
        start = int(rng.integers(1, len(p) - 3))
        a, b, d = p[start : start + 3]
        return dict(
            x,
            pattern=a
            + ("X" if example_index % 2 else "{" + ("P" if b != "P" else "A") + "}")
            + "["
            + d
            + "]",
        )
    if task_id == "protein.nglyco_sequons":
        return {
            "cds": c[:6]
            + encode("N" + str(rng.choice(list("AGVL"))) + str(rng.choice(list("ST"))), rng)
            + c[15:]
        }
    if task_id in {"protein.diagnostic_peptide", "pipeline.diagnostic_digest"}:
        changed, _ = alternate(c, rng, synonymous=False)
        return {"target_cds": c, "background_cds_panel": [changed], "length_bounds": [3, len(p)]}
    if task_id in {
        "protein.charge_at_ph",
        "protein.isoelectric_point",
        "pipeline.protein_properties",
    }:
        require(
            bio.charge(p, 0, PKA) > 0 > bio.charge(p, 14, PKA), "No pI root in specified interval"
        )
        if task_id == "protein.isoelectric_point":
            return dict(x, pka=PKA)
        return dict(x, ph=float(rng.choice([5.0, 6.5, 7.0, 8.0])), pka=PKA)
    if task_id in {"rna.apply_edits", "pipeline.rna_edit_translation", "pipeline.rna_edit_digest"}:
        # A known CAA -> UAA edit demonstrates an actual changed product.
        c = replace_codon(c, 4, "CAA")
        return {"cds": c, "rna_edits": [{"replace": [10, 10, "U"]}]}
    if task_id in {
        "rna.pair_compatibility",
        "rna.dotbracket_to_pairs",
        "rna.structure_score",
        "pipeline.structure_gated_digest",
        "rna.t1_digest",
    }:
        available = stems(c)
        require(bool(available), "No three-pair hairpin")
        pairing = available[int(rng.integers(len(available)))]
        if task_id in {"rna.dotbracket_to_pairs", "pipeline.structure_gated_digest"}:
            if task_id.startswith("pipeline."):
                require(
                    any(r[i - 1] == "G" for pair in pairing for i in pair),
                    "Structure protects no RNase T1 site",
                )
            return dict(x, dot_bracket=dotbracket(c, pairing))
        if task_id == "rna.structure_score":
            return dict(x, pairs=pairing, pair_scores=PAIR_SCORES)
        if task_id == "rna.t1_digest":
            return dict(
                x,
                accessibility="all" if example_index % 2 else "unpaired_only",
                pairs=[] if example_index % 2 else pairing,
            )
        # A separate, deliberately incompatible contact tests pair checking.
        used = {i for pair in pairing for i in pair}
        bad = next(
            (
                [i, j]
                for i in range(1, len(c))
                for j in range(i + 4, len(c) + 1)
                if i not in used and j not in used and r[i - 1] + r[j - 1] not in bio.canonical
            ),
            None,
        )
        require(bad is not None, "No incompatible extra contact")
        return dict(x, pairs=sorted(pairing + [bad]))
    if task_id == "rna.guide_hits":
        start = int(rng.integers(0, len(c) - 12))
        return dict(x, guide=bio.rcr(r[start : start + 12]), max_mismatches=1)
    if task_id == "rna.motif_counts":
        return dict(x, patterns=sorted({r[3:6], r[5:9], "CG", "UA"}))
    if task_id == "rna.max_pair_fold":
        require(bool(stems(c)), "No multi-pair hairpin to fold")
        return dict(x, min_loop=3)
    if task_id in {
        "design.pairing_repair",
        "pipeline.repair_and_verify",
        "design.expose_rna_window",
    }:
        return hairpin_design(c, rng, task_id)
    if task_id in {"design.structure_score", "joint.structure_and_codons"}:
        available = stems(c)
        require(bool(available), "No three-pair hairpin")
        pairing = available[int(rng.integers(len(available)))]
        if task_id == "design.structure_score":
            return dict(
                x,
                pairs=pairing,
                pair_scores=PAIR_SCORES,
                direction="maximize" if example_index % 2 else "minimize",
            )
        return dict(
            x,
            pairs=pairing,
            pair_scores=PAIR_SCORES,
            edit_bounds=[1, 3],
            min_pair_score=6,
            weights=weights_for(c, rng),
        )
    if task_id.startswith("design.") or task_id in {
        "joint.clone_ready_cds",
        "pipeline.controlled_panel",
    }:
        choices = bio.synonymous(c)
        witness = choices[int(rng.integers(len(choices)))]
        if task_id == "design.synonymous_distance":
            return dict(x, edit_bounds=[1, 3])
        if task_id == "design.codon_allowlist":
            return dict(
                x,
                allowed_codons={
                    str(i): [witness[3 * (i - 1) : 3 * i]] for i in range(2, len(p) + 1)
                },
            )
        if task_id in {"design.codon_preference", "design.codon_profile"}:
            weights = weights_for(c, rng)
            if task_id.endswith("preference"):
                return dict(x, weights=weights)
            return dict(
                x,
                weights=weights,
                position_bounds={
                    str(i): [weights[witness[3 * (i - 1) : 3 * i]]] * 2
                    for i in range(2, len(p) + 1)
                },
            )
        if task_id == "design.gc_windows":
            counts = [bio.gc(w) for w in bio.windows(witness, 9)]
            return dict(x, window=9, gc_bounds=[f"{min(counts)}/9", f"{max(counts)}/9"])
        if task_id in {
            "design.remove_dna_motifs",
            "design.insert_dna_motif",
            "joint.clone_ready_cds",
        }:
            # Make a genuine EcoRI recognition-site substrate, retaining sampled
            # codons outside the two engineered sense codons.
            c = replace_codon(replace_codon(c, 3, "GAA"), 4, "TTC")
            if task_id == "design.insert_dna_motif":
                return {"cds": replace_codon(c, 3, "GAG"), "pattern": "GAATTC", "start": 7}
            result = {"cds": c, "forbidden_patterns": ["GAATTC"], "strand_mode": "both"}
            if task_id.startswith("joint."):
                clean_choices = [v for v in bio.synonymous(c) if "GAATTC" not in v]
                require(bool(clean_choices), "No synonymous EcoRI removal")
                counts = [bio.gc(w) for w in bio.windows(clean_choices[len(clean_choices) // 2], 9)]
                result.update(window=9, gc_bounds=[f"{min(counts)}/9", f"{max(counts)}/9"])
            return result
        if task_id == "design.break_repeats":
            c = replace_codon(replace_codon(c, 2, "AAA"), 3, "AAA")
            return {"cds": c, "max_run": 2, "max_kmer_copies": {"3": 2}}
        if task_id == "design.rna_motif_control":
            pattern = str(rng.choice(["CG", "UA", "AA", "UU"]))
            count = len(bio.hits(bio.RNA(witness), pattern))
            require(count != len(bio.hits(r, pattern)), "RNA-motif constraint already met")
            return dict(x, rna_patterns=[pattern], count_bounds={pattern: [count, count]})
        if task_id == "design.dinucleotide_counts":
            bounds = {q: [len(bio.hits(bio.RNA(witness), q))] * 2 for q in ["CG", "UA"]}
            require(
                any(len(bio.hits(r, q)) != v[0] for q, v in bounds.items()),
                "Dinucleotide constraint already met",
            )
            return dict(x, dinucleotide_bounds=bounds)
        if task_id == "design.guide_escape":
            return dict(
                x,
                guide=bio.rcr(r[3:-3]),
                min_mismatches=2,
                editable_positions=list(range(4, len(c) - 2)),
            )
        if task_id in {"design.variant_panel", "pipeline.controlled_panel"}:
            levels = defaultdict(set)
            for sequence in choices:
                levels[bio.gc(sequence)].add(len(bio.hits(bio.RNA(sequence), "CG")))
            valid = [g for g, values in levels.items() if len(values) >= 2]
            require(bool(valid), "No GC-matched distinct CG levels")
            gc_count = int(rng.choice(valid))
            return dict(x, target_cg_counts=sorted(levels[gc_count])[:2], gc_count=gc_count)
    if task_id in {"construct.minimal_aa_edit", "joint.protein_edit_and_cloning"}:
        if task_id.startswith("joint."):
            c = replace_codon(replace_codon(c, 3, "GAT"), 4, "TTC")
            return {
                "cds": c,
                "residue_index": 3,
                "target_aa": "E",
                "forbidden_patterns": ["GAATTC"],
                "strand_mode": "both",
            }
        index = int(rng.integers(2, len(p)))
        return dict(
            x, residue_index=index, target_aa=str(rng.choice(sorted(set(bio.syn) - {p[index - 1]})))
        )
    if task_id == "construct.remove_peptide_motif":
        index = int(rng.integers(2, len(p)))
        target = str(rng.choice(sorted(set(bio.syn) - {p[index - 1]})))
        return dict(
            x,
            forbidden_peptide=p[index - 2 : index],
            allowed_residues={str(index): [p[index - 1], target]},
        )
    if task_id in {"construct.tag_fusion", "pipeline.tag_cleave_mass", "construct.tev_products"}:
        tag = encode("HHHHHHENLYFQ", rng)
        linker = encode("GGS", rng)
        placement = "N" if example_index % 2 else "C"
        if task_id == "construct.tev_products":
            return {"cds": c[:3] + tag + linker + c[3:]}
        if task_id == "pipeline.tag_cleave_mass":
            placement = "N"  # The linker supplies the G needed by the TEV site.
        return dict(x, tag_cds=tag, linker_cds=linker, placement=placement)
    if task_id in {"library.design_codon", "pipeline.library_and_verify"}:
        sets = [list(v) for v in ("AGV", "DE", "ILV", "FY", "NQ", "ST", "KR", "AG", "DN", "ACG")]
        return dict(x, codon_index=3, target_residues=sorted(sets[example_index % len(sets)]))
    if task_id in {"construct.join_modules", "pipeline.fusion_junction"}:
        second = sampler.cds(5)
        linker = encode("GGS", rng)
        result = {"cds_a": c, "cds_b": second, "linker_cds": linker}
        if task_id.startswith("pipeline."):
            result["pattern"] = bio.translate(c)[-1] + "GGS" + bio.translate(second)[1]
        return result
    if task_id in {"construct.edit_aware_encoding", "pipeline.edit_dependent_product"}:
        c = replace_codon(c, 3, "TCT")
        peptide = bio.translate(c)
        return {
            "cds": c,
            "rna_edits": [{"replace": [7, 7, "G"]}],
            "target_protein": peptide[:2] + "G" + peptide[3:],
            "editable_positions": [7, 8],
        }
    if task_id == "assay.primer_pair":
        return dict(
            x, amplicon_interval=[1, len(c)], primer_length=12, primer_gc_bounds=[0.25, 0.75]
        )
    if task_id in {"assay.select_rna_probe", "pipeline.target_and_escape"}:
        background, _ = alternate(c, rng, synonymous=False)
        result = dict(
            x, background_cds_panel=[background], probe_length=12, background_mismatch_floor=1
        )
        if task_id.startswith("pipeline."):
            result.update(escape_mismatches=1, editable_positions=list(range(4, len(c) - 2)))
        return result
    if task_id in {"assay.min_probe_panel", "pipeline.rna_probe_panel"}:
        variant_a, pos_a = alternate(c, rng)
        variant_b, pos_b = alternate(c, rng)
        require(pos_a != pos_b, "Panel mutations must differ")
        panel = [c, variant_a, variant_b]
        candidates = {
            f"probe_{index:02}": bio.rcr(r[start : start + 12])
            for index, start in enumerate(range(0, len(c) - 11, 3))
        }
        return {"cds_panel": panel, "candidate_probes": candidates}
    if task_id.startswith("overlap.") or task_id == "pipeline.overlap_edit_verify":
        # Find an actual overlapping-frame change: A changes, B is preserved.
        annotation = [{"interval": [7, 12], "strand": "+"}, {"interval": [6, 11], "strand": "+"}]
        original = bio.frames(c, {"frames": annotation})
        for position, base in product(range(7, 12), "ACGT"):
            changed = c[: position - 1] + base + c[position:]
            products = bio.frames(changed, {"frames": annotation})
            if (
                "*" not in "".join(original + products)
                and products[0] != original[0]
                and products[1] == original[1]
            ):
                if task_id == "overlap.compare_products":
                    return dict(x, frames=annotation, replacement=[position, position, base])
                return dict(
                    x,
                    frames=annotation,
                    target_peptide_a=products[0],
                    editable_positions=[position],
                )
        raise Reject("No one-base constrained overlapping-frame edit")
    if task_id == "pipeline.variant_peptides":
        require(len(bio.digest(p)) >= 2, "No trypsin cleavage to alter")
        index = next(i for i, aa in enumerate(p, 1) if aa in "KR")
        return dict(x, edits=[{"replace": [3 * index - 2, 3 * index, "GCA"]}])
    raise KeyError(task_id)
