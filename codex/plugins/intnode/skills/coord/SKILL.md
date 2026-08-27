---
name: coord
description: Coordinate repository work through the canonical host-local intnode coord command without transferring owner authority.
---

# intData Node coordination

Use the installed `intnode coord` command for advisory, host-local coordination.
Coordination records paths, contours and pinned evidence; it never grants approval,
publication authority or permission to mutate protected state.

## Workflow

1. Resolve the owning repository and inspect `git status --short --branch`.
2. Run `intnode coord status-readonly --repo-root <repo> --format json` before mutation.
3. Start or reuse one session with exact file or directory paths:

   ```text
   intnode coord begin --repo-root <repo> --owner <owner> --base HEAD --path <path> --format json
   ```

4. Stop on a real same-path, same-region, runtime, database or publication overlap.
5. Add newly discovered paths with `intnode coord intent`; never broaden an existing
   intent silently.
6. Before commit, stage whole files and run:

   ```text
   intnode coord commit-scope-check --repo-root <repo> --owner <owner> --format json
   ```

7. Release only the exact session created for the work:

   ```text
   intnode coord release --session-id <session-id> --format json
   ```

## Boundaries

- Keep coordination state local to each host; do not copy its database between hosts.
- Record task identifiers, paths, contours, relationships and bounded evidence only.
- Never store prompts, reasoning, transcripts, messages, outputs, secrets or credentials.
- Treat warnings as evidence to inspect, not as automatic authority to overwrite work.
- Never use coordination to bypass protected dirty state, repository instructions or
  an explicit owner gate.
