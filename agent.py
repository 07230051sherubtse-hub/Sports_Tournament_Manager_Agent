import json
import os
import time
from functools import wraps

import tools
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

tools.init_db()

TRACE_FILE = "trace.jsonl"
MEMORY_FILE = "memory.json"
PENDING = {"name": None}
APPROVED = set()
BLOCKED = ["ignore previous", "ignore all", "system prompt",
           "drop table", "delete from", "reveal your instructions",
           "disregard", "act as admin", "developer mode"]

SYSTEM = (
    "You are a sports tournament manager. Always use the tools to read or "
    "change tournament data, and never invent results, teams or schedules. "
    "Report what the tool returned. Weekdays are numbers: 0=Monday, "
    "1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday. "
    "Dates look like 2026-11-09 and times like 09:00. "
    "If the user's request is not about the tournament, politely refuse. "
    "If a tool says confirmation is required, ask the user to reply yes. "
    "For multi-step requests, call the tools one after another. After any "
    "change to teams, schedules or results, call find_conflicts and "
    "standings, then summarise what changed. If a needed value such as a "
    "date, court or time is missing, ask the user instead of guessing. "
    "To list or show matches, call list_matches. "
    "To record a result, first call list_matches to find the match id. "
    "If the user says never or avoid a weekday, call avoid_weekday."
)


# ---------- tracing ----------
def log(kind, **data):
    rec = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "type": kind, **data}
    with open(TRACE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def traced(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = fn(*args, **kwargs)
        except Exception as e:
            result = f"Failed: tool error: {e}"
        log("tool", tool=fn.__name__, args=kwargs or list(args),
            result=result, seconds=round(time.time() - start, 3))
        return result
    return wrapper


# ---------- persistent memory ----------
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            pass
    return {}


def save_memory(mem):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(mem, f)


# ---------- tools ----------
@tool
@traced
def add_team(name: str) -> str:
    """Add a team to the tournament."""
    return tools.add_team(name)


@tool
@traced
def withdraw_team(name: str) -> str:
    """Withdraw a team and cancel its unplayed matches. Needs user confirmation."""
    key = name.strip().lower()
    if key not in APPROVED:
        PENDING["name"] = name.strip()
        return (f"Confirmation required: ask the user to confirm "
                f"withdrawing {name}. Do not withdraw yet.")
    APPROVED.discard(key)
    return tools.withdraw_team(name)


@tool
@traced
def generate_schedule(start_date: str, courts: list[str], times: list[str],
                      days_of_week: list[int]) -> str:
    """Create a round-robin schedule. days_of_week uses 0=Mon ... 6=Sun."""
    avoid = load_memory().get("avoid_days", [])
    days_of_week = [d for d in days_of_week if d not in avoid]
    if not days_of_week:
        return "Failed: every allowed day is on your avoid list."
    result = tools.generate_schedule(start_date, courts, times, days_of_week)
    if not result.startswith("Scheduled"):
        return result
    mem = load_memory()
    mem.update({"courts": courts, "times": times, "days_of_week": days_of_week})
    save_memory(mem)
    # reflection: check own work
    note = f"{result}\nSelf-check: {tools.find_conflicts()}"
    if ", 0 could not be placed" not in result:
        note += ("\nAdvice: some matches did not fit. Add more courts, "
                 "times or days and run the schedule again.")
    return note


@tool
@traced
def find_conflicts() -> str:
    """Check the schedule for double-booked courts or teams."""
    return tools.find_conflicts()


@tool
@traced
def record_result(match_id: int, score1: int, score2: int) -> str:
    """Record the final score of a match by its match id."""
    return tools.record_result(match_id, score1, score2)


@tool
@traced
def standings() -> str:
    """Show the current league table."""
    return tools.standings()


@tool
@traced
def list_matches() -> str:
    """List all matches with id, teams, date, time, court and score."""
    from contextlib import closing
    with closing(tools._conn()) as c:
        rows = c.execute("""
            SELECT m.id, t1.name AS a, t2.name AS b, m.match_date,
                   m.match_time, m.court, m.score1, m.score2
            FROM matches m
            JOIN teams t1 ON t1.id = m.team1_id
            JOIN teams t2 ON t2.id = m.team2_id
            ORDER BY m.match_date, m.match_time""").fetchall()
    if not rows:
        return "No matches yet."
    out = []
    for r in rows:
        score = (f"{r['score1']}-{r['score2']}"
                 if r["score1"] is not None else "not played")
        out.append(f"#{r['id']} {r['a']} vs {r['b']} | {r['match_date']} "
                   f"{r['match_time']} | {r['court']} | {score}")
    return "\n".join(out)


@tool
@traced
def avoid_weekday(day: str) -> str:
    """Remember that no matches should be scheduled on this weekday, e.g. 'sunday'."""
    names = ["monday", "tuesday", "wednesday", "thursday",
             "friday", "saturday", "sunday"]
    d = day.strip().lower()
    if d not in names:
        return f"'{day}' is not a weekday name."
    mem = load_memory()
    avoid = set(mem.get("avoid_days", []))
    avoid.add(names.index(d))
    mem["avoid_days"] = sorted(avoid)
    save_memory(mem)
    return (f"Saved. Matches will not be scheduled on {d.title()}. "
            "Run the schedule again to apply it.")


TOOLS = [add_team, withdraw_team, generate_schedule, find_conflicts,
         record_result, standings, list_matches, avoid_weekday]

llm = ChatOllama(model="qwen2.5:3b", temperature=0)

try:
    from langchain.agents import create_agent
    agent = create_agent(llm, TOOLS, system_prompt=SYSTEM)
except ImportError:
    from langgraph.prebuilt import create_react_agent
    agent = create_react_agent(llm, TOOLS, prompt=SYSTEM)


# ---------- input guardrail ----------
def check_input(text):
    low = text.lower()
    if len(text) > 500:
        return "Blocked: message too long (max 500 characters)."
    for phrase in BLOCKED:
        if phrase in low:
            return "Blocked: that request is not allowed."
    return None


# ---------- feedback adaptation ----------
def adaptive_note():
    scores = []
    try:
        with open(TRACE_FILE, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("type") == "feedback":
                    scores.append(rec["score"])
    except (OSError, ValueError):
        return ""
    recent = scores[-5:]
    if recent and sum(recent) / len(recent) < 3:
        return ("\n[Recent user ratings were low. Explain each step briefly "
                "and confirm key details before acting.]")
    return ""


# ---------- main loop ----------
if __name__ == "__main__":
    messages = []
    print("Tournament manager ready. Type 'quit' to exit.")
    while True:
        text = input("\nYou: ").strip()
        if text.lower() in ("quit", "exit"):
            break
        if not text:
            continue

        problem = check_input(text)
        if problem:
            log("blocked", input=text, reason=problem)
            print("\nAgent:", problem)
            continue

        if text.lower() in ("yes", "y", "confirm") and PENDING["name"]:
            APPROVED.add(PENDING["name"].lower())
            text = f"Confirmed. Withdraw team {PENDING['name']}."
            PENDING["name"] = None

        mem = load_memory()
        prompt = text
        if mem:
            prompt = f"[Saved preferences: {json.dumps(mem)}]\n{text}"
        prompt += adaptive_note()

        log("user", input=text)
        start = time.time()
        try:
            result = agent.invoke({"messages": messages + [
                {"role": "user", "content": prompt}]})
            messages = result["messages"]
            reply = messages[-1].content
        except Exception as e:
            reply = f"Sorry, something went wrong: {e}"
        log("reply", output=reply, seconds=round(time.time() - start, 2))
        print("\nAgent:", reply)

        fb = input("Rate 1-5 (Enter to skip): ").strip()
        if fb in ("1", "2", "3", "4", "5"):
            log("feedback", score=int(fb))