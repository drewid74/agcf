#!/usr/bin/env python3
"""
AGCF pre-tag consistency gate.

The catalogue exists in three places — catalog.json, AGCF-framework.md, and
embedded inside AGCF-assessment.html — plus version strings in README.md and
AGCF-implementation.md. Every release requires all of them to move together,
and v0.9.4 shipped with the assessment tool a control behind the catalogue
because nothing checked.

This is the check. Run it before every tag:

    python verify-consistency.py            # from the repo root
    python verify-consistency.py --repo .   # explicit

Exit 0 = consistent. Exit 1 = do not tag.

Deliberately has no dependencies beyond the standard library, so it can run in
CI, in a git pre-push hook, or on a machine with nothing installed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FAIL: list[str] = []
WARN: list[str] = []
OK: list[str] = []


def fail(msg: str) -> None:
    FAIL.append(msg)


def warn(msg: str) -> None:
    WARN.append(msg)


def ok(msg: str) -> None:
    OK.append(msg)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

CTRL_RE = re.compile(
    r"^\*\*(?P<id>[A-Z]{3}-\d{2}) · (?P<title>[^*]+?)\*\*\s+`(?P<tier>T\d)`\s+`(?P<aut>A\d\+?)`\s*\n"
    r"(?P<statement>.*?)\s*\n"
    r"\*Evidence:\*\s*(?P<evidence>.*?)\s*\n",
    re.MULTILINE | re.DOTALL)


def parse_catalog(p: Path) -> dict:
    d = json.loads(p.read_text(encoding="utf-8"))
    ctrls = {}
    for dom in d["domains"]:
        for c in dom["controls"]:
            ctrls[c["id"]] = {
                "title": c.get("title", ""),
                "statement": " ".join(c.get("statement", "").split()),
                "evidence": " ".join(c.get("evidence", "").split()),
                "tier": c.get("tier"),
                "autonomy": c.get("autonomy"),
                "domain": dom["id"],
            }
    return {"version": d["meta"].get("version", ""),
            "date": d["meta"].get("date", ""),
            "controls": ctrls, "raw": d}


def parse_framework(p: Path) -> dict:
    s = p.read_text(encoding="utf-8")
    ctrls = {}
    for m in CTRL_RE.finditer(s):
        stmt = " ".join(m.group("statement").split())
        # strip trailing markdown hard-break spaces
        ctrls[m.group("id")] = {
            "title": m.group("title").strip(),
            "statement": stmt,
            "evidence": " ".join(m.group("evidence").split()),
            "tier": m.group("tier"),
            "autonomy": m.group("aut").rstrip("+"),
        }
    v = re.search(r"\*\*Version (\d+\.\d+\.\d+)", s)
    return {"version": v.group(1) if v else None, "controls": ctrls, "text": s}


def parse_assessment(p: Path) -> dict:
    s = p.read_text(encoding="utf-8")
    ids = set(re.findall(r"\b([A-Z]{3}-\d{2})\b", s))
    v = set(re.findall(r"\b(\d+\.\d+\.\d+)\b", s))
    return {"ids": ids, "versions": v, "text": s}


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_versions(cat, fw, asmt, readme_text, impl_text):
    cv = re.match(r"(\d+\.\d+\.\d+)", cat["version"])
    cv = cv.group(1) if cv else None
    versions = {"catalog.json": cv, "AGCF-framework.md": fw["version"]}

    m = re.search(r"\*\*v(\d+\.\d+\.\d+)", readme_text)
    versions["README.md"] = m.group(1) if m else None
    m = re.search(r"Companion to AGCF v(\d+\.\d+\.\d+)", impl_text)
    versions["AGCF-implementation.md"] = m.group(1) if m else None

    distinct = {v for v in versions.values() if v}
    if len(distinct) == 1:
        ok(f"version consistent across 4 files: {distinct.pop()}")
    else:
        fail("version strings disagree: "
             + ", ".join(f"{k}={v}" for k, v in versions.items()))

    target = versions["catalog.json"]
    if target and target not in asmt["versions"]:
        fail(f"AGCF-assessment.html does not contain version {target} "
             f"(found: {sorted(asmt['versions']) or 'none'})")
    elif target:
        ok(f"AGCF-assessment.html carries version {target}")
    return target


def check_control_sets(cat, fw, asmt):
    c, f = set(cat["controls"]), set(fw["controls"])
    if c == f:
        ok(f"catalog.json and AGCF-framework.md agree on {len(c)} control IDs")
    else:
        if c - f:
            fail(f"in catalog.json but NOT in framework: {sorted(c - f)}")
        if f - c:
            fail(f"in framework but NOT in catalog.json: {sorted(f - c)}")

    missing_html = sorted(c - asmt["ids"])
    if missing_html:
        fail(f"controls missing from AGCF-assessment.html: {missing_html}")
    else:
        ok(f"AGCF-assessment.html contains all {len(c)} control IDs")

    extra_html = sorted(asmt["ids"] - c)
    if extra_html:
        warn(f"IDs in assessment.html not in catalog (may be prose): {extra_html}")


def check_text_match(cat, fw):
    diffs = 0
    for cid in sorted(set(cat["controls"]) & set(fw["controls"])):
        a, b = cat["controls"][cid], fw["controls"][cid]
        for field in ("statement", "evidence"):
            if a[field] != b[field]:
                diffs += 1
                fail(f"{cid} {field} differs between catalog.json and framework\n"
                     f"      catalog:   {a[field][:110]}\n"
                     f"      framework: {b[field][:110]}")
        if a["tier"] != b["tier"]:
            diffs += 1
            fail(f"{cid} tier differs: catalog={a['tier']} framework={b['tier']}")
        if a["autonomy"] != b["autonomy"]:
            diffs += 1
            fail(f"{cid} autonomy differs: catalog={a['autonomy']} framework={b['autonomy']}")
    if not diffs:
        ok("statement, evidence, tier and autonomy match for every control")


def check_counts_and_appendices(cat, fw):
    ctrls = cat["controls"]
    n = len(ctrls)
    text = fw["text"]

    for phrase in (f"lists {n} controls", f"— {n} controls with statements",
                   f"{n} controls across 12 domains", f"How many of the {n} controls"):
        if phrase not in text:
            fail(f"framework prose does not say '{phrase}' — stale control count?")
    if not FAIL or all("prose" not in x for x in FAIL):
        ok(f"framework prose counts agree on {n} controls")

    TN = {"T1": 1, "T2": 2, "T3": 3}
    an = lambda a: int(str(a).replace("A", "").replace("+", ""))
    C = {T: [sum(1 for v in ctrls.values()
                 if TN[v["tier"]] <= TN[T] and an(v["autonomy"]) <= A)
             for A in range(5)] for T in ("T1", "T2", "T3")}
    for T in ("T1", "T2", "T3"):
        expect = f"| **{T}** | " + " | ".join(map(str, C[T])) + " |"
        if expect not in text:
            m = re.search(rf"^\| \*\*{T}\*\* \|.*$", text, re.MULTILINE)
            fail(f"Appendix C {T} row wrong.\n      expected: {expect}\n"
                 f"      found:    {m.group(0) if m else '<missing>'}")
    if not any("Appendix C" in x for x in FAIL):
        ok("Appendix C applicability matrix matches catalog.json")

    by_dom = {}
    for v in ctrls.values():
        d = by_dom.setdefault(v["domain"], [0, 0, 0, 0])
        d[0] += 1
        d[{"T1": 1, "T2": 2, "T3": 3}[v["tier"]]] += 1
    gt = [sum(d[i] for d in by_dom.values()) for i in range(4)]
    expect_total = f"| | **Total** | **{gt[0]}** | {gt[1]} | {gt[2]} | {gt[3]} |"
    if expect_total not in text:
        m = re.search(r"^\| \| \*\*Total\*\*.*$", text, re.MULTILINE)
        fail(f"Appendix D total row wrong.\n      expected: {expect_total}\n"
             f"      found:    {m.group(0) if m else '<missing>'}")
    else:
        ok("Appendix D totals match catalog.json")


def check_crosswalk(cat, fw):
    text = fw["text"]
    missing = [cid for cid in sorted(cat["controls"])
               if not re.search(rf"^\| {re.escape(cid)} \|", text, re.MULTILINE)]
    if missing:
        fail(f"controls with no crosswalk table row: {missing}")
    else:
        ok(f"every control has a crosswalk row ({len(cat['controls'])})")


def check_held_files(repo: Path):
    """The two files deliberately excluded from the public repo."""
    for name in ("AGCF-implementation-worked-example.md", "drew-stack-prefilled.json"):
        gi = repo / ".gitignore"
        if gi.exists() and name in gi.read_text(encoding="utf-8"):
            ok(f"{name} is gitignored")
        else:
            fail(f"{name} is NOT in .gitignore — it can be committed by accident")


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    a = ap.parse_args()
    r = Path(a.repo)

    need = ["catalog.json", "AGCF-framework.md", "AGCF-assessment.html",
            "README.md", "AGCF-implementation.md"]
    for f in need:
        if not (r / f).exists():
            print(f"missing required file: {f}", file=sys.stderr)
            return 2

    cat = parse_catalog(r / "catalog.json")
    fw = parse_framework(r / "AGCF-framework.md")
    asmt = parse_assessment(r / "AGCF-assessment.html")
    readme = (r / "README.md").read_text(encoding="utf-8")
    impl = (r / "AGCF-implementation.md").read_text(encoding="utf-8")

    if not fw["controls"]:
        print("parsed 0 controls from AGCF-framework.md — the control block "
              "format may have changed; update CTRL_RE.", file=sys.stderr)
        return 2

    check_versions(cat, fw, asmt, readme, impl)
    check_control_sets(cat, fw, asmt)
    check_text_match(cat, fw)
    check_counts_and_appendices(cat, fw)
    check_crosswalk(cat, fw)
    check_held_files(r)

    print(f"\nAGCF consistency check — {len(cat['controls'])} controls\n")
    for m in OK:
        print(f"  [ok]   {m}")
    for m in WARN:
        print(f"  [warn] {m}")
    for m in FAIL:
        print(f"  [FAIL] {m}")

    if FAIL:
        print(f"\n{len(FAIL)} failure(s) — DO NOT TAG\n")
        return 1
    print(f"\nconsistent{' (' + str(len(WARN)) + ' warning(s))' if WARN else ''} — safe to tag\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
