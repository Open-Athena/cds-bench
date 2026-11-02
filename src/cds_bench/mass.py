"""Exact decimal mass convention; provenance is documented in the reference bank."""

from decimal import Decimal


ISOTOPE_MASSES = dict(zip("CHNOS", map(Decimal, [
    "12.00000000000", "1.00782503223", "14.00307400443",
    "15.99491461957", "31.9720711744",
])))

# Incorporated residues: neutral free amino-acid formula minus H2O.
# Element order is C, H, N, O, S.
RESIDUE_FORMULAS = dict(zip("ACDEFGHIKLMNPQRSTVWY", [
    (3, 5, 1, 1, 0), (3, 5, 1, 1, 1), (4, 5, 1, 3, 0), (5, 7, 1, 3, 0),
    (9, 9, 1, 1, 0), (2, 3, 1, 1, 0), (6, 7, 3, 1, 0), (6, 11, 1, 1, 0),
    (6, 12, 2, 1, 0), (6, 11, 1, 1, 0), (5, 9, 1, 1, 1), (4, 6, 2, 2, 0),
    (5, 7, 1, 1, 0), (5, 8, 2, 2, 0), (6, 12, 4, 1, 0), (3, 5, 1, 2, 0),
    (4, 7, 1, 2, 0), (5, 9, 1, 1, 0), (11, 10, 2, 1, 0), (9, 9, 1, 2, 0),
]))
RESIDUE_MASSES = {
    aa: sum(ISOTOPE_MASSES[element] * count for element, count in zip("CHNOS", formula))
    for aa, formula in RESIDUE_FORMULAS.items()
}
WATER_MASS = 2 * ISOTOPE_MASSES["H"] + ISOTOPE_MASSES["O"]
