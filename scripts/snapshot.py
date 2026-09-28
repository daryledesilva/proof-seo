#!/usr/bin/env python3
"""Capture what search engines actually receive from a site, page by page.

A snapshot is the evidence every later stage works from: check.py finds
problems in it, diff.py compares two of them, and the gate and report pages
quote it verbatim. Nothing here judges anything; it only records.

Two ideas matter more than the rest:

* **--origin**: fetch the same paths from somewhere else (a local dev server,
  a staging host) while still describing them as the real site. This is how a
  change gets validated *before* it ships: snapshot production, snapshot the
  branch running locally, diff the two.
* **--paths-from**: reuse another snapshot's exact page list, so a before/after
  comparison is always over the same pages rather than whatever a second crawl
  happened to find.

Standard library only (Python 3.10+). Raw HTML is what gets parsed, because
that is what a server-rendered site actually serves; pass --browser to also
capture the JavaScript-rendered DOM for client-rendered sites.

Usage:
  snapshot.py --site https://example.com --out before.json
  snapshot.py --site https://example.com --origin http://127.0.0.1:8000 \\
              --paths-from before.json --out after.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import deque
from html.parser import HTMLParser

USER_AGENT = "proof-seo/0.1 (+https://github.com/daryledesilva/proof-seo)"
HEAD_EVIDENCE_LIMIT = 20000  # bytes of raw <head> kept per page for gate/report pages
SKIP_EXTENSIONS = re.compile(
    r"\.(?:jpe?g|png|gif|webp|avif|svg|ico|css|js|mjs|map|json|xml|txt|pdf|zip|gz|mp4|webm|mp3|woff2?|ttf|eot)$",
    re.I,
)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _opener(insecure: bool) -> urllib.request.OpenerDirector:
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), _NoRedirect)


def fetch(opener, url: str, timeout: float, max_hops: int = 10) -> dict:
    """GET a URL, following redirects by hand so every hop is recorded."""
    chain = []
    current = url
    started = time.monotonic()
    for _ in range(max_hops + 1):
        req = urllib.request.Request(current, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
        try:
            resp = opener.open(req, timeout=timeout)
            status, headers, body = resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as e:
            status, headers, body = e.code, e.headers, e.read() if e.fp else b""
        except (urllib.error.URLError, TimeoutError, ConnectionError, ssl.SSLError) as e:
            return {"url": url, "final_url": current, "status": None, "error": str(getattr(e, "reason", e)),
                    "redirects": chain, "elapsed_ms": int((time.monotonic() - started) * 1000)}
        if headers.get("Content-Encoding", "").lower() == "gzip" and body:
            try:
                body = gzip.decompress(body)
            except OSError:
                pass
        if status in (301, 302, 303, 307, 308) and headers.get("Location"):
            nxt = urllib.parse.urljoin(current, headers["Location"])
            chain.append({"from": current, "to": nxt, "status": status})
            current = nxt
            continue
        return {
            "url": url, "final_url": current, "status": status, "redirects": chain,
            "content_type": headers.get("Content-Type", ""),
            "x_robots_tag": headers.get("X-Robots-Tag"),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "body": body,
        }
    return {"url": url, "final_url": current, "status": None, "error": f"more than {max_hops} redirects",
            "redirects": chain, "elapsed_ms": int((time.monotonic() - started) * 1000)}


def _norm_text(parts: list[str]) -> str:
    # Join text nodes with the whitespace the markup actually had, then collapse
    # runs. Joining with "" instead is how "Calculate <a>DCA</a> for" becomes
    # "CalculateDCAfor": a parser artifact, not a site bug.
    return re.sub(r"\s+", " ", "".join(parts)).strip()


class PageParser(HTMLParser):
    """Collect the head and body facts search engines use. Tolerant of bad HTML."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
    INVISIBLE = {"script", "style", "noscript", "template", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.titles: list[str] = []
        self.meta: list[dict] = []
        self.links: list[dict] = []
        self.jsonld_raw: list[str] = []
        self.headings: list[dict] = []
        self.images: list[dict] = []
        self.anchors: list[str] = []
        self.text_parts: list[str] = []
        self._stack: list[str] = []
        self._capture: str | None = None
        self._buf: list[str] = []
        self._heading: str | None = None
        self._heading_buf: list[str] = []
        self._invisible_depth = 0

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html" and a.get("lang"):
            self.lang = a["lang"]
        elif tag == "title" and self._capture is None:
            self._capture, self._buf = "title", []
        elif tag == "meta":
            self.meta.append(a)
        elif tag == "link":
            self.links.append(a)
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._capture, self._buf = "jsonld", []
        elif tag in ("h1", "h2", "h3") and self._heading is None:
            self._heading, self._heading_buf = tag, []
        elif tag == "img":
            self.images.append({"src": a.get("src", ""), "alt": a.get("alt") if "alt" in a else None})
        elif tag == "a" and a.get("href"):
            self.anchors.append(a["href"])
        if tag in self.INVISIBLE:
            self._invisible_depth += 1
        if tag not in self.VOID:
            self._stack.append(tag)

    def handle_endtag(self, tag):
        if self._capture == "title" and tag == "title":
            self.titles.append(_norm_text(self._buf))
            self._capture = None
        elif self._capture == "jsonld" and tag == "script":
            self.jsonld_raw.append("".join(self._buf).strip())
            self._capture = None
        if self._heading == tag:
            self.headings.append({"level": tag, "text": _norm_text(self._heading_buf)})
            self._heading = None
        if tag in self.INVISIBLE and self._invisible_depth:
            self._invisible_depth -= 1
        if tag in self._stack:
            while self._stack and self._stack.pop() != tag:
                pass

    def handle_data(self, data):
        if self._capture:
            self._buf.append(data)
            return
        if self._heading:
            self._heading_buf.append(data)
        if not self._invisible_depth:
            self.text_parts.append(data)


def _meta_content(meta: list[dict], key: str, attr: str = "name") -> list[str]:
    return [m.get("content", "") for m in meta if m.get(attr, "").lower() == key]


def extract(html: str, page_url: str) -> dict:
    p = PageParser()
    try:
        p.feed(html)
        p.close()
    except Exception as e:  # html.parser is tolerant, but never let one page kill a crawl
        return {"parse_error": str(e)}

    jsonld = []
    for raw in p.jsonld_raw:
        entry = {"raw": raw[:4000]}
        try:
            data = json.loads(raw)
            entry["valid"] = True
            items = data if isinstance(data, list) else (data.get("@graph") if isinstance(data, dict) and "@graph" in data else [data])
            types = []
            for it in items or []:
                t = it.get("@type") if isinstance(it, dict) else None
                types.extend(t if isinstance(t, list) else ([t] if t else []))
            entry["types"] = types
        except json.JSONDecodeError as e:
            entry["valid"] = False
            entry["error"] = f"{e.msg} at line {e.lineno} column {e.colno}"
        jsonld.append(entry)

    canonicals = [l.get("href", "") for l in p.links if "canonical" in l.get("rel", "").lower().split()]
    hreflang = [{"lang": l.get("hreflang"), "href": l.get("href")} for l in p.links
                if "alternate" in l.get("rel", "").lower().split() and l.get("hreflang")]
    og = {m.get("property", "").lower(): m.get("content", "") for m in p.meta if m.get("property", "").lower().startswith("og:")}
    twitter = {m.get("name", "").lower(): m.get("content", "") for m in p.meta if m.get("name", "").lower().startswith("twitter:")}

    base = urllib.parse.urlsplit(page_url)
    internal, external = set(), set()
    for href in p.anchors:
        if href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            continue
        absu = urllib.parse.urljoin(page_url, href)
        parts = urllib.parse.urlsplit(absu)
        if parts.scheme not in ("http", "https"):
            continue
        if parts.netloc.lower() == base.netloc.lower():
            internal.add(urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, "")))
        else:
            external.add(absu)

    head_match = re.search(r"<head[^>]*>(.*?)</head>", html, re.S | re.I)
    head = head_match.group(1).strip() if head_match else ""
    text = _norm_text(p.text_parts)

    return {
        "lang": p.lang,
        "title": p.titles,
        "meta_description": _meta_content(p.meta, "description"),
        "meta_robots": _meta_content(p.meta, "robots") + _meta_content(p.meta, "googlebot"),
        "viewport": _meta_content(p.meta, "viewport"),
        "canonical": canonicals,
        "hreflang": hreflang,
        "og": og,
        "twitter": twitter,
        "headings": p.headings,
        "h1": [h["text"] for h in p.headings if h["level"] == "h1"],
        "jsonld": jsonld,
        "images": {"total": len(p.images), "missing_alt": [i["src"] for i in p.images if i["alt"] is None]},
        "internal_links": sorted(internal),
        "external_link_count": len(external),
        "word_count": len(text.split()),
        "head_html": head[:HEAD_EVIDENCE_LIMIT],
        "head_truncated": len(head) > HEAD_EVIDENCE_LIMIT,
    }


def render_dom(browser: str, url: str, timeout: float) -> tuple[str | None, str | None]:
    """Return the JavaScript-rendered DOM via a headless Chromium binary."""
    cmd = [browser, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
           f"--user-agent={USER_AGENT}", "--virtual-time-budget=10000", "--dump-dom", url]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 20)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, str(e)
    if out.returncode != 0 or not out.stdout.strip():
        return None, (out.stderr.strip().splitlines() or ["no output"])[-1]
    return out.stdout, None


def parse_robots(text: str) -> dict:
    sitemaps, groups, current = [], [], None
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, val = (s.strip() for s in line.split(":", 1))
        key = key.lower()
        if key == "sitemap":
            sitemaps.append(val)
        elif key == "user-agent":
            if current is None or current["rules"]:
                current = {"agents": [], "rules": []}
                groups.append(current)
            current["agents"].append(val.lower())
        elif key in ("allow", "disallow") and current is not None:
            current["rules"].append({"type": key, "path": val})
    return {"sitemaps": sitemaps, "groups": groups}


def robots_blocks(robots: dict, path: str, agent: str = "googlebot") -> bool:
    """Longest-match allow/disallow, per RFC 9309 section 2.2.2."""
    groups = [g for g in robots.get("groups", []) if agent in g["agents"]] or \
             [g for g in robots.get("groups", []) if "*" in g["agents"]]
    best = None
    for g in groups:
        for r in g["rules"]:
            rule = r["path"]
            if not rule:
                continue
            pattern = "^" + re.escape(rule).replace(r"\*", ".*").replace(r"\$", "$")
            if re.match(pattern, path):
                if best is None or len(rule) > len(best["path"]) or (len(rule) == len(best["path"]) and r["type"] == "allow"):
                    best = r
    return bool(best and best["type"] == "disallow")


def read_sitemaps(opener, urls: list[str], timeout: float, limit: int = 5000) -> tuple[list[dict], list[str]]:
    seen, found, queue = set(), [], deque(urls)
    info = []
    while queue and len(found) < limit:
        sm = queue.popleft()
        if sm in seen:
            continue
        seen.add(sm)
        r = fetch(opener, sm, timeout)
        entry = {"url": sm, "status": r.get("status"), "error": r.get("error")}
        info.append(entry)
        if r.get("status") != 200 or not r.get("body"):
            continue
        try:
            root = ET.fromstring(r["body"])
        except ET.ParseError as e:
            entry["error"] = f"invalid XML: {e}"
            continue
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"
        if root.tag.endswith("sitemapindex"):
            for loc in root.iter(f"{ns}loc"):
                queue.append(loc.text.strip())
        else:
            locs = [loc.text.strip() for loc in root.iter(f"{ns}loc") if loc.text]
            entry["url_count"] = len(locs)
            found.extend(locs)
    return info, found


def path_of(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", required=True, help="The real site, e.g. https://example.com")
    ap.add_argument("--origin", help="Fetch paths from here instead (local dev server, staging)")
    ap.add_argument("--paths-from", help="Reuse the page list from an earlier snapshot")
    ap.add_argument("--path", action="append", default=[], help="Extra path to include (repeatable)")
    ap.add_argument("--max-pages", type=int, default=50)
    ap.add_argument("--timeout", type=float, default=30)
    ap.add_argument("--browser", help="Headless Chromium binary; also capture the rendered DOM")
    ap.add_argument("--insecure", action="store_true", help="Skip TLS verification (local self-signed certs)")
    ap.add_argument("--label", default="", help="Free-text label stored in the snapshot (e.g. before, after)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    site = args.site.rstrip("/")
    origin = (args.origin or args.site).rstrip("/")
    site_parts = urllib.parse.urlsplit(site)
    opener = _opener(args.insecure)

    def at_origin(path: str) -> str:
        return origin + (path if path.startswith("/") else "/" + path)

    robots_r = fetch(opener, at_origin("/robots.txt"), args.timeout)
    robots_text = robots_r.get("body", b"").decode("utf-8", "replace") if robots_r.get("status") == 200 else ""
    robots = parse_robots(robots_text)
    sitemap_urls = robots["sitemaps"] or [site + "/sitemap.xml"]
    # Sitemaps name the real host; read them from the origin being snapshotted.
    sitemap_fetch = [at_origin(path_of(u)) if urllib.parse.urlsplit(u).netloc == site_parts.netloc else u for u in sitemap_urls]
    sitemap_info, sitemap_locs = read_sitemaps(opener, sitemap_fetch, args.timeout)
    sitemap_paths = [path_of(u) for u in sitemap_locs if urllib.parse.urlsplit(u).netloc.lower() == site_parts.netloc.lower()]

    fixed_paths: list[str] | None = None
    if args.paths_from:
        with open(args.paths_from) as f:
            fixed_paths = [p["path"] for p in json.load(f)["pages"]]

    order: list[str] = []
    queue = deque()
    seen: set[str] = set()

    def enqueue(p: str, source: str):
        if p in seen or SKIP_EXTENSIONS.search(urllib.parse.urlsplit(p).path):
            return
        seen.add(p)
        queue.append((p, source))

    if fixed_paths is not None:
        for p in fixed_paths + args.path:
            enqueue(p, "paths-from")
    else:
        enqueue("/", "home")
        for p in args.path:
            enqueue(p, "argument")
        for p in sitemap_paths:
            enqueue(p, "sitemap")

    pages = []
    while queue and len(pages) < args.max_pages:
        path, source = queue.popleft()
        order.append(path)
        r = fetch(opener, at_origin(path), args.timeout)
        page = {"path": path, "source": source, "status": r.get("status"), "error": r.get("error"),
                "redirects": [{"from": path_of(h["from"]), "to": h["to"], "status": h["status"]} for h in r.get("redirects", [])],
                "final_path": path_of(r["final_url"]) if r.get("final_url") else None,
                "elapsed_ms": r.get("elapsed_ms"), "x_robots_tag": r.get("x_robots_tag"),
                "in_sitemap": path in sitemap_paths, "blocked_by_robots": robots_blocks(robots, path)}
        body = r.get("body")
        if body is not None and "html" in r.get("content_type", "").lower():
            html = body.decode("utf-8", "replace")
            page["raw"] = extract(html, site + path)
            if args.browser:
                dom, err = render_dom(args.browser, at_origin(path), args.timeout)
                page["rendered"] = extract(dom, site + path) if dom else {"render_error": err}
            if fixed_paths is None:
                for link in page["raw"].get("internal_links", []):
                    enqueue(link, "link")
        elif body is not None:
            page["non_html"] = r.get("content_type")
        pages.append(page)
        print(f"  {page['status']}  {path}", file=sys.stderr)

    snapshot = {
        "tool": "proof-seo/snapshot", "version": 1,
        "label": args.label,
        "taken_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "site": site, "origin": origin,
        "rendered": bool(args.browser),
        "robots": {"status": robots_r.get("status"), "text": robots_text[:20000], "parsed": robots},
        "sitemaps": sitemap_info,
        "sitemap_paths": sitemap_paths,
        "truncated": bool(queue),
        "pages": pages,
    }
    with open(args.out, "w") as f:
        json.dump(snapshot, f, indent=1)
    print(f"{len(pages)} pages -> {args.out}" + (" (hit --max-pages; more were found)" if queue else ""), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
