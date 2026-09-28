# brief.json

Filled in at Discover. Ask the human only for what can't be found by
looking; most of it can be.

```json
{
  "run_id": "2026-09-28-example.com",
  "site": "https://example.com",
  "codebase": "/path/to/repo",
  "branch_base": "main",
  "framework": "laravel+inertia-ssr",
  "seo_mechanism": "artesaos/seotools, set in app/Http/Controllers/*",
  "preview": {
    "how": "php artisan serve --port 8010 (plus the SSR server)",
    "origin": "http://127.0.0.1:8010"
  },
  "deploy": "git pull on the server, npm run production, restart the SSR worker",
  "authority": "claude-seo 2.4.0",
  "focus": "whatever the human said they care about, in their words",
  "mode": "codebase"
}
```

`mode`:

- **`codebase`**: there's a repo to change. Implement edits it on a branch;
  Validate snapshots a local or staging preview of that branch.
- **`url-only`**: no code access. Everything up to and including Gate 1
  works the same. Implement produces a written change list (and snippets
  per page) for whoever can edit the site, and the report's status stays
  `preview` until someone applies it and a live snapshot is taken.

`seo_mechanism` matters most: it's where Implement makes changes. Find it
before planning: an SEO package, a framework metadata API, a CMS plugin, or
plain templates. Never add a second mechanism next to an existing one.
