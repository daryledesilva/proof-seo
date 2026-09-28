---
name: proof-seo
license: Apache-2.0
description: Improve a website's SEO with changes you can prove. Snapshots what search engines actually receive, audits it, shows each proposed fix batch as the exact values that will ship (before/after, snippet previews, the real markup), lets a human pick, implements the picked batches in the codebase, then re-snapshots and proves nothing broke and every promise landed. Use when someone wants to improve, fix or audit a site's SEO and act on it, not just get a report. Triggers include "improve my site's SEO", "fix the SEO on this site", "why isn't my site ranking" (when they want changes made), "add structured data to my site", and "SEO audit and fix".
---

# proof-seo

"Show me what you'll change, change only that, and prove it didn't break
anything."

Built in the shape of [redesign-lab](https://github.com/cogfoundry-labs/loomloom/tree/main/examples/community/redesign-lab)
(real artifacts at every decision, human gates, validation before anything
ships), with [claude-seo](https://github.com/AgriciDaniel/claude-seo) as the
SEO authority. See `references/seo-authority.md`.

## Entry point

1. Capture the request into `references/brief.md`'s shape: the site URL,
   whether a codebase is available (and where), the preview origin if there
   is one, and anything the human said they care about.
2. Read `pipeline.yaml` for the stage sequence and the gates.
   It is a manifest you follow stage by stage, not something you execute.
3. Work through the skills in `stages/` in the order the manifest lists:
   `discover.md` → `audit.md` → `plan-batches.md` → (Gate 1) →
   `implement.md` → `validate.md` → (Gate 2) → `report.md`.

Run files live in `.proof-seo/<run-id>/` in the target project (or the
current directory when there is no codebase). `<run-id>` is the date and
the site host, e.g. `2026-09-28-example.com`. Add `.proof-seo/` to the
project's `.gitignore` the first time; run files are evidence, not code.

**Paths.** `stages/`, `references/` and `pipeline.yaml` are next to this
file. The scripts are at the plugin root: run them as
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py"`. They need Python 3.8+
and nothing else (standard library only). If `CLAUDE_PLUGIN_ROOT` isn't
set (a manual clone rather than a plugin install), it's the repository root.

**If the SEO authority isn't installed**, say so at the start, before any
work: the run can still go ahead on the mechanical rules alone, but it will
find less, and the human should choose that knowingly rather than discover
it at Gate 1.

## The rules that govern everything else

1. **Exact values, never descriptions, at every decision point.** A batch at
   Gate 1 shows the literal title, description, canonical or JSON-LD that will
   ship, on every page it touches, rendered by `scripts/build_gate_page.py`.
   "Improve titles on product pages" is not an option; the 14 actual titles
   are.
2. **Every finding cites its source and its evidence.** `scripts/check.py`
   attaches the published sentence each rule rests on and the raw HTML it
   was found in. Findings from the SEO authority get the same treatment
   before they reach a gate: quote the raw HTML (`head_html` in the
   snapshot, or the page itself). A parser can mangle text: one text
   extractor reported an H1 as "CalculateDollar Cost Averaging (DCA)for…"
   when the HTML read `Calculate <a>Dollar Cost Averaging (DCA)</a> for…`.
   If you can't show it in the raw HTML, don't present it as a site problem.
3. **No invented numbers.** No title-length limits, no "ideal word count",
   no guessed traffic uplift. If a threshold matters, cite where it comes
   from; if nothing publishes one, don't use one. `references/rules.md`
   lists every mechanical rule and its source.
4. **Change only what was approved.** `scripts/diff.py` treats any SEO-relevant
   change nobody asked for as a preservation failure, and any promised change
   that didn't land as a failure too. Both block Gate 2.
5. **Use the site's own SEO mechanism.** If the codebase already sets meta
   tags through a package, a framework API or a CMS plugin, change them
   there. Never add a second, parallel way of emitting the same tags.
6. **Rankings are not measured here.** Validation proves the changes are
   present, valid and harmless. The report says so, and says when to check
   Search Console.

## Every gate: real choices, never a dead end

Read `references/approval-policy.md` before running a gate. In short: the
real artifact is opened first (the gate page over a local HTTP server, or the
diff/report), then the decision is an `AskUserQuestion` call, and **"Stop
here" is always one of its options.** Stopping discards nothing; everything
in `.proof-seo/<run-id>/` is kept.

## What NOT to do

- Don't ship anything that failed `diff.py`. Fix it and re-validate; the
  human never sees a failing result at Gate 2.
- Don't deploy, merge, push, or open a PR without Gate 2 approval.
- Don't request indexing, submit sitemaps, or touch Search Console on the
  human's behalf. Tell them what to do there.
- Don't copy claude-seo's code into this skill. It's a prerequisite; call it.
- Don't add a stage skill for something a script or a reference file can
  carry.
