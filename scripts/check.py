#!/usr/bin/env python3
"""Mechanical SEO checks over a snapshot. Every rule cites where it comes from.

This is deliberately narrow. It only flags things a published source states
directly, and each finding carries the exact sentence it relies on plus the
raw HTML it was found in, so nobody has to take a number or a judgment on
faith. Anything that needs judgment (is this title *good*, which schema type
fits) belongs to the SEO authority (see references/seo-authority.md), not
here. No thresholds are invented: there is no "titles must be under N
characters" rule because no primary source states one.

Usage:
  check.py snapshot.json [--out findings.json] [--rendered]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict

G = "https://developers.google.com/search/docs/"

# id -> (severity, summary, source URL, verbatim quote from that source)
RULES = {
    "page-error": ("error", "Page returns an error status",
        G + "crawling-indexing/http-network-errors",
        "Search Console generates error messages for status codes in the 4xx—5xx range, and for failed redirections (3xx)."),
    "page-unreachable": ("error", "Page could not be fetched at all",
        G + "crawling-indexing/http-network-errors",
        "Search Console generates error messages for status codes in the 4xx—5xx range, and for failed redirections (3xx)."),
    "redirect-too-many": ("error", "Redirect chain too long to be followed",
        G + "crawling-indexing/http-network-errors",
        "By default, Google's crawlers follow up to 10 redirect hops."),
    "broken-internal-link": ("error", "Internal link points at an error page",
        G + "crawling-indexing/http-network-errors",
        "Search Console generates error messages for status codes in the 4xx—5xx range, and for failed redirections (3xx)."),
    "title-missing": ("error", "No title",
        G + "appearance/title-link",
        "Make sure every page on your site has a title specified in the <title> element."),
    "title-multiple": ("warning", "More than one <title> element",
        "https://html.spec.whatwg.org/multipage/semantics.html#the-title-element",
        "There must be no more than one title element per document."),
    "title-duplicate": ("warning", "Same title as other pages",
        G + "appearance/title-link",
        "ensure each page has a unique, descriptive, and concise title within the <title> element."),
    "description-missing": ("warning", "No meta description",
        G + "appearance/snippet",
        "Create unique descriptions for each page on your site"),
    "description-duplicate": ("warning", "Same meta description as other pages",
        G + "appearance/snippet",
        "Identical or similar descriptions on every page of a site aren't helpful when individual pages appear in search results."),
    "canonical-conflict": ("error", "Page declares more than one different canonical URL",
        G + "crawling-indexing/consolidate-duplicate-urls",
        "Don't specify different URLs as canonical for the same page using different canonicalization techniques"),
    "noindex": ("info", "Page asks not to be indexed",
        G + "crawling-indexing/block-indexing",
        "Block Search Indexing with noindex"),
    "noindex-in-sitemap": ("warning", "Listed in the sitemap but marked noindex",
        G + "crawling-indexing/block-indexing",
        "Block Search Indexing with noindex"),
    "robots-blocked-in-sitemap": ("warning", "Listed in the sitemap but blocked by robots.txt",
        G + "crawling-indexing/robots/intro",
        "A robots.txt file tells search engine crawlers which URLs the crawler can access on your site."),
    "jsonld-invalid": ("error", "Structured data is not valid JSON",
        "https://www.w3.org/TR/json-ld11/",
        "A JSON-LD document is always a valid JSON document."),
    "no-structured-data": ("info", "No structured data on the page",
        G + "appearance/structured-data/intro-structured-data",
        "when a recipe page has JSON-LD structured data (describing the title of the recipe, the author of the recipe, and other details), Google Search can use that information to display a rich result"),
    "image-missing-alt": ("warning", "Images without an alt attribute",
        G + "appearance/google-images",
        "Use descriptive filenames, titles, and alt text"),
    "sitemap-missing": ("info", "No reachable sitemap",
        G + "crawling-indexing/sitemaps/overview",
        "If your site's pages are properly linked, Google can usually discover most of your site."),
}

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def _evidence(head: str, pattern: str, limit: int = 600) -> str | None:
    m = re.search(pattern, head or "", re.I | re.S)
    return m.group(0)[:limit] if m else None


def run(snapshot: dict, use_rendered: bool = False) -> list[dict]:
    findings: list[dict] = []
    pages = snapshot["pages"]
    by_path = {p["path"]: p for p in pages}

    def facts(p):
        if use_rendered and isinstance(p.get("rendered"), dict) and "title" in p["rendered"]:
            return p["rendered"]
        return p.get("raw") or {}

    def add(rule, path, detail, evidence=None, extra=None):
        sev, summary, source, quote = RULES[rule]
        f = {"rule": rule, "severity": sev, "summary": summary, "path": path, "detail": detail,
             "evidence": evidence, "source": source, "quote": quote}
        if extra:
            f.update(extra)
        findings.append(f)

    titles, descriptions = defaultdict(list), defaultdict(list)

    for p in pages:
        path = p["path"]
        if p.get("status") is None:
            add("page-unreachable", path, p.get("error") or "no response")
            continue
        if len(p.get("redirects", [])) >= 10:
            add("redirect-too-many", path, f"{len(p['redirects'])} hops", extra={"redirects": p["redirects"]})
        if p["status"] >= 400:
            add("page-error", path, f"HTTP {p['status']}", extra={"in_sitemap": p.get("in_sitemap")})
            continue
        f = facts(p)
        if not f or "title" not in f:
            continue
        head = f.get("head_html", "")

        t = [x for x in f["title"] if x]
        if not t:
            add("title-missing", path, "no non-empty <title>", _evidence(head, r"<title[^>]*>.*?</title>") or "(no <title> element in <head>)")
        else:
            titles[t[0]].append(path)
        if len(f["title"]) > 1:
            add("title-multiple", path, f"{len(f['title'])} <title> elements: {f['title']}")

        d = [x for x in f["meta_description"] if x.strip()]
        if not d:
            add("description-missing", path, "no non-empty meta description",
                _evidence(head, r"<meta[^>]+name=[\"']description[\"'][^>]*>") or "(no meta description in <head>)")
        else:
            descriptions[d[0].strip()].append(path)

        canon = {c.strip() for c in f["canonical"] if c.strip()}
        if len(canon) > 1:
            add("canonical-conflict", path, f"{len(canon)} different canonicals: {sorted(canon)}",
                "\n".join(re.findall(r"<link[^>]+rel=[\"']canonical[\"'][^>]*>", head, re.I)))

        robots = " ".join(f["meta_robots"] + ([p["x_robots_tag"]] if p.get("x_robots_tag") else [])).lower()
        if "noindex" in robots:
            rule = "noindex-in-sitemap" if p.get("in_sitemap") else "noindex"
            add(rule, path, f"robots directives: {robots}", _evidence(head, r"<meta[^>]+name=[\"'](?:robots|googlebot)[\"'][^>]*>"))
        if p.get("in_sitemap") and p.get("blocked_by_robots"):
            add("robots-blocked-in-sitemap", path, "robots.txt disallows a path the sitemap lists")

        bad = [j for j in f["jsonld"] if not j.get("valid")]
        for j in bad:
            add("jsonld-invalid", path, j.get("error"), j.get("raw", "")[:600])
        if not f["jsonld"]:
            add("no-structured-data", path, "no application/ld+json blocks")

        missing = f["images"]["missing_alt"]
        if missing:
            add("image-missing-alt", path, f"{len(missing)} of {f['images']['total']} images have no alt attribute",
                "\n".join(missing[:10]), extra={"count": len(missing)})

        for link in f.get("internal_links", []):
            target = by_path.get(link)
            if target and target.get("status") and target["status"] >= 400:
                add("broken-internal-link", path, f"links to {link} (HTTP {target['status']})", extra={"target": link})

    for title, paths in titles.items():
        if len(paths) > 1:
            for path in paths:
                add("title-duplicate", path, f"shared by {len(paths)} pages", title, extra={"shared_with": paths})
    for desc, paths in descriptions.items():
        if len(paths) > 1:
            for path in paths:
                add("description-duplicate", path, f"shared by {len(paths)} pages", desc, extra={"shared_with": paths})

    if not any(s.get("status") == 200 and s.get("url_count") for s in snapshot.get("sitemaps", [])):
        add("sitemap-missing", "/sitemap.xml", "; ".join(f"{s['url']}: {s.get('status') or s.get('error')}" for s in snapshot.get("sitemaps", [])) or "none declared")

    findings.sort(key=lambda x: (SEVERITY_ORDER[x["severity"]], x["rule"], x["path"]))
    for i, f in enumerate(findings, 1):
        f["id"] = f"F{i}"
    return findings


def summarize(findings: list[dict]) -> dict:
    out = defaultdict(lambda: {"severity": None, "pages": 0, "summary": ""})
    for f in findings:
        r = out[f["rule"]]
        r["severity"], r["summary"] = f["severity"], f["summary"]
        r["pages"] += 1
    return dict(sorted(out.items(), key=lambda kv: (SEVERITY_ORDER[kv[1]["severity"]], kv[0])))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("snapshot", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--rendered", action="store_true", help="Check the JavaScript-rendered DOM instead of raw HTML")
    ap.add_argument("--rules", action="store_true", help="Print the rule table as Markdown and exit")
    args = ap.parse_args()
    if args.rules:
        print("| Rule | Severity | What it flags | Source | What the source says |\n|---|---|---|---|---|")
        for rid, (sev, summary, source, quote) in RULES.items():
            md = lambda s: s.replace("<", "&lt;").replace(">", "&gt;")
            print(f"| `{rid}` | {sev} | {md(summary)} | [link]({source}) | \"{md(quote)}\" |")
        return 0
    if not args.snapshot:
        ap.error("snapshot is required")
    with open(args.snapshot) as f:
        snap = json.load(f)
    findings = run(snap, args.rendered)
    result = {"tool": "proof-seo/check", "version": 1, "snapshot": args.snapshot, "site": snap["site"],
              "origin": snap["origin"], "pages_checked": len(snap["pages"]), "truncated": snap.get("truncated"),
              "summary": summarize(findings), "findings": findings}
    text = json.dumps(result, indent=1)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
    else:
        print(text)
    for rule, r in result["summary"].items():
        print(f"  {r['severity']:<7} {r['pages']:>4}  {rule}  ({r['summary']})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
