# Discover

Establish what's there before anyone decides anything: the brief, the
prerequisites, the codebase, and the production baseline that every later
check is measured against.

## 1. Brief

Fill `brief.json` (`references/brief.md`). Find things out rather than
asking: the site URL is usually in the request or the project's config
(`APP_URL`, `site_url`, `baseURL`, `next.config.*`, `wp_options`). Ask only
for what looking can't answer, typically the deploy path.

## 2. Prerequisites

- **Python 3.8+** for proof-seo's scripts: `python3 --version`. Standard
  library only, nothing to install.
- **The SEO authority** (`references/seo-authority.md`): run `/seo doctor`.
  If it isn't installed, tell the human now, give them the three install
  commands, and let them choose between installing it and going ahead on the
  mechanical rules alone. claude-seo itself needs Python 3.10+; on an older
  system, `uv python install 3.12` gives it an isolated interpreter without
  touching the system one (point `CLAUDE_SEO_PYTHON` at it). Record the
  choice and the version in `brief.json`.

## 3. Codebase (mode `codebase` only)

Find three things and write them into `brief.json`:

1. **Where head tags come from** (`seo_mechanism`). Search for the tags
   themselves in templates (`<title`, `name="description"`, `rel="canonical"`,
   `application/ld+json`) and for SEO packages in the dependency manifest.
   There may be more than one source (a layout default and per-page
   overrides); record all of them.
2. **How to run it locally** (`preview`). The framework's own dev server,
   plus anything server-side rendering needs (an SSR process, a queue). A
   staging URL works too. If there's no way to preview, say so now: the
   report will stay at `implemented` until a live check is possible.
3. **How it ships** (`deploy`), if the human already has a routine.

## 4. Baseline

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/snapshot.py" --site <site> --label before --max-pages 200 \
    --out .proof-seo/<run-id>/before.json
```

- This snapshots **production**. It's the contract: what's true now, which
  nothing later may break by accident.
- `--max-pages`: enough to cover every page template, not every URL. A
  catalogue of 5,000 products needs a representative sample of product pages
  plus every distinct template, not all 5,000. The snapshot records whether it
  stopped early (`truncated`); say so in the Gate 1 message if it did.
- Client-rendered sites: add `--browser <headless chromium>` so the rendered
  DOM is captured too, and run `check.py --rendered` in Audit.
- Also take the authority's own baseline of the production pages you expect
  to change (`/seo drift baseline <url>`). Its drift rules only compare a URL
  with itself, so they run after deploy, in Report.

Nothing is asked of the human in this stage beyond missing facts, and
nothing is changed.
