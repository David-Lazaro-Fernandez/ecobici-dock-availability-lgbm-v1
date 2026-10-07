# Code comments: let the code speak

The code must explain itself. Comments add only what the code cannot say.

## Write code that explains itself

- Use names that tell the purpose: `walk_to_pickup_min`, not `w` or `tmp`.
- Use small functions with one job. The function name replaces the comment.
- Put fixed values in named constants: `STALE_AFTER_SECONDS = 3 * 60 * 60`, not a
  number with a comment.

## Write a comment only to tell why

Write a comment when the code cannot show:

- **Why** this choice, if a reader can think of a simpler one. Example: "MaxHalford sets
  `is_renting` to false when a station has no bikes, so it is not an outage."
- A **constraint** from outside the code: an API limit, a data defect, a license term,
  a decision in `docs/`.
- A **trap**: something that looks wrong but is correct, or a change that breaks
  something far away. Example: "Feature names are in the frozen booster. Do not
  rename them."

Do not write a comment that:

- says again what the code says (`# Sort by walk` above `sort("walk_m")`);
- tells the history of the change ("Changed this because…", "Fixed bug"). Git keeps
  the history;
- explains a standard language or library feature;
- repeats the function name or the type hints in a docstring.

## Keep comments short

- One idea in one sentence. Two or three sentences are the maximum for a normal
  comment.
- A module docstring tells what the module is for, how to run it, and its main
  decisions. It does not describe each function.
- A function docstring tells what the caller must know: the contract, the units, the
  edge cases. Do not describe the steps inside the function.
- If a comment needs a paragraph, the explanation goes in `docs/` and the comment
  links to it.

## Language

- English comments: follow ASD-STE100 Simplified Technical English.
  - Short sentences: 20 words maximum for an instruction, 25 for a description.
  - One instruction in one sentence. Use the imperative: "Drop stale readings".
  - Active voice. Simple present or simple past tense.
  - One word for one meaning. If the code says `pickup`, the comment says "pickup",
    not "origin" or "start station".
  - No idioms, no jokes, no filler words ("basically", "simply", "just", "note that").
- Spanish comments and docs: follow the same rules in plain technical Spanish (español
  técnico simplificado): short sentences, active voice, one term for one meaning, no
  filler.
- Keep the language of the file. The `docs/` reports are in Spanish. The code is in
  English.

## When you change code

- Read the comments near the change. Delete or correct a comment that is no longer
  true. An incorrect comment is worse than no comment.
- Before you finish, read your new comments again. Delete each one that says what the
  code already says.
