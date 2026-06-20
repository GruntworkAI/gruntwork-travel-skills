# flights-to-calendar

Turn flight confirmations into a complete, door-to-door set of calendar events —
not just the flights, but the ground transport and airport time around them, each
anchored to the correct local timezone.

Part of [`gruntwork-travel-skills`](../). **Shared setup (dedicated calendar,
connectors, install, config) lives in the [family README](../README.md).** This
file covers what's specific to flights.

---

## What it produces

For a simple round trip you get the real shape of each travel day, not just two
flight blocks. Per journey (a round trip is two journeys, outbound and return):

- **Travel to the airport** (before the journey's first flight)
- **Airport time** (a buffer before departure)
- **The flight** — departure in the origin's zone, arrival in the destination's
- **Layover** blocks between connecting flights
- **Deplane / to curb** after landing
- **Travel from the airport** to where you're staying

Connections get a layover block (no extra ground transport); a multi-day stop
starts a new journey with its own door-to-door pair.

---

## Usage

Paste, forward, or describe a booked trip:

> "Add this to my calendar: [Delta confirmation]"

The skill parses it, asks about anything it can't infer (where you're staying, how
you get to/from the airport), shows a proposal table with every event's local time
and timezone, and writes on your confirmation. Ground transport defaults to Uber;
you can say a friend is picking you up, you're driving, etc., and titles adjust.

### Timezones

Receipts already state the correct local wall-clock time at each end. The skill
preserves those exactly and attaches the right IANA zone — it never converts
across zones. One constraint: a calendar event has a single display zone, so a
flight shows in its **departure** zone (correct instants and duration) with the
true local arrival written into the description.

### Idempotency

Every event carries a hidden marker, e.g. `[ttc:AA1:2026-07-04:JFK]`. The
marker includes the departure date, so the same flight number on a different date
is a different trip. Re-running an itinerary updates in place instead of
duplicating.

---

## Flight-specific config (`flights` section)

Beyond the shared `calendars` / `default_targets` / `home_label`:

| Field | Meaning |
|---|---|
| `home_airports` | airport codes that count as home; a trip ending here defaults its destination to home |
| `home_to_airport_ride_min` | default ride from home to the airport |
| `default_ride_min` | default ride for other legs |
| `deplane_to_curb_min` | minutes from landing to curb |
| `arrival_cushion_min` | how early to arrive before departure |
| `layover_max_min` / `layover_ambiguous_max_min` | layover-vs-journey-boundary thresholds |
| `ground_transport_mode` | default ground mode (e.g. `Uber`) |

Per-trip overrides (origin/destination labels, ride times, ground mode like
`pickup` / `dropoff` / `self-drive` with an optional person) are supplied at run
time, not stored in config.

---

## Flighty (optional, but a nice payoff)

Flighty has no public write API, but it reads your calendars, so writing clean
flight events to a calendar Flighty watches *is* the integration. The catch:
**Flighty reads Apple Calendar, not Google directly.** The chain:

```
skill -> Google "Travel" calendar -> Apple Calendar -> Flighty
```

The most isolated bridge (no full Google account on iOS) is a read-only
subscription:

1. Google Calendar settings → your travel calendar → **Integrate calendar** →
   copy the **Secret address in iCal format** (`.ics`). Treat it like a password.
2. iPhone **Calendar** app → **Calendars** → **Add Calendar** → **Add
   Subscription Calendar** → paste the `.ics` URL → **Find / Subscribe**.
3. In **Flighty**, enable calendar sync and grant **Full Access** (not "Add
   Only" — it must *read*). Confirm the calendar is in Flighty's scanned list.

Flight titles are shaped (`AA 1 · JFK→LAX`) so Flighty recognizes them; the
ground/airport/layover events don't look like flights, so they're ignored.
Subscribed calendars refresh on Apple's schedule (can be hours), which is fine
since trips are added well ahead.

---

## Scope and limitations

- **Air travel only** (hotels/cars are separate skills in this family).
- **Timezone derivation** is from the receipt plus model knowledge; a bundled
  airport→IANA table is planned for obscure airports.
- **No collision scan yet** — idempotency dedupes the skill's own re-runs, not a
  flight a different source (e.g. Gmail auto-add) already placed. Keeping the
  calendar skill-owned avoids this.

See the "Known limitations and planned work" section of `SKILL.md` for the full
list and intended designs.
