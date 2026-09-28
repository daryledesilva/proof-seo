#!/usr/bin/env python3
"""End-to-end test: snapshot -> check -> diff over a fixture site with known defects.

The fixture's "before" site has one example of every mechanical rule; the
"after" site fixes most of them and deliberately breaks three things (a page
removed, noindex added, structured data dropped) plus one promise that is not
delivered. The test asserts the tools report exactly that. Run:

  python3 tests/test_fixture.py
"""
from __future__ import annotations

import functools
import http.server
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
FIXTURE = ROOT / "test-fixtures" / "site"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(directory: Path, port: int) -> http.server.ThreadingHTTPServer:
    handler = functools.partial(QuietHandler, directory=str(directory))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def run(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)


def main() -> int:
    failures = []

    def expect(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            failures.append(msg)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bport, aport = free_port(), free_port()
        site = f"http://127.0.0.1:{bport}"
        for side in ("before", "after"):
            dst = tmp / side
            shutil.copytree(FIXTURE / side, dst)
            for f in dst.rglob("*"):
                if f.is_file() and f.suffix in (".html", ".xml", ".txt"):
                    f.write_text(f.read_text().replace("http://SITE", site))
        servers = [serve(tmp / "before", bport), serve(tmp / "after", aport)]
        try:
            r = run(SCRIPTS / "snapshot.py", "--site", site, "--label", "before", "--out", tmp / "before.json")
            expect(r.returncode == 0, f"snapshot before exits 0 ({r.stderr.strip().splitlines()[-1] if r.stderr else ''})")
            r = run(SCRIPTS / "snapshot.py", "--site", site, "--origin", f"http://127.0.0.1:{aport}",
                    "--paths-from", tmp / "before.json", "--label", "after", "--out", tmp / "after.json")
            expect(r.returncode == 0, "snapshot after (via --origin, --paths-from) exits 0")

            before = json.loads((tmp / "before.json").read_text())
            paths = {p["path"] for p in before["pages"]}
            expect(paths == {"/", "/about", "/pricing", "/hidden", "/private", "/gone"},
                   f"before crawled the sitemap and linked pages: {sorted(paths)}")
            home = next(p for p in before["pages"] if p["path"] == "/")
            expect(home["raw"]["h1"] == ["Acme widgets for you"],
                   f"h1 text keeps the spaces around inline links: {home['raw']['h1']}")

            r = run(SCRIPTS / "check.py", tmp / "before.json", "--out", tmp / "findings.json")
            expect(r.returncode == 0, "check exits 0")
            found = {(f["rule"], f["path"]) for f in json.loads((tmp / "findings.json").read_text())["findings"]}
            for want in [("page-error", "/gone"), ("broken-internal-link", "/"), ("canonical-conflict", "/"),
                         ("jsonld-invalid", "/"), ("image-missing-alt", "/"), ("title-multiple", "/about"),
                         ("title-duplicate", "/"), ("title-duplicate", "/about"),
                         ("description-duplicate", "/"), ("description-duplicate", "/about"),
                         ("description-missing", "/pricing"), ("noindex-in-sitemap", "/hidden"),
                         ("robots-blocked-in-sitemap", "/private")]:
                expect(want in found, f"check finds {want[0]} on {want[1]}")
            every = json.loads((tmp / "findings.json").read_text())["findings"]
            expect(all(f.get("source") and f.get("quote") for f in every), "every finding carries a source and a quote")

            plan = {"batches": [
                {"id": "titles", "approved": True, "changes": [
                    {"path": "/", "field": "title", "after": "Acme Widgets"},
                    {"path": "/about", "field": "title", "after": "About | Acme"}]},
                {"id": "descriptions", "approved": True, "changes": [
                    {"path": "/pricing", "field": "meta_description", "after": "What Acme widgets cost."}]},
                {"id": "alt-text", "approved": True, "changes": [
                    {"path": "/", "field": "images_missing_alt", "after": 0}]},
                {"id": "product-schema", "approved": True, "changes": [
                    {"path": "/pricing", "field": "jsonld_types", "after": ["Product"]}]},
            ]}
            (tmp / "plan.json").write_text(json.dumps(plan))
            r = run(SCRIPTS / "diff.py", tmp / "before.json", tmp / "after.json", "--plan", tmp / "plan.json", "--out", tmp / "diff.json")
            d = json.loads((tmp / "diff.json").read_text())
            expect(r.returncode == 1 and d["verdict"] == "FAIL", "diff verdict is FAIL (exit 1) because of the planted regressions")
            checks = {(p["check"], p["path"]) for p in d["preservation"] if p["result"] == "FAIL"}
            expect(("page-lost", "/hidden") in checks, "preservation catches the removed page")
            expect(("noindex-added", "/about") in checks, "preservation catches noindex added")
            expect(not any(c == "structured-data-removed" and p == "/pricing" for c, p in checks),
                   "a promised structured-data change is judged as a promise, not a preservation breach")
            res = {(p["path"], p["field"]): p["result"] for p in d["promises"]}
            expect(res.get(("/", "title")) == "DELIVERED", "promise: home title delivered")
            expect(res.get(("/pricing", "meta_description")) == "DELIVERED", "promise: pricing description delivered")
            expect(res.get(("/", "images_missing_alt")) == "DELIVERED", "promise: alt text delivered")
            expect(res.get(("/pricing", "jsonld_types")) == "MISSING", "promise: Product schema reported MISSING")
            fixed = {(f["rule"], f["path"]) for f in d["findings"]["fixed"]}
            expect(("canonical-conflict", "/") in fixed and ("jsonld-invalid", "/") in fixed,
                   "fixed findings are reported")

            for b in plan["batches"]:
                b["title"], b["summary"] = b["id"], "fixture batch"
            (tmp / "plan.json").write_text(json.dumps(plan))
            r = run(SCRIPTS / "build_gate_page.py", "--plan", tmp / "plan.json", "--snapshot", tmp / "before.json", "--out", tmp / "gate")
            gate = (tmp / "gate" / "gate.html").read_text() if (tmp / "gate" / "gate.html").exists() else ""
            expect(r.returncode == 0 and gate.count("<iframe") == 4, "gate page has one iframe per batch")
            titles = (tmp / "gate" / "batches" / "titles.html").read_text()
            expect("Acme Widgets" in titles and "About | Acme" in titles, "batch page shows the exact promised values")
            r = run(SCRIPTS / "build_report.py", "--diff", tmp / "diff.json", "--plan", tmp / "plan.json", "--status", "preview", "--out", tmp / "report.html")
            rep = (tmp / "report.html").read_text() if (tmp / "report.html").exists() else ""
            expect(r.returncode == 0 and "Validated preview" in rep and "MISSING" in rep, "report states preview status and the missing promise")
        finally:
            for s in servers:
                s.shutdown()

    print(f"\n{'PASS' if not failures else 'FAIL'}: {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
