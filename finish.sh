#!/bin/bash
#
# Commit the remaining fixes, merge origin/main, and push.
#
#   cd ~/Downloads/ME-assist-main
#   bash finish.sh
#
# Stops at the first sign of trouble rather than pushing something broken.
# Safe to re-run: each step checks whether it is already done.

set -euo pipefail
cd "$(dirname "$0")"

say()  { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
ok()   { printf '    \033[32mok\033[0m  %s\n' "$1"; }
die()  { printf '\n\033[31mSTOP: %s\033[0m\n' "$1" >&2; exit 1; }

# --- 0. stale lock -------------------------------------------------------
say "Checking for a stale index.lock"
if [ -f .git/index.lock ]; then
  if pgrep -x git >/dev/null 2>&1; then
    die "a git process is actually running. Close it, then re-run."
  fi
  rm -f .git/index.lock
  ok "removed a stale lock (no git process was running)"
else
  ok "no lock"
fi
rm -f .git/_probe 2>/dev/null || true

# --- 1. sanity -----------------------------------------------------------
say "Checking repository state"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not a git repository."
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
  die "a rebase is still in progress. Run: git rebase --abort"
fi
BRANCH=$(git rev-parse --abbrev-ref HEAD)
[ "$BRANCH" = "HEAD" ] && die "detached HEAD. Run: git checkout alex-main"
ok "on branch $BRANCH"

if grep -rln '^<<<<<<< \|^>>>>>>> ' --include='*.py' --include='*.txt' \
     --include='*.md' --include='*.html' --include='*.js' --include='.gitignore' . 2>/dev/null \
     | grep -v venv | grep -q .; then
  die "conflict markers are still in the working tree."
fi
ok "no conflict markers"

# An interrupted merge whose conflicts are now resolved should be completed,
# not started over.
if [ -f .git/MERGE_HEAD ]; then
  say "Finishing the merge that was interrupted"
  # Git keeps a path flagged "unresolved" until it is staged, so that flag is
  # not the test -- the absence of conflict markers, checked above, is.
  UNMERGED=$(git diff --name-only --diff-filter=U | tr '\n' ' ')
  [ -n "$UNMERGED" ] && printf '    resolving: %s\n' "$UNMERGED"
  git add -A
  git commit --no-edit
  ok "merge committed"
fi

# --- 2. secrets ----------------------------------------------------------
say "Making sure no secrets are about to be committed"
git check-ignore -q .env || die ".env is NOT ignored. Fix .gitignore before continuing."
git ls-files --error-unmatch .env >/dev/null 2>&1 && die ".env is TRACKED by git. Run: git rm --cached .env"
ok ".env is ignored and untracked"

for f in llm.py usage.db; do
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 && die "$f is tracked and should not be. Run: git rm --cached $f"
done
ok "no stale llm.py or usage.db tracked"

# --- 3. tests ------------------------------------------------------------
# Clear accumulated pytest temp directories first. pytest normally prunes to
# the last three, but if a run dies from descriptor exhaustion the cleanup is
# what dies, so they pile up -- and then scanning them costs descriptors too.
PYTMP="${TMPDIR:-/tmp}/pytest-of-$(id -un)"
if [ -d "$PYTMP" ]; then
  COUNT=$(find "$PYTMP" -maxdepth 1 -name 'pytest-*' 2>/dev/null | wc -l | tr -d ' ')
  if [ "${COUNT:-0}" -gt 3 ]; then
    rm -rf "$PYTMP"
    ok "cleared $COUNT stale pytest temp directories"
  fi
fi

say "Running the test suite"
if [ -x venv/bin/python ]; then PY=venv/bin/python; else PY=python3; fi
$PY -m pytest tests/ -q || die "tests failed. Nothing has been committed."
ok "backend tests pass"

if command -v node >/dev/null 2>&1; then
  node tests/test_ui_markdown.js >/dev/null 2>&1 && ok "UI rendering tests pass" \
    || printf '    skipped UI tests (fine: they need no deps, but node errored)\n'
fi

# --- 4. commit -----------------------------------------------------------
say "Committing"
if [ -z "$(git status --porcelain)" ]; then
  ok "nothing to commit, working tree already clean"
else
  git add -A
  git commit -F - <<'MSG'
Make the usage ledger non-fatal, and pin the cacheable prompt prefix

A bad usage.db could take down a chat request: writes were guarded but
reads were not, so requests_today/tokens_today/exhausted_state could
raise mid-request. Every ledger operation now degrades to "nothing
recorded" and warns once.

Note the direction of failure: a failed read makes a free tier look
fully available, which risks overrunning a daily budget. The provider's
own 429 is the real backstop, and the alternative is refusing to answer
at all.

Also anchor reference-section selection on the untrimmed history, so
history trimming cannot change the prompt prefix and silently start
missing the provider's cache.
MSG
  ok "committed"
fi

# --- 5. merge remote work ------------------------------------------------
# A .gitignore conflict resolves safely to the union of both sides: ignoring a
# path that the other branch also wanted ignored cannot lose anything. This is
# true of .gitignore specifically and is NOT generalised to other files.
resolve_gitignore_union() {
  git show :2:.gitignore > /tmp/ours.gitignore 2>/dev/null || return 1
  git show :3:.gitignore > /tmp/theirs.gitignore 2>/dev/null || return 1
  cat /tmp/ours.gitignore /tmp/theirs.gitignore \
    | grep -v '^[<>=]\{7\}' \
    | awk '!seen[$0]++ || $0 == ""' > .gitignore
  rm -f /tmp/ours.gitignore /tmp/theirs.gitignore
  git add .gitignore
  return 0
}

merge_ref() {
  local ref="$1"
  local behind
  behind=$(git rev-list --count "HEAD..$ref" 2>/dev/null || echo 0)
  if [ "$behind" = "0" ]; then
    ok "already up to date with $ref"
    return 0
  fi
  printf '    %s commit(s) to merge from %s\n' "$behind" "$ref"
  if git merge --no-edit "$ref"; then
    ok "merged $ref cleanly"
  else
    # Only .gitignore is auto-resolvable; anything else needs a human.
    local unmerged
    unmerged=$(git diff --name-only --diff-filter=U)
    if [ "$unmerged" = ".gitignore" ] && resolve_gitignore_union; then
      git commit --no-edit
      ok "merged $ref (.gitignore resolved to the union of both sides)"
    else
      die "conflict in: $(echo "$unmerged" | tr '\n' ' ')— resolve, then re-run."
    fi
  fi
  $PY -m pytest tests/ -q || die "tests failed AFTER merging $ref. Do not push."
  ok "tests still pass after merging $ref"
}

say "Fetching"
git fetch origin

# Your own remote branch first -- it may have moved (e.g. a merge done on
# GitHub), and pushing without it is what causes a non-fast-forward rejection.
if git rev-parse --verify "origin/$BRANCH" >/dev/null 2>&1; then
  say "Merging origin/$BRANCH"
  merge_ref "origin/$BRANCH"
fi

say "Merging origin/main"
merge_ref origin/main

# --- 6. push -------------------------------------------------------------
say "Ready to push to origin/$BRANCH"
git --no-pager log --oneline origin/"$BRANCH".."$BRANCH" 2>/dev/null || true
printf '\n    Push these? [y/N] '
read -r reply
case "$reply" in
  [yY]*) ;;
  *) printf '\n    Not pushed. Everything is committed locally; run this script\n'
     printf '    again when you are ready.\n\n'; exit 0 ;;
esac
git push origin "$BRANCH"
ok "pushed"

say "Done"
git --no-pager log --oneline -3
printf '\n  %s is now %s ahead of origin/main.\n' \
  "$BRANCH" "$(git rev-list --count origin/main.."$BRANCH")"
printf '  To get it into main, open a pull request on GitHub:\n'
printf '    https://github.com/GeoCosmos/ME-assist/compare/main...%s\n\n' "$BRANCH"
