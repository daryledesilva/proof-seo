# Preservation contract

Changing SEO carries a risk a new build doesn't: quietly breaking what
already works. The before-snapshot taken at Discover is the contract; the
after-snapshot is checked against it by `scripts/diff.py`, over the same page
list (`--paths-from`). Anything below that changed **without an approved
batch asking for it** is judged here.

## FAIL: blocks Gate 2

| Check | Why it's never acceptable by accident |
|---|---|
| `page-lost` | A page that returned 200 no longer does |
| `noindex-added` | A page (meta robots or `X-Robots-Tag`) now asks not to be indexed |
| `canonical-changed`, `canonical-removed` | Changes which URL Google treats as the page |
| `title-removed`, `meta_description-removed`, `h1-removed` | Something that existed is gone |
| `structured-data-removed` | A JSON-LD type that was there is not |
| `structured-data-broken` | More invalid JSON-LD blocks than before |
| `sitemap-removed` | The sitemap listed pages before and lists none now |
| promise `MISSING` | A value shown at Gate 1 didn't ship, or shipped differently |
| new `error` finding | `check.py` finds a new error-severity problem |

## REVIEW: shown to the human at Gate 2, never blocks

| Check | Why a human should look |
|---|---|
| `title-changed`, `meta_description-changed`, `h1-changed` | Changed, but no batch asked for it. Often intentional (dynamic content), sometimes not |
| `internal-links-removed` | Links that existed are gone |
| `sitemap-paths-removed` | Pages dropped from the sitemap |
| `robots-disallow-added` | New crawl restrictions |
| `page-not-checked` | Couldn't compare: re-run the after-snapshot with `--paths-from` |

## Not checked by the scripts, checked by you

- **The design didn't change.** SEO work touches templates. Load a changed
  page in the preview and look at it; if the change was head-only, say so.
- **Analytics still fire.** If a template holding tracking tags was edited,
  confirm the tags are still present in the after-HTML.
- **Content is intact.** `word_count` is in every snapshot; a large drop on a
  page that wasn't meant to change needs an explanation before Gate 2.
  No threshold is applied automatically, because none is published.

## A second opinion: claude-seo's drift rules

claude-seo's `drift compare` checks 17 regression rules per URL, but only
against a baseline of **the same URL**: `--baseline-id` doesn't let it
compare a production baseline with a preview (tested with claude-seo 2.4.0:
"No baseline found for <url>"). So it's a second opinion after deploy, not
before: `drift baseline <url>` on production for the pages a batch changes
(at Discover), then `drift compare <url>` on the same production URLs after
the deploy (at Report). Before deploy, `diff.py` is the check, because it
compares by path across origins. Where the two disagree, the raw HTML
decides.
