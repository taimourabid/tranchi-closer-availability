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
TEAM_CAL  = "l8S0FxBqnRFJY1CXQqrr"
LOC_ID    = "sXAvXUKpaePasaiX4etS"
CACHE_TTL = 3600  # 1 hour

# ── Per-closer config (keyed by GHL userId) ───────────────────────────────────
# When someone joins the team calendar in GHL, they auto-appear on the dashboard.
# Add their userId here to control tz_label, work_range, capacity, and off days.
CLOSER_CONFIG = {
    "djt6k0JScB4euA8dl5Vv": {
        "name": "Alyssa Bralich", "first": "Alyssa",
        "cal_id": "GHrJK5waSI8pKD7rScLp", "tz_label": "PDT",
        "capacity": 8, "work_range": "10:00 AM – 4:00 PM PDT",
        "day_ranges": {4: "10:00 AM – 3:00 PM PDT"},
        "off_weekdays": [5, 6],
    },
    "qnm8XMoAjIJdlwXpxMGV": {
        "name": "Luke Zonka", "first": "Luke",
        "cal_id": "WnKe7pHCL6O446qI7mHG", "tz_label": "EDT",
        "capacity": 8, "work_range": "9:00 AM – 3:00 PM EDT",
        "day_ranges": {6: "9:00 AM – 1:00 PM EDT"},
        "off_weekdays": [4, 5],
    },
    "tQ4trl3utKYHvxuLwN3u": {
        "name": "Caden Church", "first": "Caden",
        "cal_id": "Sn7756eGpQ8OUdYAzdau", "tz_label": "PDT",
        "capacity": 8, "work_range": "3:30 PM – 9:30 PM PDT",
        "day_ranges": {4: "10:00 AM – 3:00 PM PDT", 5: "10:00 AM – 3:00 PM PDT"},
        "off_weekdays": [6],
    },
    "CdLTuSPvDCbQBbJ6foHM": {
        "name": "Cade Pepin", "first": "Cade",
        "cal_id": "iSttS5Lua4Kxe0d3Tf0g", "tz_label": "EDT",
        "capacity": 8, "work_range": "12:00 PM – 6:00 PM EDT",
        "off_weekdays": [6],
    },
    "kBuLVdKzAcockWIITfPi": {
        "name": "Jang Kim", "first": "Jang",
        "cal_id": "VH7Dfgfoyq13dASbjKKP", "tz_label": "PDT",
        "capacity": 6, "work_range": "11:30 AM – 5:30 PM PDT",
        "off_weekdays": [4, 5, 6],
    },
    "hQqYUjAsLphmPaVxh27l": {
        "name": "Lee Johnson", "first": "Lee",
        "cal_id": "T6XXUuO7b3LAH3Be3SQV", "tz_label": "MDT",
        "capacity": 5, "work_range": "9:00 AM – 1:15 PM MDT",
        "off_weekdays": [5, 6],
    },
    "MAnZbUiIBpBnDL8OM8PQ": {
        "name": "Harry", "first": "Harry",
        "cal_id": "umLBhJSvoB8LT6Dyea43", "tz_label": "EDT",
        "capacity": 8, "work_range": "7:45 AM – 2:00 PM EDT",
        "day_ranges": {6: "7:00 AM – 1:00 PM EDT"},
        "off_weekdays": [0],
    },
    "MJEiaehaH7xeXndSvauP": {
        "name": "Amir", "first": "Amir",
        "cal_id": "dMRa4fUQFvT5TV0gLgzx", "tz_label": "EDT",
        "capacity": 8, "work_range": "11:00 AM – 5:00 PM EDT",
        "day_ranges": {
            2: "7:00 AM – 1:30 PM & 6:00 PM – 8:00 PM EDT",
            3: "7:00 AM – 10:00 AM EDT",
            4: "7:00 AM – 8:00 AM & 2:00 PM – 8:00 PM EDT",
        },
        "off_weekdays": [0, 1],
    },
    "lRRjsbYBPoZ1ppLD4Fw1": {
        "name": "Avery", "first": "Avery",
        "cal_id": "a9Xf706ORSns9Y7DkqcW", "tz_label": "EDT",
        "capacity": 8, "work_range": "11:00 AM – 5:00 PM EDT",
        "off_weekdays": [0, 1],
    },
    "NJnJKQea7HhOm43pwAX9": {
        "name": "Peter Godwin", "first": "Peter",
        "cal_id": "292oHXCL3jU42br1i4Cn", "tz_label": "EDT",
        "capacity": 6, "work_range": "5:15 PM – 10:00 PM EDT",
        "day_ranges": {4: "5:15 PM – 9:00 PM EDT", 5: "12:00 PM – 6:00 PM EDT"},
        "off_weekdays": [6],
    },
    "qt3nCz8rsQvTCFeDrNCE": {
        "name": "Amirah Adel", "first": "Amirah",
        "cal_id": "ZshD6RItAjbJJuNicXf2", "tz_label": "EST",
        "capacity": 8, "work_range": "12:00 PM – 6:00 PM EST",
        "off_weekdays": [0, 1],
    },
}

# Display order for known closers; new team members appear after these.
CLOSER_ORDER = list(CLOSER_CONFIG.keys())

# ── Team member cache (auto-detects GHL team calendar membership) ─────────────
_team_cache = {"ids": None, "expires": 0.0}
_cache_lock = threading.Lock()


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


def fetch_closer(cfg, start, start_ms, end_ms):
    user_id    = cfg["user_id"]
    cal_id     = cfg.get("cal_id", "")
    capacity   = cfg.get("capacity", 8)
    off_days   = set(cfg.get("off_weekdays", []))
    day_ranges = cfg.get("day_ranges", {})
    work_range = cfg.get("work_range", "")

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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
