# core/ — shared spine (placeholder, intentionally still empty)

This directory will hold code and conventions shared across the travel skills:
the calendar-write field mapping (connector-agnostic create/update with timezone
handling), the idempotency mechanism (marker + search→update→create→reconcile
loop, with per-skill key construction), the config/profile system and first-run
interview, and the cross-cutting doctrine (dedicated calendar, propose-before-
write, connector-resolution gate).

It is empty on purpose. With two skills now in the family
(`flights-to-calendar` and `lodging-to-calendar`), the seam is visible but not
yet worth hardening into shared modules — the rule of three says wait for a third
(`cars-to-calendar`) to confirm it before extracting.

## What the second skill revealed about the seam

Building `lodging-to-calendar` reused exactly the parts predicted to be shared
and none of the parts predicted to be skill-specific, which is the evidence the
decomposition is sound:

**Shared (strong candidates for `core/`):**
- The config/profile system and first-run interview (lodging just added its own
  `lodging` section to the family `config.json`).
- The idempotency mechanism — the marker format and the search→update→create→
  reconcile loop — with the *key* constructed per skill (flights: airline+flight#
  +date+origin; lodging: city+check-in date).
- The connector-resolution gate and propose-before-write doctrine.
- The calendar-write plumbing (create/update by ID, the all-day vs timed
  handling).

**Not shared (stays per skill):**
- The event model itself. Flights have journeys, layovers, and a different
  timezone at each end; lodging has an all-day span with an exclusive end date
  and (sometimes) two single-zone timed events. Almost no overlap.
- Ground transport lives entirely in flights; lodging deliberately omits it to
  avoid duplicate "travel to the place" events. That clean ownership boundary is
  itself a reason the skills compose rather than collide.

## Runtime note

Literal shared code (importing from `core/`) works where there's a filesystem and
a stable path (Claude Code, OpenClaw / ZeroClaw). In self-contained runtimes
(e.g. Claude Desktop) the conventions are the floor — documented in each
`SKILL.md` so every skill still stands alone — and any shared script is an
accelerator, not a hard dependency. The family-level `config.json` is already
shared today because it's about the user's setup, not code structure.
