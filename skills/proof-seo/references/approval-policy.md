# Approval policy: the two gates

Only two moments stop for a human: choosing what to change (Gate 1) and
choosing to ship it (Gate 2). Everything else just runs. The shape follows
redesign-lab's approval policy, which earned its rules the hard way; the
mechanics below are inherited from it where they apply.

## Every gate: three outcomes, not two

- **Approve**: the choice itself (these batches; ship it).
- **Reject and retry**: "not these, try again", or "change this value". Fix
  the specific thing named and rebuild only that batch's page, not the whole
  set. This is ordinary chat, not a button.
- **Stop**: halt the workflow. Nothing is discarded; everything in
  `.proof-seo/<run-id>/` is real, saved output. Resuming is just asking again.

"Stop here" is **always an option in the same `AskUserQuestion` call** as the
real choices. A gate that only offers the choices has been presented wrong.

## Write every gate for someone who doesn't do SEO

Confirmed on the first real run: a gate phrased as "Which batches should
proof-seo implement? · WebSite JSON-LD + og:site_name · 40 pages" got the
answer "I don't get this question". The person answering owns the site, not
the jargon. Every gate message and every option says:

- **What it does, in plain words.** "Tell Google the site is called 'DCA
  Crypto Calculator'", not "WebSite JSON-LD on the home page". The technical
  term can follow in brackets once.
- **What the visitor or Google will notice**, or plainly that nothing visible
  changes.
- **What happens after they answer.** "I'll make these on a branch and test
  them; nothing goes live until you say so at the next step."

Keep the page counts and sources in the chat message and on the gate page,
where there's room for them. Option descriptions stay short and readable.

## Show the real thing first, then ask

The artifact is always opened before the question is asked, and the question
is always an `AskUserQuestion` call, never a numbered list typed into chat.

**Gate 1 mechanism** (single page, real URLs, as in redesign-lab rev 8):

1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_gate_page.py" --plan plan.json --snapshot before.json --out .proof-seo/<run-id>/gate`
2. Serve it over HTTP, not `file://`:
   `python3 -m http.server 8765 --bind 127.0.0.1 --directory .proof-seo/<run-id>/gate`
   (`file://` breaks the iframes).
3. Open `http://127.0.0.1:8765/gate.html` in the browser pane if there is
   one. If there isn't (a remote or terminal-only session), send the batch
   pages with `SendUserFile`, or print the key before/after values in chat.
   The human must be able to see the actual values before choosing.
4. Say in chat what each batch is, in one line each, with its page count and
   the source behind it.
5. Then ask.

**Verify it loaded; don't trust "opened".** Check the page title or the
active iframe's content before telling the human it's ready. An earlier
lesson from redesign-lab: the tool saying a page opened is not evidence the
human can see it.

## Gate 1: which batches

`AskUserQuestion` allows 2 to 4 options, so:

- `multiSelect: true`
- Up to **3 batches** as options, highest value first. Label: the batch
  title. Description: page count, the one-line why, and the source domain
  (e.g. "14 pages · duplicate titles · Google Search Central").
- **"Stop here"** as the last option, always.

More than 3 batches: say so in the chat message ("5 batches; the 3 with the
most evidence are in the question, the other 2 are on the page"). The human
can name the others in the free-text answer. Same for "change a value
first": they type what to change, you edit plan.json, rebuild that batch's
page, and ask again.

If "Stop here" is ticked alongside batches, stop, and say that nothing was
implemented. On approval, set `"approved": true` on the chosen batches in
`plan.json` and record `approved_at`.

## Gate 2: ship it

Only reached when `diff.py` returned PASS. A FAIL goes back to Implement;
the human never sees a failing result presented as shippable.

Open `report.html` (same HTTP-and-verify rule), summarize in chat: batches
applied, promises delivered, preservation result, anything marked REVIEW.
Then `AskUserQuestion`:

- **"Open a pull request"**
- **"Open a pull request and deploy"** (only offer this if Discover found a
  deploy path the human already uses)
- **"Change something first"** (they describe it; back to Implement)
- **"Stop here"** (the branch stays; nothing is pushed)

Anything marked REVIEW is listed in the chat message before the question,
with what changed, so the human decides with it in view. REVIEW never
blocks; FAIL always does.

## What never gets a gate

Discover, Audit and Plan run without stopping: nothing is changed and
nothing is spent. Implement and Validate run without stopping too: Gate 1
already approved the changes, and Gate 2 approves the result. The post-deploy
live check and the report need no gate either; they only read.
