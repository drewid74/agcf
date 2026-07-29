#!/usr/bin/env python3
"""
AGCF version bump — moves every version string together.

The README states that the repository tag always equals the version string in
AGCF-framework.md. That rule is only as good as the thing enforcing it, and
five files carry the version:

    AGCF-framework.md        **Version X.Y.Z (draft for review) · DD Month YYYY**
    catalog.json             meta.version, meta.date
    AGCF-assessment.html     embedded version string
    README.md                **vX.Y.Z (draft for review) · DD Month YYYY**
    AGCF-implementation.md   Companion to AGCF vX.Y.Z

Usage, from the repo root:

    python bump-version.py 0.9.5 --date "29 July 2026" \
        --note "v0.9.5 corrects v0.9.4, which shipped with ..."

    python bump-version.py 0.9.5 --date "29 July 2026" --dry-run

Then ALWAYS:

    python verify-consistency.py

Refuses to guess. If any file does not match the expected pattern it reports
and changes nothing — a partial bump is worse than no bump, because it produces
exactly the drift this script exists to prevent.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VER = r"\d+\.\d+\.\d+"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("version", help="new version, e.g. 0.9.5")
    ap.add_argument("--date", required=True, help='e.g. "29 July 2026"')
    ap.add_argument("--iso-date", help="ISO date for catalog.json meta.date; "
                                       "derived from --date if omitted")
    ap.add_argument("--note", help="sentence appended to the framework changelog "
                                   "paragraph. Say what changed and why.")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not re.fullmatch(VER, a.version):
        print(f"bad version {a.version!r}", file=sys.stderr)
        return 2

    iso = a.iso_date
    if not iso:
        import datetime
        try:
            iso = datetime.datetime.strptime(a.date, "%d %B %Y").strftime("%Y-%m-%d")
        except ValueError:
            print("could not derive ISO date; pass --iso-date", file=sys.stderr)
            return 2

    r = Path(a.repo)
    edits: list[tuple[Path, str, str]] = []   # (path, before, after)
    problems: list[str] = []

    def one(path: Path, pattern: str, repl: str, label: str, text: str) -> str:
        n = len(re.findall(pattern, text))
        if n != 1:
            problems.append(f"{path.name}: {label} matched {n} times, expected 1")
            return text
        return re.sub(pattern, repl, text)

    # --- AGCF-framework.md -------------------------------------------------
    p = r / "AGCF-framework.md"
    t0 = t = p.read_text(encoding="utf-8")
    t = one(p, rf"\*\*Version {VER} \(draft for review\) · [^*]+\*\*",
            f"**Version {a.version} (draft for review) · {a.date}**",
            "version header", t)
    if a.note:
        # the changelog is the single italic paragraph that ends with '.*'
        m = re.search(r"^\*v0\.9\.2 adds.*\*$", t, re.MULTILINE | re.DOTALL)
        if not m:
            problems.append("AGCF-framework.md: changelog paragraph not found")
        else:
            para = m.group(0)
            t = t.replace(para, para[:-1].rstrip() + " " + a.note.strip() + "*")
    edits.append((p, t0, t))

    # --- catalog.json ------------------------------------------------------
    # catalog.json is the authoritative source of the CURRENT version. Read it
    # first, then use that exact string to find the version elsewhere. Do not
    # discover versions by regex in the HTML: ISO 42001 clause references
    # ("A.6.2.2", "Clause 9.1") match a bare \d+\.\d+\.\d+ and a blind
    # search-and-replace would silently rewrite the crosswalk data.
    p = r / "catalog.json"
    t0 = p.read_text(encoding="utf-8")
    d = json.loads(t0)
    m = re.match(rf"({VER})", str(d["meta"].get("version", "")))
    if not m:
        problems.append("catalog.json: meta.version is not an X.Y.Z string")
        old_version = None
    else:
        old_version = m.group(1)
    d["meta"]["version"] = f"{a.version} (draft for review)"
    d["meta"]["date"] = iso
    edits.append((p, t0, json.dumps(d, indent=2, ensure_ascii=False) + "\n"))

    # --- AGCF-assessment.html ---------------------------------------------
    p = r / "AGCF-assessment.html"
    t0 = t = p.read_text(encoding="utf-8")
    if old_version:
        n = len(re.findall(rf"\b{re.escape(old_version)}\b", t))
        if n == 0:
            problems.append(f"AGCF-assessment.html: does not contain the current "
                            f"version {old_version} — it is already out of sync")
        else:
            t = re.sub(rf"\b{re.escape(old_version)}\b", a.version, t)
            print(f"  (assessment.html: {n} occurrence(s) of {old_version})")
    edits.append((p, t0, t))

    # --- README.md ---------------------------------------------------------
    p = r / "README.md"
    t0 = t = p.read_text(encoding="utf-8")
    t = one(p, rf"\*\*v{VER} \(draft for review\) · [^*]+\*\*",
            f"**v{a.version} (draft for review) · {a.date}**", "README version", t)
    edits.append((p, t0, t))

    # --- AGCF-implementation.md -------------------------------------------
    p = r / "AGCF-implementation.md"
    t0 = t = p.read_text(encoding="utf-8")
    t = one(p, rf"Companion to AGCF v{VER}", f"Companion to AGCF v{a.version}",
            "companion pointer", t)
    edits.append((p, t0, t))

    if problems:
        print("REFUSING TO BUMP — nothing written:\n", file=sys.stderr)
        for x in problems:
            print(f"  {x}", file=sys.stderr)
        return 1

    changed = [(p, b, n) for p, b, n in edits if b != n]
    for p, before, after in changed:
        print(f"  {p.name}: {len(before)} -> {len(after)} bytes")
        if not a.dry_run:
            p.write_text(after, encoding="utf-8")

    if a.dry_run:
        print(f"\ndry run — {len(changed)} file(s) would change")
    else:
        print(f"\nbumped {len(changed)} file(s) to {a.version}")
        print("NOW RUN: python verify-consistency.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
