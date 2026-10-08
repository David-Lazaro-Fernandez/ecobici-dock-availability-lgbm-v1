<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

## Before you finish a change

Run every npm command from `web/`. The repo root has no `package.json`.

1. `npm test`: unit tests in `lib/*.test.mjs`.
2. `npm run build`: the build that Vercel runs. It also does the type check of the app. `npm test` does not do a
   type check, so a passing `npm test` does not show that the build passes.
3. `npm run test:e2e`: Playwright tests in `e2e/`, after a change to the layout, the search or the planner.

Do not commit or push a change until `npm run build` passes. If you cannot run it, tell the user.

## Dependencies

- Add a package with `npm install` before you commit code that imports it. `package.json` and `package-lock.json`
  go in the same commit as that code.
- Packages come from npmjs only. See `.claude/rules/package-index.md`.

## Type check boundaries

- `tsconfig.json` checks the app only. It excludes `e2e/` and `playwright.config.ts`, because the build must not
  need the test tools.
- `e2e/tsconfig.json` checks the Playwright tests. Keep the test files there, out of the app type check.
