# Mechanical rules

What `scripts/check.py` flags, and the published sentence each rule rests on.
This table is generated from the `RULES` dict in `check.py`
(`check.py --rules > references/rules.md`), so it can't drift from the code.
Each source was fetched and the quoted sentence confirmed in it when the rule
was added.

Deliberately absent, because no primary source states them: title or
description length limits, a required H1, one H1 per page, keyword density,
minimum word counts, and a viewport rule (Google's mobile-first indexing
page doesn't mention the viewport meta tag). Judgment calls like these
belong to the SEO authority, and have to be argued from evidence rather than
applied as rules.

Severity:

- **error**: the source says this stops a page being used, or it's invalid.
- **warning**: the source recommends against it.
- **info**: an opportunity or a heads-up, not a defect.

| Rule | Severity | What it flags | Source | What the source says |
|---|---|---|---|---|
| `page-error` | error | Page returns an error status | [link](https://developers.google.com/search/docs/crawling-indexing/http-network-errors) | "Search Console generates error messages for status codes in the 4xx—5xx range, and for failed redirections (3xx)." |
| `page-unreachable` | error | Page could not be fetched at all | [link](https://developers.google.com/search/docs/crawling-indexing/http-network-errors) | "Search Console generates error messages for status codes in the 4xx—5xx range, and for failed redirections (3xx)." |
| `redirect-too-many` | error | Redirect chain too long to be followed | [link](https://developers.google.com/search/docs/crawling-indexing/http-network-errors) | "By default, Google's crawlers follow up to 10 redirect hops." |
| `broken-internal-link` | error | Internal link points at an error page | [link](https://developers.google.com/search/docs/crawling-indexing/http-network-errors) | "Search Console generates error messages for status codes in the 4xx—5xx range, and for failed redirections (3xx)." |
| `title-missing` | error | No title | [link](https://developers.google.com/search/docs/appearance/title-link) | "Make sure every page on your site has a title specified in the &lt;title&gt; element." |
| `title-multiple` | warning | More than one &lt;title&gt; element | [link](https://html.spec.whatwg.org/multipage/semantics.html#the-title-element) | "There must be no more than one title element per document." |
| `title-duplicate` | warning | Same title as other pages | [link](https://developers.google.com/search/docs/appearance/title-link) | "ensure each page has a unique, descriptive, and concise title within the &lt;title&gt; element." |
| `description-missing` | warning | No meta description | [link](https://developers.google.com/search/docs/appearance/snippet) | "Create unique descriptions for each page on your site" |
| `description-duplicate` | warning | Same meta description as other pages | [link](https://developers.google.com/search/docs/appearance/snippet) | "Identical or similar descriptions on every page of a site aren't helpful when individual pages appear in search results." |
| `canonical-conflict` | error | Page declares more than one different canonical URL | [link](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls) | "Don't specify different URLs as canonical for the same page using different canonicalization techniques" |
| `noindex` | info | Page asks not to be indexed | [link](https://developers.google.com/search/docs/crawling-indexing/block-indexing) | "Block Search Indexing with noindex" |
| `noindex-in-sitemap` | warning | Listed in the sitemap but marked noindex | [link](https://developers.google.com/search/docs/crawling-indexing/block-indexing) | "Block Search Indexing with noindex" |
| `robots-blocked-in-sitemap` | warning | Listed in the sitemap but blocked by robots.txt | [link](https://developers.google.com/search/docs/crawling-indexing/robots/intro) | "A robots.txt file tells search engine crawlers which URLs the crawler can access on your site." |
| `jsonld-invalid` | error | Structured data is not valid JSON | [link](https://www.w3.org/TR/json-ld11/) | "A JSON-LD document is always a valid JSON document." |
| `no-structured-data` | info | No structured data on the page | [link](https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data) | "when a recipe page has JSON-LD structured data (describing the title of the recipe, the author of the recipe, and other details), Google Search can use that information to display a rich result" |
| `image-missing-alt` | warning | Images without an alt attribute | [link](https://developers.google.com/search/docs/appearance/google-images) | "Use descriptive filenames, titles, and alt text" |
| `sitemap-missing` | info | No reachable sitemap | [link](https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview) | "If your site's pages are properly linked, Google can usually discover most of your site." |
