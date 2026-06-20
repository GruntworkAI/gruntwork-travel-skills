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

## Releases & packaging (how the Desktop zip ships)

The repo is the source of truth; the **product artifact** is a clean installer zip
attached to a GitHub Release. Two pieces:

- **`scripts/package.sh [version]`** — builds `dist/gruntwork-travel-skills-<version>.zip`
  containing *only* what an installer needs: `README.md`, `LICENSE`,
  `config.example.json`, `core/`, and the two skill dirs. It uses an **explicit
  allowlist** (not exclusions) so dev/git metadata can't leak. Excluded by design:
  `.git/`, `.github/`, `.claude/`, `CLAUDE.md`, `docs/`, `dist/`, and any stray
  `config.json` / `__pycache__` / `.DS_Store`. `dist/` is gitignored — built zips
  are never committed.
- **`.github/workflows/release.yml`** — triggers on a `v*` tag push, runs
  `package.sh "$GITHUB_REF_NAME"`, then `gh release create` with the zip attached
  and auto-generated notes (`permissions: contents: write`).

### Cutting a release (the tag mechanism)

A release is driven entirely by pushing an annotated tag — do **not** hand-build or
upload zips:

```bash
# from main, after the release commit is merged:
git tag -a vX.Y.Z -m "vX.Y.Z — <summary>"
git push origin vX.Y.Z          # this push is what fires the workflow
```

Then verify the run and asset:

```bash
gh run list --limit 3                    # confirm the Release run succeeded
gh release view vX.Y.Z --json assets     # confirm the zip is attached
```

Rules:
- **Tag from `main`** only, after the release PR is merged (the workflow checks out
  the tagged commit; the packaging script + skill content must already be on it).
- **Tag name must be `vX.Y.Z`** (semver, `v` prefix) — the `v*` filter and the asset
  filename both depend on it.
- If a release is wrong, fix forward with a new patch tag; don't rewrite a published
  tag.
- Before tagging, sanity-check locally with `scripts/package.sh vX.Y.Z` and inspect
  the printed file list — it should match the allowlist above and contain no
  personal data (synthetic examples only; see the personal-data lesson in the
  migration session note).
