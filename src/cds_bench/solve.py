"""Exact reference algorithms for the unchanged published task definitions.

Small design instances are enumerated completely, including the canonical
lexicographic tie-break. A missing candidate rejects generation; it is never
silently labeled IMPOSSIBLE. Tables come from index.html's reference bank.
"""

import json
import math
import re
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from functools import lru_cache
from itertools import combinations, product

from Bio.Data import CodonTable, IUPACData

from .catalog import SPEC

code = CodonTable.unambiguous_dna_by_id[11]
bases = "ACGT"
codons = ["".join(p) for p in product(bases, repeat=3)]


def clean(sequence):
    return "".join(sequence.split()).upper()


def RNA(sequence):
    return clean(sequence).replace("T", "U")


def rc(sequence):
    return clean(sequence).translate(str.maketrans("ACGTU", "TGCAA"))[::-1]


def rcr(sequence):
    return clean(sequence).translate(str.maketrans("ACGU", "UGCA"))[::-1]


def rawaa(codon):
    """Internal codon meaning, without the initiation or termination rules."""
    return "*" if codon in code.stop_codons else code.forward_table[codon]


def translate(s, internal=False):
    s = clean(s).replace("U", "T")
    out = ""
    for i in range(0, len(s) - 2, 3):
        c = s[i : i + 3]
        a = rawaa(c)
        if not internal and a == "*":
            break
        if not internal and i == 0 and (c in code.start_codons):
            a = "M"
        out += a
    return out


syn = {a: [c for c in codons if rawaa(c) == a] for a in "ACDEFGHIKLMNPQRSTVWY"}
canonical = {"AU", "UA", "CG", "GC"}


def windows(s, n):
    return [s[i : i + n] for i in range(len(s) - n + 1)]


def hits(s, p):
    return [i + 1 for i in range(len(s) - len(p) + 1) if s[i : i + len(p)] == p]


def dist(a, b):
    assert len(a) == len(b)
    return sum((x != y for x, y in zip(a, b)))


def gc(s):
    return sum((b in "GC" for b in s))


def bound(v):
    return Fraction(str(v))


def gcpass(s, x):
    return all(
        (
            bound(x["gc_bounds"][0]) <= Fraction(gc(w), len(w)) <= bound(x["gc_bounds"][1])
            for w in windows(s, x["window"])
        )
    )


def has_forbidden_motif(sequence, inputs):
    patterns = set(inputs["forbidden_patterns"])
    if inputs["strand_mode"] == "both":
        patterns |= {rc(p) for p in patterns}
    return any(pattern in sequence for pattern in patterns)


def edit(s, edits):
    s = clean(s)
    reps = {e["replace"][0]: e["replace"] for e in edits if "replace" in e}
    ins = {e["insert_after"]: e["sequence"] for e in edits if "insert_after" in e}
    out = ins.get(0, "")
    i = 1
    while i <= len(s):
        if i in reps:
            a, b, t = reps[i]
            out += t + ins.get(b, "")
            i = b + 1
        else:
            out += s[i - 1] + ins.get(i, "")
            i += 1
    return out


def digest(p):
    cuts = [0] + [
        i + 1 for i, c in enumerate(p) if c in "KR" and (i + 1 == len(p) or p[i + 1] != "P")
    ]
    if cuts[-1] != len(p):
        cuts.append(len(p))
    return [{"start": a + 1, "end": b, "peptide": p[a:b]} for a, b in zip(cuts, cuts[1:]) if a < b]


def t1(r, blocked=()):
    cuts = [0] + [i + 1 for i, c in enumerate(r) if c == "G" and i + 1 not in blocked]
    if cuts[-1] != len(r):
        cuts.append(len(r))
    return [{"start": a + 1, "end": b, "fragment": r[a:b]} for a, b in zip(cuts, cuts[1:]) if a < b]


def pattern_hits(p, pattern):
    pieces = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c in "[{":
            j = pattern.index("]" if c == "[" else "}", i)
            pieces.append("[" + ("^" if c == "{" else "") + pattern[i + 1 : j] + "]")
            i = j + 1
        else:
            pieces.append("." if c == "X" else c)
            i += 1
    regex = "".join(pieces)
    return [
        [m.start() + 1, m.start() + len(m.group(1))] for m in re.finditer("(?=(" + regex + "))", p)
    ]


def pairs(db):
    stack = []
    out = []
    for i, c in enumerate(db, 1):
        if c == "(":
            stack.append(i)
        elif c == ")":
            out.append([stack.pop(), i])
    assert not stack
    return sorted(out)


def expand(c):
    return ["".join(t) for t in product(*(IUPACData.ambiguous_dna_values[b] for b in c))]


def library_counts(c):
    return dict(
        sorted(Counter(("STOP" if rawaa(k) == "*" else rawaa(k) for k in expand(c))).items())
    )


def synonymous(s):
    s = clean(s)
    cs = [s[i : i + 3] for i in range(0, len(s), 3)]
    return sorted(
        (cs[0] + "".join(p) + cs[-1] for p in product(*(syn[rawaa(c)] for c in cs[1:-1])))
    )


def permitted(s, positions):
    s = clean(s)
    for p in product("ACGT", repeat=len(positions)):
        a = list(s)
        for i, c in zip(positions, p):
            a[i - 1] = c
        yield "".join(a)


def editable(c, x):
    return all(
        (
            a == b or i in x["editable_positions"]
            for i, (a, b) in enumerate(zip(c, clean(x["cds"])), 1)
        )
    )


def pairscore(c, ps, sc):
    r = RNA(c)
    return sum((sc[r[i - 1] + r[j - 1]] for i, j in ps))


def allcanonical(c, ps):
    r = RNA(c)
    return all((r[i - 1] + r[j - 1] in canonical for i, j in ps))


def guide_min(r, g):
    return min((dist(w, rcr(g)) for w in windows(r, len(g))))


def probe(x):
    candidates = {rcr(w) for w in windows(RNA(x["cds"]), x["probe_length"])}
    return min(
        (
            g
            for g in candidates
            if all(
                (
                    guide_min(RNA(c), g) >= x["background_mismatch_floor"]
                    for c in x["background_cds_panel"]
                )
            )
        )
    )


def panel(x):
    choices = [
        [c for c in synonymous(x["cds"]) if gc(c) == x["gc_count"] and len(hits(RNA(c), "CG")) == n]
        for n in x["target_cg_counts"]
    ]
    # Sorted candidate lists make product visit panels in the required order.
    return list(next(p for p in product(*choices) if len(set(p)) == len(p)))


def frames(s, x):
    out = []
    for f in x["frames"]:
        a, b = f["interval"]
        part = clean(s)[a - 1 : b]
        if f["strand"] == "-":
            part = rc(part)
        out.append(translate(part, True))
    return out


def frame_records(before, after, x):
    return [
        {"frame": n, "original_peptide": a, "edited_peptide": b, "changed": a != b}
        for n, a, b in zip("AB", frames(before, x), frames(after, x))
    ]


def rounded(n, places):
    return float(Decimal(str(n)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def mass(p):
    return rounded(sum((masses[a] for a in p)) + Decimal("18.010565"), 4)


def charge(p, ph, pka):
    return (
        1 / (1 + 10 ** (ph - pka["N_term"]))
        - 1 / (1 + 10 ** (pka["C_term"] - ph))
        + sum((p.count(a) / (1 + 10 ** (ph - pka[a])) for a in "KRH"))
        - sum((p.count(a) / (1 + 10 ** (pka[a] - ph)) for a in "DECY"))
    )


def pi(p, pka):
    lo, hi = (0, 14)
    for _ in range(80):
        mid = (lo + hi) / 2
        if charge(p, mid, pka) > 0:
            lo = mid
        else:
            hi = mid
    return rounded((lo + hi) / 2, 2)


def solve(k, x):
    c = clean(x.get("cds", ""))
    p = translate(c) if c and (not any((b not in "ACGT" for b in c))) else ""
    r = RNA(c)
    if k == "dna.reverse_complement":
        return rc(c)
    if k == "dna.transcribe":
        return r
    if k == "cds.translate" or k == "rna.translate":
        return p
    if k == "cds.validate":
        return sorted(
            [
                name
                for name, test in [
                    ("bad_length", len(c) < 6 or len(c) % 3 != 0),
                    ("invalid_start", c[:3] not in code.start_codons),
                    ("missing_terminal_stop", c[-3:] not in code.stop_codons),
                    (
                        "internal_stop",
                        any((c[i : i + 3] in code.stop_codons for i in range(0, len(c) - 3, 3))),
                    ),
                ]
                if test
            ]
        )
    if k == "coords.nt_to_codon":
        n = x["nt_position"]
        i = (n - 1) // 3
        return {"codon_index": i + 1, "offset": (n - 1) % 3, "codon": c[i * 3 : i * 3 + 3]}
    if k == "coords.aa_to_nt":
        a, b = x["aa_interval"]
        return [3 * a - 2, 3 * b]
    if k == "variant.apply":
        return edit(c, x["edits"])
    if k == "variant.protein_effect":
        q = translate(edit(c, [{"replace": x["replacement"]}]))
        return "stop_gained" if len(q) < len(p) else "synonymous" if q == p else "missense"
    if k == "variant.frame_status":
        phase = 0
        out = []

        def pos(e):
            return e["insert_after"] + 1 if "insert_after" in e else e["replace"][0]

        for i, e in sorted(enumerate(x["edits"], 1), key=lambda ie: (pos(ie[1]), ie[0])):
            delta = (
                len(e["sequence"])
                if "insert_after" in e
                else len(e["replace"][2]) - (e["replace"][1] - e["replace"][0] + 1)
            )
            phase = (phase + delta) % 3
            out.append({"edit_index": i, "phase": phase})
        return {"edits": out, "final_phase": phase}
    if k == "cds.protein_equivalence":
        return translate(x["cds_a"]) == translate(x["cds_b"])
    if k.startswith("ambiguity."):
        i = x["codon_index"] - 1
        a = {"STOP" if rawaa(k) == "*" else rawaa(k) for k in expand(c[3 * i : 3 * i + 3])}
        return (
            sorted(a)
            if k == "ambiguity.codon_set"
            else "never"
            if "STOP" not in a
            else "guaranteed"
            if a == {"STOP"}
            else "possible"
        )
    if k == "stats.codon_counts":
        return dict(Counter((c[i : i + 3] for i in range(0, len(c) - 3, 3))))
    if k == "stats.gc_fraction":
        return rounded(gc(c) / len(c), 6)
    if k == "stats.gc3_fraction":
        v = c[2:-3:3]
        return rounded(gc(v) / len(v), 6)
    if k == "stats.gc_windows":
        return [
            i + 1
            for i, w in enumerate(windows(c, x["window"]))
            if not bound(x["gc_bounds"][0]) <= Fraction(gc(w), len(w)) <= bound(x["gc_bounds"][1])
        ]
    if k == "stats.cai":
        vals = [x["weights"][c[i : i + 3]] for i in range(3, len(c) - 3, 3)]
        return rounded(math.prod(vals) ** (1 / len(vals)), 6)
    if k == "dna.motif_positions":
        pattern = x["pattern"]
        matches = [(i, "+") for i in hits(c, pattern)]
        if x["strand_mode"] == "both" and rc(pattern) != pattern:
            matches += [(i, "-") for i in hits(c, rc(pattern))]
        return [
            {"start": i, "end": i + len(pattern) - 1, "strand": strand}
            for i, strand in sorted(matches)
        ]
    if k == "protein.motif_positions":
        return pattern_hits(p, x["pattern"])
    if k == "protein.nglyco_sequons":
        return [a for a, b in pattern_hits(p, "N{P}[ST]")]
    if k == "protein.residue_counts":
        return dict(Counter(p))
    if k == "protein.monoisotopic_mass":
        return mass(p)
    if k == "protein.mean_hydropathy":
        return rounded(sum((hydro[a] for a in p)) / len(p), 4)
    if k == "protein.trypsin_digest":
        return digest(p)
    if k in ["protein.diagnostic_peptide", "pipeline.diagnostic_digest"]:
        target = {z["peptide"] for z in digest(translate(x["target_cds"]))}
        bg = {z["peptide"] for c in x["background_cds_panel"] for z in digest(translate(c))}
        return min(
            (v for v in target - bg if x["length_bounds"][0] <= len(v) <= x["length_bounds"][1]),
            key=lambda v: (len(v), v),
        )
    if k == "protein.charge_at_ph":
        return rounded(charge(p, x["ph"], x["pka"]), 4)
    if k == "protein.isoelectric_point":
        return pi(p, x["pka"])
    if k == "rna.apply_edits":
        return edit(r, x["rna_edits"])
    if k == "rna.pair_compatibility":
        return sorted([v for v in x["pairs"] if r[v[0] - 1] + r[v[1] - 1] not in canonical])
    if k == "rna.dotbracket_to_pairs":
        return pairs(x["dot_bracket"])
    if k == "rna.t1_digest":
        return t1(
            r, [] if x["accessibility"] == "all" else [i for pair in x["pairs"] for i in pair]
        )
    if k == "rna.guide_hits":
        return [
            {
                "target_start": i + 1,
                "target_end": i + len(x["guide"]),
                "mismatches": dist(w, rcr(x["guide"])),
            }
            for i, w in enumerate(windows(r, len(x["guide"])))
            if dist(w, rcr(x["guide"])) <= x["max_mismatches"]
        ]
    if k == "rna.motif_counts":
        return {v: len(hits(r, v)) for v in set(x["patterns"])}
    if k == "rna.structure_score":
        positions = [i for pair in x["pairs"] for i in pair]
        if len(set(positions)) != len(positions) or not allcanonical(c, x["pairs"]):
            return "INVALID"
        return pairscore(c, x["pairs"], x["pair_scores"])
    if k == "rna.max_pair_fold":

        @lru_cache(None)
        def fold(i, j):
            if i > j:
                return (0, "")
            n, t = fold(i + 1, j)
            out = [(n, "." + t)]
            for k in range(i + x["min_loop"] + 1, j + 1):
                if r[i] + r[k] in canonical:
                    n, a = fold(i + 1, k - 1)
                    m, b = fold(k + 1, j)
                    out.append((1 + n + m, "(" + a + ")" + b))
            return min(out, key=lambda v: (-v[0], v[1]))

        return fold(0, len(r) - 1)[1]
    if k.startswith("design.") or k in [
        "joint.clone_ready_cds",
        "pipeline.repair_and_verify",
        "joint.structure_and_codons",
    ]:
        choices = synonymous(c)
        if k == "design.synonymous_distance":
            choices = [
                v for v in choices if x["edit_bounds"][0] <= dist(c, v) <= x["edit_bounds"][1]
            ]
        elif k == "design.codon_allowlist":
            choices = [
                v
                for v in choices
                if all(
                    (v[3 * (int(i) - 1) : 3 * int(i)] in a for i, a in x["allowed_codons"].items())
                )
            ]
        elif k in ["design.codon_preference", "joint.structure_and_codons"]:
            if k.startswith("joint."):
                choices = [
                    v
                    for v in choices
                    if x["edit_bounds"][0] <= dist(c, v) <= x["edit_bounds"][1]
                    and allcanonical(v, x["pairs"])
                    and (pairscore(v, x["pairs"], x["pair_scores"]) >= x["min_pair_score"])
                ]

            def score(v):
                return math.prod(
                    (Decimal(str(x["weights"][v[i : i + 3]])) for i in range(3, len(v) - 3, 3))
                )

            return min(choices, key=lambda v: (-score(v), v))
        elif k == "design.codon_profile":
            choices = [
                v
                for v in choices
                if all(
                    (
                        lo <= x["weights"][v[3 * (int(i) - 1) : 3 * int(i)]] <= hi
                        for i, (lo, hi) in x["position_bounds"].items()
                    )
                )
            ]
        elif k == "design.gc_windows":
            choices = [v for v in choices if gcpass(v, x)]
        elif k in ["design.remove_dna_motifs", "joint.clone_ready_cds"]:
            choices = [
                v
                for v in choices
                if not has_forbidden_motif(v, x) and (not k.startswith("joint.") or gcpass(v, x))
            ]
        elif k == "design.insert_dna_motif":
            choices = [
                v
                for v in choices
                if v[x["start"] - 1 : x["start"] - 1 + len(x["pattern"])] == x["pattern"]
            ]
        elif k == "design.break_repeats":
            choices = [
                v
                for v in choices
                if max((len(m.group()) for m in re.finditer("(.)\\1*", v))) <= x["max_run"]
                and all(
                    (
                        max(Counter(windows(v, int(n))).values()) <= limit
                        for n, limit in x["max_kmer_copies"].items()
                    )
                )
            ]
        elif k == "design.rna_motif_control":
            choices = [
                v
                for v in choices
                if all(
                    (lo <= len(hits(RNA(v), q)) <= hi for q, (lo, hi) in x["count_bounds"].items())
                )
            ]
        elif k == "design.dinucleotide_counts":
            choices = [
                v
                for v in choices
                if all(
                    (
                        lo <= len(hits(RNA(v), q)) <= hi
                        for q, (lo, hi) in x["dinucleotide_bounds"].items()
                    )
                )
            ]
        elif k in ["design.pairing_repair", "pipeline.repair_and_verify"]:
            choices = [v for v in choices if editable(v, x) and allcanonical(v, x["pairs"])]
        elif k == "design.structure_score":
            return min(
                (v for v in choices if allcanonical(v, x["pairs"])),
                key=lambda v: (
                    (-1 if x["direction"] == "maximize" else 1)
                    * pairscore(v, x["pairs"], x["pair_scores"]),
                    v,
                ),
            )
        elif k == "design.expose_rna_window":
            choices = [
                v
                for v in choices
                if editable(v, x)
                and all(
                    (
                        not allcanonical(v, [q])
                        for q in x["candidate_pairs"]
                        if any(
                            (x["target_interval"][0] <= pos <= x["target_interval"][1] for pos in q)
                        )
                    )
                )
            ]
        elif k == "design.guide_escape":
            choices = [
                v
                for v in choices
                if editable(v, x) and guide_min(RNA(v), x["guide"]) >= x["min_mismatches"]
            ]
        elif k == "design.variant_panel":
            return panel(x)
        else:
            raise KeyError(k)
        return min(choices)
    if k in ["construct.minimal_aa_edit", "joint.protein_edit_and_cloning"]:
        a = x["residue_index"] - 1
        if k == "construct.minimal_aa_edit":
            choices = [c[: a * 3] + v + c[a * 3 + 3 :] for v in syn[x["target_aa"]]]
        else:
            q = p[:a] + x["target_aa"] + p[a + 1 :]
            choices = [c[:3] + "".join(v) + c[-3:] for v in product(*(syn[z] for z in q[1:]))]
            choices = [v for v in choices if not has_forbidden_motif(v, x)]
        return min(choices, key=lambda v: (dist(c, v), v))
    if k == "construct.remove_peptide_motif":
        aa_choices = [x["allowed_residues"].get(str(i), [a]) for i, a in enumerate(p, 1)]
        choices = []
        for q in product(*aa_choices):
            if x["forbidden_peptide"] in "".join(q):
                continue
            choices.extend((c[:3] + "".join(v) + c[-3:] for v in product(*(syn[a] for a in q[1:]))))
        return min(choices)
    if k == "construct.tag_fusion" or k == "pipeline.tag_cleave_mass":
        tag = clean(x["tag_cds"])
        link = clean(x["linker_cds"])
        v = c[:3] + tag + link + c[3:] if x["placement"] == "N" else c[:-3] + link + tag + c[-3:]
        if k == "construct.tag_fusion":
            return v
        q = translate(v)
        cuts = [0] + [i + 6 for i in range(len(q) - 6) if q[i : i + 7] == "ENLYFQG"] + [len(q)]
        frags = [q[a:b] for a, b in zip(cuts, cuts[1:]) if a < b]
        return {"cds": v, "fragments": [{"peptide": a, "mass_da": mass(a)} for a in frags]}
    if k == "construct.tev_products":
        return [
            v["peptide"]
            for v in [
                {"peptide": p[a:b]}
                for a, b in zip(
                    [0] + [m.start() + 6 for m in re.finditer("ENLYFQG", p)],
                    [m.start() + 6 for m in re.finditer("ENLYFQG", p)] + [len(p)],
                )
            ]
        ]
    if k == "library.codon_products":
        i = x["codon_index"] - 1
        return library_counts(c[3 * i : 3 * i + 3])
    if k == "library.design_codon" or k == "pipeline.library_and_verify":
        options = []
        alphabet = sorted(set(IUPACData.ambiguous_dna_values) - {"X"})
        for cod in map("".join, product(alphabet, repeat=3)):
            counts = library_counts(cod)
            if "STOP" not in counts and set(x["target_residues"]) <= set(counts):
                options.append(
                    (
                        len(set(counts) - set(x["target_residues"])),
                        sum(counts.values()),
                        cod,
                        counts,
                    )
                )
        _, _, cod, counts = min(options)
        return (
            cod
            if k == "library.design_codon"
            else {"status": "ok", "codon": cod, "residue_counts": counts}
        )
    if k == "construct.inframe_deletion":
        a, b = x["aa_interval"]
        return c[: 3 * (a - 1)] + c[3 * b :]
    if k in ["construct.join_modules", "pipeline.fusion_junction"]:
        v = clean(x["cds_a"])[:-3] + clean(x["linker_cds"]) + clean(x["cds_b"])[3:]
        if k == "construct.join_modules":
            return v
        return {
            "fused_cds": v,
            "matches": [
                {"aa_interval": [a, b], "nt_interval": [3 * a - 2, 3 * b]}
                for a, b in pattern_hits(translate(v), x["pattern"])
            ],
        }
    if k in ["construct.edit_aware_encoding", "pipeline.edit_dependent_product"]:
        v = min(
            (
                v
                for v in synonymous(c)
                if editable(v, x) and translate(edit(RNA(v), x["rna_edits"])) == x["target_protein"]
            )
        )
        return (
            v
            if k.startswith("construct.")
            else {
                "status": "ok",
                "cds": v,
                "unedited_protein": translate(v),
                "edited_protein": translate(edit(RNA(v), x["rna_edits"])),
            }
        )
    if k == "assay.primer_pair":
        a, b = x["amplicon_interval"]
        v = c[a - 1 : b]
        n = x["primer_length"]
        f = v[:n]
        q = rc(v[-n:])
        assert all(
            (x["primer_gc_bounds"][0] <= gc(z) / len(z) <= x["primer_gc_bounds"][1] for z in [f, q])
        )
        assert len(hits(c, f)) == len(hits(c, rc(q))) == 1
        return {"status": "ok", "forward": f, "reverse": q}
    if k in ["assay.select_rna_probe", "pipeline.target_and_escape"]:
        g = probe(x)
        if k.startswith("assay."):
            return g
        v = min(
            (
                v
                for v in synonymous(c)
                if editable(v, x) and guide_min(RNA(v), g) >= x["escape_mismatches"]
            )
        )
        return {"status": "ok", "probe": g, "escape_cds": v}
    if k in ["assay.min_probe_panel", "pipeline.rna_probe_panel"]:
        ids = sorted(x["candidate_probes"])
        winner = None
        for n in range(len(ids) + 1):
            options = []
            for chosen in combinations(ids, n):
                sig = [
                    "".join(
                        ("1" if rcr(x["candidate_probes"][i]) in RNA(v) else "0" for i in chosen)
                    )
                    for v in x["cds_panel"]
                ]
                if len(set(sig)) == len(sig):
                    options.append((chosen, sig))
            if options:
                winner = min(options)
                break
        chosen, sig = winner
        return (
            list(chosen)
            if k.startswith("assay.")
            else {
                "status": "ok",
                "probe_ids": list(chosen),
                "signatures": [{"cds_index": i + 1, "bits": v} for i, v in enumerate(sig)],
            }
        )
    if k == "overlap.compare_products":
        v = edit(c, [{"replace": x["replacement"]}])
        return frame_records(c, v, x)
    if k in ["overlap.constrained_edit", "pipeline.overlap_edit_verify"]:
        before = frames(c, x)
        v = min(
            (
                v
                for v in permitted(c, x["editable_positions"])
                if frames(v, x) == [x["target_peptide_a"], before[1]]
            )
        )
        return (
            v
            if k.startswith("overlap.")
            else {"status": "ok", "cds": v, "frames": frame_records(c, v, x)}
        )
    if k == "pipeline.motif_to_dna":
        return [
            {"aa_interval": [a, b], "nt_interval": [3 * a - 2, 3 * b]}
            for a, b in pattern_hits(p, x["pattern"])
        ]
    if k == "pipeline.protein_properties":
        return {
            "residue_counts": dict(Counter(p)),
            "mass_da": mass(p),
            "mean_hydropathy": rounded(sum((hydro[a] for a in p)) / len(p), 4),
            "charge": rounded(charge(p, x["ph"], x["pka"]), 4),
            "pi": pi(p, x["pka"]),
        }
    if k == "pipeline.variant_peptides":
        a = {v["peptide"] for v in digest(p)}
        b = {v["peptide"] for v in digest(translate(edit(c, x["edits"])))}
        return {"lost": sorted(a - b), "gained": sorted(b - a)}
    if k == "pipeline.rna_edit_translation":
        return translate(edit(r, x["rna_edits"]))
    if k == "pipeline.rna_edit_digest":
        return t1(edit(r, x["rna_edits"]))
    if k == "pipeline.structure_gated_digest":
        return t1(r, [i for pair in pairs(x["dot_bracket"]) for i in pair])
    if k == "pipeline.controlled_panel":
        return {
            "status": "ok",
            "members": [
                {
                    "cds": v,
                    "cg_count": len(hits(RNA(v), "CG")),
                    "gc_fraction": rounded(gc(v) / len(v), 6),
                }
                for v in panel(x)
            ],
        }
    raise KeyError(k)


def expected(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


_mass_block = re.search(r'id="ref-mass".*?<pre>(.*?)</pre>', SPEC, re.S).group(1)
masses = {k: Decimal(v) for k, v in re.findall(r"([A-Z])=(\d+\.\d+)", _mass_block)}
_hydro_block = re.search(r'id="ref-hydro".*?<pre>(.*?)</pre>', SPEC, re.S).group(1)
hydro = {k: Decimal(v) for k, v in re.findall(r"([A-Z])=(-?\d+(?:\.\d+)?)", _hydro_block)}
