# proof-seo

**SEO changes you can prove.** A Claude Code skill that improves a site's SEO
the careful way: it shows you exactly what it will change before touching
anything, changes only what you approve, then proves every change landed and
nothing else broke.

Most SEO tools stop at a report: a list of issues and recommendations,
and the rest is up to you. proof-seo closes the loop:

1. **Snapshot** what search engines actually receive from your site, page by
   page: titles, descriptions, canonicals, robots directives, structured
   data, links, status codes, and the raw `<head>` as evidence.
2. **Audit** it: a small set of mechanical rules, each quoting the published
   source it rests on, plus [claude-seo](https://github.com/AgriciDaniel/claude-seo)
   for the judgment calls.
3. **Show you the fixes as the exact values that will ship.** Not "improve
   titles", but every page's current and new title side by side, a search
   snippet preview, and the literal structured-data block. You pick which
   batches to apply.
4. **Implement** them on a branch, through whatever SEO mechanism your site
   already uses.
5. **Prove it.** Snapshot the branch running locally, compare it with
   production over the same pages, and check three things: what got fixed,
   that every value shown to you actually shipped, and that nothing else
   changed (no page lost, no stray `noindex`, no canonical or structured
   data quietly removed). Anything failing goes back to be fixed; you never
   get asked to ship a failing result.
6. **Ship** only when you say so, re-check it live, and get a before/after
   report plus a date to look at Search Console.

## Install

As a Claude Code plugin:

```
/plugin marketplace add daryledesilva/proof-seo
/plugin install proof-seo@daryledesilva-proof-seo
```

Then install the SEO authority it relies on for judgment calls
(recommended; proof-seo tells you upfront if it's missing and can run on
its mechanical rules alone):

```
/plugin marketplace add AgriciDaniel/claude-seo
/plugin install claude-seo@agricidaniel-claude-seo
/seo setup
```

Requirements: Python 3.8+ for proof-seo's scripts (standard library only).
claude-seo needs Python 3.10+.

## Use

In a project, ask Claude something like:

> Improve the SEO on https://example.com. The code is in this repo.

It works without a codebase too: point it at a URL and it stops at a
written, page-by-page change list for whoever can edit the site.

You'll be asked twice: which fixes to make, and whether to ship the result.
"Stop here" is always an option, and stopping loses nothing. Run files are
kept in `.proof-seo/<run-id>/` in your project.

## The scripts on their own

The evidence tools are plain Python and work without Claude, for example in
CI to block a deploy that breaks SEO:

```sh
# production, before a change
python3 scripts/snapshot.py --site https://example.com --out before.json
python3 scripts/check.py before.json --out findings.json

# the branch running locally, same pages, judged against production
python3 scripts/snapshot.py --site https://example.com --origin http://127.0.0.1:8000 \
    --paths-from before.json --out after.json
python3 scripts/diff.py before.json after.json --out diff.json   # exits 1 on FAIL
python3 scripts/build_report.py --diff diff.json --status preview --out report.html
```

| Script | What it does |
|---|---|
| `snapshot.py` | Crawls the sitemap and internal links; records every page's SEO facts and raw `<head>`. `--origin` fetches the same paths from a local or staging server; `--browser` also captures the JavaScript-rendered DOM |
| `check.py` | Mechanical findings, each with evidence, a source URL and the quoted sentence ([rules and sources](skills/proof-seo/references/rules.md)) |
| `diff.py` | Before vs after: fixed/introduced findings, the [preservation contract](skills/proof-seo/references/preservation-contract.md), and promised-vs-delivered for an approved plan |
| `build_gate_page.py` | The page you choose fixes from |
| `build_report.py` | The before/after report |

## What it deliberately doesn't do

- **Invent numbers.** No title-length limits, ideal word counts or traffic
  forecasts. A rule is only a rule if a published source states it, and every
  finding quotes that source. See [rules.md](skills/proof-seo/references/rules.md)
  for the list, and for the common "rules" left out because nothing primary
  backs them.
- **Measure rankings.** Validation proves changes are present, valid and
  harmless. Whether they help shows up in Search Console weeks later; the
  report says when to look.
- **Act for you in Search Console, or ship without asking.** No indexing
  requests, no merges, no deploys without an explicit yes.

## Layout

```
skills/proof-seo/
  SKILL.md            entry point and the rules that govern the run
  pipeline.yaml       stages and gates
  stages/             discover, audit, plan-batches, implement, validate, report
  references/         approval policy, preservation contract, SEO authority,
                      plan schema, rule table
scripts/              the evidence tools (standard library Python)
tests/                end-to-end test over a fixture site with planted defects
```

`python3 tests/test_fixture.py` runs the full snapshot, check, diff, gate-page
and report path against a local fixture site, with one example of every rule
and three planted regressions.

## Status

0.1. The scripts are covered by the fixture test on Python 3.8 and 3.12, and
have been run against a live 342-page site. The full human-in-the-loop flow
has run on a real site through Gate 1; its first run is what rewrote the
gates in plain language.

## Credits

The flow is modelled on [redesign-lab](https://github.com/cogfoundry-labs/loomloom/tree/main/examples/community/redesign-lab)
(real artifacts at every decision, human gates, validation before anything
ships). SEO judgment comes from [claude-seo](https://github.com/AgriciDaniel/claude-seo),
which proof-seo calls rather than copies.

## License

Apache-2.0
