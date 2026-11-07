import os
import tools

tools.DB = "test_tournament.db"
if os.path.exists(tools.DB):
    os.remove(tools.DB)
tools.init_db()

for n in ["Lions", "Tigers", "Eagles", "Wolves"]:
    print(tools.add_team(n))
print(tools.add_team("Lions"))
print(tools.add_team("x"))
print(tools.generate_schedule("2026-11-09", ["Court 1", "Court 2"], ["09:00", "11:00"], [6]))
print(tools.find_conflicts())
print(tools.record_result(1, 2, 1))
print(tools.record_result(1, 2, 1))
print(tools.record_result(999, 1, 1))
print(tools.standings())
print(tools.withdraw_team("Wolves"))
print(tools.standings())