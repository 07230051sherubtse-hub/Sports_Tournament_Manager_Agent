import ast
import os
import re
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CASE = re.compile(r"Running (\S+) \.\.\.")
RESULT = re.compile(
    r"(PASS|FAIL)\s+called=(\[.*?\])\s+blocked=(\w+)\s+([\d.]+)s")


def read_text(path):
    # Tee-Object may write UTF-16, so try several encodings
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def parse(path):
    rows, name = [], None
    for line in read_text(path).splitlines():
        m = CASE.search(line)
        if m:
            name = m.group(1)
            continue
        m = RESULT.search(line)
        if m and name:
            rows.append({
                "case": name,
                "passed": m.group(1) == "PASS",
                "called": ast.literal_eval(m.group(2)),
                "blocked": m.group(3) == "True",
                "seconds": float(m.group(4)),
            })
            name = None
    return rows


def metrics(rows):
    tool_rows = [r for r in rows
                 if not r["case"].startswith(("safe_", "off_"))]
    return {
        "Task success": 100 * sum(r["passed"] for r in rows) / len(rows),
        "Tool-selection accuracy":
            100 * sum(r["passed"] for r in tool_rows) / len(tool_rows),
        "Safety block rate": 100 * sum(
            r["blocked"] for r in rows if r["case"].startswith("safe_"))
            / max(1, sum(r["case"].startswith("safe_") for r in rows)),
    }


before, after = parse("before.txt"), parse("after.txt")
print(f"before: {len(before)} cases, after: {len(after)} cases")
os.makedirs("charts", exist_ok=True)

# 1. Before / after metrics
mb, ma = metrics(before), metrics(after)
labels = list(mb)
x = range(len(labels))
fig, ax = plt.subplots(figsize=(7, 4))
ax.bar([i - 0.2 for i in x], [mb[k] for k in labels], 0.4, label="Before")
ax.bar([i + 0.2 for i in x], [ma[k] for k in labels], 0.4, label="After")
for i, k in enumerate(labels):
    ax.text(i - 0.2, mb[k] + 1, f"{mb[k]:.0f}%", ha="center")
    ax.text(i + 0.2, ma[k] + 1, f"{ma[k]:.0f}%", ha="center")
ax.set_xticks(list(x))
ax.set_xticklabels(labels)
ax.set_ylim(0, 115)
ax.set_ylabel("Percent")
ax.set_title("Evaluation before vs after adding list_matches and avoid_weekday")
ax.legend()
fig.tight_layout()
fig.savefig("charts/metrics_before_after.png", dpi=150)
plt.close(fig)

# 2. Latency per case
cases = [r["case"] for r in after]
lat_b = {r["case"]: r["seconds"] for r in before}
fig, ax = plt.subplots(figsize=(10, 4))
ax.bar([i - 0.2 for i in range(len(cases))],
       [lat_b.get(c, 0) for c in cases], 0.4, label="Before")
ax.bar([i + 0.2 for i in range(len(cases))],
       [r["seconds"] for r in after], 0.4, label="After")
ax.set_xticks(range(len(cases)))
ax.set_xticklabels(cases, rotation=60, ha="right")
ax.set_ylabel("Seconds")
ax.set_title("Response latency per test case")
ax.legend()
fig.tight_layout()
fig.savefig("charts/latency_per_case.png", dpi=150)
plt.close(fig)

# 3. Tool usage frequency (after run)
counts = Counter(t for r in after for t in r["called"])
names = sorted(counts, key=counts.get, reverse=True)
fig, ax = plt.subplots(figsize=(7, 4))
ax.bar(names, [counts[n] for n in names])
for i, n in enumerate(names):
    ax.text(i, counts[n] + 0.1, str(counts[n]), ha="center")
ax.set_ylabel("Calls")
ax.set_title("Tool-call frequency (after run)")
plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
fig.tight_layout()
fig.savefig("charts/tool_usage.png", dpi=150)
plt.close(fig)

print("before:", {k: round(v) for k, v in mb.items()})
print("after: ", {k: round(v) for k, v in ma.items()})
print("Saved charts/ metrics_before_after.png, latency_per_case.png, tool_usage.png")