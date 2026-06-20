# lodging-to-calendar

Turn wherever you're staying into calendar events — a hotel, an Airbnb, a
friend's or family's place. The centerpiece is an all-day "where am I this week"
bar; hotels and Airbnbs also get timed check-in and check-out events.

Part of [`gruntwork-travel-skills`](../). **Shared setup (dedicated calendar,
connectors, install, config) lives in the [family README](../README.md).** This
file covers what's specific to lodging.

---

## What it produces

Two modes, by the nature of the stay:

- **Hotel / Airbnb** (has check-in semantics) → **three** events: an all-day stay
  span, a timed **check-in** (default 4 PM), and a timed **check-out** (default
  11 AM).
- **Personal stay** (parents', a friend's place) → **one** event: just the
  all-day span. No invented check-in times.

The all-day bar's title leads with the **city** — `Columbus — Homewood Suites`,
`Austin — Airbnb`, `Columbus — Parents'` — so the "where" is readable in month
view even when the name truncates.

## Lodging only (by design)

No ground-transport events. In this family,
[`flights-to-calendar`](../flights-to-calendar) owns the ride to where you're
staying, so lodging stays lodging and the two compose without duplicating.

## Usage

From a confirmation:

> "Add my hotel: [Hilton confirmation]"

Or just describe it (no confirmation needed):

> "I'm staying at my parents' in Columbus, Jul 2–5"

For a described personal stay the skill asks only for the essentials (city and
dates; a label like "Parents'"), treats address and other details as optional,
and produces the single all-day bar.

## Notes

- **All-day end date is exclusive**, so a Jul 2–5 stay stores with end Jul 6 to
  cover check-out day. The skill handles this.
- **Defaults** (timed stays only): 4 PM check-in / 11 AM check-out unless the
  confirmation says otherwise; set in the `lodging` config section and flagged in
  the proposal when used.

## Lodging-specific config (`lodging` section)

| Field | Meaning |
|---|---|
| `default_checkin_time` | check-in time when a hotel/Airbnb omits it (e.g. `16:00`) |
| `default_checkout_time` | check-out time when omitted (e.g. `11:00`) |

## Idempotency

Marker keyed on city + check-in date, e.g.
`[ttc:lodging:COLUMBUS:2026-07-02]`. Re-running the same stay updates in place;
the same city on different dates is a different stay.

## Scope and limitations

- **Lodging only** (ground transport is the flights skill's job).
- **Timezone** derived from the stay's city plus model knowledge.
- **No cross-source collision scan yet** (a shared family limitation).
