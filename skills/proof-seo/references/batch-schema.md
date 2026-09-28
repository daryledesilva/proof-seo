# plan.json: batches

A batch is one kind of change applied across the pages that need it, for
example "unique titles on coin pages" or "BreadcrumbList on every coin page".
One batch is one option at Gate 1, one commit at Implement, and one set of
promises checked by `diff.py`.

```json
{
  "site": "https://example.com",
  "run_id": "2026-09-28-example.com",
  "snapshot": "before.json",
  "batches": [
    {
      "id": "breadcrumbs",
      "label": "Breadcrumb structured data",
      "title": "Add BreadcrumbList structured data to coin pages",
      "summary": "Coin pages show a breadcrumb trail but don't describe it in markup.",
      "source": "https://developers.google.com/search/docs/appearance/structured-data/breadcrumb",
      "quote": "the exact sentence from the source that supports this batch",
      "findings": ["F3", "F4"],
      "evidence": [{"path": "/bitcoin", "rule": "no-structured-data", "evidence": "raw HTML excerpt"}],
      "risk": "low: adds a script tag, changes nothing visible",
      "effort": "one template",
      "approved": false,
      "approved_at": null,
      "changes": [
        {
          "path": "/bitcoin",
          "field": "jsonld_types",
          "before": [],
          "after": ["BreadcrumbList"],
          "preview": {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": []}
        }
      ]
    }
  ]
}
```

## Fields a change can promise

`diff.py` checks each of these in the after-snapshot:

| `field` | `after` is | Delivered when |
|---|---|---|
| `title` | the exact title string | the first `<title>` matches (whitespace-normalized) |
| `meta_description` | the exact description | the first non-empty description matches |
| `canonical` | the exact URL | the first canonical matches |
| `meta_robots` | the exact directives, lowercase | the joined robots/googlebot meta matches |
| `h1` | the exact heading text | the first H1 matches |
| `jsonld_types` | a list of `@type`s | every listed type is present in valid JSON-LD |
| `images_missing_alt` | a number, usually `0` | that many images still lack `alt` |

`before` is what the before-snapshot has, copied from it rather than retyped.
`preview` is optional: the literal markup the change adds (a JSON-LD object
or an HTML string). When present, the gate page shows it, and Implement
ships that same markup.

## Writing good batches

- **`label`, `title` and `summary` in plain words.** They're what the site
  owner reads at the gate: "Tell Google the site's name", not "WebSite
  JSON-LD". See the approval policy's plain-language section.
- **One kind of change per batch.** "Titles and schema" is two batches, so
  the human can take one without the other.
- **Every affected page listed.** On a large site that's still every page,
  generated rather than typed; the gate page shows the first few snippets
  and the full table.
- **Dynamic values are written as they'll render.** If a title is built from
  a template (`{coin} DCA Calculator`), the change lists each page's
  resulting string, not the template, because that's what gets checked.
- **Say what it costs.** `risk` and `effort` are shown at the gate; keep
  them factual ("one template", "touches the layout used by every page").
