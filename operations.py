#!/usr/bin/env python3
"""BMW operation database with graded Evidence (Protocol Explorer core).

Reframes the platform from "features" to "an open BMW protocol database".
Every diagnostic operation (per ECU) is a record carrying an EVIDENCE grade
rather than a binary implemented/not. This is the honest data model: a job
documented in BMW's SGBD but never seen on the wire is "documented, not
verified"; one captured in a trace is "observed"; one our code sends and
reads back is "verified".

Evidence flags (all default False):
    documented  - appears in a BMW SGBD/PRG job definition
    observed    - seen in a captured OEM-tool trace
    implemented - this platform can construct the request
    tested      - exercised end-to-end (demo or car), result checked
    safe        - read-only, or write with verified rollback
    rollback    - a restore path exists (transaction layer)

An operation is "usable on the car" only when implemented AND (safe OR
tested). A write with no rollback and no trace stays clearly ungated.

Data lives in operations.json (seeded here + importable from SGBD parsing).
Pure stdlib, offline.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "operations.json")

EVIDENCE_FIELDS = ("documented", "observed", "implemented",
                   "tested", "safe", "rollback")


def blank_evidence():
    return {k: False for k in EVIDENCE_FIELDS}


def make_operation(name, ecu, kind="read", request=None, sgbd_job=None,
                   description="", evidence=None):
    ev = blank_evidence()
    if evidence:
        ev.update({k: bool(v) for k, v in evidence.items()
                   if k in EVIDENCE_FIELDS})
    return {"name": name, "ecu": ecu, "kind": kind,
            "request": request, "sgbd_job": sgbd_job,
            "description": description, "evidence": ev}


def evidence_grade(op):
    """One-word grade for UI/reporting, derived from the flags."""
    e = op.get("evidence", {})
    if e.get("tested") and e.get("implemented"):
        return "verified"
    if e.get("implemented") and e.get("safe"):
        return "implemented-safe"
    if e.get("observed"):
        return "observed"
    if e.get("documented"):
        return "documented"
    return "unknown"


def usable_on_car(op):
    """True only if we can construct it AND it is safe or tested. Writes
    with neither stay unusable — this is the honesty gate."""
    e = op.get("evidence", {})
    return bool(e.get("implemented") and (e.get("safe") or e.get("tested")))


class OperationDB:
    def __init__(self, ops=None):
        # keyed by (ecu, name)
        self._ops = {}
        for op in (ops or []):
            self.add(op)

    def add(self, op, merge=True):
        key = (op["ecu"], op["name"])
        if merge and key in self._ops:
            # merge evidence (OR the flags), keep richest fields
            cur = self._ops[key]
            for k in EVIDENCE_FIELDS:
                cur["evidence"][k] = cur["evidence"].get(k) or \
                    op["evidence"].get(k)
            for f in ("request", "sgbd_job", "description"):
                if not cur.get(f) and op.get(f):
                    cur[f] = op[f]
        else:
            self._ops[key] = op
        return self._ops[key]

    def get(self, ecu, name):
        return self._ops.get((ecu, name))

    def all(self, ecu=None, kind=None):
        return [o for o in self._ops.values()
                if (ecu is None or o["ecu"] == ecu)
                and (kind is None or o["kind"] == kind)]

    def ecus(self):
        return sorted({o["ecu"] for o in self._ops.values()})

    def summary(self):
        grades = {}
        for o in self._ops.values():
            g = evidence_grade(o)
            grades[g] = grades.get(g, 0) + 1
        return {"total": len(self._ops), "by_grade": grades,
                "usable_on_car": sum(1 for o in self._ops.values()
                                     if usable_on_car(o))}

    def save(self, path=DB_PATH):
        data = {"_schema": "bmw-operations-v1",
                "_evidence_fields": list(EVIDENCE_FIELDS),
                "operations": list(self._ops.values())}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)

    @classmethod
    def load(cls, path=DB_PATH):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(data.get("operations", []))


def seed_db():
    """Seed the DB with operations this platform has actually verified this
    session (evidence graded honestly), so the database starts truthful."""
    ops = [
        # DS2 read-only, implemented + tested + safe on the E39:
        make_operation("read_ident", "DME", "read", "00",
                       "IDENT", "ECU identification",
                       {"documented": True, "implemented": True,
                        "tested": True, "safe": True}),
        make_operation("read_faults", "DME", "read", "04",
                       "FS_LESEN", "Read fault memory",
                       {"documented": True, "implemented": True,
                        "tested": True, "safe": True}),
        make_operation("read_live_block", "DME", "read", "0B 03",
                       "STATUS_*", "MS41 status/live block",
                       {"documented": True, "implemented": True,
                        "tested": True, "safe": True}),
        make_operation("ram_read", "DME", "read", "0B 01 / 0B 00",
                       None, "Read-only RAM via address list",
                       {"implemented": True, "tested": True, "safe": True}),
        make_operation("clear_faults", "DME", "write", "04-based",
                       "FS_LOESCHEN", "Clear fault memory (has rollback "
                       "snapshot)",
                       {"documented": True, "implemented": True,
                        "tested": True, "rollback": True, "safe": True}),
        # Writes documented but opcode not confirmed -> honestly ungated:
        make_operation("erase_adaptation", "DME", "write", "43 <mask_hi> <mask_lo>",
                       "ADAP_SELEKTIV_LOESCHEN",
                       "Selective adaptation erase — opcode 0x43+mask "
                       "confirmed by TWO independent sources (RomRaider + "
                       "emdzej/j2534); not yet car-verified; reversible",
                       {"documented": True, "observed": True,
                        "implemented": True, "rollback": True}),
        make_operation("actuator_control", "DME", "actuate", "22 <id> <val>",
                       "STEUERN_*",
                       "Component activation (fuel pump, fan, VANOS valve, "
                       "purge…); opcode 0x22+id sourced from emdzej/j2534 "
                       "(MS43); STOP=0x0A; verify ids per-engine",
                       {"documented": True, "observed": True,
                        "implemented": True}),
        make_operation("oil_service_reset", "IKE", "write", None,
                       "SIA_RESET", "Reset service interval (opcode "
                       "unconfirmed)",
                       {"documented": True, "implemented": False}),
        make_operation("read_faults", "IKE", "read", "04",
                       "FS_LESEN", "Read cluster fault memory",
                       {"documented": True, "implemented": True,
                        "tested": True, "safe": True}),
    ]
    return OperationDB(ops)


if __name__ == "__main__":
    db = seed_db()
    db.save()
    print(json.dumps(db.summary(), indent=2))
    for o in db.all():
        print(f"  [{evidence_grade(o):16}] {o['ecu']:4} {o['name']:20} "
              f"{'CAR-USABLE' if usable_on_car(o) else 'gated'}")
