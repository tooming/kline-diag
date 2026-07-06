#!/usr/bin/env python3
"""SGBD/PRG job parser (Protocol Explorer — "the gold mine").

BMW's EDIABAS .prg files (SGBDs) define every diagnostic job an ECU
supports: job name, arguments, results, and a description. The emdzej
`ediabasx-docs-sgbd` project renders those .prg files to markdown; this
parser turns that markdown into structured operation records, so the
platform's database instantly knows hundreds of operations per ECU —
each marked `documented` (not yet verified on the wire).

This does NOT invent opcodes. A parsed job is evidence that the operation
*exists* and what its arguments/results are; the raw request bytes still
come from a trace. That is exactly the honest split: parse -> documented,
trace -> observed, implement+test -> verified.

Input: sgbd_docs/*.md (job docs). Output: operation records for
operations.OperationDB.

Pure stdlib, offline.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SGBD_DIR = os.path.join(HERE, "sgbd_docs")

sys.path.insert(0, HERE)
from operations import make_operation  # noqa: E402

# Map SGBD file stem -> (ECU label). Extend as more docs are added.
SGBD_ECU = {
    "MS410DS0": "DME", "MS411DS1": "DME", "MS411DS2": "DME",
    "KOMBI39": "IKE", "IKE": "IKE", "C_KMB38": "IKE",
    "EWS3": "EWS", "EWS": "EWS",
    "ABS5": "ABS", "ABSMK20": "ABS",
    "IHKA39": "IHKA", "LCM": "LCM", "LCM_A": "LCM",
    "PDCE38": "PDC", "FBZV": "FBZV", "D_RADIO": "RADIO",
}

# Heuristic: classify a job as read vs write/actuate from its name.
WRITE_HINT = re.compile(
    r"schreib|loesch|reset|steuern|write|clear|erase|adaption|"
    r"codier|programmier|aktiv|stellgli|selbsttest", re.I)
ACTUATE_HINT = re.compile(r"steuern|aktiv|stellgli|selbsttest", re.I)


def _classify(job_name, desc):
    text = f"{job_name} {desc}"
    if ACTUATE_HINT.search(text):
        return "actuate"
    if WRITE_HINT.search(text):
        return "write"
    return "read"


def parse_sgbd_markdown(text, ecu):
    """Parse one SGBD markdown doc into operation records.

    Recognizes the emdzej format: a "### JOBNAME" heading, an optional
    description line, and Arguments/Results tables.
    """
    ops = []
    # Split on job headings. Job sections start with "### NAME" that also
    # appears in the index; use the anchored body sections (after "## Jobs"
    # or the <a id="job-..."> anchors).
    sections = re.split(r'\n###\s+', text)
    for sec in sections[1:]:
        lines = sec.splitlines()
        name = lines[0].strip()
        if not re.fullmatch(r"[A-Za-z0-9_]+", name):
            continue
        # skip document-structure headings that aren't jobs
        if name.lower() in ("index", "jobs", "tables", "results", "arguments",
                            "overview", "contents"):
            continue
        # description = first non-empty, non-table line after the heading
        desc = ""
        for ln in lines[1:]:
            s = ln.strip()
            if s and not s.startswith("|") and not s.startswith("#") \
                    and not s.startswith("_No") and not s.startswith("<a"):
                desc = s
                break
        args = _table_column(sec, "Arguments")
        results = _table_column(sec, "Results")
        kind = _classify(name, desc)
        ev = {"documented": True}
        op = make_operation(
            name=name.lower(), ecu=ecu, kind=kind,
            request=None, sgbd_job=name, description=desc, evidence=ev)
        op["args"] = args
        op["results"] = results
        ops.append(op)
    return ops


def _table_column(section, header):
    """Extract the first column (names) of the table under a '#### header'."""
    m = re.search(rf'####\s+{header}\s*\n(.*?)(?=\n####|\n###|\n##|\Z)',
                  section, re.S)
    if not m:
        return []
    names = []
    for row in re.findall(r'^\|\s*([^|]+?)\s*\|', m.group(1), re.M):
        r = row.strip()
        if r and r != "Name" and not set(r) <= set("-: "):
            names.append(r)
    return names


def parse_dir(path=SGBD_DIR):
    """Parse every sgbd_docs/*.md into operation records."""
    ops = []
    stats = {}
    if not os.path.isdir(path):
        return ops, stats
    for fn in sorted(os.listdir(path)):
        if not fn.endswith(".md"):
            continue
        stem = fn[:-3]
        ecu = SGBD_ECU.get(stem)
        if ecu is None:
            continue
        with open(os.path.join(path, fn), encoding="utf-8") as f:
            got = parse_sgbd_markdown(f.read(), ecu)
        ops.extend(got)
        stats[fn] = len(got)
    return ops, stats


if __name__ == "__main__":
    ops, stats = parse_dir()
    print(f"parsed {len(ops)} jobs from {len(stats)} SGBD docs:")
    for fn, n in stats.items():
        print(f"  {fn}: {n} jobs")
    kinds = {}
    for o in ops:
        kinds[o["kind"]] = kinds.get(o["kind"], 0) + 1
    print("by kind:", kinds)
