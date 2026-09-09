import os, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, jsonify, send_file, redirect

app = Flask(__name__)

API_KEY = "pit-ecd392f6-ec0c-4db5-beb0-5809c99b6c96"
H       = {"Authorization": f"Bearer {API_KEY}", "Version": "2021-04-15"}
BASE    = "https://services.leadconnectorhq.com"
ROOT    = os.path.dirname(os.path.abspath(__file__))
LA      = ZoneInfo("America/Los_Angeles")

# off_weekdays: 0=Mon 1=Tue 2=Wed 3=Thu 4=Fri 5=Sat 6=Sun
# day_ranges: per-day work-range label overrides {weekday_int: "label"}
CLOSERS = [
    {"name": "Alyssa Bralich", "first": "Alyssa", "cal_id": "GHrJK5waSI8pKD7rScLp", "tz_label": "PDT",
     "capacity": 8, "work_range": "10:00 AM – 4:00 PM PDT",
     "day_ranges": {4: "10:00 AM – 3:00 PM PDT"},
     "off_weekdays": [5, 6]},
    {"name": "Luke Zonka",     "first": "Luke",   "cal_id": "WnKe7pHCL6O446qI7mHG", "tz_label": "EDT",
     "capacity": 8, "work_range": "9:00 AM – 3:00 PM EDT",
     "day_ranges": {6: "9:00 AM – 1:00 PM EDT"},
     "off_weekdays": [4, 5]},
    {"name": "Caden Church",   "first": "Caden",  "cal_id": "Sn7756eGpQ8OUdYAzdau", "tz_label": "PDT",
     "capacity": 8, "work_range": "3:30 PM – 9:30 PM PDT",
     "day_ranges": {4: "10:00 AM – 3:00 PM PDT", 5: "10:00 AM – 3:00 PM PDT"},
     "off_weekdays": [6]},
    {"name": "Cade Pepin",     "first": "Cade",   "cal_id": "iSttS5Lua4Kxe0d3Tf0g", "tz_label": "EDT",
     "capacity": 8, "work_range": "12:00 PM – 6:00 PM EDT",
     "off_weekdays": [6]},
    {"name": "Jang Kim",       "first": "Jang",   "cal_id": "VH7Dfgfoyq13dASbjKKP", "tz_label": "PDT",
     "capacity": 6, "work_range": "11:30 AM – 5:30 PM PDT",
     "off_weekdays": [4, 5, 6]},
    {"name": "Ken Johnson",    "first": "Ken",    "cal_id": "QoGbwiSumcHigNI6HtlP", "tz_label": "EDT",
     "capacity": 8, "work_range": "9:00 AM – 3:00 PM EDT",
     "off_weekdays": [5, 6]},
    {"name": "Lee Johnson",    "first": "Lee",    "cal_id": "T6XXUuO7b3LAH3Be3SQV", "tz_label": "MDT",
     "capacity": 5, "work_range": "9:00 AM – 1:15 PM MDT",
     "off_weekdays": [5, 6]},
    {"name": "Harry",          "first": "Harry",  "cal_id": "umLBhJSvoB8LT6Dyea43", "tz_label": "PDT",
     "capacity": 8, "work_range": "7:45 AM – 2:00 PM PDT",
     "off_weekdays": [0, 1, 4, 5, 6]},
    {"name": "Amir",           "first": "Amir",   "cal_id": "dMRa4fUQFvT5TV0gLgzx", "tz_label": "EDT",
     "capacity": 8, "work_range": "11:00 AM – 5:00 PM EDT",
     "day_ranges": {1: "11:00 AM – 6:00 PM EDT",
                    2: "7:00 AM – 1:30 PM & 6:00 PM – 8:00 PM EDT",
                    3: "7:00 AM – 10:00 AM EDT",
                    4: "7:00 AM – 8:00 AM & 2:00 PM – 8:00 PM EDT"},
     "off_weekdays": [0]},
    {"name": "Avery",          "first": "Avery",  "cal_id": "a9Xf706ORSns9Y7DkqcW", "tz_label": "EDT",
     "capacity": 8, "work_range": "11:00 AM – 5:00 PM EDT",
     "off_weekdays": [0, 1]},
    {"name": "Peter Godwin",   "first": "Peter",  "cal_id": "292oHXCL3jU42br1i4Cn", "tz_label": "EDT",
     "capacity": 6, "work_range": "5:15 PM – 10:00 PM EDT",
     "day_ranges": {4: "5:15 PM – 9:00 PM EDT", 5: "12:00 PM – 6:00 PM EDT"},
     "off_weekdays": [6]},
    {"name": "Amirah Adel",    "first": "Amirah", "cal_id": "ZshD6RItAjbJJuNicXf2", "tz_label": "EST",
     "capacity": 8, "work_range": "12:00 PM – 6:00 PM EST",
     "off_weekdays": [0, 1]},
]


def fetch_closer(closer, start, start_ms, end_ms):
    raw = {}
    if closer.get("cal_id"):
        try:
            r = requests.get(
                f"{BASE}/calendars/{closer['cal_id']}/free-slots",
                headers=H,
                params={"startDate": start_ms, "endDate": end_ms,
                        "timezone": "America/Los_Angeles"},
                timeout=15,
            )
            raw = r.json()
        except Exception:
            pass

    capacity   = closer.get("capacity", 0)
    off_days   = set(closer.get("off_weekdays", []))
    day_ranges = closer.get("day_ranges", {})
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
            })
        else:
            no_data  = not bool(closer.get("cal_id"))
            slots    = raw.get(date_str, {}).get("slots", [])
            free     = len(slots)
            # taken can't exceed capacity; no data = show 0 taken (unknown)
            taken    = 0 if no_data else max(0, capacity - free)
            day_work = day_ranges.get(weekday, closer.get("work_range", ""))
            days.append({
                "date": date_str, "day_abbr": day.strftime("%a"),
                "day_num": day.strftime("%-d"),
                "free": free, "taken": taken, "capacity": capacity,
                "slots": slots, "work_range": day_work, "off": False,
                "no_data": no_data,
            })

    return closer, days


@app.route("/api/closer-availability")
def api_closer_availability():
    now_la  = datetime.now(LA)
    start   = now_la.replace(hour=0, minute=0, second=0, microsecond=0)
    end     = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    start_ms = int(start.timestamp() * 1000)
    end_ms   = int(end.timestamp()   * 1000)

    results_map = {}
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {
            pool.submit(fetch_closer, c, start, start_ms, end_ms): c
            for c in CLOSERS
        }
        for future in as_completed(futures):
            closer, days = future.result()
            results_map[closer["name"]] = {
                "name":       closer["name"],
                "first":      closer["first"],
                "tz_label":   closer.get("tz_label", "PDT"),
                "days":       days,
                "total_free": sum(d["free"] for d in days),
            }

    results = [results_map[c["name"]] for c in CLOSERS if c["name"] in results_map]

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
