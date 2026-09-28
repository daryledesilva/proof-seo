# SEO authority

proof-seo doesn't make SEO judgment calls of its own. It records evidence,
applies a small set of published rules (`rules.md`), and proves changes. The
judgment (which schema type fits this page, whether a title is good, what an
AI search engine needs) comes from an installed SEO authority. Resolved once
at Discover, recorded in `brief.json`, never switched mid-run.

## Active authority

```yaml
name: claude-seo
repo: https://github.com/AgriciDaniel/claude-seo
license: MIT
tested_with: "2.4.0"
capabilities:
  audit:            /seo audit <url>        # full audit, parallel sub-agents
  page:             /seo page <url>         # one page in depth
  schema:           /seo schema <url>       # detect, validate, generate JSON-LD
  technical:        /seo technical <url>
  content:          /seo content <url>      # E-E-A-T, content quality
  geo:              /seo geo <url>          # AI Overviews / answer engines
  sitemap:          /seo sitemap <url>
  regression_check: /seo drift baseline|compare <url>   # same URL only; after deploy
```

It's a prerequisite, not bundled: proof-seo calls it, and never copies its
code. Check it's present at Discover with `/seo doctor`. If it isn't, the
human installs it (slash commands only they can run):

```
/plugin marketplace add AgriciDaniel/claude-seo
/plugin install claude-seo@agricidaniel-claude-seo
/seo setup
```

## How its output is used

- **Findings become candidates, not facts.** Every authority finding that
  would reach a gate is confirmed in the raw HTML first (`head_html` in the
  snapshot, or a fresh fetch), and the evidence is attached to the batch.
  Parsers disagree with HTML more often than you'd expect: claude-seo 2.4.0's
  drift baseline reported an H1 as `CalculateDollar Cost Averaging (DCA)for…`
  for markup that reads `Calculate <a>…</a> for…`.
- **Generated markup is shown verbatim at Gate 1.** If `/seo schema`
  generates JSON-LD, that exact block goes into the batch's `preview`, and
  that exact block is what Implement ships.
- **Numbers need a source.** If the authority cites a threshold (a length,
  a count, a score), it goes to the human with its source, or not at all.

## Known limits

- Its rendered-page features use Playwright's bundled Chromium, which
  doesn't support every OS (for example, not Ubuntu 20.04). Without it,
  claude-seo reports `browser_ready: false` and its non-rendered checks
  still work. For server-rendered sites the raw HTML is what matters anyway;
  for client-rendered sites, pass any headless Chromium to
  `snapshot.py --browser`.
- Without Google API credentials it can't read Search Console or CrUX field
  data. proof-seo doesn't need them to run.
- Its standalone generator script (`schema_generate.py`) covers four types
  only (reservation, order, discussion, profile). For other types, the
  `/seo schema` skill, or the example markup in Google's documentation for
  that type, is the starting point; validate the result as JSON either way.
- Its drift rules compare a URL only with its own earlier baseline, so they
  can't check a preview against production (see the preservation contract).

## Registering another authority

Add a block like the one above for it, and note which capabilities it
lacks. Don't build a per-authority plugin system until a second authority
has actually been run end to end.
