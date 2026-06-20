---
name: lodging-to-calendar
description: >-
  Turn where-you're-staying into calendar events. For a hotel or Airbnb (with
  check-in semantics): an all-day span across the stay plus a timed check-in and
  check-out. For a personal stay (parents', a friend's place): just the all-day
  span. Use whenever the user shares a lodging confirmation, pastes reservation
  details, or simply describes where they're staying ("I'm at my parents' in
  Columbus Jul 2-5", "Airbnb in Austin Mar 3-6"). Lodging only: it does NOT add
  ground transport (flights-to-calendar owns that). Part of the
  gruntwork-travel-skills family.
---

# Lodging to Calendar (v0.2)

Convert a stay into calendar events on the user's dedicated travel calendar.
"Lodging" is wherever you're staying: a hotel, an Airbnb, a friend's or family's
place. Two modes:

- **With check-in semantics** (hotel, Airbnb) -> three events: an all-day span
  across the stay, a timed **check-in**, and a timed **check-out**.
- **Personal stay** (parents', a friend's) -> one event: just the all-day span.
  A made-up check-in time for your parents' house is noise, so omit the timed
  events.

The all-day span is the point: a "where am I this week" bar you can read at a
glance in month view.

Calendar-only; writes through the user's Google / Outlook connectors. The helper
`scripts/build_lodging_events.py` builds the event list (it never touches a
calendar). Where code execution isn't available, follow the same rules inline.

## Lodging only — no ground transport

This skill does **not** create "travel to the place" events. In this family,
`flights-to-calendar` owns all airport and ground movement, including the ride to
where you're staying. Adding it here would duplicate. Keep lodging to the stay
events.

## The all-day span

- **Title is city first:** `{City} — {detail}` (e.g. `Columbus — Homewood
  Suites`, `Austin — Airbnb`, `Columbus — Parents'`). City leads so the "where"
  survives month-view truncation; the detail is whatever you call the place.
- **End date is exclusive.** The bar should cover check-in day through check-out
  day inclusive, and all-day events use an exclusive end, so the end is
  **check-out date + 1** (a Jul 2-5 stay is start Jul 2, end Jul 6). Using the
  check-out date as the end hides check-out day. Create it with the all-day flag
  set, both ends at midnight. (Verified: the tool stores a date-type all-day
  event and treats the end as exclusive.)

## Workflow: configure -> parse -> propose -> write

### 0a. First run

Same family config as the other skills (repo-root `config.json`, gitignored). If
missing / `REPLACE_ME` / no calendars, run the shared first-run interview to fill
the `shared` section. Lodging adds a `lodging` section with `default_checkin_time`
and `default_checkout_time` (used only for hotel/Airbnb stays).

### 0. Load config and resolve targets (a hard gate)

Read the repo-root `config.json`; this skill uses `shared` merged with `lodging`.
(`build_lodging_events.py` does the merge and accepts a legacy flat profile.)

- **The calendar must already exist; this skill never creates one.** If it isn't
  found, stop and tell the user.
- **Confirm** the resolved calendar/targets before writing.
- **Resolve connectors before writing**; never half-write across targets.

### 1. Parse

Two input styles:
- **A confirmation** (hotel/Airbnb): extract name, city, check-in/out dates and
  times, confirmation number, loyalty, address, and the IANA timezone (derive
  from the city if unstated; show the derivation in the proposal). This is a
  `"timed": true` stay.
- **A described personal stay** ("my parents' in Columbus, Jul 2-5"): there's no
  confirmation and no check-in time. Get the **city and the dates** (the only
  required fields) and a label for the place (e.g. "Parents'"). Ask for an
  address or other details if useful, but treat them as optional. This is a
  `"timed": false` stay -> all-day span only.

Decide `timed` from the nature of the stay: hotels and Airbnbs have check-in
times (timed = true); a personal residence does not (timed = false). When unsure,
ask.

### 2. Build the event set

If code execution is available, write the parsed reservation to JSON (shape at
the top of `scripts/build_lodging_events.py`), run it, use the output (`write`
blocks, `needs_input`, `expected_count`, `markers`).

```
python3 scripts/build_lodging_events.py --input stay.json
```

If not, build by hand:
- **Stay (all-day, always):** title `{City} — {detail}`; start = check-in date;
  end = check-out date **+ 1** (all-day flag, midnight ends); hotel/place zone.
  Send both as **full ISO timestamps at midnight** (`2026-06-22T00:00:00`) with the
  all-day flag set — **not** a bare `YYYY-MM-DD` date. Some calendar connectors
  (e.g. the hosted Google Calendar tool) reject a date-only value with
  "start_time must be an ISO 8601 timestamp"; the midnight-timestamp form is stored
  as a proper date-type all-day event everywhere. (`build_lodging_events.py` already
  emits this form.)
- **Check-in / Check-out (timed, only when `timed`):** 30-minute blocks at the
  check-in/out times on those dates, in the stay's zone.

**Defaults (timed stays only):** check-in **16:00**, check-out **11:00** unless
stated; from the `lodging` config section; flagged in `needs_input` when used.

A stay sits in **one timezone** (no two-zone handling); naive local time plus the
zone renders correctly.

### 3. Propose

Show the events: the stay's date span (display the inclusive check-out date, not
the exclusive end), and for timed stays the check-in/out times with zone. Call
out any derived timezone and any defaulted time. For a personal stay, note it's
the single all-day bar by design. Confirm before writing.

**Unattended runtimes (OpenClaw / ZeroClaw).** With no human to confirm, this gate
is governed by `shared.auto_approve` in config. If it is absent or `enabled` is
false (the default, and always the case in Desktop / Claude Code), **do not
write** — surface the proposal and stop. Only when `enabled` is true may you
proceed without a human, and then only within its guardrails: write solely to the
listed `calendars`, refuse if the event set exceeds `max_events_per_run`, skip any
event in the past when `future_dated_only` is true, and when
`updates_via_marker_only` is true write only marker-matched updates (never create
new events). If a run would breach a guardrail, stop and report instead of writing.

### 4. Write, then reconcile (idempotently)

Write programmatically from each `write` block (the stay uses the all-day flag +
exclusive end; timed events use naive local + zone). Reuse the resolved calendar
ID. After writing, list the calendar over the stay window and confirm every
marker in `markers` is present once and the count matches `expected_count`.

**Idempotency.** Marker keyed on **city + check-in date** (you rarely start two
stays in one city the same day; falls back to the place name if no city):
`[ttc:lodging:{CITY}:{CHECKIN_DATE}]` plus `:stay` / `:in` / `:out`. Search the
marker before writing; update in place if found, else create. Never delete in a
normal run.

## Metadata convention (v0.2; may evolve)

Stay title is `{City} — {detail}` (scannable). Check-in/out titles carry the
place name. Location is the address (or city). Body carries the confirmation
number, loyalty, address, and the marker.

## Known limitations and planned work

- **Lodging only by design** (ground transport belongs to `flights-to-calendar`).
- **Timezone derivation** is from the confirmation plus model knowledge; the
  family's planned shared location->IANA data would remove the guess.
- **No cross-source collision scan yet** (shared family limitation). Keep the
  travel calendar skill-owned.
