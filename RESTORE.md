# Recovering from the stalled rebase

Run these in Terminal, in order.

## 0. Clear the stale lock (do this first)

```bash
cd ~/Downloads/ME-assist-main
rm -f .git/index.lock .git/_probe
```

No git process is running — those two files were left behind when this session
inspected the repo. The sandbox can create files under `.git` but cannot delete
them, so the lock stayed put. Deleting it is safe.

If you want to confirm nothing is genuinely running first:

```bash
ps aux | grep '[g]it'
```

## 1. Look before you leap

```bash
git status
git log --oneline -5 alex-main      # where your branch was before the rebase
git log --oneline -5 origin/main    # what the remote has
```

You are currently in detached HEAD, part way through an interactive rebase
(step 4 of 25).

## 2. Abandon the rebase

```bash
git rebase --abort
```

This returns you to `alex-main` as it was before the rebase started.

**It also hard-resets the working tree**, discarding the repaired files. That is
expected — step 3 puts them back. Do not skip ahead.

## 3. Restore the repaired code

Unpack `me-assist-FIXED.tar.gz` over the folder (adjust the path to wherever you
saved it):

```bash
tar xzf ~/Downloads/me-assist-FIXED.tar.gz -C ~/Downloads/ME-assist-main
```

The archive deliberately excludes `.env`, `usage.db`, `venv/` and the stale
`llm.py`, so your keys and local data are untouched.

## 4. Remove the stale `llm.py`

The pre-refactor single-file `llm.py` is still on disk and shadows the `llm/`
package. It must not be committed:

```bash
git rm --cached llm.py 2>/dev/null; rm -f llm.py
```

## 5. Confirm nothing secret is staged

```bash
git status --short
git diff --cached --name-only | grep -E '^\.env$' && echo "STOP: .env is staged"
```

`.env` should never appear. It is in `.gitignore`, but check anyway.

## 6. Verify before committing

```bash
source venv/bin/activate
pytest tests/ -q                 # expect 167 passed
node tests/test_ui_markdown.js   # expect 15 passed
```

If `pytest` reports `sqlite3.OperationalError: unable to open database file`,
you are on an older copy of `usage.py` — the archive fixes it. Ledger reads now
degrade to zero and print one warning instead of raising, so a bad `usage.db`
can never fail a test or a chat request.

## 7. Commit and push

```bash
git checkout alex-main           # leave detached HEAD
git add -A
git commit -F - <<'MSG'
Add provider chain with explicit paid-provider approval

Free tiers are used first and a paid provider is never called without a
click. The stream stops before the first token and reports which model
would answer, the estimated cost, and the conversation total so far.

Rate limiting:
- pace requests locally against published RPM/TPM limits rather than
  discovering them via 429s
- a per-minute limit falls through to another free tier, or waits, and
  never escalates to a paid prompt on its own
- track the daily token budget, which is the binding limit on Groq

Prompt:
- reference sheet split into 13 sections; a discipline selects its own,
  otherwise sections are chosen from the first question and then held
  fixed so the prefix stays cacheable
- record cached tokens per turn so cache behaviour can be measured
- cap re-sent history and tell the user when turns are dropped

UI:
- each discipline is a separate conversation, persisted across reloads
- model handoffs are marked in the transcript
- fixed numbered lists rendering as "1." repeatedly, and a layout bug
  that let the transcript scroll under the input bar

Also: Groq provider, editable free-tier limits, settings panel for keys
and models, double-click launchers, and a usage ledger that degrades
instead of failing the request.
MSG
git push origin alex-main
```

## If push is rejected

The remote has commits you do not. Do **not** force-push. Instead:

```bash
git pull --rebase origin alex-main
```

and resolve conflicts one at a time — or ask for help rather than guessing.

## If `index.lock` comes back

Only two things create it: a real git process, or a crashed one. Check with
`ps aux | grep '[g]it'` first; if nothing is running, `rm -f .git/index.lock`
is safe. It will not reappear from this session — no further git commands will
be run against your repo from the sandbox.

## Why the rebase hurt

It was replaying 25 commits across a large refactor: `llm.py` became the `llm/`
package, and `config.py` moved from module constants to accessor functions.
Nearly every commit touched files that no longer exist in the same shape, so
almost every step conflicts. A merge, or a single squashed commit, is far less
painful for a change of this size.
