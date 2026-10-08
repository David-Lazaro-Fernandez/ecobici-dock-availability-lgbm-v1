# Agent rules for this repo

`web/AGENTS.md` has the rules for the web app. `.claude/rules/` has the rules for comments, packages and PRs.

## Validate before you describe

A PR description, a commit message or a report tells only what you ran and saw.

- Before you write the Test Plan, run each check. Write the command or the steps, and the result that you saw.
- If you cannot run a check, do not put it in the Test Plan. Tell the user what is not validated and why.
- Words like "after the merge, run…", "deploy note", "the server will…" or "this should…" show a claim that is
  not validated. Stop. Validate it first, then write again what you saw.
- Tell what a check did not cover. A dry run, a copy of the logic in a shell command or a syntax check is not a
  run of the real script. Say so.
- If a check fails, do not change the text to hide it. Find the cause with the user, fix it, then run the check
  again.

## Changes to the server

The API runs on the server in `deploy/api/README.md`. A merge to `main` is a deploy.

- Validate a change to `deploy/` on the server before the merge, in the same context as production: a systemd unit
  as root, with SELinux enforcing. A manual `sudo` run is a different SELinux context and can pass when the timer
  fails.
- Tell the user before a step that restarts the API or changes the server checkout.
- Put the server checkout back on `main`, with no local changes, when you finish.
