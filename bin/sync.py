#!/usr/bin/env python3
"""
whoop-journal sync: Pull Whoop + Strava data into Obsidian journal entries.

Zero external dependencies — uses only Python stdlib.
Works with Python 3.8+.

Usage:
    python3 sync.py                    # Sync yesterday's data
    python3 sync.py --date 2026-03-28  # Sync a specific date
    python3 sync.py --verbose          # Debug logging
    python3 sync.py --skip-existing    # Skip dates that already have whoop data
    python3 sync.py --whoop-only       # Only pull Whoop data
    python3 sync.py --strava-only      # Only pull Strava data
"""

import argparse
import json
import logging
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".whoop-journal"
CONFIG_FILE = CONFIG_DIR / "config.json"
WHOOP_TOKENS_FILE = CONFIG_DIR / "whoop_tokens.json"
STRAVA_TOKENS_FILE = CONFIG_DIR / "strava_tokens.json"

WHOOP_API = "https://api.prod.whoop.com/developer"
WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
STRAVA_API = "https://www.strava.com/api/v3"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"

log = logging.getLogger("whoop-sync")


def load_config():
    if not CONFIG_FILE.exists():
        log.error("Config not found at %s. Run setup.py first.", CONFIG_FILE)
        sys.exit(1)
    with open(CONFIG_FILE) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------

def load_tokens(path):
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def save_tokens(path, tokens):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(tokens, f, indent=2)
    os.chmod(str(path), 0o600)


def refresh_whoop_token(config, tokens):
    log.info("Refreshing Whoop access token...")
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": config["whoop_client_id"],
        "client_secret": config["whoop_client_secret"],
    }).encode()
    req = urllib.request.Request(WHOOP_TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", "whoop-journal/0.1.0")
    try:
        with urllib.request.urlopen(req) as resp:
            new_tokens = json.loads(resp.read())
        tokens["access_token"] = new_tokens["access_token"]
        if "refresh_token" in new_tokens:
            tokens["refresh_token"] = new_tokens["refresh_token"]
        tokens["expires_at"] = time.time() + new_tokens.get("expires_in", 3600)
        save_tokens(WHOOP_TOKENS_FILE, tokens)
        return tokens
    except urllib.error.HTTPError as e:
        log.error("Whoop token refresh failed: %s %s", e.code, e.read().decode())
        return None


def refresh_strava_token(config, tokens):
    log.info("Refreshing Strava access token...")
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": config["strava_client_id"],
        "client_secret": config["strava_client_secret"],
    }).encode()
    req = urllib.request.Request(STRAVA_TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", "whoop-journal/0.1.0")
    try:
        with urllib.request.urlopen(req) as resp:
            new_tokens = json.loads(resp.read())
        tokens["access_token"] = new_tokens["access_token"]
        if "refresh_token" in new_tokens:
            tokens["refresh_token"] = new_tokens["refresh_token"]
        tokens["expires_at"] = new_tokens.get("expires_at", time.time() + 21600)
        save_tokens(STRAVA_TOKENS_FILE, tokens)
        return tokens
    except urllib.error.HTTPError as e:
        log.error("Strava token refresh failed: %s %s", e.code, e.read().decode())
        return None


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def api_get(url, access_token, params=None, retries=3):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Bearer " + access_token)
    req.add_header("User-Agent", "whoop-journal/0.1.0")
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 2 ** (attempt + 1)
                log.warning("Rate limited. Waiting %ds...", wait)
                time.sleep(wait)
                continue
            if e.code >= 500:
                wait = 2 ** (attempt + 1)
                log.warning("Server error %d. Retrying in %ds...", e.code, wait)
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            raise
    return None


# ---------------------------------------------------------------------------
# Whoop data fetching
# ---------------------------------------------------------------------------

def fetch_whoop_data(config, tokens, target_date):
    """Fetch cycle, recovery, sleep, and workouts for target_date."""
    if tokens and tokens.get("expires_at", 0) < time.time() + 60:
        tokens = refresh_whoop_token(config, tokens)
    if not tokens:
        log.warning("No valid Whoop tokens. Skipping Whoop data.")
        return {}

    token = tokens["access_token"]

    # Whoop cycles are wake-to-wake. Query a wide window.
    day_start = datetime(target_date.year, target_date.month, target_date.day,
                         tzinfo=timezone.utc)
    window_start = (day_start - timedelta(hours=14)).isoformat()
    window_end = (day_start + timedelta(hours=36)).isoformat()

    data = {}

    # Cycle (strain)
    try:
        resp = api_get(f"{WHOOP_API}/v1/cycle", token,
                       {"start": window_start, "end": window_end, "limit": "10"})
        if resp and resp.get("records"):
            for cycle in resp["records"]:
                cycle_start = cycle.get("start", "")
                if target_date.isoformat() in cycle_start[:10]:
                    data["cycle"] = cycle
                    break
            if "cycle" not in data:
                data["cycle"] = resp["records"][0]
        log.debug("Cycle data: %s", "found" if "cycle" in data else "none")
    except Exception as e:
        log.warning("Failed to fetch cycle: %s", e)

    # Recovery
    try:
        resp = api_get(f"{WHOOP_API}/v2/recovery", token,
                       {"start": window_start, "end": window_end, "limit": "10"})
        if resp and resp.get("records"):
            for rec in resp["records"]:
                if rec.get("cycle_id") == data.get("cycle", {}).get("id"):
                    data["recovery"] = rec
                    break
            if "recovery" not in data:
                data["recovery"] = resp["records"][0]
        log.debug("Recovery data: %s", "found" if "recovery" in data else "none")
    except Exception as e:
        log.warning("Failed to fetch recovery: %s", e)

    # Sleep
    try:
        resp = api_get(f"{WHOOP_API}/v2/activity/sleep", token,
                       {"start": window_start, "end": window_end, "limit": "10"})
        if resp and resp.get("records"):
            for sleep in resp["records"]:
                end_str = sleep.get("end", "")
                if not sleep.get("nap") and target_date.isoformat() in end_str[:10]:
                    data["sleep"] = sleep
                    break
            if "sleep" not in data and resp["records"]:
                non_naps = [s for s in resp["records"] if not s.get("nap")]
                if non_naps:
                    data["sleep"] = non_naps[0]
        log.debug("Sleep data: %s", "found" if "sleep" in data else "none")
    except Exception as e:
        log.warning("Failed to fetch sleep: %s", e)

    # Workouts
    try:
        resp = api_get(f"{WHOOP_API}/v2/activity/workout", token,
                       {"start": window_start, "end": window_end, "limit": "25"})
        if resp and resp.get("records"):
            data["workouts"] = [w for w in resp["records"]
                                if target_date.isoformat() in w.get("start", "")[:10]]
        log.debug("Workouts: %d found", len(data.get("workouts", [])))
    except Exception as e:
        log.warning("Failed to fetch workouts: %s", e)

    # Save refreshed tokens
    save_tokens(WHOOP_TOKENS_FILE, tokens)
    return data


# ---------------------------------------------------------------------------
# Strava data fetching
# ---------------------------------------------------------------------------

def fetch_strava_data(config, tokens, target_date):
    """Fetch activities from Strava for target_date."""
    if tokens and tokens.get("expires_at", 0) < time.time() + 60:
        tokens = refresh_strava_token(config, tokens)
    if not tokens:
        log.warning("No valid Strava tokens. Skipping Strava data.")
        return {}

    token = tokens["access_token"]

    day_start = datetime(target_date.year, target_date.month, target_date.day,
                         tzinfo=timezone.utc)
    after_epoch = int(day_start.timestamp())
    before_epoch = int((day_start + timedelta(days=1)).timestamp())

    data = {}
    try:
        activities = api_get(f"{STRAVA_API}/athlete/activities", token,
                             {"after": str(after_epoch), "before": str(before_epoch),
                              "per_page": "30"})
        if activities:
            data["activities"] = activities
        log.debug("Strava activities: %d found", len(data.get("activities", [])))
    except Exception as e:
        log.warning("Failed to fetch Strava activities: %s", e)

    save_tokens(STRAVA_TOKENS_FILE, tokens)
    return data


# ---------------------------------------------------------------------------
# Frontmatter parsing and writing
# ---------------------------------------------------------------------------

def parse_journal(content):
    """Parse a journal file into (frontmatter_dict, frontmatter_raw_lines, body)."""
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, [], content

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return {}, [], content

    fm_lines = lines[1:end_idx]
    body = "\n".join(lines[end_idx + 1:])

    # Parse frontmatter — handles simple key: value and list items
    fm = {}
    current_key = None
    current_list = None
    for line in fm_lines:
        if line.startswith("  - "):
            if current_key and current_list is not None:
                current_list.append(line.strip()[2:])
            continue
        match = re.match(r'^([a-zA-Z0-9_-]+):\s*(.*)', line)
        if match:
            if current_key and current_list is not None:
                fm[current_key] = current_list
            key = match.group(1)
            val = match.group(2).strip()
            if val == "":
                current_key = key
                current_list = []
                fm[key] = ""
            elif val.startswith('"') and val.endswith('"'):
                fm[key] = val[1:-1]
                current_key = key
                current_list = None
            else:
                try:
                    fm[key] = int(val)
                except ValueError:
                    try:
                        fm[key] = float(val)
                    except ValueError:
                        fm[key] = val
                current_key = key
                current_list = None
        else:
            current_key = None
            current_list = None
    if current_key and current_list is not None:
        fm[current_key] = current_list

    return fm, fm_lines, body


def build_frontmatter_string(fm, original_lines, whoop_data, strava_data):
    """Build frontmatter string preserving original keys, appending whoop/strava keys."""
    # Start with original non-whoop, non-strava lines
    lines = []
    skip_list = False
    for line in original_lines:
        if line.startswith("  - ") and skip_list:
            continue
        match = re.match(r'^([a-zA-Z0-9_-]+):', line)
        if match:
            key = match.group(1)
            if key.startswith("whoop-") or key.startswith("strava-"):
                skip_list = True
                continue
        skip_list = False
        lines.append(line)

    # Append whoop metrics
    recovery = whoop_data.get("recovery", {})
    cycle = whoop_data.get("cycle", {})
    sleep = whoop_data.get("sleep", {})

    rec_score = recovery.get("score", {})
    cyc_score = cycle.get("score", {})
    slp_score = sleep.get("score", {})

    if rec_score.get("recovery_score") is not None:
        lines.append("whoop-recovery: %d" % round(rec_score["recovery_score"]))
    if rec_score.get("hrv_rmssd_milli") is not None:
        lines.append("whoop-hrv: %.1f" % rec_score["hrv_rmssd_milli"])
    if rec_score.get("resting_heart_rate") is not None:
        lines.append("whoop-rhr: %d" % round(rec_score["resting_heart_rate"]))
    if cyc_score.get("strain") is not None:
        lines.append("whoop-strain: %.1f" % cyc_score["strain"])
    if slp_score.get("sleep_performance_percentage") is not None:
        lines.append("whoop-sleep-score: %d" % round(slp_score["sleep_performance_percentage"]))

    # Calculate sleep hours from stage durations
    stage_summary = slp_score.get("stage_summary", {})
    if stage_summary:
        total_ms = sum([
            stage_summary.get("total_light_sleep_time_milli", 0),
            stage_summary.get("total_slow_wave_sleep_time_milli", 0),
            stage_summary.get("total_rem_sleep_time_milli", 0),
            stage_summary.get("total_awake_time_milli", 0),
        ])
        if total_ms > 0:
            lines.append("whoop-sleep-hours: %.1f" % (total_ms / 3600000))

    # Strava metrics
    activities = strava_data.get("activities", [])
    if activities:
        total_miles = sum(a.get("distance", 0) for a in activities) / 1609.34
        run_count = len([a for a in activities
                         if "run" in a.get("type", "").lower()])
        if total_miles > 0:
            lines.append("strava-miles: %.1f" % total_miles)
        if run_count > 0:
            lines.append("strava-runs: %d" % run_count)

    return "---\n" + "\n".join(lines) + "\n---"


# ---------------------------------------------------------------------------
# Body section building
# ---------------------------------------------------------------------------

def ms_to_hm(ms):
    """Convert milliseconds to 'Xh Ym' string."""
    if not ms:
        return "0m"
    total_min = int(ms / 60000)
    h, m = divmod(total_min, 60)
    if h > 0:
        return "%dh %02dm" % (h, m)
    return "%dm" % m


def seconds_to_hms(s):
    """Convert seconds to 'H:MM:SS' or 'MM:SS'."""
    if not s:
        return "0:00"
    s = int(s)
    h, remainder = divmod(s, 3600)
    m, sec = divmod(remainder, 60)
    if h > 0:
        return "%d:%02d:%02d" % (h, m, sec)
    return "%d:%02d" % (m, sec)


def pace_per_mile(distance_m, moving_time_s):
    """Calculate pace in min:sec per mile."""
    if not distance_m or not moving_time_s:
        return None
    miles = distance_m / 1609.34
    if miles < 0.01:
        return None
    pace_seconds = moving_time_s / miles
    m, s = divmod(int(pace_seconds), 60)
    return "%d:%02d" % (m, s)


def format_time_local(iso_str):
    """Extract a human-readable time from an ISO timestamp."""
    if not iso_str:
        return ""
    try:
        # Handle various ISO formats
        clean = re.sub(r'\.\d+', '', iso_str)
        if clean.endswith('Z'):
            clean = clean[:-1] + '+00:00'
        dt = datetime.fromisoformat(clean)
        return dt.strftime("%-I:%M %p")
    except (ValueError, AttributeError):
        return ""


def _md_table(headers, values):
    """Build a markdown table from parallel header/value lists."""
    row1 = "| " + " | ".join(headers) + " |"
    sep  = "| " + " | ".join(["---"] * len(headers)) + " |"
    row2 = "| " + " | ".join(values) + " |"
    return "\n".join([row1, sep, row2])


def _bar(value, max_val, width=10, invert=False):
    """Unicode block progress bar. \u2588 = filled, \u2591 = empty."""
    if not max_val or max_val <= 0:
        return "\u2591" * width
    frac = max(0.0, min(1.0, value / max_val))
    if invert:
        frac = 1.0 - frac
    filled = round(frac * width)
    return "\u2588" * filled + "\u2591" * (width - filled)


def build_whoop_section(whoop_data, strava_data):
    """Build the ## Whoop markdown section as a bar-chart dashboard."""
    parts = []
    parts.append("## Whoop")
    parts.append("")

    recovery = whoop_data.get("recovery", {})
    cycle = whoop_data.get("cycle", {})
    sleep = whoop_data.get("sleep", {})
    whoop_workouts = whoop_data.get("workouts", [])

    rec_score = recovery.get("score", {})
    cyc_score = cycle.get("score", {})
    slp_score = sleep.get("score", {})
    stage_summary = slp_score.get("stage_summary", {})

    # rows: (label, value_str, bar_str, extras_str) — ("","","","") = blank separator
    rows = []

    # Recovery block
    if recovery.get("score_state") == "PENDING_SCORE":
        rows.append(("Recovery", "Pending", "\u2591" * 10, ""))
    else:
        if rec_score.get("recovery_score") is not None:
            v = rec_score["recovery_score"]
            rows.append(("Recovery", "%d%%" % round(v), _bar(v, 100), ""))
        if rec_score.get("hrv_rmssd_milli") is not None:
            v = rec_score["hrv_rmssd_milli"]
            rows.append(("HRV", "%.1fms" % v, _bar(v, 100), ""))
        if rec_score.get("resting_heart_rate") is not None:
            v = rec_score["resting_heart_rate"]
            extras = []
            if rec_score.get("spo2_percentage") is not None:
                extras.append("SpO2 %.0f%%" % rec_score["spo2_percentage"])
            if rec_score.get("skin_temp_celsius") is not None:
                extras.append("%.1f\u00b0C" % rec_score["skin_temp_celsius"])
            # RHR: inverted, 30–80 bpm range
            rows.append(("RHR", "%dbpm" % round(v), _bar(v - 30, 50, invert=True), " \u00b7 ".join(extras)))

    # Sleep block
    if stage_summary:
        total_ms = sum([
            stage_summary.get("total_light_sleep_time_milli", 0),
            stage_summary.get("total_slow_wave_sleep_time_milli", 0),
            stage_summary.get("total_rem_sleep_time_milli", 0),
            stage_summary.get("total_awake_time_milli", 0),
        ])
        perf = slp_score.get("sleep_performance_percentage")
        eff  = slp_score.get("sleep_efficiency_percentage")
        resp = slp_score.get("respiratory_rate")

        sleep_extras = []
        if perf is not None:
            sleep_extras.append("%d%% perf" % round(perf))
        if eff is not None:
            sleep_extras.append("%.1f%% eff" % eff)
        if resp is not None:
            sleep_extras.append("%.1f rpm" % resp)

        rows.append(("", "", "", ""))
        rows.append(("Sleep", ms_to_hm(total_ms), _bar(total_ms, 9 * 3600000), " \u00b7 ".join(sleep_extras)))
        for label, key in [("  Light", "total_light_sleep_time_milli"),
                            ("  Deep",  "total_slow_wave_sleep_time_milli"),
                            ("  REM",   "total_rem_sleep_time_milli"),
                            ("  Awake", "total_awake_time_milli")]:
            v = stage_summary.get(key, 0)
            if v:
                rows.append((label, ms_to_hm(v), _bar(v, total_ms) if total_ms else "\u2591" * 10, ""))

    # Strain block
    if cyc_score.get("strain") is not None:
        strain_extras = []
        if cyc_score.get("average_heart_rate") is not None:
            strain_extras.append("avg %d bpm" % round(cyc_score["average_heart_rate"]))
        if cyc_score.get("max_heart_rate") is not None:
            strain_extras.append("max %d bpm" % round(cyc_score["max_heart_rate"]))
        if cyc_score.get("kilojoule") is not None:
            kcal = round(cyc_score["kilojoule"] / 4.184)
            strain_extras.append("%s kcal" % format(kcal, ","))
        rows.append(("", "", "", ""))
        rows.append(("Strain", "%.1f" % cyc_score["strain"], _bar(cyc_score["strain"], 21), " \u00b7 ".join(strain_extras)))

    # Render as a fenced code block for reliable monospace alignment
    if rows:
        label_w = max((len(r[0]) for r in rows if r[0]), default=8)
        value_w = max((len(r[1]) for r in rows if r[1]), default=6)
        block = []
        for r in rows:
            if not r[0] and not r[1]:
                block.append("")
                continue
            line = "%s  %s  %s" % (r[0].ljust(label_w), r[1].ljust(value_w), r[2])
            if r[3]:
                line += "   " + r[3]
            block.append(line)
        parts.append("```")
        parts.extend(block)
        parts.append("```")

    parts.append("")

    # Activities
    strava_activities = strava_data.get("activities", [])
    if whoop_workouts or strava_activities:
        parts.append("### Activities")
        parts.append("")
        for sa in strava_activities:
            parts.append(_format_strava_activity(sa, whoop_workouts))
            parts.append("")
        for ww in whoop_workouts:
            matched = any(
                _times_overlap(ww.get("start", ""), ww.get("end", ""),
                               sa.get("start_date", ""), sa.get("elapsed_time", 0))
                for sa in strava_activities
            )
            if not matched:
                parts.append(_format_whoop_workout(ww))
                parts.append("")

    return "\n".join(parts).rstrip()


def _times_overlap(start1_iso, end1_iso, start2_iso, duration2_s):
    """Check if two time periods overlap (within 30 min tolerance)."""
    try:
        s1 = re.sub(r'\.\d+', '', start1_iso.replace('Z', '+00:00'))
        s2 = re.sub(r'\.\d+', '', start2_iso.replace('Z', '+00:00'))
        t1_start = datetime.fromisoformat(s1)
        t2_start = datetime.fromisoformat(s2)
        diff = abs((t1_start - t2_start).total_seconds())
        return diff < 1800  # within 30 min
    except (ValueError, AttributeError):
        return False


def _format_strava_activity(sa, whoop_workouts):
    """Format a Strava activity as a header line + metrics table."""
    name = sa.get("name", sa.get("type", "Activity"))
    start_time = format_time_local(sa.get("start_date_local", ""))
    distance = sa.get("distance", 0)
    moving_time = sa.get("moving_time", 0)
    elapsed_time = sa.get("elapsed_time", 0)
    elevation = sa.get("total_elevation_gain", 0)
    avg_hr = sa.get("average_heartrate")
    max_hr = sa.get("max_heartrate")

    header = "**%s**" % name
    if start_time:
        header += " \u00b7 " + start_time

    headers, values = [], []
    if distance > 0:
        miles = distance / 1609.34
        headers.append("Distance"); values.append("%.1f mi" % miles)
        pace = pace_per_mile(distance, moving_time)
        if pace:
            headers.append("Pace"); values.append("%s/mi" % pace)
    if elapsed_time:
        headers.append("Duration"); values.append(seconds_to_hms(elapsed_time))
    if elevation and elevation > 0:
        headers.append("Elevation"); values.append("\u2191 %d ft" % round(elevation * 3.28084))
    if avg_hr:
        headers.append("Avg HR"); values.append("%d bpm" % round(avg_hr))
    if max_hr:
        headers.append("Max HR"); values.append("%d bpm" % round(max_hr))
    for ww in whoop_workouts:
        if _times_overlap(ww.get("start", ""), ww.get("end", ""),
                          sa.get("start_date", ""), elapsed_time):
            ww_score = ww.get("score", {})
            if ww_score.get("strain") is not None:
                headers.append("Strain"); values.append("%.1f" % ww_score["strain"])
            break

    if headers:
        return header + "\n" + _md_table(headers, values)
    return header


def _format_whoop_workout(ww):
    """Format a Whoop-only workout as a header line + metrics table."""
    sport = ww.get("sport_name", "Workout")
    start_time = format_time_local(ww.get("start", ""))
    ww_score = ww.get("score", {})

    header = "**%s**" % sport
    if start_time:
        header += " \u00b7 " + start_time

    headers, values = [], []
    try:
        s = re.sub(r'\.\d+', '', ww["start"].replace('Z', '+00:00'))
        e = re.sub(r'\.\d+', '', ww["end"].replace('Z', '+00:00'))
        dur_s = (datetime.fromisoformat(e) - datetime.fromisoformat(s)).total_seconds()
        headers.append("Duration"); values.append(seconds_to_hms(dur_s))
    except (ValueError, KeyError):
        pass
    if ww_score.get("average_heart_rate") is not None:
        headers.append("Avg HR"); values.append("%d bpm" % round(ww_score["average_heart_rate"]))
    if ww_score.get("max_heart_rate") is not None:
        headers.append("Max HR"); values.append("%d bpm" % round(ww_score["max_heart_rate"]))
    if ww_score.get("strain") is not None:
        headers.append("Strain"); values.append("%.1f" % ww_score["strain"])

    if headers:
        return header + "\n" + _md_table(headers, values)
    return header


# ---------------------------------------------------------------------------
# Journal file operations
# ---------------------------------------------------------------------------

JOURNAL_TEMPLATE = """---
type: journal
date: "{date}"
day: "{day}"
tags:
  - journal
people:
places:
---

# {day_long}

## What happened today


## What's on my mind


## Grateful for


## Whoop

"""

WHOOP_SECTION_PATTERN = re.compile(
    r'(## Whoop\n)(.*?)(?=\n## (?!#)|\Z)',
    re.DOTALL
)


def create_journal_from_template(target_date):
    """Create a minimal journal entry from template."""
    day_name = target_date.strftime("%A")
    return JOURNAL_TEMPLATE.format(
        date=target_date.isoformat(),
        day=day_name,
        day_long=target_date.strftime("%A, %B %-d, %Y")
    )


def merge_body(existing_body, whoop_section):
    """Replace existing ## Whoop section or append."""
    if WHOOP_SECTION_PATTERN.search(existing_body):
        return WHOOP_SECTION_PATTERN.sub(whoop_section, existing_body)
    # Append after existing content
    body = existing_body.rstrip()
    if body:
        body += "\n\n"
    body += whoop_section + "\n"
    return body


def atomic_write(path, content):
    """Write content atomically via temp file + rename."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        os.rename(tmp_path, str(path))
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Sync Whoop + Strava data to Obsidian journal")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD). Default: yesterday.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip dates that already have whoop/strava data")
    parser.add_argument("--whoop-only", action="store_true", help="Only pull Whoop data")
    parser.add_argument("--strava-only", action="store_true", help="Only pull Strava data")
    args = parser.parse_args()

    logging.basicConfig(
        format="[whoop-sync] %(levelname)s: %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO
    )

    # Determine target date
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            log.error("Invalid date format. Use YYYY-MM-DD.")
            sys.exit(1)
    else:
        target_date = (datetime.now() - timedelta(days=1)).date()

    log.info("Syncing data for %s", target_date)

    config = load_config()
    vault_path = Path(config.get("vault_path", "")).expanduser()
    journal_path = vault_path / config.get("journal_path", "_Riley/Journal")
    journal_file = journal_path / (target_date.isoformat() + ".md")

    # Check skip-existing
    if args.skip_existing and journal_file.exists():
        content = journal_file.read_text()
        fm, _, _ = parse_journal(content)
        has_whoop = any(k.startswith("whoop-") for k in fm)
        has_strava = any(k.startswith("strava-") for k in fm)
        if has_whoop or has_strava:
            log.info("Data already exists for %s. Skipping.", target_date)
            return

    # Fetch data
    whoop_data = {}
    strava_data = {}

    if not args.strava_only:
        whoop_tokens = load_tokens(WHOOP_TOKENS_FILE)
        if whoop_tokens:
            whoop_data = fetch_whoop_data(config, whoop_tokens, target_date)
        else:
            log.warning("No Whoop tokens found. Skipping Whoop. Run setup.py to configure.")

    if not args.whoop_only:
        strava_tokens = load_tokens(STRAVA_TOKENS_FILE)
        if strava_tokens:
            strava_data = fetch_strava_data(config, strava_tokens, target_date)
        else:
            log.warning("No Strava tokens found. Skipping Strava. Run setup.py to configure.")

    if not whoop_data and not strava_data:
        log.warning("No data retrieved from any source. Nothing to write.")
        return

    # Load or create journal
    if journal_file.exists():
        content = journal_file.read_text()
        log.info("Updating existing journal: %s", journal_file.name)
    else:
        content = create_journal_from_template(target_date)
        log.info("Creating new journal: %s", journal_file.name)

    fm, fm_lines, body = parse_journal(content)

    # Build frontmatter
    new_fm = build_frontmatter_string(fm, fm_lines, whoop_data, strava_data)

    # Build body section
    whoop_section = build_whoop_section(whoop_data, strava_data)

    # Merge
    new_body = merge_body(body, whoop_section)

    # Write — ensure a blank line always separates frontmatter close from body
    final_content = new_fm + "\n" + new_body.lstrip("\n")
    atomic_write(journal_file, final_content)
    log.info("Written: %s", journal_file)


if __name__ == "__main__":
    main()
