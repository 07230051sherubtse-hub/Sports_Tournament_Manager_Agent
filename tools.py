import sqlite3
from contextlib import closing
from datetime import date, timedelta
from itertools import combinations

DB = "tournament.db"


def _conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with closing(_conn()) as c, c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS teams ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name TEXT UNIQUE NOT NULL COLLATE NOCASE, "
            "active INTEGER NOT NULL DEFAULT 1)"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS matches ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "team1_id INTEGER NOT NULL, team2_id INTEGER NOT NULL, "
            "match_date TEXT, match_time TEXT, court TEXT, "
            "score1 INTEGER, score2 INTEGER)"
        )


def add_team(name):
    name = (name or "").strip()
    if len(name) < 2:
        return "Failed: team name must be at least 2 characters."
    with closing(_conn()) as c, c:
        try:
            c.execute("INSERT INTO teams (name) VALUES (?)", (name,))
        except sqlite3.IntegrityError:
            return f"Failed: team '{name}' already exists."
    return f"Added team {name}."


def withdraw_team(name):
    name = (name or "").strip()
    with closing(_conn()) as c, c:
        row = c.execute(
            "SELECT id, name FROM teams WHERE name = ? AND active = 1", (name,)
        ).fetchone()
        if not row:
            return f"Failed: no active team named '{name}'."
        c.execute("UPDATE teams SET active = 0 WHERE id = ?", (row["id"],))
        cur = c.execute(
            "DELETE FROM matches WHERE (team1_id = ? OR team2_id = ?) "
            "AND score1 IS NULL",
            (row["id"], row["id"]),
        )
        n = cur.rowcount
    return f"{row['name']} withdrawn. {n} unplayed match(es) cancelled."


def generate_schedule(start_date, courts, times, days_of_week):
    """days_of_week: weekday numbers allowed (0=Mon ... 6=Sun)."""
    try:
        start = date.fromisoformat(start_date)
    except (ValueError, TypeError):
        return "Failed: start_date must look like 2026-11-09."
    if not courts or not times:
        return "Failed: need at least one court and one time."
    allowed = set(days_of_week) if days_of_week else set(range(7))

    with closing(_conn()) as c, c:
        team_ids = [r["id"] for r in c.execute(
            "SELECT id FROM teams WHERE active = 1 ORDER BY id")]
        existing = c.execute(
            "SELECT team1_id, team2_id, match_date, match_time, court FROM matches"
        ).fetchall()
        have_pair = {frozenset((r["team1_id"], r["team2_id"])) for r in existing}
        used_slots = {(r["match_date"], r["match_time"], r["court"])
                      for r in existing if r["match_date"]}
        busy = set()
        for r in existing:
            if r["match_date"]:
                busy.add((r["match_date"], r["match_time"], r["team1_id"]))
                busy.add((r["match_date"], r["match_time"], r["team2_id"]))

        slots = []
        for i in range(120):
            d = start + timedelta(days=i)
            if d.weekday() in allowed:
                for t in times:
                    for court in courts:
                        slots.append((d.isoformat(), t, court))

        placed = 0
        failed = 0
        for a, b in combinations(team_ids, 2):
            if frozenset((a, b)) in have_pair:
                continue
            for slot in slots:
                d, t, court = slot
                if slot in used_slots:
                    continue
                if (d, t, a) in busy or (d, t, b) in busy:
                    continue
                c.execute(
                    "INSERT INTO matches (team1_id, team2_id, match_date, "
                    "match_time, court) VALUES (?, ?, ?, ?, ?)",
                    (a, b, d, t, court),
                )
                used_slots.add(slot)
                busy.add((d, t, a))
                busy.add((d, t, b))
                placed += 1
                break
            else:
                failed += 1
    return f"Scheduled {placed} match(es), {failed} could not be placed."


def find_conflicts():
    with closing(_conn()) as c:
        rows = c.execute(
            "SELECT id, team1_id, team2_id, match_date, match_time, court "
            "FROM matches WHERE match_date IS NOT NULL"
        ).fetchall()
    problems = []
    seen_court = {}
    seen_team = {}
    for r in rows:
        key = (r["match_date"], r["match_time"], r["court"])
        if key in seen_court:
            problems.append(
                f"Court double-booked: matches {seen_court[key]} and {r['id']} "
                f"on {key[0]} {key[1]} at {key[2]}")
        else:
            seen_court[key] = r["id"]
        for team in (r["team1_id"], r["team2_id"]):
            tkey = (r["match_date"], r["match_time"], team)
            if tkey in seen_team:
                problems.append(
                    f"Team {team} double-booked: matches {seen_team[tkey]} and "
                    f"{r['id']} on {tkey[0]} {tkey[1]}")
            else:
                seen_team[tkey] = r["id"]
    if not problems:
        return "0 conflict(s) found"
    return f"{len(problems)} conflict(s) found:\n" + "\n".join(problems)


def record_result(match_id, score1, score2):
    if not isinstance(score1, int) or not isinstance(score2, int) or score1 < 0 or score2 < 0:
        return "Failed: scores must be whole numbers, 0 or higher."
    with closing(_conn()) as c, c:
        row = c.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
        if not row:
            return f"Failed: no match with id {match_id}."
        if row["score1"] is not None:
            return f"Failed: match {match_id} already has a result."
        c.execute("UPDATE matches SET score1 = ?, score2 = ? WHERE id = ?",
                  (score1, score2, match_id))
    return f"Recorded {score1}-{score2} for match {match_id}"


def standings():
    with closing(_conn()) as c:
        teams = c.execute("SELECT id, name FROM teams WHERE active = 1").fetchall()
        matches = c.execute(
            "SELECT * FROM matches WHERE score1 IS NOT NULL").fetchall()
    table = {t["id"]: {"name": t["name"], "p": 0, "w": 0, "d": 0, "l": 0,
                       "gf": 0, "ga": 0} for t in teams}
    for m in matches:
        a, b = m["team1_id"], m["team2_id"]
        if a not in table or b not in table:
            continue
        s1, s2 = m["score1"], m["score2"]
        table[a]["p"] += 1
        table[b]["p"] += 1
        table[a]["gf"] += s1
        table[a]["ga"] += s2
        table[b]["gf"] += s2
        table[b]["ga"] += s1
        if s1 > s2:
            table[a]["w"] += 1
            table[b]["l"] += 1
        elif s2 > s1:
            table[b]["w"] += 1
            table[a]["l"] += 1
        else:
            table[a]["d"] += 1
            table[b]["d"] += 1
    rows = list(table.values())
    for r in rows:
        r["pts"] = r["w"] * 3 + r["d"]
        r["gd"] = r["gf"] - r["ga"]
    rows.sort(key=lambda r: (-r["pts"], -r["gd"], -r["gf"], r["name"]))
    if not rows:
        return "No teams yet."
    lines = [f"{'Team':<12}{'P':>3}{'W':>3}{'D':>3}{'L':>3}{'GF':>4}{'GA':>4}{'GD':>4}{'Pts':>5}"]
    for r in rows:
        lines.append(f"{r['name']:<12}{r['p']:>3}{r['w']:>3}{r['d']:>3}{r['l']:>3}"
                     f"{r['gf']:>4}{r['ga']:>4}{r['gd']:>4}{r['pts']:>5}")
    return "\n".join(lines)