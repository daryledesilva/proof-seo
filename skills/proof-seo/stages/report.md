# Report

After Gate 2: ship what was approved, check it live, and leave the human
with an honest record and a date to look again.

## 1. Ship (only what Gate 2 approved)

- **Pull request**: push the branch and open a PR. The body lists the
  batches, links the report, and pastes the verdict and counts. Don't merge
  it.
- **Pull request and deploy**: the same, then deploy the way `brief.json`
  records, and nothing more.

If neither was approved, stop here with status `preview`; the report from
Validate is the record.

## 2. Live check (after a deploy)

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/snapshot.py" --site <site> --paths-from .proof-seo/<run-id>/before.json \
    --label live --out .proof-seo/<run-id>/live.json
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/diff.py" .proof-seo/<run-id>/before.json .proof-seo/<run-id>/live.json \
    --plan .proof-seo/<run-id>/plan.json --out .proof-seo/<run-id>/diff-live.json
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_report.py" --diff .proof-seo/<run-id>/diff-live.json \
    --plan .proof-seo/<run-id>/plan.json --status live-verified \
    --out .proof-seo/<run-id>/report.html
```

Then the authority's second opinion on the same production URLs it
baselined at Discover: `/seo drift compare <url>`. Put anything it triggers
in the hand-over message next to `diff.py`'s result.

A CDN or page cache can serve the old HTML for a while. If the live diff
shows promises MISSING that passed in preview, check the response headers
for a cache hit before assuming the deploy failed, and say which it was.

A live FAIL is reported immediately and plainly, with the rollback the
deploy path allows. Don't silently fix forward.

Merged but not yet deployed: `--status implemented` with the preview diff.

## 3. Hand over

Open the report. In chat: what shipped, the verdict, anything REVIEW, and
the follow-up date the report gives. Then offer, once, to set a reminder for
that date (for example with a scheduled task), and only create it on a yes.

What to tell them to do themselves, since proof-seo never acts in Search
Console: request indexing for the changed pages if they want it sooner, and
at the follow-up date compare impressions and clicks for those pages with
the same period before the change.
