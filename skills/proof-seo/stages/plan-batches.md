# Plan batches

Turn findings into a small number of concrete, separately approvable
changes, each written out as the exact values that will ship.

## 1. Group

One batch is one kind of change: all the missing descriptions, or
BreadcrumbList on every page with a breadcrumb trail. Don't mix kinds; the
human should be able to take one and leave another.

Order batches by value, highest first, using only what the evidence
supports: errors before warnings before opportunities; many pages before
few; low-risk before template-wide.

Default to **3 batches** at Gate 1. If more exist, plan them too, but put
the 3 strongest in the question and say how many others there are.

Skip what shouldn't be changed: a deliberate `noindex` (an admin page, a
thank-you page), a duplicate title that's correct because the pages really
are duplicates (then the fix is a canonical, which is a different batch).
When in doubt, it's a question for the human, not a batch.

## 2. Write the exact values

For every page a batch touches, write the change as `references/batch-schema.md`
describes: `before` copied from the snapshot, `after` as it will render on
that page. For structured data, generate the block (the authority's
`/seo schema` can), validate it as JSON, and put it in `preview`.

The values are real because they're what Implement will ship and what
`diff.py` will check. Don't write placeholder text you intend to improve
later: improve it now, or it's the wrong value at the gate.

Where a value comes from a template, render it per page. If the template
produces something awkward on some page (a title with an empty variable, a
description that repeats the name twice), that's visible in the table, which
is the point.

## 3. Build the gate page

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_gate_page.py" --plan .proof-seo/<run-id>/plan.json \
    --snapshot .proof-seo/<run-id>/before.json --out .proof-seo/<run-id>/gate
```

Then follow `references/approval-policy.md`: serve it, open it, verify it
loaded, describe each batch in one line, and ask.
