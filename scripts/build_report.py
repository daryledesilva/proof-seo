#!/usr/bin/env python3
"""Build the final before/after report: one self-contained HTML page.

It states what was promised at the gate and whether each promise landed,
which findings were fixed, what the preservation contract found, and what is
still open. It is honest about status: "validated preview" (checked against a
local or staging build, not yet live), "implemented" (merged, not yet
re-checked live) or "live-verified" (re-snapshotted in production). It also
says plainly that rankings are not measured here: crawling alone takes days
to weeks, so the report ends with what to check later and where.

Usage:
  build_report.py --diff diff.json --plan plan.json --status preview --out report.html
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
from collections import defaultdict

STATUS_COPY = {
    "preview": ("Validated preview", "Checked against a local or staging build of the change. Nothing is live yet."),
    "implemented": ("Implemented", "Merged into the codebase. Not yet re-checked on the live site."),
    "live-verified": ("Live-verified", "Re-snapshotted on the live site after deploy and compared against the original baseline."),
}
RECRAWL_SOURCE = "https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl"
RECRAWL_QUOTE = "Crawling can take anywhere from a few days to a few weeks."

CSS = """
:root{--ink:#15171c;--muted:#5b616e;--line:#e2e5eb;--bg:#f5f6f8;--card:#fff;--pass:#11622f;--passbg:#e5f5ea;--fail:#8a1c1c;--failbg:#fdeaea;
--review:#7a4b00;--reviewbg:#fff3d6;--accent:#1f4fd1}
@media (prefers-color-scheme:dark){:root{--ink:#e8eaef;--muted:#a3a9b6;--line:#2c313b;--bg:#12151a;--card:#1a1e25;--pass:#7fd49a;--passbg:#15301f;
--fail:#f0a0a0;--failbg:#3a1a1a;--review:#f0c674;--reviewbg:#35290f;--accent:#8fb0ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:980px;margin:0 auto;padding:32px 20px 64px}h1{font-size:1.7rem;margin:.2rem 0 .4rem;text-wrap:balance}
h2{font-size:1.1rem;margin:2.2rem 0 .7rem}.muted{color:var(--muted)}a{color:var(--accent)}
.status{display:inline-block;font-size:.75rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:3px 8px;border-radius:5px;border:1.5px solid currentColor}
.verdict{display:flex;flex-wrap:wrap;gap:12px;margin:1.2rem 0}.tile{flex:1 1 150px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.tile .n{font-size:1.8rem;font-weight:700;font-variant-numeric:tabular-nums}.tile .k{color:var(--muted);font-size:.85rem}
.pass{color:var(--pass)}.fail{color:var(--fail)}.review{color:var(--review)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:4px 0;margin:0 0 12px}
.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{text-align:left;vertical-align:top;padding:8px 14px;border-bottom:1px solid var(--line)}
tr:last-child td{border-bottom:0}th{color:var(--muted);font-weight:600}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.84rem}
.pill{display:inline-block;font-size:.72rem;font-weight:700;padding:2px 7px;border-radius:999px}
.p-pass{background:var(--passbg);color:var(--pass)}.p-fail{background:var(--failbg);color:var(--fail)}.p-review{background:var(--reviewbg);color:var(--review)}
blockquote{margin:.5rem 0;padding:.5rem .9rem;border-left:3px solid var(--line);color:var(--muted)}
"""


def esc(v) -> str:
    if isinstance(v, (list, dict)):
        v = json.dumps(v, ensure_ascii=False)
    return html.escape("" if v is None else str(v))


def pill(result: str) -> str:
    cls = {"DELIVERED": "p-pass", "PASS": "p-pass", "FAIL": "p-fail", "MISSING": "p-fail", "REVIEW": "p-review"}.get(result, "p-review")
    return f'<span class="pill {cls}">{esc(result)}</span>'


def table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return '<p class="muted">None.</p>'
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="card table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def by_rule(findings: list[dict]) -> list[list[str]]:
    groups = defaultdict(list)
    for f in findings:
        groups[(f["severity"], f["rule"], f["summary"], f["source"])].append(f["path"])
    order = {"error": 0, "warning": 1, "info": 2}
    rows = []
    for (sev, rule, summary, source), paths in sorted(groups.items(), key=lambda kv: (order[kv[0][0]], kv[0][1])):
        shown = ", ".join(paths[:6]) + (f" and {len(paths) - 6} more" if len(paths) > 6 else "")
        rows.append([esc(sev), f'{esc(summary)} <span class="muted mono">{esc(rule)}</span>', str(len(paths)),
                     f'<span class="mono">{esc(shown)}</span>', f'<a href="{esc(source)}" target="_blank" rel="noopener">source</a>'])
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--diff", required=True)
    ap.add_argument("--plan")
    ap.add_argument("--status", choices=STATUS_COPY, required=True)
    ap.add_argument("--site-name", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    d = json.load(open(args.diff))
    plan = json.load(open(args.plan)) if args.plan else {"batches": []}
    c = d["counts"]
    label, blurb = STATUS_COPY[args.status]
    site = args.site_name or plan.get("site") or d["before"]["origin"]
    ok = d["verdict"] == "PASS"
    batches = {b["id"]: b for b in plan.get("batches", [])}
    approved = [b for b in plan.get("batches", []) if b.get("approved")]

    promise_rows = [[esc(batches.get(p["batch"], {}).get("title", p["batch"])), f'<span class="mono">{esc(p["path"])}</span>',
                     esc(p["field"]), esc(p["promised"]), esc(p["actual"]), pill(p["result"])] for p in d["promises"]]
    pres_rows = [[pill(p["result"]), esc(p["check"]), f'<span class="mono">{esc(p["path"])}</span>', esc(p["detail"])]
                 for p in sorted(d["preservation"], key=lambda p: (p["result"] != "FAIL", p["check"], p["path"]))]
    followed = dt.date.today() + dt.timedelta(days=28)

    out = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SEO changes: {esc(site)}</title><style>{CSS}</style></head><body><main>
<span class="status {'pass' if ok else 'fail'}">{esc(label)} · {esc(d['verdict'])}</span>
<h1>SEO changes for {esc(site)}</h1>
<p class="muted">{esc(blurb)} Before: {esc(d['before']['origin'])} ({esc(d['before']['taken_at'])}). After: {esc(d['after']['origin'])} ({esc(d['after']['taken_at'])}). {d['after']['pages']} pages compared.</p>
<div class="verdict">
<div class="tile"><div class="n pass">{c['fixed']}</div><div class="k">findings fixed</div></div>
<div class="tile"><div class="n {'fail' if c['introduced'] else ''}">{c['introduced']}</div><div class="k">findings introduced</div></div>
<div class="tile"><div class="n {'pass' if c['delivered'] == c['promised'] else 'fail'}">{c['delivered']}/{c['promised']}</div><div class="k">promised changes delivered</div></div>
<div class="tile"><div class="n {'fail' if c['preservation_fail'] else 'pass'}">{c['preservation_fail']}</div><div class="k">preservation failures ({c['preservation_review']} to review)</div></div>
</div>
<h2>What was approved</h2>
{table(['Batch', 'Pages', 'Summary'], [[esc(b['title']), str(len({x['path'] for x in b.get('changes', [])})), esc(b.get('summary'))] for b in approved])}
<h2>Promised vs delivered</h2>
<p class="muted">Every value shown at the gate, looked up in the after-snapshot.</p>
{table(['Batch', 'Page', 'Field', 'Promised', 'Actual', ''], promise_rows)}
<h2>Did anything break?</h2>
<p class="muted">The preservation contract: pages lost, noindex added, canonicals or structured data removed, and anything else that changed without being asked for.</p>
{table(['', 'Check', 'Page', 'Detail'], pres_rows)}
<h2>Fixed</h2>{table(['Severity', 'Finding', 'Pages', 'Where', ''], by_rule(d['findings']['fixed']))}
<h2>Introduced</h2>{table(['Severity', 'Finding', 'Pages', 'Where', ''], by_rule(d['findings']['introduced']))}
<h2>Still open</h2>{table(['Severity', 'Finding', 'Pages', 'Where', ''], by_rule(d['findings']['persisting']))}
<h2>What this report can't tell you yet</h2>
<p>These checks prove the changes are present, valid and didn't break anything. They don't measure rankings or traffic: Google has to recrawl first.</p>
<blockquote>{esc(RECRAWL_QUOTE)} <a href="{RECRAWL_SOURCE}" target="_blank" rel="noopener">Google Search Central</a></blockquote>
<p>Check again around <b>{followed.isoformat()}</b>. Four weeks isn't a number Google gives; it's a margin chosen to sit past "a few weeks". Look at URL Inspection for the changed pages, and the Performance report's impressions and clicks for the same pages, compared with the four weeks before the change.</p>
<p class="muted">Generated by proof-seo from {esc(args.diff)}.</p>
</main></body></html>"""
    with open(args.out, "w") as f:
        f.write(out)
    print(f"report ({label}, {d['verdict']}) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
