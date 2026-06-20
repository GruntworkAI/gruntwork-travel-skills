---
name: flights-to-calendar
description: >-
  Turn flight itineraries into a complete set of calendar events (flights,
  layovers, and door-to-door ground transport) on the user's personal and/or
  work calendars, each anchored to the correct local timezone. Use this whenever
  the user shares a flight confirmation email, pastes booking details, forwards
  an airline itinerary, or describes a trip they've booked and wants it on their
  calendar. Trigger even when the user just says things like "put this trip on my
  calendar," "add my flights," "I'm flying to X next month," or forwards a
  confirmation without explicit instructions. Air travel only in this version
  (no hotels, trains, or rental cars yet).
---

# Flights to Calendar (v0.7)

Convert a flight itinerary into a reviewed set of calendar events, then write
them to the user's calendars. The goal is a calendar that reflects the real
door-to-door day: not just the flights, but the ground transport and airport
time around them, each anchored to the correct local timezone.

This skill is calendar-only. The writes happen through the user's connected
calendar tools (Google Calendar for personal, Microsoft 365 / Outlook for work),
which are MCP connectors Claude invokes directly. It runs in OpenClaw / ZeroClaw,
Claude Code, and Claude Desktop.

There is an optional helper script (`scripts/build_events.py`) that does the
slip-prone deterministic work (offset arithmetic and journey segmentation). Use
it when code execution is available; the instructions in this file are a
complete fallback when it isn't. The script never touches a calendar.

## The non-negotiable: never do timezone math

Flight receipts already state the correct **local wall-clock time** at each
endpoint (a flight departs 9:00 AM in its origin city and arrives 5:00 PM in its
destination city; the duration is neither). Preserve those wall-clock times
exactly and attach the correct IANA timezone to each end of each event. Never
convert times across zones, never "normalize" to one zone, never compute an
arrival time yourself. If the receipt says arrives 5:00 PM, the event ends at
5:00 PM in the destination's zone.

- Where the receipt names the zone, use it.
- Where it doesn't, derive the IANA zone from the airport code (e.g. `SFO` ->
  `America/Los_Angeles`, `LHR` -> `Europe/London`).
- **Always show the zone stamped on each event in the proposal** so a wrong guess
  on an obscure airport is caught before anything is written. This is the most
  common failure mode; surfacing the zone is how it gets caught. (A bundled
  airport->IANA table is planned for a later version to remove the guess entirely.)

### Flights cross two zones; a calendar event displays only one

A flight departs in one zone and arrives in another, but a calendar event (and
the create-event tool) has a single display zone. You cannot show departure-local
and arrival-local on the same event. The rule, which the script applies for you:

- Anchor each flight to its **departure** zone for display.
- Provide both endpoints as timestamps carrying their **correct UTC offset**, so
  the stored instant and the duration are exact regardless of the display zone.
  (Verified behavior: the calendar keeps the instant and renders both ends in the
  one display zone. A naive local time without an offset on the arrival end would
  be misread as departure-zone local and corrupt the event. Always send offsets
  on flight endpoints.)
- Write the **true local departure and arrival** into the description, e.g.
  `Departs 8:00 AM JFK / Arrives 11:30 AM LAX (local)`, so the destination-local
  time is never lost even though the event renders in the departure zone.

Single-zone events (every ground and airport block) have no such issue: send a
naive local time plus that zone and they render exactly. The `write` block from
the script already encodes all of this per event; use it verbatim.

## Workflow: configure -> parse -> propose -> write

Follow this order every time. Do not write to any calendar before the user
confirms the proposal. This matters most when the skill runs unattended in
OpenClaw / ZeroClaw.

### 0a. First run: set up config if it's missing or unconfigured

Before anything else, check whether this install is configured. Treat the profile
as **unconfigured** if any of these hold: `config.json` does not exist; a
`calendar_name` still contains `REPLACE_ME`; or `home_airports` is empty. (A
fresh clone ships only `config.example.json`; `config.json` is gitignored.)

If unconfigured, run a short setup interview before parsing any itinerary. The
config is shared across the whole skill family: it lives at the **repo root**
(`gruntwork-travel-skills/config.json`), with a `shared` section (calendars,
targets, home) used by every skill plus a per-skill `flights` section. The
interview fills both. Ask, conversationally and ideally one thing at a time:

1. **Home airport(s).** "Which airport(s) do you fly home to?" Accept one (e.g.
   `LAX`) or several for a metro (e.g. `LAX BUR SNA LGB`). These let a trip that
   *ends* at one of them default its final destination to home.
2. **Home label.** What to call home in event titles (default `Home`).
3. **Travel calendar.** The name of the dedicated calendar to write to, and
   whether it's Google or Outlook. **State plainly that the user must create this
   calendar themselves first; the skill never creates one.** Explain why it's
   dedicated: it bounds blast radius and keeps Flighty's scan clean (see README).
4. **Targets.** Personal only, or also a work calendar? If work, get its name and
   connector. Set `default_targets` accordingly.
5. **Defaults.** Offer the standard set (90-min airport cushion, 60-min ride,
   30-min deplane, Uber) and only ask for changes if they want them.

Then **write `config.json`** from these answers (start from
`config.example.json`'s shape). Put calendars, targets, and home label in
`shared` (every skill uses them); put home airports and the ride/cushion knobs in
the `flights` section. Note the runtime limit: only filesystem runtimes
(OpenClaw / ZeroClaw, Claude Code) can persist the file. In Claude Desktop, show
the user the finished JSON and ask them to save it as `config.json` once;
otherwise setup repeats next session. After writing, continue to step 0.

### 0. Load config and resolve targets (a hard gate)

Read `config.json` (a keyed map of profiles; use `active_profile` unless told
otherwise). It lives at the repo root and is shared by the skill family: each
profile has a `shared` section (calendar names, default targets, home label) plus
a per-skill `flights` section (home airports, the ground/cushion defaults). This
skill uses `shared` merged with `flights`. (`build_events.py` does this merge for
you and also accepts a legacy flat profile.)

- **Calendars must already exist. This skill never creates a calendar.** Using a
  dedicated personal `Travel` calendar is deliberate: it bounds blast radius and
  keeps Flighty's calendar scan (see below) looking at only the events this skill
  writes. If the configured calendar name isn't found on the account, stop and
  tell the user to create it (don't fall back to a primary calendar silently).
- If the config has calendars set, **confirm them** with the user before writing
  ("personal -> Google 'Travel', work -> Outlook 'Calendar', both targets").
  If it doesn't, **ask**.
- **Resolve connectors before writing anything.** If the user wants both targets
  but only one connector (Google or Microsoft 365) is live in this runtime, say
  so and let the user choose to proceed with the one or stop. Never write the
  events to one calendar and discover the other is unavailable mid-run; that
  leaves a half-booked trip.

### 1. Parse

Accept any of three input shapes: a forwarded or pasted **confirmation email**
(the common case), **pasted fragments**, or a **prose description** ("I'm flying
LAX to JFK on the 4th, back on the 8th").

Extract, per flight segment: airline + flight number, origin and destination
airport codes, departure and arrival date/time with their local zones,
confirmation/record locator (PNR), and any loyalty number. If something required
is missing (a return time, which calendar), ask rather than guess.

### 2. Build the event set

**If code execution is available:** write the parsed segments to a JSON file in
the shape documented at the top of `scripts/build_events.py`, run the script,
and use its output. The script segments journeys, applies the offsets, handles
day-boundary crossings, builds the markers, and returns the full event list plus
`needs_input` (unknown hotel/origin locations) and `warnings` (ambiguous layover
calls). Surface those to the user in the proposal. Each event also carries a
`write` block (API-ready `summary`, `location`, `description`, `startTime`,
`endTime`, `timeZone`) that already encodes the flight-zone handling above, plus
top-level `expected_count` and `markers` for the reconciliation step.

```
python3 scripts/build_events.py --input itinerary.json
```

**If code execution is not available**, build the same set by hand using the
rules below. Either way, the event model is identical.

A **journey** is a continuous travel sequence from one origin to one destination.
A round trip is two journeys (outbound, return); a multi-city trip is several.
Within a journey, consecutive flights are **connections**; the break between
journeys is a **journey boundary** (you leave the airport). Distinguish them:
- **Connection (layover):** the previous flight's destination equals the next
  flight's origin, the gap is short (default: <= 4 hours), and it's not
  overnight. Gets a layover block, no ground transport.
- **Journey boundary:** overnight, a long gap, a different airport, or separate
  bookings. Starts a new journey.
- **Ambiguous** (gap ~4-6 hours): treat as a connection but flag it for the user
  to reclassify.

For each **journey**, emit events in this order:

1. **Travel to airport** -- only before the journey's **first** flight. Ends at
   (first departure - 90 min); starts at (that end - ride duration); origin
   airport's zone. Title `Travel to {AIRPORT} (Uber) from {ORIGIN}`. Origin is
   **home** for the outbound journey (config `home_label`, ride
   `home_to_airport_ride_min`); for a later journey, **prompt** for the origin
   (e.g. hotel) and default the ride to `default_ride_min` (60).
2. **Time at airport** -- only before the journey's first flight. `[first
   departure - 90 min, first departure]`, origin airport's zone.
3. **Flight** -- one per segment. Start = departure local time in origin zone;
   end = arrival local time in destination zone (two zones on one event is
   correct). Title `{AIRLINE} {FLIGHT#} - {ORIGIN}->{DEST}` (e.g. `UA 123 ·
   SFO->EWR`). Location = origin airport code. Body = metadata (below).
4. **Layover at {AIRPORT}** -- between consecutive flights within the journey.
   `[arrival, next departure]`, that airport's zone.
5. **Deplane / to curb** -- only after the journey's **last** flight. `[arrival,
   arrival + 30 min]`, destination airport's zone.
6. **Travel from airport** -- only after the journey's last flight. Starts at
   (arrival + 30 min); ends at (start + ride duration, default 60). Destination
   defaults to **home only when the trip ends at one of the user's home airports**
   (config `home_airports`, e.g. `["LAX"]`). This is keyed on arriving home, not
   on returning to where the trip started, so it correctly handles a trip that
   begins away from home and ends home (e.g. `MIA -> ... -> LAX` after a stay at
   family) as well as an ordinary round trip. Any trip whose final arrival airport
   is **not** a home airport (a one-way to a destination, an open-jaw, or a
   side-trip that returns to a non-home airport you flew out of) does **not**
   assume home; the destination is flagged in `needs_input` and must be confirmed
   (hotel, family, etc.). Falls back to the origin-airport check if `home_airports`
   is unset.

**Ground transport mode.** Confirmations never state how you reach or leave the
airport, so it's always user-supplied. Default is Uber. Per-leg overrides set the
mode and (optionally) who: `to_mode`/`to_by` for the departure-side leg,
`from_mode`/`from_by` for the arrival-side leg. Modes: `uber` (default), `pickup`
(someone collects you on arrival), `dropoff` (someone takes you to departure),
`self-drive`. The script renders the title accordingly (e.g. a parent pickup
becomes `Pickup from MIA (parents) -> Parents' house` rather than an Uber title).

So a simple round trip with no connections yields five events per direction (ten
total). A connection adds one flight + one layover inside that journey and does
**not** add another ground-transport pair.

### 3. Propose

Present the full set as a compact table before writing. For each event show
title, start (local time **+ zone**), end (local time **+ zone**), target
calendar(s), and body. Call out: the journey segmentation and any ambiguous
boundaries, any timezone you derived rather than read, any unknown
hotel/origin location (the script's `needs_input`), and the ground assumptions
(Uber, ride durations, home/hotel origin). Ask the user to confirm or correct,
then proceed.

**Unattended runtimes (OpenClaw / ZeroClaw).** When there is no human to confirm,
this gate is governed by `shared.auto_approve` in config. If it is absent or
`enabled` is false (the default, and always the case in Desktop / Claude Code),
**do not write** — surface the proposal and stop. Only when `enabled` is true may
you proceed without a human, and then only within its guardrails: write solely to
the listed `calendars`, refuse if the set exceeds `max_events_per_run`, skip any
event in the past when `future_dated_only` is true, and when
`updates_via_marker_only` is true write only marker-matched updates (never create
new events). If a run would breach a guardrail, stop and report instead of writing.

### 4. Write, then reconcile (idempotently)

Write programmatically as a loop over the event list, not by hand-issuing calls.
Hand-transcribing N create calls is how an event silently goes missing or a
calendar ID gets fat-fingered. For each event, pass the fields from its `write`
block straight into the connected calendar tool's create call (`startTime`,
`endTime`, `timeZone`, `summary`, `location`, `description`). Use the exact
calendar ID resolved in step 0; do not retype it per call. Discover the connected
calendar tools at runtime; don't assume specific tool names.

**Reconcile after writing (required, not optional).** When the loop finishes,
list the target calendar over the window [earliest event start, latest event end]
and confirm every marker in `markers` is present exactly once, and that the count
matches `expected_count`. Report any missing (re-create them) or duplicated
(investigate) before telling the user it's done. In an unattended runtime this
step is the only thing standing between a dropped call and a quietly half-booked
trip.

**Idempotency.** Re-running on the same itinerary must update, not duplicate.
Every event carries a stable marker in its body:
- Flight: `[ttc:{AIRLINE}{FLIGHT#}:{DEPART_DATE_LOCAL}:{ORIGIN}]` (e.g.
  `[ttc:UA123:2026-07-04:SFO]`).
- Derived events reuse the parent flight's marker plus a suffix: `:to`, `:apt`,
  `:layover`, `:curb`, `:from`.

Before creating an event, search the target calendar around the flight's date
for that exact marker. If found, **update in place** (this is how a later re-run
with a now-known hotel corrects the placeholder ground legs); if not, **create**.
Do this per target calendar. Never delete events in a normal run.

## Metadata convention (v0.7; may evolve)

Title carries flight number and route; location carries the airport code; body
carries the PNR, the loyalty program/number, and the idempotency marker. Flight
bodies additionally lead with a one-line true-local summary (`Departs ... /
Arrives ... (local)`), because the event itself can only render one zone (see the
flight timezone rule above). This local line is flights-only; single-zone events
don't need it. Keep
the body lean.

## Flighty (and similar trackers): nothing to build

Flighty has no write API. Its relevant ingestion path is **calendar sync**: it
scans the user's calendars on-device for events that look like flights and adds
them automatically. Writing a clean flight event to a calendar Flighty watches is
the integration. Two consequences, both handled above:
- Keep flight titles in the `{AIRLINE} {FLIGHT#} - {ORIGIN}->{DEST}` shape so
  Flighty's parser recognizes them. The layover and ground-transport titles
  deliberately don't look like flights, so they won't be falsely ingested.
- Flighty only scans Apple Calendar and calendars visible in it. In practice this
  favors the **personal** calendar (a Google `Travel` calendar subscribed into
  Apple Calendar on the Flighty device). A work Outlook calendar usually isn't
  surfaced in personal Apple Calendar, so **don't imply Flighty picks up the work
  events** -- they're written for scheduling, not for Flighty. This is one-time
  user setup, not something the skill does.

Do not email-forward to Flighty or call any Flighty endpoint.

## Defaults (in config.json; state them when they apply; let the user override)

Arrive 90 min before departure (cushion baked in, no extra pad). Ground mode:
Uber unless specified. Ride duration: 60 min default; outbound origin is home;
later journey origins (hotel) are prompted. Deplane-to-curb: 30 min. Layover vs.
journey-boundary cutoff: ~4 hours / overnight (ask when borderline). Home
airports (`home_airports`, e.g. `["LAX"]`): trips ending at one of these default
their final destination to Home; add metro siblings (BUR/SNA/LGB) if relevant.
Targets: both personal and work. Scope: air travel only.

`config.json` supports multiple named profiles under `profiles` (selected by
`active_profile`); ship with one. Editing defaults or calendar names means
editing that file.

## Known limitations and planned work (documented, not yet implemented)

These are deliberate v0.3 scope boundaries, captured so they aren't rediscovered
later.

1. **Airport -> IANA timezone table.** v0.3 derives zones from the receipt plus
   model knowledge and surfaces them in the proposal for the user to catch a bad
   guess. A future version should bundle a real airport->IANA table (e.g. from
   OpenFlights) to remove the guess for obscure airports.

2. **Collision scan for foreign events (idempotency against non-skill writes).**
   Marker idempotency only dedupes the skill's own prior runs. A Gmail-added or
   hand-added flight event has no marker, so the current skill would create a
   parallel event next to it. The dedicated, skill-owned `Travel` calendar
   is the first-line defense (Gmail auto-adds to the *primary* calendar, not a
   secondary one), and Flighty dedupes by flight number/date. The documented fix:
   before writing, scan the trip window and classify each existing event as
   *ours* (marker match -> update), *collision* (`eventType == "fromGmail"`, or a
   flight-number-plus-date title match, with no marker), or *unrelated* (ignore).
   Collisions are **surfaced in the proposal**, never auto-merged, since editing
   or deleting a user/Gmail event is mutating data the skill didn't create. Per
   collision, offer: skip the flight (add only ground events around it), adopt it
   (annotate the existing event with the skill's marker), or create a parallel
   event. Caveat: the `fromGmail` signal is reliable; the title fallback is fuzzy
   (misses untitled-by-flight events, can false-positive on a same-day number
   match), which is itself a reason to surface rather than auto-resolve.

3. **Operational invariant.** None of the above substitutes for keeping
   `Travel` skill-owned. Marker-dedup handles re-runs, the dedicated
   calendar handles Gmail, the collision scan is the catch-all; the cheapest
   safety is simply not letting other writers into the skill's calendar.
