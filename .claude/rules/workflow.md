# Workflow Rules

## Development Loop

1. **Plan** — Understand the requirement. Read relevant files first. Use Plan Mode for non-trivial changes.
2. **Build** — Make focused changes. One logical change per commit.
3. **Verify** — Check health endpoints, run tests, verify UI renders correctly.
4. **Prune** — Remove dead code, unused imports, and stale comments.

## Branching

- Feature branches: `feature/<short-description>`
- Bug fixes: `fix/<short-description>`
- Never commit directly to `main`

## Commit Messages

- Use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- Keep subject line under 72 characters
- Reference related issues when applicable

## Pull Requests

- One PR per logical change
- Include a description of what and why
- Self-review the diff before requesting review

## When Stuck

- Re-read `AGENTS.md` for architectural context
- Check `design_guidelines.json` for UI decisions
- Check `DEPLOYMENT.md` for infrastructure questions
- Ask rather than guess
