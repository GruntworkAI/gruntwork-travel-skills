# Session: Migrate travel-skills from Claude Desktop → GitHub

**Date:** 2026-06-19
**Outcome:** Public repo live at https://github.com/GruntworkAI/gruntwork-travel-skills (initial commit `ab28ced`)

## Goal

Migrate a skill built in Claude Desktop into a version-controlled GitHub repo for
easy sharing and change management.

## What the source actually was

A `gruntwork-travel-skills.zip` in `~/Code/drafts/` (filename typo "gruntowrk"; the
internal folder was correctly `gruntwork-travel-skills`). Not one skill — a clean
two-skill bundle, already authored for publishing:

- `flights-to-calendar/` (SKILL.md + README + `scripts/build_events.py`)
- `lodging-to-calendar/` (SKILL.md + README + `scripts/build_lodging_events.py`)
- `core/` — intentionally empty placeholder (rule of three; waits for a 3rd skill,
  `cars-to-calendar`, to confirm the shared seam)
- Shared README, MIT LICENSE (© 2026 GruntworkAI), `config.example.json`,
  `.gitignore` (already excluded `config.json`)

## Decisions (user)

- Workspace: **gruntwork** → `~/Code/gruntwork/gruntwork-travel-skills`
- Hosting: **public** GitHub repo under **GruntworkAI**
- Scaffold with `organize-project`: **yes**
- Example data: replace the real-looking itinerary with a **JFK→LAX** example

## Steps

1. Extracted bundle into the gruntwork workspace.
2. Ran `organize-project` → created `docs/` + `.claude/work/{todos,plans,sessions}`,
   `.claude/debt/`, `.claude/archive/`. No scattered files to migrate.
3. Wrote project **CLAUDE.md** (Usable archetype) capturing invariants: gitignored
   `config.json`, propose-before-write, dedicated-calendar guarantee, idempotent
   marker writes, `core/` stays empty until the 3rd skill.
4. Secret scan: clean. Hardened `.gitignore` with standard secret patterns
   (`.env`, `*.pem`, `*.key`, etc.).
5. `git init` → initial commit (global pre-commit secret hook passed).
6. `gh repo create --public --source=. --push`.

## Personal-data catch (the important part)

User flagged: "double check there isn't anything personal in there." A scan beyond
secrets found **one real-looking test itinerary** breaking the otherwise-synthetic
example convention:

- `DL 3704 · LAX→ASE` on `2026-08-03` (Aspen) — appeared in
  `flights-to-calendar/README.md` (marker + Flighty title examples) AND in
  `SKILL.md:64` (`Departs 5:10 PM LAX / Arrives 8:24 PM ASE`).

All other examples were obviously fake (`UA 123`, PNR `ABC123`). Replaced every
occurrence with synthetic **JFK→LAX** data (`AA 1`, marker `[ttc:AA1:2026-07-04:JFK]`,
`Departs 8:00 AM JFK / Arrives 11:30 AM LAX`). No names/emails/addresses anywhere.
`LAX` kept as the generic home-airport example (conventional, user's call).

**Lesson:** secret scanning ≠ personal-data scanning. Interactively-built skills
often carry real test itineraries (flight #, route, date) that no secret scanner
flags. Grep for specific flight numbers / dates / routes that break the synthetic
example pattern before publishing.

## Verified on remote

12 files tracked, `config.json` absent (gitignored), branch `main`, visibility
PUBLIC.

## Open / optional follow-ups

- `docs/` and `.claude/work/` are empty → Git doesn't track empty dirs; they appear
  once populated.
- Branch-protection / PR-template baseline not set up (offered, not done).
- `cars-to-calendar` is the planned 3rd skill that would trigger extracting `core/`.
