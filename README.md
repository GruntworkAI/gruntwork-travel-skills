# gruntwork-travel-skills

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

Place this repo where your runtime loads skills. The skills live in sibling
directories (`flights-to-calendar/`, etc.); the shared `config.json` lives at the
repo root.

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
```

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
