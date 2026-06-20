# gruntwork-travel-skills

A family of Claude skills that turn travel confirmations into clean, accurate
calendar events. Published by **GruntworkAI** under MIT.

**Archetype:** Usable — a distributable skill bundle others install into a Claude
runtime. Optimize for the installer/end-user experience, not just our dev loop.

## Workspace

- Org: gruntwork (`~/Code/gruntwork/gruntwork-travel-skills`)
- Repo: `GruntworkAI/gruntwork-travel-skills` (GitHub, public)

## Layout

```
README.md            # shared setup (the family-level entry point)
LICENSE              # MIT
config.example.json  # template (committed)
config.json          # personal values (GITIGNORED — never commit)
core/                # shared spine, intentionally empty until a 3rd skill (rule of three)
flights-to-calendar/ # SKILL.md + README.md + scripts/build_events.py
lodging-to-calendar/ # SKILL.md + README.md + scripts/build_lodging_events.py
docs/                # reference docs (for users/deployers)
.claude/work/        # plans, sessions, todos (for developers — not shipped intent)
```

## Invariants (do not break)

- **`config.json` is gitignored and stays that way.** It holds the user's real
  calendar names. Only `config.example.json` is committed.
- **Propose before write.** Every skill parses → proposes → writes only on
  confirmation. Critical in unattended runtimes (these skills write to a live
  calendar).
- **Dedicated-calendar guarantee.** Skills write only to the calendar named in
  config and never create one. Don't add code that creates/targets other calendars.
- **Idempotent writes.** Events carry a hidden marker; re-running an itinerary
  updates in place via search → update → create → reconcile. Don't regress to blind
  creates.
- **`core/` stays empty until `cars-to-calendar` (the third skill) confirms the
  seam.** Each SKILL.md must stand alone; shared scripts are accelerators, not hard
  deps (self-contained runtimes like Claude Desktop have no shared filesystem).

## Conventions

- Python helpers under each skill's `scripts/`; deterministic, no network beyond
  the calendar connector.
- snake_case across config keys and Python (org convention).
- README at root = shared setup; each skill's README = domain-specific detail.

## Change management

- Solo project: code changes go through a branch + PR; doc/session-note touch-ups
  may go direct to `main`.
- This is a public repo — run `/run-scan-secrets` before pushing changes that touch
  config or scripts.
