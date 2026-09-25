import os, requests, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, jsonify, send_file, redirect

app = Flask(__name__)

API_KEY   = "pit-ecd392f6-ec0c-4db5-beb0-5809c99b6c96"
H         = {"Authorization": f"Bearer {API_KEY}", "Version": "2021-04-15"}
BASE      = "https://services.leadconnectorhq.com"
ROOT      = os.path.dirname(os.path.abspath(__file__))
LA        = ZoneInfo("America/Los_Angeles")
EDT       = ZoneInfo("America/New_York")
TEAM_CAL  = "l8S0FxBqnRFJY1CXQqrr"
WEBINAR_CAL = "iLz9bkWMA1T9Hs7CwdDH"
LOC_ID    = "sXAvXUKpaePasaiX4etS"
CACHE_TTL     = 3600  # 1 hour
CAL_HOURS_TTL = 3600  # cache individual calendar openHours for 1 hour

# GHL uses Sun=0 … Sat=6; Python weekday() uses Mon=0 … Sun=6
GHL_TO_PY = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}

# ── Per-closer config (keyed by GHL userId) ───────────────────────────────────
# When someone joins the team calendar in GHL, they auto-appear on the dashboard.
# Add their userId here to control tz_label, work_range, capacity, and off days.
CLOSER_CONFIG = {
    "djt6k0JScB4euA8dl5Vv": {
        "name": "Alyssa Bralich", "first": "Alyssa",
        "cal_id": "GHrJK5waSI8pKD7rScLp", "tz_label": "PDT",
        "capacity": 8, "work_range": "10:00 AM – 4:00 PM PDT",
        "off_weekdays": [5, 6],
    },
    "tQ4trl3utKYHvxuLwN3u": {
        "name": "Caden Church", "first": "Caden",
        "cal_id": "Sn7756eGpQ8OUdYAzdau", "tz_label": "PDT",
        "capacity": 8, "work_range": "3:30 PM – 9:30 PM PDT",
        "day_ranges": {2: "3:30 PM – 5:00 PM PDT", 4: "10:00 AM – 3:00 PM PDT", 5: "10:00 AM – 3:00 PM PDT"},
        "off_weekdays": [6],
    },
    "CdLTuSPvDCbQBbJ6foHM": {
        "name": "Cade Pepin", "first": "Cade",
        "cal_id": "iSttS5Lua4Kxe0d3Tf0g", "tz_label": "EDT",
        "capacity": 8, "work_range": "12:00 PM – 6:00 PM EDT",
        "off_weekdays": [6],
    },
    "hQqYUjAsLphmPaVxh27l": {
        "name": "Lee Johnson", "first": "Lee",
        "cal_id": "T6XXUuO7b3LAH3Be3SQV", "tz_label": "MDT",
        "capacity": 8, "work_range": "9:00 AM – 3:00 PM MDT",
        "off_weekdays": [5, 6],
    },
    "MAnZbUiIBpBnDL8OM8PQ": {
        "name": "Harry", "first": "Harry",
        "cal_id": "umLBhJSvoB8LT6Dyea43", "tz_label": "EDT",
        "capacity": 8, "work_range": "10:45 AM – 5:00 PM EDT",
        "day_ranges": {6: "7:00 AM – 1:00 PM EDT", 4: "7:45 AM – 2:00 PM EDT", 5: "7:45 AM – 5:00 PM EDT"},
        "off_weekdays": [0],
    },
    "MJEiaehaH7xeXndSvauP": {
        "name": "Amir", "first": "Amir",
        "cal_id": "dMRa4fUQFvT5TV0gLgzx", "tz_label": "EDT",
        "capacity": 8, "work_range": "11:00 AM – 5:00 PM EDT",
        "day_ranges": {
            6: "4:00 PM – 10:00 PM EDT",   # Sun
            0: "6:00 PM – 12:00 AM EDT",   # Mon
            1: "6:00 PM – 12:00 AM EDT",   # Tue
            3: "8:00 PM – 12:00 AM EDT",   # Thu
            4: "2:00 PM – 8:00 PM EDT",    # Fri
        },
        "off_weekdays": [5],
    },
    "lRRjsbYBPoZ1ppLD4Fw1": {
        "name": "Avery", "first": "Avery",
        "cal_id": "a9Xf706ORSns9Y7DkqcW", "tz_label": "EDT",
        "capacity": 8, "work_range": "11:00 AM – 5:00 PM EDT",
        "day_ranges": {6: "11:00 AM – 4:00 PM EDT", 4: "11:00 AM – 6:00 PM EDT"},
        "off_weekdays": [0, 1],
    },
    "NJnJKQea7HhOm43pwAX9": {
        "name": "Peter Godwin", "first": "Peter",
        "cal_id": "292oHXCL3jU42br1i4Cn", "tz_label": "EDT",
        "capacity": 6, "work_range": "7:00 AM – 10:00 PM EDT",
        "day_ranges": {3: "7:00 AM – 6:00 PM EDT", 5: "10:00 AM – 7:00 PM EDT"},
        "off_weekdays": [6],
    },
    "qt3nCz8rsQvTCFeDrNCE": {
        "name": "Amirah Adel", "first": "Amirah",
        "cal_id": "ZshD6RItAjbJJuNicXf2", "tz_label": "BST",
        "capacity": 8, "work_range": "3:00 PM – 10:00 PM BST",
        "off_weekdays": [0, 1],
    },
    "k9PJ9X296OSPiuYlwSJL": {
        "name": "Adam Kuperman", "first": "Adam",
        "cal_id": "g0JUmlXjHuafdO3avoem", "tz_label": "EDT",
        "capacity": 8, "work_range": "11:00 AM – 5:00 PM EDT",
        "off_weekdays": [5, 6],
    },
    "Kom4DBd4cfmGKyCtxdUl": {
        "name": "Alexander N", "first": "Alexander",
        "cal_id": "fwq8ZGR0f24x2yJgiFWz", "tz_label": "EDT",
        "capacity": 8, "work_range": "12:00 PM – 6:00 PM EDT",
        "day_ranges": {4: "10:00 AM – 4:00 PM EDT"},
        "off_weekdays": [5, 6],
    },
    "fYOGA6Qx7ePCSyj4OHoK": {
        "name": "Tate Zablotny", "first": "Tate",
        "cal_id": "4f3Fqo5B9tNDtW6JeETf", "tz_label": "EDT",
        "capacity": 8, "work_range": "10:00 AM – 4:00 PM EDT",
        "day_ranges": {6: "11:00 AM – 6:00 PM EDT"},
        "off_weekdays": [],
    },
    "0QXG4WmuozFII9i4qgax": {
        "name": "Caleb Rice", "first": "Caleb",
        "cal_id": "clKTuP4p0g2pFxj4Dp4V", "tz_label": "EDT",
        "capacity": 8, "work_range": "11:00 AM – 5:00 PM EDT",
        "off_weekdays": [1],
    },
    "04HxeHctHNWK1HzrzvKA": {
        "name": "Kera Beattie", "first": "Kera",
        "cal_id": "77YwGuoYftp4A09avPUK", "tz_label": "EDT",
        "capacity": 8, "work_range": "10:00 AM – 4:00 PM EDT",
        "off_weekdays": [6],
    },
}

# Display order for known closers; new team members appear after these.
CLOSER_ORDER = list(CLOSER_CONFIG.keys())

# ── Team member cache (auto-detects GHL team calendar membership) ─────────────
_team_cache      = {"ids": None, "expires": 0.0}
_cache_lock      = threading.Lock()
_cal_hours_cache = {}          # cal_id → (expires_ts, result_tuple)
_cal_hours_lock  = threading.Lock()
_webinar_cache        = {"ids": None, "expires": 0.0}
_webinar_lock         = threading.Lock()
_webinar_slots_cache  = {"data": None, "expires": 0.0}
_webinar_slots_lock   = threading.Lock()
WEBINAR_SLOTS_TTL     = 300  # 5 minutes


def get_team_user_ids():
    """Return GHL team calendar member user IDs, cached for 1 hour.
    Handles adds/removes from GHL automatically without code changes."""
    now = datetime.utcnow().timestamp()
    with _cache_lock:
        if _team_cache["ids"] is not None and now < _team_cache["expires"]:
            return list(_team_cache["ids"])

    ids = []
    try:
        r   = requests.get(f"{BASE}/calendars/{TEAM_CAL}", headers=H, timeout=10)
        cal = r.json().get("calendar", r.json())
        raw = (
            cal.get("teamMembers")
            or cal.get("team_members")
            or cal.get("members")
            or []
        )
        for m in raw:
            if isinstance(m, dict):
                uid = m.get("userId") or m.get("user_id") or m.get("id")
            elif isinstance(m, str):
                uid = m
            else:
                uid = None
            if uid:
                ids.append(uid)
    except Exception:
        pass

    # Fallback to static config if API call fails
    if not ids:
        ids = list(CLOSER_CONFIG.keys())

    with _cache_lock:
        _team_cache["ids"]     = ids
        _team_cache["expires"] = now + CACHE_TTL
    return ids


def resolve_closer_cfg(user_id):
    """Return config for user_id; auto-fetches name from GHL for unknown members."""
    if user_id in CLOSER_CONFIG:
        cfg = dict(CLOSER_CONFIG[user_id])
        cfg["user_id"] = user_id
        return cfg

    cfg = {
        "user_id": user_id, "name": user_id, "first": user_id[:6],
        "cal_id": "", "tz_label": "", "capacity": 8,
        "work_range": "", "off_weekdays": [], "day_ranges": {},
    }
    try:
        r    = requests.get(f"{BASE}/users/{user_id}", headers=H, timeout=10)
        u    = r.json().get("user", r.json())
        name = u.get("name") or u.get("fullName") or ""
        if name:
            cfg["name"]  = name
            cfg["first"] = name.split()[0]
    except Exception:
        pass
    return cfg


def _fmt_time(h, m):
    suf = "AM" if h < 12 else "PM"
    return f"{h % 12 or 12}:{m:02d} {suf}"


def fetch_calendar_hours(cal_id):
    """
    Fetch openHours from a GHL individual calendar and return:
      (day_hours, off_days, work_range_no_tz, day_ranges_no_tz)
    where day_hours is {py_weekday: (open_h, open_m, close_h, close_m)}.
    Returns (None, None, None, None) if unavailable or empty.
    Cached for CAL_HOURS_TTL seconds.
    """
    if not cal_id:
        return None, None, None, None

    now = datetime.utcnow().timestamp()
    with _cal_hours_lock:
        cached = _cal_hours_cache.get(cal_id)
        if cached and now < cached[0]:
            return cached[1]

    result = (None, None, None, None)
    try:
        r = requests.get(f"{BASE}/calendars/{cal_id}", headers=H, timeout=10)
        cal = r.json().get("calendar", r.json())
        open_hours = cal.get("openHours", [])
        if open_hours and isinstance(open_hours, list):
            day_hours = {}
            for entry in open_hours:
                ghl_days = entry.get("daysOfTheWeek", [])
                hrs = entry.get("hours", [])
                if not hrs:
                    continue
                h = hrs[0]
                oh = int(h.get("openHour", 9));  om = int(h.get("openMinute", 0))
                ch = int(h.get("closeHour", 17)); cm = int(h.get("closeMinute", 0))
                for gd in ghl_days:
                    py_d = GHL_TO_PY.get(int(gd))
                    if py_d is not None:
                        day_hours[py_d] = (oh, om, ch, cm)

            if day_hours:
                from collections import Counter
                base = Counter(day_hours.values()).most_common(1)[0][0]
                work_range_no_tz = f"{_fmt_time(*base[:2])} – {_fmt_time(*base[2:])}"
                day_ranges_no_tz = {
                    d: f"{_fmt_time(*s[:2])} – {_fmt_time(*s[2:])}"
                    for d, s in day_hours.items() if s != base
                }
                off_days = [d for d in range(7) if d not in day_hours]
                result = (day_hours, off_days, work_range_no_tz, day_ranges_no_tz)
    except Exception:
        pass

    with _cal_hours_lock:
        _cal_hours_cache[cal_id] = (now + CAL_HOURS_TTL, result)
    return result


def fetch_closer(cfg, start, start_ms, end_ms):
    user_id  = cfg["user_id"]
    cal_id   = cfg.get("cal_id", "")
    capacity = cfg.get("capacity", 8)
    tz_label = cfg.get("tz_label", "PDT")

    # Pull schedule live from GHL; fall back to hardcoded config if unavailable
    _, ghl_off_days, ghl_work_range, ghl_day_ranges = fetch_calendar_hours(cal_id)
    if ghl_off_days is not None:
        off_days   = set(ghl_off_days)
        work_range = f"{ghl_work_range} {tz_label}" if ghl_work_range else cfg.get("work_range", "")
        day_ranges = {d: f"{r} {tz_label}" for d, r in (ghl_day_ranges or {}).items()}
        # Config day_ranges override GHL (manual corrections take precedence)
        day_ranges.update(cfg.get("day_ranges", {}))
    else:
        off_days   = set(cfg.get("off_weekdays", []))
        work_range = cfg.get("work_range", "")
        day_ranges = cfg.get("day_ranges", {})

    # ── Four parallel GHL calls ───────────────────────────────────────────────
    team_raw   = {}
    ind_raw    = {}
    appts_raw  = {}   # date → booked appointment count
    blocks_raw = set()  # dates with a manual "blocked" entry

    def _team():
        try:
            r = requests.get(
                f"{BASE}/calendars/{TEAM_CAL}/free-slots", headers=H,
                params={"startDate": start_ms, "endDate": end_ms,
                        "timezone": "America/Los_Angeles", "userId": user_id},
                timeout=15)
            return r.json()
        except Exception:
            return {}

    def _ind():
        if not cal_id:
            return {}
        try:
            r = requests.get(
                f"{BASE}/calendars/{cal_id}/free-slots", headers=H,
                params={"startDate": start_ms, "endDate": end_ms,
                        "timezone": "America/Los_Angeles"},
                timeout=15)
            return r.json()
        except Exception:
            return {}

    def _appts():
        # Query by userId (not calendarId) — bookings go through the team calendar,
        # not the closer's individual calendar, so calendarId filter misses most appointments.
        ACTIVE = {"confirmed", "scheduled", "new"}
        try:
            r = requests.get(
                f"{BASE}/calendars/events", headers=H,
                params={"startTime": start_ms, "endTime": end_ms,
                        "userId": user_id, "locationId": LOC_ID},
                timeout=15)
            # Return {date: [startTime, ...]} for confirmed appointments only
            result = {}
            for e in r.json().get("events", []):
                if e.get("appointmentStatus", "") not in ACTIVE:
                    continue
                d = e.get("startTime", "")[:10]
                t = e.get("startTime", "")
                if d and t:
                    result.setdefault(d, []).append(t)
            return result
        except Exception:
            return {}

    def _blocks():
        # Returns {date: [(block_start_dt, block_end_dt), ...]} for manual blocks only.
        from datetime import datetime as _dt
        try:
            r = requests.get(
                f"{BASE}/calendars/blocked-slots", headers=H,
                params={"startTime": start_ms, "endTime": end_ms,
                        "userId": user_id, "locationId": LOC_ID},
                timeout=15)
            result = {}
            for e in r.json().get("events", []):
                if (e.get("title") == "blocked" and
                        e.get("createdBy", {}).get("source") == "calendar_page"):
                    d  = e.get("startTime", "")[:10]
                    bs = e.get("startTime", "")
                    be = e.get("endTime", "")
                    if d and bs and be:
                        try:
                            result.setdefault(d, []).append(
                                (_dt.fromisoformat(bs), _dt.fromisoformat(be)))
                        except Exception:
                            pass
            return result
        except Exception:
            return {}

    from concurrent.futures import ThreadPoolExecutor as _TPE, as_completed as _ac
    with _TPE(max_workers=4) as p:
        ft = {p.submit(_team): "team", p.submit(_ind): "ind",
              p.submit(_appts): "appts", p.submit(_blocks): "blocks"}
        for f in _ac(ft):
            k = ft[f]
            v = f.result()
            if k == "team":   team_raw   = v
            elif k == "ind":  ind_raw    = v
            elif k == "appts": appts_raw = v
            else:             blocks_raw = v

    days = []
    for i in range(7):
        day      = start + timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")
        weekday  = day.weekday()

        if weekday in off_days:
            days.append({
                "date": date_str, "day_abbr": day.strftime("%a"),
                "day_num": day.strftime("%-d"),
                "free": 0, "taken": 0, "capacity": 0,
                "slots": [], "work_range": "", "off": True,
                "booked": 0, "is_blocked": False,
            })
        else:
            if date_str in team_raw:
                slots = team_raw[date_str].get("slots", [])
            else:
                slots = ind_raw.get(date_str, {}).get("slots", [])

            # Confirmed appointment start times for this day
            appt_starts = appts_raw.get(date_str, [])
            booked      = len(appt_starts)

            # Filter: only keep a slot if it doesn't overlap any confirmed appointment.
            # Overlap: slot [t, t+45min) intersects appointment [a, a+45min)
            # when t < a+45min AND a < t+45min.
            if appt_starts:
                from datetime import datetime as _dt, timedelta as _td
                SLOT_DUR = _td(minutes=45)
                appt_dts = []
                for a in appt_starts:
                    try:
                        appt_dts.append(_dt.fromisoformat(a))
                    except Exception:
                        pass
                valid = []
                for s in slots:
                    try:
                        s_dt  = _dt.fromisoformat(s)
                        s_end = s_dt + SLOT_DUR
                        if not any(s_dt < (a + SLOT_DUR) and a < s_end for a in appt_dts):
                            valid.append(s)
                    except Exception:
                        valid.append(s)
                slots = valid

            free     = len(slots)
            taken    = max(0, capacity - free)
            day_work = day_ranges.get(weekday, work_range)

            # Only flag BLOCKED if the manual block overlaps working time on this day:
            # i.e. it overlaps at least one appointment or free slot.
            # Blocks entirely outside working hours (e.g. 5–11 PM after-hours cleanup)
            # are irrelevant and hidden. If there are no appointments AND no free slots,
            # any block is relevant (it's preventing booking for the whole day).
            from datetime import datetime as _dt, timedelta as _td
            SLOT_DUR   = _td(minutes=45)
            day_blocks = blocks_raw.get(date_str, [])
            if not day_blocks:
                is_blocked = False
            elif not appt_starts and not slots:
                is_blocked = True  # full-day block with nothing else → relevant
            else:
                working_periods = []
                for a in appt_starts:
                    try:
                        a_dt = _dt.fromisoformat(a)
                        working_periods.append((a_dt, a_dt + SLOT_DUR))
                    except Exception:
                        pass
                for s in slots:
                    try:
                        s_dt = _dt.fromisoformat(s)
                        working_periods.append((s_dt, s_dt + SLOT_DUR))
                    except Exception:
                        pass
                is_blocked = any(
                    b_start < p_end and p_start < b_end
                    for b_start, b_end in day_blocks
                    for p_start, p_end in working_periods
                )

            # Build human-readable block time ranges (for display in the badge)
            TZ_NAMES = {
                "PDT": "America/Los_Angeles", "PST": "America/Los_Angeles",
                "EDT": "America/New_York",    "EST": "America/New_York",
                "MDT": "America/Denver",      "MST": "America/Denver",
                "CDT": "America/Chicago",     "CST": "America/Chicago",
                "BST": "Europe/London",       "GMT": "Europe/London",
            }
            block_times = []
            if is_blocked:
                tz_lbl    = cfg.get("tz_label", "PDT")
                closer_tz = ZoneInfo(TZ_NAMES.get(tz_lbl, "America/Los_Angeles"))
                def _fmt(dt):
                    s = dt.strftime("%-I:%M %p")
                    return s.replace(":00 ", " ")  # "5:00 PM" → "5 PM"
                for b_start, b_end in day_blocks:
                    bs = b_start.astimezone(closer_tz)
                    be = b_end.astimezone(closer_tz)
                    block_times.append(f"{_fmt(bs)} – {_fmt(be)} {tz_lbl}")

            days.append({
                "date": date_str, "day_abbr": day.strftime("%a"),
                "day_num": day.strftime("%-d"),
                "free": free, "taken": taken, "capacity": capacity,
                "slots": slots, "work_range": day_work, "off": False,
                "booked": booked, "is_blocked": is_blocked,
                "block_times": block_times,
            })

    return cfg, days


@app.route("/api/closer-availability")
def api_closer_availability():
    now_la   = datetime.now(LA)
    start    = now_la.replace(hour=0, minute=0, second=0, microsecond=0)
    end      = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    start_ms = int(start.timestamp() * 1000)
    end_ms   = int(end.timestamp()   * 1000)

    team_ids = get_team_user_ids()
    cfgs     = [resolve_closer_cfg(uid) for uid in team_ids]

    # Known members in defined order, then unknown/new members alphabetically
    order_idx = {uid: i for i, uid in enumerate(CLOSER_ORDER)}
    cfgs.sort(key=lambda c: (order_idx.get(c["user_id"], len(CLOSER_ORDER)), c["name"]))

    results_map = {}
    with ThreadPoolExecutor(max_workers=max(len(cfgs), 1)) as pool:
        futures = {pool.submit(fetch_closer, c, start, start_ms, end_ms): c for c in cfgs}
        for future in as_completed(futures):
            cfg, days = future.result()
            results_map[cfg["user_id"]] = {
                "name":       cfg["name"],
                "first":      cfg["first"],
                "tz_label":   cfg.get("tz_label", ""),
                "days":       days,
                "total_free": sum(d["free"] for d in days),
            }

    results = [results_map[c["user_id"]] for c in cfgs if c["user_id"] in results_map]

    return jsonify({
        "closers":    results,
        "week_label": f"{start.strftime('%b %-d')} – {end.strftime('%b %-d, %Y')}",
        "timezone":   "PDT (America/Los_Angeles)",
        "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    })


@app.route("/closer-availability")
def dashboard():
    return send_file(os.path.join(ROOT, "index.html"))


@app.route("/")
def root():
    return redirect("/closer-availability")


# ── Webinar Calendar Availability ─────────────────────────────────────────────

def get_webinar_user_ids():
    """Return GHL webinar calendar member user IDs, cached for 1 hour."""
    now = datetime.utcnow().timestamp()
    with _webinar_lock:
        if _webinar_cache["ids"] is not None and now < _webinar_cache["expires"]:
            return list(_webinar_cache["ids"])

    ids = []
    try:
        r   = requests.get(f"{BASE}/calendars/{WEBINAR_CAL}", headers=H, timeout=10)
        cal = r.json().get("calendar", r.json())
        raw = cal.get("teamMembers") or cal.get("team_members") or cal.get("members") or []
        for m in raw:
            if isinstance(m, dict):
                uid = m.get("userId") or m.get("user_id") or m.get("id")
            elif isinstance(m, str):
                uid = m
            else:
                uid = None
            if uid:
                ids.append(uid)
    except Exception:
        pass

    with _webinar_lock:
        _webinar_cache["ids"]     = ids
        _webinar_cache["expires"] = now + CACHE_TTL
    return ids


def _ghl_free_slots(cal_id, start_ms, end_ms, user_id=None, retries=2):
    """Call GHL free-slots with automatic retry on empty/failed responses."""
    params = {"startDate": start_ms, "endDate": end_ms, "timezone": "America/New_York"}
    if user_id:
        params["userId"] = user_id
    for attempt in range(retries + 1):
        try:
            r = requests.get(f"{BASE}/calendars/{cal_id}/free-slots",
                             headers=H, params=params, timeout=20)
            data = r.json()
            # If we got actual slot keys (dates), it's a real response
            if any(k.startswith("20") for k in data):
                return data
        except Exception:
            pass
        if attempt < retries:
            import time; time.sleep(0.3 * (attempt + 1))
    return {}


def fetch_webinar_closer(cfg, start_ms, end_ms, tonight_cutoff_h, today_str, tomorrow_str):
    """
    Query the webinar calendar with userId. The webinar calendar has its own
    evening schedule (openHours not exposed in API) — individual calendars
    don't have those hours so we must use the webinar cal directly.
    Sequential calls (no parallel) prevent GHL rate-limit drops.
    """
    data = _ghl_free_slots(WEBINAR_CAL, start_ms, end_ms, user_id=cfg["user_id"])

    def fmt(slot_iso):
        try:
            return datetime.fromisoformat(slot_iso).astimezone(EDT).strftime("%-I:%M %p")
        except Exception:
            return slot_iso

    tonight_slots = []
    for s in data.get(today_str, {}).get("slots", []):
        try:
            dt = datetime.fromisoformat(s).astimezone(EDT)
            if dt.hour >= tonight_cutoff_h:
                tonight_slots.append(fmt(s))
        except Exception:
            pass

    tomorrow_slots = [fmt(s) for s in data.get(tomorrow_str, {}).get("slots", [])]

    return {
        "name":           cfg["name"],
        "first":          cfg["first"],
        "tonight_slots":  tonight_slots,
        "tonight_count":  len(tonight_slots),
        "tomorrow_slots": tomorrow_slots,
        "tomorrow_count": len(tomorrow_slots),
    }


@app.route("/api/webinar-availability")
def api_webinar_availability():
    now_ts  = datetime.utcnow().timestamp()
    now_edt = datetime.now(EDT)
    today   = now_edt.replace(hour=0, minute=0, second=0, microsecond=0)

    # Return cached payload if still fresh AND it's for today's date
    with _webinar_slots_lock:
        cached = _webinar_slots_cache["data"]
        if (cached is not None
                and now_ts < _webinar_slots_cache["expires"]
                and cached.get("today_label") == today.strftime("%A, %b %-d")):
            return jsonify(cached)

    tomorrow     = today + timedelta(days=1)
    start_ms     = int(today.timestamp() * 1000)
    end_ms       = int((tomorrow + timedelta(days=1)).timestamp() * 1000)
    today_str    = today.strftime("%Y-%m-%d")
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")

    team_ids = get_webinar_user_ids()
    cfgs     = [resolve_closer_cfg(uid) for uid in team_ids]
    cfgs.sort(key=lambda c: c["name"])

    results = []
    for cfg in cfgs:
        results.append(fetch_webinar_closer(cfg, start_ms, end_ms, 20, today_str, tomorrow_str))

    results.sort(key=lambda r: r["name"])

    payload = {
        "closers":        results,
        "today_label":    today.strftime("%A, %b %-d"),
        "tomorrow_label": tomorrow.strftime("%A, %b %-d"),
        "tonight_note":   "Slots from 8:00 PM EDT onward",
        "updated_at":     datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }

    with _webinar_slots_lock:
        _webinar_slots_cache["data"]    = payload
        _webinar_slots_cache["expires"] = now_ts + WEBINAR_SLOTS_TTL

    return jsonify(payload)


@app.route("/api/webinar-refresh", methods=["POST", "GET"])
def api_webinar_refresh():
    with _webinar_slots_lock:
        _webinar_slots_cache["data"]    = None
        _webinar_slots_cache["expires"] = 0.0
    with _webinar_lock:
        _webinar_cache["ids"]     = None
        _webinar_cache["expires"] = 0.0
    return jsonify({"ok": True, "message": "Cache cleared — next load will fetch fresh data."})


@app.route("/webinar-availability")
def webinar_dashboard():
    return send_file(os.path.join(ROOT, "webinar.html"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
