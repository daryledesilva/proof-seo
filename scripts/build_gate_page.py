#!/usr/bin/env python3
"""Build the Gate 1 comparison page: one real preview page per proposed batch.

Each batch page shows the exact values that will ship, never a description of
them: the before and after of every field on every affected page, a search
snippet preview where a title or description changes, the structured data
block that will be added, and the raw HTML evidence behind the finding. A
parent page (gate.html) switches between batches with one button per option
and shows each batch in a real <iframe src>, following the single-page
mechanism in references/approval-policy.md.

Serve the output directory over HTTP (not file://) and open gate.html:

  build_gate_page.py --plan plan.json --snapshot before.json --out .proof-seo/gate
  python3 -m http.server 8765 --directory .proof-seo/gate
"""
from __future__ import annotations

import argparse
import html
import json
import os
import urllib.parse

CSS = """
:root{--ink:#16181d;--muted:#5d6370;--line:#e3e5ea;--bg:#f6f7f9;--card:#fff;--add:#e7f6ec;--addink:#11622f;
--del:#fdecec;--delink:#8a1c1c;--tool:#ffcf33;--toolink:#1b1400;--link:#1a0dab;--url:#1f6d34}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1060px;margin:0 auto;padding:28px 20px 60px}
h1{font-size:1.55rem;margin:0 0 .3rem;text-wrap:balance}h2{font-size:1.05rem;margin:2rem 0 .6rem}
.lede{color:var(--muted);margin:0 0 1.2rem;max-width:70ch}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:0 0 14px}
.facts{display:flex;flex-wrap:wrap;gap:8px 18px;color:var(--muted);font-size:.9rem}.facts b{color:var(--ink)}
blockquote{margin:.4rem 0 0;padding:.5rem .8rem;border-left:3px solid var(--line);color:var(--muted);font-size:.92rem}
a{color:#1f4fd1}
.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{text-align:left;vertical-align:top;padding:8px 10px;border-bottom:1px solid var(--line)}th{color:var(--muted);font-weight:600}
td.path{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.85rem;white-space:nowrap}
.before{background:var(--del);color:var(--delink)}.after{background:var(--add);color:var(--addink)}
.none{color:var(--muted);font-style:italic}
pre{margin:0;white-space:pre-wrap;word-break:break-word;font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}
.pair{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.label{font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:0 0 6px}
.label code{text-transform:none;letter-spacing:0;font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--ink)}
.serp{background:#fff;border:1px solid var(--line);border-radius:8px;padding:12px 14px;font-family:arial,sans-serif}
.serp .site{font-size:14px;color:#202124}.serp .crumb{font-size:12px;color:var(--url)}
.serp .t{font-size:20px;line-height:1.3;color:var(--link);margin:4px 0 3px}.serp .d{font-size:14px;color:#4d5156}
.note{font-size:.85rem;color:var(--muted)}
"""

GATE_CSS = """
*{box-sizing:border-box}body{margin:0;font:14px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;background:#1b1400}
header{position:sticky;top:0;display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;padding:10px 14px;background:#ffcf33;color:#1b1400}
.badge{font-size:.7rem;font-weight:700;letter-spacing:.07em;border:1.5px solid #1b1400;border-radius:4px;padding:2px 6px}
.title{font-weight:700;margin-right:auto}
button{font:inherit;cursor:pointer;border:1.5px solid #1b1400;background:transparent;color:#1b1400;border-radius:6px;padding:6px 10px}
button[aria-pressed="true"]{background:#1b1400;color:#ffcf33}
button:focus-visible{outline:3px solid #1f4fd1;outline-offset:2px}
.score{opacity:.75;font-size:.8rem;margin-left:4px}
iframe{display:none;width:100%;height:calc(100vh - 56px);border:0;background:#fff}iframe.is-active{display:block}
"""

SNIPPET_CAVEAT = ("Preview only. Google decides what it shows: it can use other text from the page for the title "
                  "link and the snippet (see developers.google.com/search/docs/appearance/title-link and /snippet).")


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def cell(v, cls: str) -> str:
    if v is None or v == "" or v == []:
        return f'<td class="{cls}"><span class="none">(none)</span></td>'
    if isinstance(v, (dict, list)):
        return f'<td class="{cls}"><pre>{esc(json.dumps(v, indent=1, ensure_ascii=False))}</pre></td>'
    return f'<td class="{cls}">{esc(v)}</td>'


def serp(site: str, path: str, title, desc) -> str:
    host = urllib.parse.urlsplit(site).netloc
    crumb = host + (" › " + " › ".join(s for s in path.split("/") if s) if path.strip("/") else "")
    return (f'<div class="serp"><div class="site">{esc(host)}</div><div class="crumb">{esc(crumb)}</div>'
            f'<div class="t">{esc(title) if title else "<span class=none>(no title)</span>"}</div>'
            f'<div class="d">{esc(desc) if desc else "<span class=none>(no description: Google picks text from the page)</span>"}</div></div>')


def page_facts(snapshot: dict, path: str) -> dict:
    for p in snapshot["pages"]:
        if p["path"] == path:
            return p.get("raw") or {}
    return {}


def batch_page(batch: dict, snapshot: dict, run_title: str) -> str:
    site = snapshot["site"]
    changes = batch.get("changes", [])
    paths = sorted({c["path"] for c in changes})
    rows = "".join(
        f'<tr><td class="path">{esc(c["path"])}</td><td>{esc(c["field"])}</td>{cell(c.get("before"), "before")}{cell(c.get("after"), "after")}</tr>'
        for c in changes)

    snippets = []
    for path in paths:
        fields = {c["field"]: c for c in changes if c["path"] == path}
        if not ({"title", "meta_description"} & fields.keys()):
            continue
        f = page_facts(snapshot, path)
        cur_t = (f.get("title") or [None])[0]
        cur_d = next((d for d in f.get("meta_description", []) if d.strip()), None)
        new_t = fields["title"]["after"] if "title" in fields else cur_t
        new_d = fields["meta_description"]["after"] if "meta_description" in fields else cur_d
        snippets.append(f'<div class="card"><p class="label"><code>{esc(path)}</code></p><div class="pair">'
                        f'<div><p class="label">Now</p>{serp(site, path, cur_t, cur_d)}</div>'
                        f'<div><p class="label">After this batch</p>{serp(site, path, new_t, new_d)}</div></div></div>')
        if len(snippets) >= 6:
            break

    blocks = [c for c in changes if c.get("preview")]
    shown = blocks[:2]
    previews = "".join(
        f'<div class="card"><p class="label"><code>{esc(c["path"])}</code> · exact markup to be added</p><pre>{esc(c["preview"] if isinstance(c["preview"], str) else json.dumps(c["preview"], indent=2, ensure_ascii=False))}</pre></div>'
        for c in shown)
    if len(blocks) > len(shown):
        previews += (f'<p class="note">The same markup, with each page\'s own values, goes on {len(blocks) - len(shown)} more '
                     f'page(s): {esc(", ".join(c["path"] for c in blocks[len(shown):len(shown) + 8]))}'
                     f'{" and others" if len(blocks) > len(shown) + 8 else ""}. Every page is listed in the table below.</p>')

    evidence = "".join(
        f'<div class="card"><p class="label"><code>{esc(e.get("path"))}</code> · {esc(e.get("rule"))}</p><pre>{esc(e.get("evidence"))}</pre></div>'
        for e in batch.get("evidence", [])[:6] if e.get("evidence"))

    more = len(paths) - len(snippets)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(batch['title'])}</title><style>{CSS}</style></head><body><main>
<h1>{esc(batch['title'])}</h1>
<p class="lede">{esc(batch.get('summary'))}</p>
<div class="card facts"><span><b>{len(paths)}</b> page(s)</span><span><b>{len(changes)}</b> change(s)</span>
<span>Risk: <b>{esc(batch.get('risk', 'not stated'))}</b></span><span>Effort: <b>{esc(batch.get('effort', 'not stated'))}</b></span></div>
{f'<div class="card"><p class="label">Why</p><div>Source: <a href="{esc(batch["source"])}" target="_blank" rel="noopener">{esc(batch["source"])}</a></div><blockquote>{esc(batch.get("quote"))}</blockquote></div>' if batch.get("source") else ''}
{('<h2>Search snippet preview</h2><p class="note">' + esc(SNIPPET_CAVEAT) + '</p>' + ''.join(snippets)) if snippets else ''}
{('<h2>Markup that will ship</h2>' + previews) if previews else ''}
<h2>Every change, field by field</h2>
<div class="card table-wrap"><table><thead><tr><th>Page</th><th>Field</th><th>Now</th><th>After</th></tr></thead><tbody>{rows}</tbody></table></div>
{('<h2>Evidence from the live HTML</h2>' + evidence) if evidence else ''}
<p class="note">Run: {esc(run_title)} · snapshot {esc(snapshot.get('taken_at'))} of {esc(snapshot.get('origin'))}</p>
</main></body></html>"""


def gate_page(title: str, options: list[tuple[str, str, str]]) -> str:
    buttons = "".join(
        f'<button type="button" data-i="{i}" aria-pressed="{"true" if i == 0 else "false"}">{esc(label)}<span class="score">{esc(score)}</span></button>'
        for i, (label, _, score) in enumerate(options))
    frames = "".join(
        f'<iframe title="{esc(label)}" src="{esc(src)}" class="{"is-active" if i == 0 else ""}" loading="lazy"></iframe>'
        for i, (label, src, _) in enumerate(options))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{GATE_CSS}</style></head><body>
<header><span class="badge">PROOF-SEO GATE — NOT PART OF YOUR SITE</span><span class="title">{esc(title)}</span>{buttons}</header>
{frames}
<script>
const bs=[...document.querySelectorAll('header button')],fs=[...document.querySelectorAll('iframe')];
function show(i){{bs.forEach((b,j)=>b.setAttribute('aria-pressed',j===i));fs.forEach((f,j)=>f.classList.toggle('is-active',j===i));history.replaceState(null,'','#'+i)}}
bs.forEach(b=>b.addEventListener('click',()=>show(+b.dataset.i)));
const h=+location.hash.slice(1);if(h>0&&h<bs.length)show(h);
</script></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--snapshot", required=True, help="The before-snapshot the plan was written from")
    ap.add_argument("--out", required=True, help="Directory to write gate.html and batches/ into")
    ap.add_argument("--only", action="append", default=[], help="Only these batch ids (repeatable); default all")
    ap.add_argument("--title", default="")
    args = ap.parse_args()

    plan = json.load(open(args.plan))
    snap = json.load(open(args.snapshot))
    os.makedirs(os.path.join(args.out, "batches"), exist_ok=True)
    title = args.title or f"Gate 1: {snap['site']}"
    options = []
    for b in plan["batches"]:
        if args.only and b["id"] not in args.only:
            continue
        with open(os.path.join(args.out, "batches", f"{b['id']}.html"), "w") as f:
            f.write(batch_page(b, snap, title))
        pages = len({c["path"] for c in b.get("changes", [])})
        options.append((b.get("label") or b["title"], f"batches/{b['id']}.html", f"{pages} page{'s' if pages != 1 else ''}"))
    with open(os.path.join(args.out, "gate.html"), "w") as f:
        f.write(gate_page(title, options))
    print(f"{len(options)} batch page(s) + gate.html -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
