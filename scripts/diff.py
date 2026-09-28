#!/usr/bin/env python3
"""Compare two snapshots and answer three questions with evidence.

1. **Did it get better?**   Findings fixed, introduced and still open (check.py
   run on both sides).
2. **Did anything break?**  The preservation contract: pages lost, noindex
   added, canonicals changed, structured data removed or broken, headings or
   titles dropped. Anything the approved plan did not ask for is a Fail.
3. **Did we ship what we showed?**  Every change an approved batch promised
   (see references/batch-schema.md) is looked up in the after-snapshot and
   marked delivered or missing. A change that was shown at a gate but never
   landed is a Fail, and so is one that landed differently.

Exit status is 0 when the verdict is PASS and 1 when it is FAIL, so this can
gate a CI job or a deploy.

Usage:
  diff.py before.json after.json [--plan plan.json] [--out diff.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check  # noqa: E402

FIELD_READERS = {
    "title": lambda f: (f.get("title") or [None])[0],
    "meta_description": lambda f: next((d.strip() for d in f.get("meta_description", []) if d.strip()), None),
    "canonical": lambda f: (f.get("canonical") or [None])[0],
    "meta_robots": lambda f: " ".join(f.get("meta_robots", [])).lower() or None,
    "h1": lambda f: (f.get("h1") or [None])[0],
    "jsonld_types": lambda f: sorted({t for j in f.get("jsonld", []) if j.get("valid") for t in j.get("types", [])}),
    "images_missing_alt": lambda f: len(f.get("images", {}).get("missing_alt", [])),
}


def read_field(field: str, f: dict):
    """og:* and twitter:* fields read straight from those tag maps."""
    if field.startswith("og:"):
        return (f.get("og") or {}).get(field)
    if field.startswith("twitter:"):
        return (f.get("twitter") or {}).get(field)
    return FIELD_READERS[field](f)


def facts(page: dict | None) -> dict:
    return (page or {}).get("raw") or {}


def promised_index(plan: dict | None) -> dict[tuple[str, str], list[dict]]:
    idx: dict[tuple[str, str], list[dict]] = {}
    for batch in (plan or {}).get("batches", []):
        if not batch.get("approved", True):
            continue
        for ch in batch.get("changes", []):
            idx.setdefault((ch["path"], ch["field"]), []).append({**ch, "batch": batch["id"]})
    return idx


def delivered(change: dict, value) -> bool:
    want = change.get("after")
    if change["field"] == "jsonld_types":
        return set(want or []) <= set(value or [])
    if change["field"] == "images_missing_alt":
        return value == want
    if isinstance(want, str) and isinstance(value, str):
        return " ".join(want.split()) == " ".join(value.split())
    return want == value


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--plan", help="plan.json with the approved batches")
    ap.add_argument("--out")
    args = ap.parse_args()

    before, after = (json.load(open(p)) for p in (args.before, args.after))
    plan = json.load(open(args.plan)) if args.plan else None
    promised = promised_index(plan)

    b_pages = {p["path"]: p for p in before["pages"]}
    a_pages = {p["path"]: p for p in after["pages"]}

    preservation: list[dict] = []

    def breach(kind, path, severity, detail, before_v=None, after_v=None):
        preservation.append({"check": kind, "path": path, "result": severity, "detail": detail,
                             "before": before_v, "after": after_v})

    for path, bp in b_pages.items():
        ap_ = a_pages.get(path)
        if bp.get("status") != 200:
            continue
        if ap_ is None:
            breach("page-not-checked", path, "REVIEW", "page is in the before-snapshot but was not fetched after; re-run with --paths-from")
            continue
        if ap_.get("status") != 200:
            breach("page-lost", path, "FAIL", f"was 200, now {ap_.get('status') or ap_.get('error')}", 200, ap_.get("status"))
            continue
        bf, af = facts(bp), facts(ap_)
        for field in ("title", "meta_description", "canonical", "h1"):
            bv, av = FIELD_READERS[field](bf), FIELD_READERS[field](af)
            if bv == av or (isinstance(bv, str) and isinstance(av, str) and " ".join(bv.split()) == " ".join(av.split())):
                continue
            if (path, field) in promised:
                continue  # judged below, against what was promised
            if bv and not av:
                breach(f"{field}-removed", path, "FAIL", f"{field} was present and is now gone", bv, av)
            else:
                breach(f"{field}-changed", path, "FAIL" if field == "canonical" else "REVIEW",
                       f"{field} changed but no approved batch asked for it", bv, av)
        b_rob, a_rob = FIELD_READERS["meta_robots"](bf) or "", FIELD_READERS["meta_robots"](af) or ""
        if "noindex" in a_rob and "noindex" not in b_rob and (path, "meta_robots") not in promised:
            breach("noindex-added", path, "FAIL", "page is now marked noindex", b_rob or None, a_rob)
        if ap_.get("x_robots_tag") != bp.get("x_robots_tag") and "noindex" in (ap_.get("x_robots_tag") or "").lower():
            breach("noindex-added", path, "FAIL", "X-Robots-Tag header now carries noindex", bp.get("x_robots_tag"), ap_.get("x_robots_tag"))
        b_types, a_types = set(FIELD_READERS["jsonld_types"](bf)), set(FIELD_READERS["jsonld_types"](af))
        lost = b_types - a_types
        if lost and (path, "jsonld_types") not in promised:
            breach("structured-data-removed", path, "FAIL", f"types no longer present: {sorted(lost)}", sorted(b_types), sorted(a_types))
        b_bad = sum(1 for j in bf.get("jsonld", []) if not j.get("valid"))
        a_bad = sum(1 for j in af.get("jsonld", []) if not j.get("valid"))
        if a_bad > b_bad:
            breach("structured-data-broken", path, "FAIL", f"{a_bad - b_bad} more invalid JSON-LD block(s)", b_bad, a_bad)
        lost_links = sorted(set(bf.get("internal_links", [])) - set(af.get("internal_links", [])))
        if lost_links:
            breach("internal-links-removed", path, "REVIEW", f"{len(lost_links)} internal link(s) gone", lost_links[:20], None)

    b_sm, a_sm = set(before.get("sitemap_paths", [])), set(after.get("sitemap_paths", []))
    if b_sm and not a_sm:
        breach("sitemap-removed", "/sitemap.xml", "FAIL", "the sitemap listed pages before and lists none now", len(b_sm), 0)
    elif b_sm - a_sm:
        breach("sitemap-paths-removed", "/sitemap.xml", "REVIEW", f"{len(b_sm - a_sm)} path(s) no longer listed", sorted(b_sm - a_sm)[:20], None)
    b_dis = {(r["path"]) for g in before["robots"]["parsed"]["groups"] for r in g["rules"] if r["type"] == "disallow"}
    a_dis = {(r["path"]) for g in after["robots"]["parsed"]["groups"] for r in g["rules"] if r["type"] == "disallow"}
    if a_dis - b_dis:
        breach("robots-disallow-added", "/robots.txt", "REVIEW", "new Disallow rules", sorted(b_dis), sorted(a_dis))

    promises = []
    for (path, field), changes in promised.items():
        value = read_field(field, facts(a_pages.get(path)))
        for ch in changes:
            promises.append({"batch": ch["batch"], "path": path, "field": field, "promised": ch.get("after"),
                             "actual": value, "result": "DELIVERED" if delivered(ch, value) else "MISSING"})

    b_find, a_find = check.run(before), check.run(after)
    key = lambda f: (f["rule"], f["path"])
    b_keys, a_keys = {key(f) for f in b_find}, {key(f) for f in a_find}
    by_key_after = {key(f): f for f in a_find}
    by_key_before = {key(f): f for f in b_find}
    compared = set(a_pages) | {"/sitemap.xml"}
    fixed = [by_key_before[k] for k in sorted(b_keys - a_keys) if k[1] in compared]
    introduced = [by_key_after[k] for k in sorted(a_keys - b_keys)]
    persisting = [by_key_after[k] for k in sorted(a_keys & b_keys)]

    fails = [p for p in preservation if p["result"] == "FAIL"]
    missing = [p for p in promises if p["result"] == "MISSING"]
    new_errors = [f for f in introduced if f["severity"] == "error"]
    verdict = "FAIL" if (fails or missing or new_errors) else "PASS"

    result = {
        "tool": "proof-seo/diff", "version": 1, "verdict": verdict,
        "before": {"file": args.before, "origin": before["origin"], "taken_at": before["taken_at"], "pages": len(b_pages)},
        "after": {"file": args.after, "origin": after["origin"], "taken_at": after["taken_at"], "pages": len(a_pages)},
        "counts": {"fixed": len(fixed), "introduced": len(introduced), "persisting": len(persisting),
                   "preservation_fail": len(fails), "preservation_review": sum(p["result"] == "REVIEW" for p in preservation),
                   "promised": len(promises), "delivered": len(promises) - len(missing)},
        "preservation": preservation, "promises": promises,
        "findings": {"fixed": fixed, "introduced": introduced, "persisting": persisting},
    }
    if args.out:
        with open(args.out, "w") as f:
            json.dump(result, f, indent=1)
    c = result["counts"]
    print(f"verdict: {verdict}", file=sys.stderr)
    print(f"  findings: {c['fixed']} fixed, {c['introduced']} introduced, {c['persisting']} still open", file=sys.stderr)
    print(f"  preservation: {c['preservation_fail']} fail, {c['preservation_review']} to review", file=sys.stderr)
    if promises:
        print(f"  promised changes: {c['delivered']}/{c['promised']} delivered", file=sys.stderr)
    for p in fails + missing:
        print(f"  FAIL {p.get('check') or p['field']} {p['path']}: {p.get('detail') or ('promised ' + repr(p['promised']) + ', got ' + repr(p['actual']))}", file=sys.stderr)
    for f in new_errors:
        print(f"  FAIL new {f['rule']} {f['path']}: {f['detail']}", file=sys.stderr)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
