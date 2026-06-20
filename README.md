# gruntwork-travel-skills

[![Latest release](https://img.shields.io/github/v/release/GruntworkAI/gruntwork-travel-skills?label=latest&sort=semver)](https://github.com/GruntworkAI/gruntwork-travel-skills/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)

A family of Claude skills that turn travel confirmations into clean, accurate
calendar events. Each skill handles one domain (flights today; hotels and ground
transport planned) and shares a single setup: one dedicated calendar, one config,
one first-run interview.

Published by **GruntworkAI**.

> **Heads up — these skills write to your calendar.** They create and update
> events through your connected Google/Outlook account. By design a skill only
> writes after you review and confirm a proposal, and only to the dedicated
> calendar you name in config (it never creates a calendar and never touches your
> other calendars). Install pointing at a **dedicated, empty calendar** you made
> for this, review proposals before approving, and note that the same write
> access applies in an unattended runtime (e.g. an always-on agent). Keep the
> travel calendar skill-owned and the blast radius stays bound to it.

---

## Skills in this family

| Skill | Status | What it does |
|---|---|---|
| [`flights-to-calendar`](./flights-to-calendar) | available | Flight confirmations → door-to-door events (flights, layovers, airport time, ground transport), each in the correct local timezone |
| [`lodging-to-calendar`](./lodging-to-calendar) | available | Hotels, Airbnbs, or a friend/family stay → all-day "where am I" span (+ timed check-in/out for hotels), in local time |
| `cars-to-calendar` | planned | Rental car pickups / returns |

Each skill has its own `SKILL.md` and `README.md` with domain-specific detail.
This file covers the setup they share.

---

## Shared setup (do this once for the whole family)

### 1. Create a dedicated travel calendar (you, not the skill)

Make a new, empty calendar in Google (or Outlook) just for this — e.g. `Travel`.
The skills **never create a calendar**; they write only to the one you name in
config, and stop with an error if it doesn't exist. A dedicated calendar bounds
blast radius and keeps flight-tracker ingestion clean (see the flights skill's
README for the Flighty setup).

### 2. Connect the calendar connector

Authorize Google Calendar (and Microsoft 365, if using work) in Claude. On Claude
Desktop this is the connectors settings; Claude Code inherits connectors
authorized on the same Claude account. The hosted Google/Microsoft connectors
must be authorized from Claude.ai / Desktop.

### 3. Install

**Claude Desktop (drop-in):** download the latest
`gruntwork-travel-skills-vX.Y.Z.zip` from the
[Releases page](https://github.com/GruntworkAI/gruntwork-travel-skills/releases) —
it contains just the skills, setup, and config template (no git or dev metadata) —
and unzip it where Desktop loads skills.

**Claude Code / OpenClaw / ZeroClaw (filesystem runtimes):** clone the repo where
your runtime loads skills. The skills live in sibling directories
(`flights-to-calendar/`, etc.); the shared `config.json` lives at the repo root.
See [Running in OpenClaw / ZeroClaw](#running-in-openclaw--zeroclaw) below for the
self-hosted specifics.

### 4. Configure (once, shared by every skill)

Either let a skill set it up — on first use it detects there's no `config.json`,
runs a short interview, and writes it — or do it by hand: copy
`config.example.json` to `config.json` and fill in the `REPLACE_ME` values.

The config is a profile with a `shared` section (calendars, targets, home label —
used by every skill) plus one section per skill (e.g. `flights` for the
flight-specific knobs). `config.json` is gitignored, so your personal values are
never published.

```jsonc
{
  "active_profile": "default",
  "profiles": {
    "default": {
      "shared": {
        "calendars": { "personal": { "connector": "google", "calendar_name": "Travel" } },
        "default_targets": ["personal"],
        "home_label": "Home"
      },
      "flights": { "home_airports": ["LAX"], "arrival_cushion_min": 90, "...": "..." }
    }
  }
}
```

---

## Requirements

- A Claude runtime that loads skills (OpenClaw / ZeroClaw, Claude Code, Claude
  Desktop).
- A Google Calendar and/or Microsoft 365 connector.
- A paid Claude plan (hosted connectors require one).
- Code execution is optional (accelerates the deterministic helpers where
  available; skills follow the same rules inline where it isn't).

---

## Running in OpenClaw / ZeroClaw

These skills are runtime-agnostic by design — each `SKILL.md` discovers the
calendar tools at runtime and never hardcodes tool names — so they run in a
self-hosted runtime as-is. What differs from Claude Desktop is the *environment*
around them, not the skills:

**1. You provide the calendar tools.** Desktop's hosted Google / Microsoft 365
connectors don't exist in a self-hosted runtime. Stand up a Google Calendar (and,
if you use `work` targets, an Outlook / M365) **MCP server** in the runtime and
authorize it with your own OAuth credentials or service account. The skills will
discover and use whatever create/update/search-event tools the runtime exposes;
your job is to make those tools present. The config's logical `connector` label
(`"google"` / `"outlook"`) maps to whichever discovered tool serves that calendar
— the names need not match literally.

**2. Validate the calendar semantics once.** The skills depend on two behaviors
that MCP servers expose differently: all-day events stored as a *date* type with
an exclusive end date (lodging), and timed flight events that carry an explicit
UTC offset so a cross-timezone flight renders correctly. Before trusting an
unattended agent, do one round-trip test against your server — create a lodging
all-day span and a cross-zone flight, then read them back and confirm the dates
and local times render as written. If your server normalizes times to one zone or
drops the all-day date type, fix that at the server before going live.

**3. Decide the unattended-write policy.** Every skill *proposes before it writes*
and waits for a human to confirm. An always-on agent has no human in the loop, so
that gate is governed by `shared.auto_approve` in `config.json`:

```jsonc
"auto_approve": {
  "enabled": false,             // default: still require confirmation; nothing auto-writes
  "calendars": ["personal"],    // auto-writes allowed only to these logical targets
  "max_events_per_run": 20,     // refuse a run that would write more (runaway-parse guard)
  "future_dated_only": true,    // never auto-touch past-dated events
  "updates_via_marker_only": false  // true = only update marker-matched events, never create
}
```

With `enabled: false` (the default, and the only behavior in Desktop / Claude
Code), an unattended run **surfaces the proposal and stops** rather than writing
blind. Turn it on only once you've validated step 2, and keep the guardrails tight
— the dedicated travel calendar is what bounds the blast radius. A run that would
breach a guardrail stops and reports instead of writing.

---

## Repo layout

```
gruntwork-travel-skills/
  README.md            <- you are here (shared setup)
  LICENSE              <- MIT
  .gitignore           <- ignores config.json
  config.example.json  <- template (committed)
  config.json          <- your values (gitignored; you create)
  core/                <- shared spine (placeholder; see core/README.md)
  flights-to-calendar/
    SKILL.md
    README.md
    scripts/
  lodging-to-calendar/
    SKILL.md
    README.md
    scripts/
  scripts/package.sh   <- repo tooling: builds the Desktop installer zip (not shipped)
  .github/workflows/   <- repo tooling: cuts a Release on a vX.Y.Z tag (not shipped)
```

The Desktop installer zip (from Releases) contains only the skills, `README.md`,
`LICENSE`, `config.example.json`, and `core/` — the repo tooling above and the
`.claude/` working directory are stripped out.

---

## Design notes

- **Shared config, not yet shared code.** The family-level config is shared from
  day one because the user's setup is obviously common. Shared executable code
  (`core/`) is deliberately deferred until a second skill defines the seam — see
  `core/README.md`.
- **Propose before write.** Every skill parses, proposes, and writes only on
  confirmation. This matters most in unattended runtimes.
- **Idempotent.** Events carry a hidden marker so re-running an itinerary updates
  in place instead of duplicating.

---

## License

MIT — see [`LICENSE`](./LICENSE). © 2026 GruntworkAI.
