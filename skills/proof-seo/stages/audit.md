# Audit

Two sources of findings, one standard of evidence.

## 1. Mechanical

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check.py" .proof-seo/<run-id>/before.json --out .proof-seo/<run-id>/findings.json
```

Each finding has a rule, a page, the raw evidence, the source URL and the
quoted sentence it rests on (`references/rules.md`). These can go straight
into batches.

## 2. The SEO authority

Run claude-seo for the judgment calls the mechanical rules deliberately
don't make. `/seo audit <site>` for a whole site, or the narrower commands
when the human's focus is specific (`/seo schema`, `/seo content`,
`/seo geo`, `/seo technical`). Save its report as `audit.md`.

## 3. Verify before anything goes further

For every authority finding you intend to act on, confirm it in the raw
HTML: the page's `head_html` in `before.json`, or a fresh fetch. Attach the
exact excerpt. Findings that can't be shown in the HTML are dropped, or
kept as questions for the human, never presented as site defects.

Also drop, or flag as unsupported, any finding that rests on a number with
no source (a "title should be under 60 characters" style rule). If the
authority gives a source, keep the source with the finding.

## 4. Record

`findings.json` holds the mechanical findings. Append verified authority
findings to it in the same shape (`rule` prefixed with `authority:`,
`source` and `quote` from the authority's cited reference, or `null` with a
note if it cited none), so Plan works from one list.
