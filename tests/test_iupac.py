"""Regression checks for the published IUPAC motif and strand rules."""

import unittest
from itertools import product

from cds_bench import solve as bio


# Independent expansion oracle from the specification's 15 IUPAC DNA symbols.
BASE_SETS = dict(zip(
    "ACGTRYSWKMBDHVN",
    "A C G T AG CT CG AT GT AC CGT AGT ACT ACG ACGT".split(),
))


def concrete_codons(pattern):
    return {"".join(p) for p in product(*(BASE_SETS[s] for s in pattern))}


def concrete_rc(sequence):
    return sequence.translate(str.maketrans("ACGT", "TGCA"))[::-1]


def literal_starts(sequence, patterns):
    starts = set()
    for pattern in patterns:
        start = sequence.find(pattern)
        while start != -1:
            starts.add(start + 1)
            start = sequence.find(pattern, start + 1)
    return starts


def expected_matches(sequence, pattern):
    forward = concrete_codons(pattern)
    reverse = {concrete_rc(c) for c in forward}
    hits = [(i, "+") for i in literal_starts(sequence, forward)]
    if reverse != forward:
        hits.extend((i, "-") for i in literal_starts(sequence, reverse))
    return [
        {"start": i, "end": i + len(pattern) - 1, "strand": strand}
        for i, strand in sorted(hits)
    ]


class IupacTests(unittest.TestCase):
    def test_reverse_complement_all_symbols(self):
        self.assertEqual(bio.rc("ACGTRYSWKMBDHVN"), "NBDHVKMWSRYACGT")
        self.assertEqual(bio.rc(" a c g t u "), "AACGT")

    def test_reverse_complements_match_concrete_expansions(self):
        for pattern in map("".join, product(BASE_SETS, repeat=3)):
            expected = {concrete_rc(c) for c in concrete_codons(pattern)}
            self.assertEqual(concrete_codons(bio.rc(pattern)), expected, pattern)
            self.assertEqual(bio.rc(bio.rc(pattern)), pattern)

    def test_all_iupac_triplets_on_both_strands(self):
        # This DNA contains all 64 concrete triplets, plus their boundary windows.
        sequence = "".join(map("".join, product("ACGT", repeat=3)))
        for pattern in map("".join, product(BASE_SETS, repeat=3)):
            actual = bio.solve("dna.motif_positions", {
                "cds": sequence, "pattern": pattern, "strand_mode": "both",
            })
            self.assertEqual(actual, expected_matches(sequence, pattern), pattern)

    def test_overlapping_matches(self):
        self.assertEqual(bio.solve("dna.motif_positions", {
            "cds": "AAAT", "pattern": "AN", "strand_mode": "forward",
        }), [
            {"start": 1, "end": 2, "strand": "+"},
            {"start": 2, "end": 3, "strand": "+"},
            {"start": 3, "end": 4, "strand": "+"},
        ])

    def test_reverse_strand_coordinates(self):
        self.assertEqual(bio.solve("dna.motif_positions", {
            "cds": "AGCT", "pattern": "AR", "strand_mode": "both",
        }), [
            {"start": 1, "end": 2, "strand": "+"},
            {"start": 3, "end": 4, "strand": "-"},
        ])

    def test_self_reverse_complementary_pattern_is_reported_once(self):
        self.assertEqual(bio.solve("dna.motif_positions", {
            "cds": "ACGT", "pattern": "RY", "strand_mode": "both",
        }), [
            {"start": 1, "end": 2, "strand": "+"},
            {"start": 3, "end": 4, "strand": "+"},
        ])

    def test_nonpalindromic_pattern_can_hit_both_strands_at_one_interval(self):
        self.assertEqual(bio.solve("dna.motif_positions", {
            "cds": "AT", "pattern": "AN", "strand_mode": "both",
        }), [
            {"start": 1, "end": 2, "strand": "+"},
            {"start": 1, "end": 2, "strand": "-"},
        ])

    def test_forbidden_pattern_checks_every_expansion(self):
        inputs = {"forbidden_patterns": ["GAATTY"], "strand_mode": "forward"}
        self.assertTrue(bio.has_forbidden_motif("GAATTC", inputs))
        self.assertTrue(bio.has_forbidden_motif("GAATTT", inputs))
        self.assertFalse(bio.has_forbidden_motif("GAATTA", inputs))
        self.assertFalse(bio.has_forbidden_motif("GAATTG", inputs))

    def test_forbidden_reverse_complement(self):
        inputs = {"forbidden_patterns": ["AR"], "strand_mode": "forward"}
        self.assertFalse(bio.has_forbidden_motif("CT", inputs))
        inputs["strand_mode"] = "both"
        self.assertTrue(bio.has_forbidden_motif("CT", inputs))

    def test_short_sequence_has_no_match(self):
        self.assertEqual(bio.solve("dna.motif_positions", {
            "cds": "AC", "pattern": "NNN", "strand_mode": "both",
        }), [])

    def test_literal_hits_keep_their_existing_semantics(self):
        self.assertEqual(bio.hits("AAAA", "AN"), [])
        self.assertEqual(bio.hits("AAAA", "AA"), [1, 2, 3])

    def test_ambiguous_pattern_design_counterexamples(self):
        cases = [
            ("design.remove_dna_motifs", {
                "cds": "ATGCTCGAATTCGTTCGCGACTAG",
                "forbidden_patterns": ["GAATTY"], "strand_mode": "both",
            }, "ATGCTAGAGTTCGTAAGAGACTAG"),
            ("joint.clone_ready_cds", {
                "cds": "ATGACAGAATTCTTTGGTATCTAA",
                "forbidden_patterns": ["GAATTY"], "strand_mode": "both",
                "gc_bounds": ["2/9", "4/9"], "window": 9,
            }, "ATGACAGAGTTCTTTGGAATATAA"),
            ("joint.protein_edit_and_cloning", {
                "cds": "ATGGCCGATTTCGTCATCCAATGA",
                "forbidden_patterns": ["GAATTY"], "strand_mode": "both",
                "residue_index": 3, "target_aa": "E",
            }, "ATGGCCGAGTTCGTCATCCAATGA"),
        ]
        for task, inputs, expected in cases:
            with self.subTest(task=task):
                actual = bio.solve(task, inputs)
                self.assertEqual(actual, expected)
                self.assertFalse(bio.has_forbidden_motif(actual, inputs))


if __name__ == "__main__":
    unittest.main()
