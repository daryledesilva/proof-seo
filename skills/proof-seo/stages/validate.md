# Validate

Prove the branch does what Gate 1 approved and nothing else, before anyone
is asked to ship it.

## 1. Preview

Run the branch the way `brief.json` says (`preview.how`), on a port that
isn't in use, alongside anything server-side rendering needs. Don't touch the
production processes: use a separate checkout (`git worktree add`) if the
production site is served from the same directory. Wait until the preview
answers before snapshotting.

## 2. After-snapshot and diff

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/snapshot.py" --site <site> --origin <preview origin> \
    --paths-from .proof-seo/<run-id>/before.json --label after \
    --out .proof-seo/<run-id>/after.json

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/diff.py" .proof-seo/<run-id>/before.json .proof-seo/<run-id>/after.json \
    --plan .proof-seo/<run-id>/plan.json --out .proof-seo/<run-id>/diff.json
```

`--site` stays the production URL so paths and canonicals are interpreted
as the real site; `--origin` is where they're fetched from. If the app routes by
domain (a Laravel `Route::domain`, a multi-site CMS), add `--host-header
<production host>` so the preview answers as the real site. If it builds
absolute URLs from the request's scheme, serve the preview as HTTPS too (for
PHP's built-in server, a router script that sets `$_SERVER['HTTPS'] = 'on'`),
or every canonical will show up as changed. `--paths-from`
makes the comparison over exactly the same pages.

Expect differences that come from the environment, not the change: a local
server's absolute URLs, a missing CDN, test data. Read each REVIEW entry and
explain it; a preview that can't reproduce production closely enough to
compare is itself a finding to report, not something to paper over.

## 3. If it failed

`diff.py` exits 1 on FAIL. Go back to Implement, fix the cause, re-run
Validate. Don't present a failing result at Gate 2, and don't loosen a
check to get a pass.

## 4. Report and Gate 2

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_report.py" --diff .proof-seo/<run-id>/diff.json \
    --plan .proof-seo/<run-id>/plan.json --status preview \
    --out .proof-seo/<run-id>/report.html
```

Look at a changed page in the preview yourself (a browser, or the snapshot's
`head_html`) to confirm the design didn't move. Then Gate 2, per
`references/approval-policy.md`. Stop the preview processes you started once
the gate is answered.
