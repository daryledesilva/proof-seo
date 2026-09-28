# Implement

Make exactly the approved changes, through the site's own mechanism, on a
branch.

## 1. Branch

```
git switch -c proof-seo/<run-id>
```

from the base recorded in `brief.json`. If the working tree has unrelated
uncommitted changes, stop and tell the human rather than carrying them onto
the branch.

## 2. Change

For each approved batch, in plan order:

- Change the values where `seo_mechanism` says they're set: the SEO
  package's calls, the framework's metadata API, the CMS field, or the
  template. Never add a parallel mechanism; if a page's tags come from two
  places, change the one that wins and note the other.
- Ship the batch's `preview` markup verbatim. If it has to differ (the
  template can't produce it exactly), update `plan.json` to match what ships
  and say so at Gate 2. What was approved and what ships must be the same
  thing, and `diff.py` will check.
- Values built from data (a coin's name, a product's price) are built from
  the same data the page already uses, so they can't drift from the visible
  content.
- One commit per batch, message naming the batch id.

Build steps that production needs (asset compilation, an SSR bundle) are
part of the change: if committed build output is how this project ships, run
the build and include it the same way the project's history does.

## 3. url-only mode

No edits. Write `changes.md`: per batch, per page, what to set and where,
with the exact values and markup. That's the deliverable, and the report's
status is `preview`.
