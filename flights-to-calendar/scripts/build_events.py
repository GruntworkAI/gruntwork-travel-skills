#!/usr/bin/env python3
"""
build_events.py — deterministic event construction for the travel-to-calendar skill.

Takes a parsed flight itinerary plus a config profile and emits the full set of
calendar events (flights, layovers, and door-to-door ground transport), each
with correct local datetimes and IANA timezones. It does the slip-prone parts a
model fumbles inline: the offset arithmetic (including day-boundary crossings)
and the layover-vs-journey-boundary segmentation.

It does NOT touch any calendar. The model takes this JSON, shows the proposal,
and makes the calendar MCP calls itself.

Usage:
    python3 build_events.py --input itinerary.json [--config config.json] [--profile default]
    cat itinerary.json | python3 build_events.py

Input JSON shape:
{
  "config_profile": "default",                 # optional; overrides config's active_profile
  "segments": [
    {
      "airline": "UA", "flight_number": "123",
      "origin": "SFO", "origin_tz": "America/Los_Angeles",
      "dest": "EWR",  "dest_tz": "America/New_York",
      "depart_local": "2026-07-04T09:00:00",   # naive local wall-clock at origin
      "arrive_local": "2026-07-04T17:25:00",   # naive local wall-clock at destination
      "pnr": "ABC123",                          # optional
      "loyalty": "UA MileagePlus 900..."        # optional
    }
  ],
  "journey_overrides": {                        # optional, keyed by 0-based journey index
    "1": { "origin_label": "Hotel Indigo downtown", "to_airport_ride_min": 75,
           "dest_label": "Home", "from_airport_ride_min": 50,
           "to_mode": "dropoff", "to_by": "a friend",  # mode in {uber,pickup,dropoff,self-drive}
           "from_mode": "pickup", "from_by": "family" }  # `by` is optional
  }
}

Output JSON: { "events": [...], "journeys": [...summary...], "needs_input": [...], "warnings": [...] }
Each event: title, location, body, start{dateTime,timeZone}, end{dateTime,timeZone}, marker, targets, kind.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# ---------- helpers ----------

def parse_local(s, tzname):
    """Return a tz-aware datetime from a naive local ISO string + IANA zone name."""
    try:
        tz = ZoneInfo(tzname)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"Unknown timezone '{tzname}'. Use a valid IANA name (e.g. 'America/New_York').")
    naive = datetime.fromisoformat(s)
    if naive.tzinfo is not None:
        # If an offset was supplied, drop it and re-anchor to the named zone to
        # avoid double-accounting; the named zone is the source of truth.
        naive = naive.replace(tzinfo=None)
    return naive.replace(tzinfo=tz)

def fmt(dt):
    """Emit {dateTime, timeZone} as local naive ISO + IANA name (what gCal/Outlook want)."""
    return {
        "dateTime": dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "timeZone": str(dt.tzinfo),
    }

def local_with_offset(dtstr, tzname):
    """Naive local ISO + IANA zone -> ISO string carrying the correct UTC offset
    (DST-aware). Used for flight endpoints so the stored instant/duration is exact
    even though the event displays in a single zone."""
    return datetime.fromisoformat(dtstr).replace(tzinfo=ZoneInfo(tzname)).isoformat()

def pretty_time(dtstr):
    return datetime.fromisoformat(dtstr).strftime("%-I:%M %p")

def attach_write_fields(events):
    """Add an API-ready `write` block to each event.

    Single-zone events (ground/airport) write as naive local + their own zone,
    which displays exactly in that zone. Flights cross two zones but a calendar
    event has only one display zone, so the flight is anchored to the DEPARTURE
    zone with both endpoints carrying correct UTC offsets (instant + duration
    stay exact), and the true local departure/arrival is written into the
    description so the destination-local time is never lost."""
    for e in events:
        s, en = e["start"], e["end"]
        if e["kind"] == "flight":
            otz, dtz = s["timeZone"], en["timeZone"]
            dest = e["title"].split("\u2192")[1].strip()
            desc = (f"Departs {pretty_time(s['dateTime'])} {e['location']} / "
                    f"Arrives {pretty_time(en['dateTime'])} {dest} (local)\n" + e["body"])
            e["write"] = {
                "summary": e["title"], "location": e["location"], "description": desc,
                "startTime": local_with_offset(s["dateTime"], otz),
                "endTime": local_with_offset(en["dateTime"], dtz),
                "timeZone": otz,
            }
        else:
            e["write"] = {
                "summary": e["title"], "location": e["location"], "description": e["body"],
                "startTime": s["dateTime"], "endTime": en["dateTime"],
                "timeZone": s["timeZone"],
            }
    return events

def ground_title(direction, airport, other, mode, by):
    """Title for a ground-transport leg. `direction` is 'to' or 'from' relative
    to the airport. `mode` in {uber, pickup, dropoff, self-drive}; `by` is the
    optional person (parents, a friend). Pickup is an arrival-side concept,
    dropoff a departure-side one; the caller attaches each to the right leg."""
    by_clause = f" ({by})" if by else ""
    m = (mode or "uber").lower()
    if m == "uber":
        return (f"Travel to {airport} (Uber) from {other}" if direction == "to"
                else f"Travel from {airport} (Uber) to {other}")
    if m == "self-drive":
        return (f"Drive to {airport} from {other}" if direction == "to"
                else f"Drive from {airport} to {other}")
    if m == "pickup":   # someone collects you at arrival
        return f"Pickup from {airport}{by_clause} \u2192 {other}"
    if m == "dropoff":  # someone takes you to departure
        return f"Dropoff at {airport}{by_clause} from {other}"
    # unknown mode: keep it visible rather than guessing
    return (f"Travel to {airport} ({m}) from {other}" if direction == "to"
            else f"Travel from {airport} ({m}) to {other}")

def flight_marker(seg):
    dep = parse_local(seg["depart_local"], seg["origin_tz"])
    return f"[ttc:{seg['airline']}{seg['flight_number']}:{dep.date().isoformat()}:{seg['origin']}]"

def build_body(seg, marker):
    lines = []
    if seg.get("pnr"):
        lines.append(f"Confirmation: {seg['pnr']}")
    if seg.get("loyalty"):
        lines.append(f"Loyalty: {seg['loyalty']}")
    lines.append(marker)
    return "\n".join(lines)

# ---------- segmentation ----------

def segment_journeys(segments, layover_max_min, ambiguous_max_min):
    """Group segments into journeys. A connection (same journey) requires the
    previous flight's destination to equal the next flight's origin, a gap at or
    under the layover threshold, and no overnight crossing. Everything else is a
    journey boundary."""
    journeys = []
    warnings = []
    if not segments:
        return journeys, warnings
    current = [0]
    for i in range(1, len(segments)):
        prev, cur = segments[i - 1], segments[i]
        prev_arr = parse_local(prev["arrive_local"], prev["dest_tz"])
        cur_dep = parse_local(cur["depart_local"], cur["origin_tz"])
        gap_min = (cur_dep - prev_arr).total_seconds() / 60.0
        same_airport = prev["dest"] == cur["origin"]
        # overnight: local calendar date differs at the connection airport
        overnight = prev_arr.date() != cur_dep.date()
        is_connection = same_airport and (0 <= gap_min <= layover_max_min) and not overnight
        if is_connection:
            current.append(i)
            if layover_max_min < gap_min <= ambiguous_max_min:
                warnings.append(
                    f"Segment {prev['origin']}\u2192{prev['dest']} to {cur['origin']}\u2192{cur['dest']}: "
                    f"gap is {gap_min/60:.1f}h (ambiguous). Treated as a connection/layover; "
                    f"reclassify as a separate journey if you leave the airport."
                )
        else:
            journeys.append(current)
            current = [i]
            if same_airport and not overnight and gap_min > layover_max_min and gap_min <= ambiguous_max_min:
                warnings.append(
                    f"Connection at {prev['dest']} with a {gap_min/60:.1f}h gap was treated as a "
                    f"journey boundary. If you stay airside, reclassify it as a layover."
                )
    journeys.append(current)
    return journeys, warnings

# ---------- event construction ----------

def build_events(data, profile):
    segs = data["segments"]
    overrides = data.get("journey_overrides", {})

    cushion = profile["arrival_cushion_min"]
    home_ride = profile["home_to_airport_ride_min"]
    default_ride = profile["default_ride_min"]
    deplane = profile["deplane_to_curb_min"]
    layover_max = profile["layover_max_min"]
    ambiguous_max = profile["layover_ambiguous_max_min"]
    mode = profile.get("ground_transport_mode", "Uber")
    targets = profile["default_targets"]
    home = profile["home_label"]
    home_airports = set(profile.get("home_airports", []))

    journeys, warnings = segment_journeys(segs, layover_max, ambiguous_max)
    events = []
    needs_input = []
    summary = []

    for j_idx, seg_idxs in enumerate(journeys):
        journey = [segs[k] for k in seg_idxs]
        first, last = journey[0], journey[-1]
        is_first_journey = (j_idx == 0)
        is_last_journey = (j_idx == len(journeys) - 1)
        ov = overrides.get(str(j_idx), {})

        first_dep = parse_local(first["depart_local"], first["origin_tz"])
        last_arr = parse_local(last["arrive_local"], last["dest_tz"])

        # ---- pre-flight pair (journey's first flight only) ----
        apt_start = first_dep - timedelta(minutes=cushion)
        ride_to = ov.get("to_airport_ride_min", home_ride if is_first_journey else default_ride)
        travel_to_start = apt_start - timedelta(minutes=ride_to)
        if is_first_journey:
            origin_label = ov.get("origin_label", home)
        else:
            origin_label = ov.get("origin_label")
            if not origin_label:
                origin_label = "[origin not set]"
                needs_input.append(
                    f"Journey {j_idx}: starting location unknown (e.g. hotel). Used a {ride_to}-min "
                    f"ride default; provide the location and ride time to fix."
                )

        m_first = flight_marker(first)
        events.append({
            "kind": "travel_to_airport",
            "title": ground_title("to", first["origin"], origin_label,
                                   ov.get("to_mode", mode), ov.get("to_by")),
            "location": origin_label,
            "body": m_first + ":to",
            "start": fmt(travel_to_start), "end": fmt(apt_start),
            "marker": m_first + ":to", "targets": targets,
        })
        events.append({
            "kind": "airport_time",
            "title": f"Airport time \u2014 {first['origin']}",
            "location": first["origin"],
            "body": m_first + ":apt",
            "start": fmt(apt_start), "end": fmt(first_dep),
            "marker": m_first + ":apt", "targets": targets,
        })

        # ---- flights + layovers ----
        for k, seg in enumerate(journey):
            dep = parse_local(seg["depart_local"], seg["origin_tz"])
            arr = parse_local(seg["arrive_local"], seg["dest_tz"])
            m = flight_marker(seg)
            events.append({
                "kind": "flight",
                "title": f"{seg['airline']} {seg['flight_number']} \u00b7 {seg['origin']}\u2192{seg['dest']}",
                "location": seg["origin"],
                "body": build_body(seg, m),
                "start": fmt(dep), "end": fmt(arr),
                "marker": m, "targets": targets,
            })
            if k < len(journey) - 1:
                nxt = journey[k + 1]
                nxt_dep = parse_local(nxt["depart_local"], nxt["origin_tz"])
                events.append({
                    "kind": "layover",
                    "title": f"Layover at {seg['dest']}",
                    "location": seg["dest"],
                    "body": m + ":layover",
                    "start": fmt(arr), "end": fmt(nxt_dep),
                    "marker": m + ":layover", "targets": targets,
                })

        # ---- post-flight pair (journey's last flight only) ----
        deplane_end = last_arr + timedelta(minutes=deplane)
        ride_from = ov.get("from_airport_ride_min", default_ride if not is_last_journey else home_ride)
        travel_from_end = deplane_end + timedelta(minutes=ride_from)
        # Default to Home when the trip ends at one of the user's home airports
        # (config `home_airports`), regardless of where the trip started. This
        # correctly handles a one-way/open-jaw that ends home (MIA->...->LAX) and
        # a round trip (LAX->...->LAX), while still flagging a trip that ends
        # somewhere you're staying (e.g. a side-trip that returns to a non-home
        # airport you flew out of). Falls back to the origin-airport check when
        # home_airports isn't configured, for backward compatibility.
        ends_at_home = (last["dest"] in home_airports) or (
            not home_airports and last["dest"] == segs[0]["origin"])
        if is_last_journey and ends_at_home:
            dest_label = ov.get("dest_label", home)
        else:
            dest_label = ov.get("dest_label")
            if not dest_label:
                dest_label = "[destination not set]"
                why = ("trip does not end at a home airport" if is_last_journey
                       else "intermediate stay")
                needs_input.append(
                    f"Journey {j_idx}: arrival destination unknown ({why}; e.g. hotel/"
                    f"family). Used a {ride_from}-min ride default; provide the location "
                    f"and ride time to fix."
                )

        m_last = flight_marker(last)
        events.append({
            "kind": "deplane_to_curb",
            "title": f"Deplane / to curb \u2014 {last['dest']}",
            "location": last["dest"],
            "body": m_last + ":curb",
            "start": fmt(last_arr), "end": fmt(deplane_end),
            "marker": m_last + ":curb", "targets": targets,
        })
        events.append({
            "kind": "travel_from_airport",
            "title": ground_title("from", last["dest"], dest_label,
                                  ov.get("from_mode", mode), ov.get("from_by")),
            "location": last["dest"],
            "body": m_last + ":from",
            "start": fmt(deplane_end), "end": fmt(travel_from_end),
            "marker": m_last + ":from", "targets": targets,
        })

        summary.append({
            "journey_index": j_idx,
            "flights": [f"{s['airline']} {s['flight_number']} {s['origin']}\u2192{s['dest']}" for s in journey],
            "is_first_journey": is_first_journey,
            "is_last_journey": is_last_journey,
        })

    attach_write_fields(events)
    return {
        "events": events,
        "journeys": summary,
        "needs_input": needs_input,
        "warnings": warnings,
        "expected_count": len(events),
        "markers": [e["marker"] for e in events],
    }

# ---------- config ----------

def load_profile(config_path, profile_name, skill="flights"):
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(
            f"{config_path} not found. This skill needs a config. Run the first-run "
            f"setup interview (see SKILL.md / README.md), or copy config.example.json "
            f"to config.json and edit it."
        )
    cfg = json.loads(p.read_text())
    name = profile_name or cfg.get("active_profile", "default")
    profiles = cfg.get("profiles", {})
    if name not in profiles:
        raise ValueError(f"Profile '{name}' not found in {config_path}. Available: {list(profiles)}")
    prof = profiles[name]
    # Family schema: {"shared": {...}, "<skill>": {...}} -> flatten for this skill.
    # Legacy flat profile (all keys at top level) is passed through unchanged.
    if "shared" in prof or skill in prof:
        merged = {}
        merged.update(prof.get("shared", {}))
        merged.update(prof.get(skill, {}))
        return merged, name
    return prof, name

# ---------- main ----------

def main():
    here = Path(__file__).resolve().parent
    # Look for config.json skill-locally first (back-compat), then at the repo
    # root (family layout: gruntwork-travel-skills/config.json shared by all skills).
    skill_local = here.parent / "config.json"
    family_root = here.parent.parent / "config.json"
    default_config = skill_local if skill_local.exists() else family_root

    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="Path to itinerary JSON (default: stdin)")
    ap.add_argument("--config", default=str(default_config), help="Path to config.json")
    ap.add_argument("--profile", help="Config profile name (overrides active_profile)")
    args = ap.parse_args()

    raw = Path(args.input).read_text() if args.input else sys.stdin.read()
    data = json.loads(raw)

    profile_name = data.get("config_profile") or args.profile
    profile, used = load_profile(args.config, profile_name)

    result = build_events(data, profile)
    result["profile_used"] = used
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
