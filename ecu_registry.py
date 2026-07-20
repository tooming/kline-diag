#!/usr/bin/env python3
"""Generic body/chassis-module ECU registry + detection (companion to
dme_registry.py, which stays engine/DME-specific for its RAM-param-map
duties -- this covers everything else: GM/ZKE, EGS, EWS, ABS, IHKA, PDC,
RADIO, DSP, IKE, MRS, MID, TEL, LCM, FBZV, SZM, CDC, MFL).

Same problem dme_registry.py already solved for the DME, generalized: BMW
reuses one physical module address (e.g. 0x00 GM/ZKE) across many real ECU
part numbers/software revisions spanning chassis generations, and the SGBD
doc that correctly describes that module's status-group/actuator jobs
differs per revision. Guessing wrong here would repeat the exact bug
MS43's DME had (ms43_ram_params.json silently using a different real ECU's
addresses) -- see dme_registry.py's docstring for how that was found and
fixed. So MODULE_REGISTRY below only ever matches a REAL observed ident's
part-number prefix, never a documentation-based guess.

SGBD_CANDIDATES is a separate, much weaker signal: for each module address,
SGBD docs (from the sgbd_full submodule) whose own "ECU" info field
mentions this chassis, found by grepping sgbd_full for "E39"/"E38, E39" --
offered only as a head start for whoever next connects to the real car and
captures that module's ident, NEVER used to auto-select a param map or
claimed as a confirmed match. Where more than one doc plausibly applies
(common -- BMW has a dozen EGS/IHKA/ABS sub-revisions per chassis), all
plausible candidates are listed rather than picking one; where sgbd_docs/
already has a cached doc for this module (chosen in an earlier session,
before this file existed), that's included as a candidate too, still
unconfirmed against a real part number unless MODULE_REGISTRY says so.

MODULE_REGISTRY is empty today for every address -- this project has no
live-observed idents yet for anything but the DME. Fill in an entry the
same way dme_registry.py's MS41/MS43 entries were: connect to the real
car, capture the module's ident (E39Adapter.scan()'s ident_ascii), narrow
against SGBD_CANDIDATES (or ms4x.net/RomRaider-style community ECU-id
lists) which sgbd_full doc actually matches, and only then register it
here with its real part-number prefix.

Pure stdlib, offline -- SGBD_CANDIDATES is a static list, not a live
filesystem scan of the submodule (which may not even be checked out).
"""

# addr -> [{"sgbd": "<doc stem>", "name": "...", "part_numbers": [...]}]
# CONFIRMED matches only, each verified against a real observed ident.
MODULE_REGISTRY = {}

# addr -> [doc stems] -- chassis-narrowed hints only, not confirmed matches.
# Source: sgbd_full/docs/sgbd/*.md, each doc's own "ECU" info field grepped
# for an E38/E39 mention. Multiple entries per address are genuinely
# ambiguous sub-revisions (e.g. EGS's GS8.6x family) -- narrowing further
# needs the real car's ident, not more reading.
SGBD_CANDIDATES = {
    0x00: ["ZKE3_GM1"],                 # GM/ZKE: sole "E38, E39" Grundmodul
    0x08: ["SZM38"],                    # SZM: only "E38" in its own ECU
                                         # field -- E39 applicability (this
                                         # module likely being E38-shared)
                                         # unconfirmed
    0x18: ["CDC"],                      # CD changer: generic doc, era-
                                         # appropriate but chassis-unstated
    0x32: ["GS832", "GS8600", "GS8601", "GS8602", "GS8603", "GS8604"],
                                         # EGS: several "E38, E39" GS8.x
                                         # generations: this car's automatic
                                         # is contemporaneous with MS43/2003,
                                         # likely a GS8.60.x, but which
                                         # sub-revision needs a live ident
    0x44: ["EWS3"],                     # already cached in sgbd_docs/
    0x50: ["MFL"],                      # only "E38" in its own ECU field
    0x56: ["ABS5", "ABSMK20"],          # both cached in sgbd_docs/;
                                         # ABS5's own ECU field says E31/32/
                                         # 34/38 (no E39) -- ABSMK20 is the
                                         # more likely E39 candidate
    0x5B: ["IHKA39", "IHKA39_2", "IHKA39_3", "IHKA39_4", "IHKA39_5"],
                                         # IHKA39 cached in sgbd_docs/; 4
                                         # sibling revisions exist too
    0x60: ["PDCE38"],                   # already cached in sgbd_docs/
    0x68: ["D_RADIO"],                  # already cached in sgbd_docs/
    0x6A: ["DSP"],                      # sole "E38, E39" DSP-Booster
    0x80: ["KOMBI39", "IKE"],           # both cached in sgbd_docs/ under
                                         # different names for what's
                                         # likely the same physical module
    0xA4: ["MRS4"],                     # explicitly "Airbag SG E39 (Temic)"
    0xC0: [],                           # MID: the only MID*.md found is
                                         # E31-specific: E39's MID doc, if
                                         # it exists under a different name,
                                         # not yet located
    0xC8: [],                           # TEL: several TELE60/TELEFON/
                                         # TELIBUS docs exist, none with a
                                         # clear E39 mention in their ECU
                                         # field -- not narrowed
    0xD0: ["LCM", "LCM_A"],             # both cached in sgbd_docs/
    0xE8: ["FBZV"],                     # already cached in sgbd_docs/;
                                         # its own ECU field says "E38"
                                         # only, E39 applicability unconfirmed
}


def _digits(ident_ascii):
    return "".join(ch for ch in (ident_ascii or "") if ch.isdigit())


def detect_variant(addr, ident_ascii):
    """Match a module's real ident against MODULE_REGISTRY[addr]'s
    confirmed part numbers. Returns a descriptor with `matched: bool`;
    when unmatched, `observed_part` (for registering a real entry later)
    and `sgbd_candidates` (from SGBD_CANDIDATES, informational only -- not
    a match) are included so a future session has a head start."""
    digits = _digits(ident_ascii)
    for entry in MODULE_REGISTRY.get(addr, []):
        for pn in entry["part_numbers"]:
            if pn in digits:
                return {"matched": True, "sgbd": entry["sgbd"],
                        "name": entry["name"], "matched_part": pn}
    return {"matched": False, "sgbd": None, "name": None,
            "observed_part": digits[:8] or None,
            "sgbd_candidates": SGBD_CANDIDATES.get(addr, [])}
