#!/usr/bin/env python3
"""
build_lodging_events.py — deterministic event construction for the
lodging-to-calendar skill.

Lodging = wherever you're staying: a hotel, an Airbnb, a friend's or family's
place. Two modes:

  * Stays with real check-in semantics (hotel, Airbnb) -> THREE events:
    an all-day span across the stay, a timed check-in, and a timed check-out.
  * Personal stays with no check-in (parents', a friend's place) -> ONE event:
    just the all-day span. (Set "timed": false.)

Lodging only: it does NOT generate ground transport (the flights skill owns
airport/ground movement; adding it here would duplicate).

It does NOT touch any calendar. The model takes this JSON, shows the proposal,
and makes the calendar MCP calls.

Usage:
    python3 build_lodging_events.py --input stay.json [--config config.json] [--profile default]
    cat stay.json | python3 build_lodging_events.py

Input JSON shape:
{
  "config_profile": "default",                 # optional
  "reservations": [
    {
      "name": "Homewood Suites Columbus/OSU",   # the lodging detail / what to call it
      "city": "Columbus",                        # used for the title and the marker key
      "tz": "America/New_York",                  # IANA zone of the stay
      "checkin_date": "2026-07-02",
      "checkout_date": "2026-07-05",
      "timed": true,                             # true: hotel/airbnb (3 events). false: personal stay (1 event). default true
      "checkin_time": "16:00",                   # optional; default from config (only used when timed)
      "checkout_time": "11:00",                  # optional; default from config (only used when timed)
      "confirmation": "ABC123",                  # optional
      "loyalty": "Hilton Honors 9000...",        # optional
      "address": "123 Olentangy River Rd"        # optional; goes in location
    }
  ]
}

Output JSON: { "events": [...], "needs_input": [...], "warnings": [...],
               "expected_count": N, "markers": [...] }
The all-day "stay" event uses an EXCLUSIVE end date (check-out + 1 day) per the
Google Calendar convention so the bar covers check-in day through check-out day.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def slug(s):
    return re.sub(r"[^A-Za-z0-9]", "", s or "").upper()[:24]

def lodging_marker(r):
    # Key on city + check-in date (you rarely start two stays in the same city
    # the same day). Fall back to the name if no city is given.
    key = slug(r.get("city")) or slug(r.get("name")) or "STAY"
    return f"[ttc:lodging:{key}:{r['checkin_date']}]"

def stay_title(r):
    # City first, so the "where am I" answer survives month-view truncation.
    name, city = r.get("name"), r.get("city")
    if city and name:
        return f"{city} \u2014 {name}"
    return city or name or "Lodging"

def validate_tz(tzname):
    try:
        ZoneInfo(tzname)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"Unknown timezone '{tzname}'. Use a valid IANA name (e.g. 'America/New_York').")

def at(date_str, time_str):
    return f"{date_str}T{time_str}:00"

def add_days(date_str, n):
    return (datetime.fromisoformat(date_str).date() + timedelta(days=n)).isoformat()

def plus_30(hhmm):
    return (datetime.strptime(hhmm, "%H:%M") + timedelta(minutes=30)).strftime("%H:%M")

def build_body(r, marker):
    lines = []
    if r.get("confirmation"):
        lines.append(f"Confirmation: {r['confirmation']}")
    if r.get("loyalty"):
        lines.append(f"Loyalty: {r['loyalty']}")
    if r.get("address"):
        lines.append(f"Address: {r['address']}")
    lines.append(marker)
    return "\n".join(lines)


def build_events(data, profile):
    reservations = data["reservations"]
    targets = profile["default_targets"]
    default_in = profile.get("default_checkin_time", "16:00")
    default_out = profile.get("default_checkout_time", "11:00")

    events, needs_input, warnings, markers = [], [], [], []

    for r in reservations:
        validate_tz(r["tz"])
        tz = r["tz"]
        title = stay_title(r)
        loc = r.get("address") or r.get("city") or r.get("name") or ""
        marker = lodging_marker(r)
        ci_date, co_date = r["checkin_date"], r["checkout_date"]
        timed = r.get("timed", True)
        if co_date < ci_date:
            warnings.append(f"{title}: check-out date {co_date} is before check-in {ci_date}.")
        body = build_body(r, marker)

        # 1. All-day span (always). Exclusive end = check-out + 1.
        events.append({
            "kind": "stay",
            "title": title,
            "marker": marker + ":stay",
            "targets": targets,
            "write": {
                "summary": title,
                "location": loc,
                "description": body,
                "allDay": True,
                "startTime": f"{ci_date}T00:00:00",
                "endTime": f"{add_days(co_date, 1)}T00:00:00",
                "timeZone": tz,
            },
            "display": {"checkin_date": ci_date, "checkout_date": co_date, "timed": timed},
        })
        markers.append(marker + ":stay")

        # 2 & 3. Timed check-in / check-out — only for stays that have them.
        if timed:
            ci_time = r.get("checkin_time") or default_in
            co_time = r.get("checkout_time") or default_out
            if not r.get("checkin_time"):
                needs_input.append(f"{title}: check-in time not given; used default {default_in}.")
            if not r.get("checkout_time"):
                needs_input.append(f"{title}: check-out time not given; used default {default_out}.")
            name_for_action = r.get("name") or r.get("city") or "lodging"
            events.append({
                "kind": "checkin",
                "title": f"Check-in \u2014 {name_for_action}",
                "marker": marker + ":in",
                "targets": targets,
                "write": {
                    "summary": f"Check-in \u2014 {name_for_action}",
                    "location": loc, "description": body, "allDay": False,
                    "startTime": at(ci_date, ci_time), "endTime": at(ci_date, plus_30(ci_time)),
                    "timeZone": tz,
                },
            })
            events.append({
                "kind": "checkout",
                "title": f"Check-out \u2014 {name_for_action}",
                "marker": marker + ":out",
                "targets": targets,
                "write": {
                    "summary": f"Check-out \u2014 {name_for_action}",
                    "location": loc, "description": body, "allDay": False,
                    "startTime": at(co_date, co_time), "endTime": at(co_date, plus_30(co_time)),
                    "timeZone": tz,
                },
            })
            markers.extend([marker + ":in", marker + ":out"])

    return {
        "events": events,
        "needs_input": needs_input,
        "warnings": warnings,
        "expected_count": len(events),
        "markers": markers,
    }


def load_profile(config_path, profile_name, skill="lodging"):
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(
            f"{config_path} not found. Run the first-run setup (see SKILL.md / README.md), "
            f"or copy config.example.json to config.json and edit it."
        )
    cfg = json.loads(p.read_text())
    name = profile_name or cfg.get("active_profile", "default")
    profiles = cfg.get("profiles", {})
    if name not in profiles:
        raise ValueError(f"Profile '{name}' not found in {config_path}. Available: {list(profiles)}")
    prof = profiles[name]
    if "shared" in prof or skill in prof:
        merged = {}
        merged.update(prof.get("shared", {}))
        merged.update(prof.get(skill, {}))
        return merged, name
    return prof, name


def main():
    here = Path(__file__).resolve().parent
    skill_local = here.parent / "config.json"
    family_root = here.parent.parent / "config.json"
    default_config = skill_local if skill_local.exists() else family_root

    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="Path to reservation JSON (default: stdin)")
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
