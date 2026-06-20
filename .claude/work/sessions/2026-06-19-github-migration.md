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

---

# Part 2: Packaging + self-hosted runtime support (same session)

Two open questions from the user after the migration: (1) ship a drop-in zip for
Claude Desktop users without git/dev metadata, and (2) what's needed for OpenClaw /
ZeroClaw. Both shipped via **PR #1** (squash-merged) → tag **v0.1.0** → Release.

## 1. Desktop installer packaging

- **`scripts/package.sh [version]`** — builds `dist/<name>-<version>.zip` from an
  **explicit allowlist** (README, LICENSE, config.example.json, core/, the two skill
  dirs). Excludes `.git/`, `.github/`, `.claude/`, `CLAUDE.md`, `docs/`, `dist/`,
  and stray `config.json`/`__pycache__`/`.DS_Store`. `dist/` is gitignored.
- **`.github/workflows/release.yml`** — on a `v*` tag push, runs the script and
  `gh release create` with the zip attached + auto-notes (`contents: write`).
- README **Install** split: Desktop downloads the Release zip; filesystem runtimes
  clone. Repo layout + CLAUDE.md document the build/release process.

## 2. OpenClaw / ZeroClaw

The skills were *already* runtime-agnostic by design (author explicitly named
OpenClaw/ZeroClaw; tools discovered at runtime, no hardcoded names; config-path
difference already handled). So no code changes for the happy path — the work was
environmental + the one real gap (unattended writes):

- **`shared.auto_approve` config block** — disabled by default. When enabled, bounds
  unattended writes: `calendars` allowlist, `max_events_per_run`, `future_dated_only`,
  `updates_via_marker_only`.
- **Both SKILL.md propose-gates honor it** — no human + auto_approve off ⇒ surface
  the proposal and stop; never write blind. Interactive runtimes ignore the block.
- **README "Running in OpenClaw / ZeroClaw"** — stand up the calendar MCP server(s)
  + credentials, run a one-time round-trip semantics validation (all-day exclusive
  end + cross-zone offset), then opt into auto_approve with tight guardrails.

## Release mechanism (how to cut the next one)

Tag-driven, never hand-built:

```bash
git tag -a vX.Y.Z -m "vX.Y.Z — summary"   # from main, after release PR merged
git push origin vX.Y.Z                     # the push fires the workflow
gh run list --limit 3                       # confirm success
gh release view vX.Y.Z --json assets        # confirm zip attached
```

Tag must be semver `vX.Y.Z` (the `v*` filter + asset filename depend on it). Fix
forward with a new tag; never rewrite a published one. Full process is in CLAUDE.md
("Releases & packaging").

## Verified

- CI-built v0.1.0 asset downloaded and audited: 16 files, no dev/git metadata, no
  `config.json`, no `docs/`. Release live at
  https://github.com/GruntworkAI/gruntwork-travel-skills/releases/tag/v0.1.0
- `main` history: `ab28ced` import → `ca42514` session note → `26193b3` feat (#1).

## Remaining follow-ups (Part 2)

- **Smoke-test against a real Google Calendar MCP server** to validate the
  round-trip semantics step (all-day exclusive end + cross-zone offset) before
  anyone relies on unattended `auto_approve` mode. Not yet done.
- Pre-existing README "Design notes" still says shared code is deferred "until a
  *second* skill" — slightly stale now that there are two (defer is really to the
  third). Minor; left as-is.
