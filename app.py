import json
import os
import time
from contextlib import closing

import pandas as pd
import streamlit as st

import agent
import tools


# =====================================================
# 1. PAGE CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="Sports Tournament Manager",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =====================================================
# 2. SESSION STATE
# =====================================================

defaults = {
    "history": [],
    "chat": [],
    "rated": set(),
    "page": "Tournament Dashboard",
    "sidebar_page": "Tournament Dashboard",
    "queued": None
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =====================================================
# 3. CUSTOM CSS
# =====================================================

st.markdown("""
<style>

.stApp {
    background-color: #f5f4fc;
}

header[data-testid="stHeader"] {
    background: transparent;
}

.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}

section[data-testid="stSidebar"] {
    background-color: #e9eafa;
    border-right: 1px solid #d6d8ed;
}

section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #172554;
}

.top-header {
    background: #101b50;
    padding: 22px 28px;
    border-radius: 12px;
    color: white;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    min-height: 110px;
}

.brand {
    font-size: 22px;
    font-weight: 800;
    letter-spacing: 1px;
}

.project-name {
    font-size: 21px;
    font-weight: 650;
}

.status-pill {
    background: #26376e;
    padding: 7px 12px;
    border-radius: 20px;
    font-size: 12px;
    white-space: nowrap;
}

.navbar {
    background: linear-gradient(90deg, #7026dc, #176fed);
    padding: 7px 12px;
    border-radius: 10px;
    margin-bottom: 24px;
}

div.stButton > button {
    border-radius: 9px;
    border: 1px solid #d5d8e8;
    font-weight: 600;
    min-height: 42px;
    transition: 0.2s;
}

div.stButton > button:hover {
    border-color: #7138dd;
    color: #7138dd;
}

.dashboard-card {
    background: white;
    border: 1px solid #e5e5ee;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 5px 22px rgba(0,0,0,0.05);
    margin-bottom: 12px;
}

.agent-header {
    background: linear-gradient(110deg, #edf6e6, #f4f8ed);
    padding: 20px;
    border-radius: 14px;
    margin-bottom: 18px;
}

.agent-header h3 {
    color: #101b50;
    margin: 0;
    font-size: 23px;
}

.agent-header p {
    color: #53627a;
    margin: 5px 0 0 0;
}

.welcome-title {
    font-size: 23px;
    font-weight: 700;
    color: #101b50;
    margin-top: 10px;
}

.welcome-description {
    color: #64748b;
    font-size: 15px;
    line-height: 1.6;
}

.section-heading {
    color: #172554;
    font-weight: 700;
    font-size: 18px;
    margin-bottom: 10px;
}

div[data-testid="stMetric"] {
    background: white;
    border: 1px solid #e6e6ee;
    padding: 15px;
    border-radius: 12px;
}

div[data-testid="stChatInput"] {
    border-radius: 15px;
}

.footer {
    text-align: center;
    color: #8991a7;
    font-size: 12px;
    padding: 15px;
}

@media (max-width: 768px) {
    .top-header {
        flex-direction: column;
        align-items: flex-start;
    }

    .project-name {
        font-size: 17px;
    }
}

</style>
""", unsafe_allow_html=True)


# =====================================================
# 4. DATABASE FUNCTIONS
# =====================================================

def query_df(sql, columns=None):

    with closing(tools._conn()) as connection:
        rows = connection.execute(sql).fetchall()

    if rows:
        return pd.DataFrame([dict(row) for row in rows])

    return pd.DataFrame(columns=columns or [])


def ensure_team_category_column():

    """
    Add category to the existing teams table if missing.
    Existing team records will not be deleted.
    """

    with closing(tools._conn()) as connection:

        columns = [
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(teams)"
            ).fetchall()
        ]

        if "category" not in columns:

            connection.execute("""
                ALTER TABLE teams
                ADD COLUMN category TEXT DEFAULT 'Uncategorized'
            """)

            connection.commit()


ensure_team_category_column()


def get_teams():

    return query_df(
        """
        SELECT id, name, category, active
        FROM teams
        ORDER BY category, name
        """,
        ["id", "name", "category", "active"]
    )


def get_matches():

    return query_df(
        """
        SELECT
            m.id AS match_id,
            t1.name AS team1,
            t2.name AS team2,
            m.match_date AS date,
            m.match_time AS time,
            m.court,
            m.score1,
            m.score2
        FROM matches m
        JOIN teams t1 ON t1.id = m.team1_id
        JOIN teams t2 ON t2.id = m.team2_id
        ORDER BY m.match_date, m.match_time, m.court
        """,
        [
            "match_id",
            "team1",
            "team2",
            "date",
            "time",
            "court",
            "score1",
            "score2"
        ]
    )


def load_trace():

    output = []

    if os.path.exists(agent.TRACE_FILE):

        with open(agent.TRACE_FILE, encoding="utf-8") as file:

            for line in file:

                try:
                    output.append(json.loads(line))

                except ValueError:
                    pass

    return output


# =====================================================
# 5. NAVIGATION FUNCTIONS
# =====================================================

VALID_PAGES = [
    "Tournament Dashboard",
    "AI Assistant",
    "Teams",
    "Fixtures & Schedule",
    "Results",
    "Standings",
    "Analytics"
]


def navigate_to(page):

    if page in VALID_PAGES:

        st.session_state.page = page
        st.session_state.sidebar_page = page


def sync_sidebar_navigation():

    st.session_state.page = st.session_state.sidebar_page


def queue_prompt(prompt):

    st.session_state.queued = prompt
    navigate_to("AI Assistant")


WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"]

GENERATE_PROMPT = (
    "Generate tournament fixtures using my saved preferences if I have "
    "any, otherwise ask me for the details."
)


def submit_fixtures():
    s = st.session_state
    days = s.get("fx_days") or WEEKDAYS[:6]
    numbers = [WEEKDAYS.index(d) for d in days]
    queue_prompt(
        f"Create a round-robin schedule starting {s.fx_start.isoformat()} "
        f"using courts {s.fx_courts} at times {s.fx_times} "
        f"on days_of_week {numbers} ({', '.join(days)})."
    )


# =====================================================
# 6. AGENT FUNCTIONS
# =====================================================

def run_agent(user_text):

    problem = agent.check_input(user_text)

    if problem:

        agent.log(
            "blocked",
            input=user_text,
            reason=problem
        )

        return problem

    memory = agent.load_memory()

    prompt = (
        f"[Saved preferences: {json.dumps(memory)}]\n{user_text}"
        if memory else user_text
    )

    if hasattr(agent, "adaptive_note"):
        prompt += agent.adaptive_note()

    agent.log("user", input=user_text)

    start = time.time()

    try:

        result = agent.agent.invoke({
            "messages": st.session_state.history + [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        })

        st.session_state.history = result["messages"]

        reply = result["messages"][-1].content

    except Exception as error:

        reply = f"Sorry, something went wrong: {error}"

    agent.log(
        "reply",
        output=reply,
        seconds=round(time.time() - start, 2)
    )

    return reply


# =====================================================
# 7. TOP HEADER
# =====================================================

st.markdown("""
<div class="top-header">
    <div class="brand">🏆 SPORTS AI</div>
    <div class="project-name">Sports Tournament Manager</div>
    <div class="status-pill">● AI AGENT</div>
</div>
""", unsafe_allow_html=True)


# =====================================================
# 8. MAIN NAVIGATION
# =====================================================

st.markdown(
    '<div class="navbar">',
    unsafe_allow_html=True
)

nav1, nav2, nav3, nav4 = st.columns(4)

with nav1:

    st.button(
        "🏠 DASHBOARD",
        width="stretch",
        type="primary"
        if st.session_state.page == "Tournament Dashboard"
        else "secondary",
        on_click=navigate_to,
        args=("Tournament Dashboard",),
        key="top_dashboard"
    )

with nav2:

    tournament_pages = [
        "Teams",
        "Fixtures & Schedule",
        "Results",
        "Standings"
    ]

    st.button(
        "🏆 TOURNAMENT",
        width="stretch",
        type="primary"
        if st.session_state.page in tournament_pages
        else "secondary",
        on_click=navigate_to,
        args=("Teams",),
        key="top_tournament"
    )

with nav3:

    st.button(
        "🤖 AI ASSISTANT",
        width="stretch",
        type="primary"
        if st.session_state.page == "AI Assistant"
        else "secondary",
        on_click=navigate_to,
        args=("AI Assistant",),
        key="top_ai"
    )

with nav4:

    st.button(
        "📊 ANALYTICS",
        width="stretch",
        type="primary"
        if st.session_state.page == "Analytics"
        else "secondary",
        on_click=navigate_to,
        args=("Analytics",),
        key="top_analytics"
    )

st.markdown('</div>', unsafe_allow_html=True)


# =====================================================
# 9. SIDEBAR NAVIGATION
# =====================================================

st.sidebar.markdown("## 🏆 TOURNAMENT MENU")

st.sidebar.caption("SPORTS TOURNAMENT MANAGEMENT")

st.sidebar.radio(
    "Select Page",
    VALID_PAGES,
    key="sidebar_page",
    on_change=sync_sidebar_navigation,
    label_visibility="collapsed"
)

# Use the synchronized page
page = st.session_state.page

st.sidebar.divider()


# =====================================================
# 10. SIDEBAR QUICK ACTIONS
# =====================================================

st.sidebar.markdown("### ⚡ Quick Actions")

st.sidebar.button(
    "🏠 Open Dashboard",
    width="stretch",
    on_click=navigate_to,
    args=("Tournament Dashboard",)
)

st.sidebar.button(
    "👥 Register Teams",
    width="stretch",
    on_click=navigate_to,
    args=("Teams",)
)

st.sidebar.button(
    "🏆 Create Tournament",
    width="stretch",
    on_click=queue_prompt,
    args=("Help me create a new sports tournament.",)
)

st.sidebar.button(
    "📅 Generate Fixtures",
    width="stretch",
    on_click=queue_prompt,
    args=(GENERATE_PROMPT,)
)

st.sidebar.button(
    "⚠️ Check Conflicts",
    width="stretch",
    on_click=queue_prompt,
    args=("Check the tournament schedule for conflicts.",)
)

st.sidebar.button(
    "📊 Show Standings",
    width="stretch",
    on_click=navigate_to,
    args=("Standings",)
)

st.sidebar.divider()


# =====================================================
# 11. SAVED PREFERENCES
# =====================================================

st.sidebar.markdown("### 🧠 Saved Preferences")

memory = agent.load_memory()

if memory:

    st.sidebar.json(memory)

    if st.sidebar.button(
        "Clear Preferences",
        width="stretch"
    ):

        agent.save_memory({})
        st.rerun()

else:

    st.sidebar.caption("No saved preferences yet.")


st.sidebar.divider()

st.sidebar.caption("DAT404 | Sports Tournament Manager")


# =====================================================
# 12. LOAD DATABASE INFORMATION
# =====================================================

teams = get_teams()
matches = get_matches()

total_teams = len(teams)

if not teams.empty:

    active_teams = int(
        (teams["active"] == 1).sum()
    )

    withdrawn_teams = total_teams - active_teams

else:

    active_teams = 0
    withdrawn_teams = 0


total_matches = len(matches)

if not matches.empty:

    completed_mask = (
        matches["score1"].notna()
        & matches["score2"].notna()
        & matches["score1"].astype(str).str.strip().ne("")
        & matches["score2"].astype(str).str.strip().ne("")
    )

    completed_matches = int(completed_mask.sum())

    today = pd.Timestamp.today().normalize()

    match_dates = pd.to_datetime(
        matches["date"],
        errors="coerce"
    )

    upcoming_mask = (
        (match_dates >= today)
        & (~completed_mask)
    )

    upcoming_matches = int(upcoming_mask.sum())

else:

    completed_mask = pd.Series(dtype=bool)
    completed_matches = 0
    upcoming_matches = 0


pending_matches = total_matches - completed_matches


# =====================================================
# 13. REUSABLE PAGE NAVIGATION
# =====================================================

def show_page_navigation():

    st.divider()
    st.subheader("Quick Navigation")

    c1, c2, c3 = st.columns(3)

    with c1:

        st.button(
            "🏠 Dashboard",
            width="stretch",
            on_click=navigate_to,
            args=("Tournament Dashboard",),
            key=f"nav_dashboard_{page}"
        )

    with c2:

        st.button(
            "👥 Teams",
            width="stretch",
            on_click=navigate_to,
            args=("Teams",),
            key=f"nav_teams_{page}"
        )

    with c3:

        st.button(
            "🤖 AI Assistant",
            width="stretch",
            on_click=navigate_to,
            args=("AI Assistant",),
            key=f"nav_ai_{page}"
        )


# =====================================================
# 14. TOURNAMENT DASHBOARD
# =====================================================

if page == "Tournament Dashboard":

    st.title("🏆 Tournament Dashboard")

    st.caption(
        "Monitor your sports tournament activities, "
        "teams, fixtures and match results in one place."
    )

    st.divider()

    st.subheader("Tournament Overview")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total Teams", total_teams)
    c2.metric("Active Teams", active_teams)
    c3.metric("Total Matches", total_matches)
    c4.metric("Completed Matches", completed_matches)

    c5, c6, c7 = st.columns(3)

    c5.metric("Upcoming Matches", upcoming_matches)
    c6.metric("Pending Matches", pending_matches)
    c7.metric("Withdrawn Teams", withdrawn_teams)

    st.divider()

    st.subheader("Supported Sports")

    sport1, sport2, sport3, sport4 = st.columns(4)

    sport1.info("⚽ Football")
    sport2.info("🏀 Basketball")
    sport3.info("🏐 Volleyball")
    sport4.info("🏸 Badminton")

    st.subheader("Tournament Formats")

    format1, format2 = st.columns(2)

    format1.info("🏆 Knockout Tournament")
    format2.info("🔄 Round-Robin Tournament")

    st.divider()

    left, right = st.columns(2)

    with left:

        st.subheader("Team Overview by Sport")

        if not teams.empty:

            category_summary = teams.copy()

            category_summary["category"] = (
                category_summary["category"].fillna("Uncategorized")
            )

            category_counts = (
                category_summary.groupby("category")
                .size()
                .reset_index(name="Teams")
                .set_index("category")
            )

            st.bar_chart(category_counts)

        else:

            st.info("No teams registered yet.")

    with right:

        st.subheader("Match Overview")

        if total_matches > 0:

            match_status = pd.DataFrame({
                "Status": ["Completed", "Pending"],
                "Matches": [
                    completed_matches,
                    pending_matches
                ]
            })

            st.bar_chart(
                match_status.set_index("Status")
            )

        else:

            st.info("No matches generated yet.")

    st.divider()

    st.subheader("📅 Upcoming Fixtures")

    if not matches.empty:

        upcoming = matches.loc[
            upcoming_mask
        ].copy()

        if not upcoming.empty:

            st.dataframe(
                upcoming[
                    [
                        "match_id",
                        "team1",
                        "team2",
                        "date",
                        "time",
                        "court"
                    ]
                ],
                width="stretch",
                hide_index=True
            )

        else:

            st.info("There are no upcoming matches.")

    else:

        st.info("Generate fixtures to see upcoming matches.")

    st.divider()

    st.subheader("Quick Navigation")

    q1, q2, q3 = st.columns(3)

    with q1:

        st.button(
            "👥 Manage Teams",
            width="stretch",
            on_click=navigate_to,
            args=("Teams",)
        )

    with q2:

        st.button(
            "📅 View Fixtures",
            width="stretch",
            on_click=navigate_to,
            args=("Fixtures & Schedule",)
        )

    with q3:

        st.button(
            "🤖 Open AI Assistant",
            width="stretch",
            on_click=navigate_to,
            args=("AI Assistant",)
        )


# =====================================================
# 15. AI TOURNAMENT ASSISTANT
# =====================================================

elif page == "AI Assistant":

    st.markdown(
        '<div class="section-heading">SPORTS TOURNAMENT AI ASSISTANT</div>',
        unsafe_allow_html=True
    )

    left, center, right = st.columns([1, 3, 1])

    with center:

        st.markdown("""
        <div class="agent-header">
            <h3>🤖 Sports Tournament AI</h3>
            <p>Your intelligent tournament management assistant</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(
            '<div class="welcome-title">Welcome! How can I help?</div>',
            unsafe_allow_html=True
        )

        st.markdown("""
        <div class="welcome-description">
        I can help you manage your sports tournaments.
        Register teams, create tournaments, generate fixtures,
        schedule matches, check conflicts, record results
        and calculate tournament standings.
        </div>
        """, unsafe_allow_html=True)

        st.write("")

        st.markdown("#### Explore options")

        q1, q2, q3 = st.columns(3)

        with q1:

            st.button(
                "🏆 Create Tournament",
                width="stretch",
                on_click=queue_prompt,
                args=("Help me create a new tournament.",)
            )

        with q2:

            st.button(
                "📅 Generate Fixtures",
                width="stretch",
                on_click=queue_prompt,
                args=(GENERATE_PROMPT,)
            )

        with q3:

            st.button(
                "📊 View Standings",
                width="stretch",
                on_click=queue_prompt,
                args=("Show the tournament standings.",)
            )

        st.divider()

        chat_tab, tools_tab, history_tab = st.tabs([
            "💬 Chat",
            "🛠️ Tools",
            "🕘 History"
        ])

        # -------------------------------------------------
        # CHAT TAB
        # -------------------------------------------------

        with chat_tab:

            st.caption(
                "Example: Register teams Lions, Tigers and Eagles "
                "for a football tournament."
            )

            text = st.chat_input(
                "Ask your Sports Tournament Manager..."
            )

            if not text:

                text = st.session_state.pop(
                    "queued",
                    None
                )

            if text:

                st.session_state.chat.append({
                    "role": "user",
                    "content": text
                })

                with st.spinner(
                    "Sports AI is processing your request..."
                ):

                    reply = run_agent(text)

                st.session_state.chat.append({
                    "role": "assistant",
                    "content": reply
                })

                st.rerun()

            for i, message in enumerate(st.session_state.chat):

                with st.chat_message(message["role"]):

                    st.write(message["content"])

                    if message["role"] == "assistant":

                        stars = st.feedback(
                            "stars",
                            key=f"feedback_{i}"
                        )

                        if (
                            stars is not None
                            and i not in st.session_state.rated
                        ):

                            st.session_state.rated.add(i)

                            agent.log(
                                "feedback",
                                score=stars + 1
                            )

            pending = agent.PENDING.get("name")

            if pending:

                st.warning(
                    f"Confirm withdrawing **{pending}**? "
                    "This cancels their unplayed matches."
                )

                c1, c2, _ = st.columns([1, 1, 4])

                if c1.button(
                    "Confirm",
                    type="primary"
                ):

                    agent.APPROVED.add(pending.lower())

                    agent.PENDING["name"] = None

                    st.session_state.queued = (
                        f"Confirmed. Withdraw team {pending}."
                    )

                    st.rerun()

                if c2.button("Cancel"):

                    agent.PENDING["name"] = None

                    st.rerun()

        # -------------------------------------------------
        # TOOLS TAB
        # -------------------------------------------------

        with tools_tab:

            st.subheader("Available Agent Tools")

            tool_data = [
                ("👥", "Team Registration",
                 "Register and manage tournament teams."),
                ("🏆", "Tournament Management",
                 "Create and configure tournaments."),
                ("📅", "Fixture Generation",
                 "Generate knockout and round-robin fixtures."),
                ("⏰", "Match Scheduling",
                 "Allocate match dates, times and courts."),
                ("✅", "Conflict Checking",
                 "Detect scheduling and venue conflicts."),
                ("⚽", "Score Management",
                 "Record match results."),
                ("📊", "Standings Calculation",
                 "Calculate tournament standings."),
                ("📈", "Tournament Analytics",
                 "Review tournament activity and performance.")
            ]

            for icon, name, description in tool_data:

                with st.container(border=True):

                    st.markdown(f"**{icon} {name}**")
                    st.caption(description)

            st.info(
                "Your Python agent and tools module execute "
                "the actual tournament operations."
            )

        # -------------------------------------------------
        # HISTORY TAB
        # -------------------------------------------------

        with history_tab:

            st.subheader("Conversation History")

            if not st.session_state.chat:

                st.info("No conversations yet.")

            else:

                for message in st.session_state.chat:

                    with st.container(border=True):

                        st.markdown(
                            f"**{message['role'].capitalize()}**"
                        )

                        st.write(message["content"])

    show_page_navigation()


# =====================================================
# 16. TEAMS - REGISTRATION AND MANAGEMENT
# =====================================================

elif page == "Teams":

    st.title("👥 Team Management")

    st.caption(
        "Register teams under different sports categories "
        "and manage tournament participants."
    )

    st.divider()

    st.subheader("➕ Register a New Team")

    with st.container(border=True):

        with st.form(
            "register_team_form",
            clear_on_submit=True
        ):

            team_name = st.text_input(
                "Team Name",
                placeholder="Example: Thunder FC"
            )

            category = st.selectbox(
                "Sport Category",
                [
                    "Football",
                    "Basketball",
                    "Volleyball",
                    "Badminton"
                ]
            )

            submitted = st.form_submit_button(
                "➕ Register Team",
                width="stretch",
                type="primary"
            )

            if submitted:

                clean_name = team_name.strip()

                if not clean_name:

                    st.error("Please enter a team name.")

                else:

                    try:

                        with closing(tools._conn()) as connection:

                            existing = connection.execute(
                                """
                                SELECT id
                                FROM teams
                                WHERE LOWER(name) = LOWER(?)
                                AND LOWER(
                                    COALESCE(category, 'Uncategorized')
                                ) = LOWER(?)
                                """,
                                (clean_name, category)
                            ).fetchone()

                            if existing:

                                st.warning(
                                    f"{clean_name} is already registered "
                                    f"under {category}."
                                )

                            else:

                                connection.execute(
                                    """
                                    INSERT INTO teams
                                    (name, category, active)
                                    VALUES (?, ?, 1)
                                    """,
                                    (clean_name, category)
                                )

                                connection.commit()

                                st.success(
                                    f"{clean_name} successfully registered "
                                    f"under {category}!"
                                )

                                st.rerun()

                    except Exception as error:

                        st.error(
                            f"Unable to register team: {error}"
                        )

    st.divider()

    st.subheader("📊 Teams by Sport Category")

    sport_categories = [
        "Football",
        "Basketball",
        "Volleyball",
        "Badminton"
    ]

    category_columns = st.columns(4)

    for index, sport in enumerate(sport_categories):

        if teams.empty:
            sport_count = 0

        else:
            sport_count = int(
                (
                    teams["category"].fillna("Uncategorized")
                    == sport
                ).sum()
            )

        category_columns[index].metric(
            sport,
            sport_count
        )

    st.divider()

    st.subheader("📋 Registered Teams")

    if not teams.empty:

        filter1, filter2, filter3 = st.columns(3)

        with filter1:

            category_filter = st.selectbox(
                "Filter by Sport",
                ["All Sports"] + sport_categories + ["Uncategorized"]
            )

        with filter2:

            status_filter = st.selectbox(
                "Filter by Status",
                ["All", "Active", "Withdrawn"]
            )

        with filter3:

            search_team = st.text_input(
                "Search Team",
                placeholder="Enter team name..."
            )

        filtered_teams = teams.copy()

        filtered_teams["category"] = (
            filtered_teams["category"].fillna("Uncategorized")
        )

        if category_filter != "All Sports":

            filtered_teams = filtered_teams[
                filtered_teams["category"] == category_filter
            ]

        if status_filter == "Active":

            filtered_teams = filtered_teams[
                filtered_teams["active"] == 1
            ]

        elif status_filter == "Withdrawn":

            filtered_teams = filtered_teams[
                filtered_teams["active"] == 0
            ]

        if search_team:

            filtered_teams = filtered_teams[
                filtered_teams["name"].str.contains(
                    search_team,
                    case=False,
                    na=False
                )
            ]

        display_teams = filtered_teams.copy()

        display_teams["active"] = display_teams["active"].map({
            1: "Active",
            0: "Withdrawn"
        })

        display_teams = display_teams.rename(columns={
            "id": "Team ID",
            "name": "Team Name",
            "category": "Sport Category",
            "active": "Status"
        })

        st.dataframe(
            display_teams,
            width="stretch",
            hide_index=True
        )

        st.caption(
            f"Showing {len(filtered_teams)} "
            f"of {len(teams)} registered teams."
        )

    else:

        st.info(
            "No teams registered yet. "
            "Use the form above to register your first team."
        )

    st.divider()

    st.subheader("🤖 AI Team Management")

    st.write(
        "You can also ask the AI Assistant to register or manage teams "
        "using natural-language instructions."
    )

    st.button(
        "🤖 Open AI Assistant",
        width="stretch",
        on_click=navigate_to,
        args=("AI Assistant",)
    )

    show_page_navigation()


# =====================================================
# 17. FIXTURES AND SCHEDULE
# =====================================================

elif page == "Fixtures & Schedule":

    st.title("📅 Fixtures & Match Schedule")

    st.caption(
        "View and filter tournament fixtures and scheduled matches."
    )

    st.divider()

    if not matches.empty:

        completed = (
            matches["score1"].notna()
            & matches["score2"].notna()
            & matches["score1"].astype(str).str.strip().ne("")
            & matches["score2"].astype(str).str.strip().ne("")
        )

        today = pd.Timestamp.today().normalize()

        dates = pd.to_datetime(
            matches["date"],
            errors="coerce"
        )

        upcoming = (
            (dates >= today)
            & (~completed)
        )

        matches_display = matches.copy()

        matches_display["status"] = "Pending"

        matches_display.loc[
            completed,
            "status"
        ] = "Completed"

        matches_display.loc[
            upcoming,
            "status"
        ] = "Upcoming"

        f1, f2, f3 = st.columns(3)

        with f1:

            status_filter = st.selectbox(
                "Match Status",
                [
                    "All",
                    "Upcoming",
                    "Completed",
                    "Pending"
                ]
            )

        with f2:

            team_options = ["All Teams"]

            team_names = sorted(
                set(matches["team1"].dropna().tolist())
                | set(matches["team2"].dropna().tolist())
            )

            team_options.extend(team_names)

            selected_team = st.selectbox(
                "Filter by Team",
                team_options
            )

        with f3:

            court_options = ["All Courts"]

            courts = sorted(
                matches["court"].dropna().astype(str).unique()
            )

            court_options.extend(courts)

            selected_court = st.selectbox(
                "Filter by Court",
                court_options
            )

        filtered_matches = matches_display.copy()

        if status_filter != "All":

            filtered_matches = filtered_matches[
                filtered_matches["status"] == status_filter
            ]

        if selected_team != "All Teams":

            filtered_matches = filtered_matches[
                (
                    filtered_matches["team1"] == selected_team
                )
                |
                (
                    filtered_matches["team2"] == selected_team
                )
            ]

        if selected_court != "All Courts":

            filtered_matches = filtered_matches[
                filtered_matches["court"].astype(str)
                == selected_court
            ]

        st.dataframe(
            filtered_matches,
            width="stretch",
            hide_index=True
        )

        st.caption(
            f"Displaying {len(filtered_matches)} matches."
        )

    else:

        st.info(
            "No fixtures available. Ask the AI Assistant "
            "to generate tournament fixtures."
        )

    st.divider()

    st.subheader("⚠️ Schedule Conflict Check")

    if st.button(
        "Check Schedule Conflicts",
        width="stretch"
    ):

        try:

            conflicts = tools.find_conflicts()

            st.write(conflicts)

        except Exception as error:

            st.error(
                f"Unable to check conflicts: {error}"
            )

    st.subheader("📅 Generate Fixtures")

    with st.form("fixtures_form"):

        fc1, fc2 = st.columns(2)

        fc1.date_input("Start date", key="fx_start")
        fc2.text_input("Courts (comma-separated)",
                       "Court 1, Court 2", key="fx_courts")
        fc1.text_input("Match times (comma-separated)",
                       "09:00, 11:00", key="fx_times")
        fc2.multiselect("Days of the week", WEEKDAYS,
                        default=WEEKDAYS[:6], key="fx_days")

        st.form_submit_button(
            "🤖 Generate with AI",
            type="primary",
            width="stretch",
            on_click=submit_fixtures
        )

    show_page_navigation()


# =====================================================
# 18. RESULTS
# =====================================================

elif page == "Results":

    st.title("⚽ Match Results")

    st.caption(
        "Review completed matches and their recorded scores."
    )

    st.divider()

    if not matches.empty:

        results = matches[
            completed_mask
        ].copy()

        if not results.empty:

            results["Score"] = (
                results["score1"].astype(str)
                + " - "
                + results["score2"].astype(str)
            )

            st.dataframe(
                results[
                    [
                        "match_id",
                        "team1",
                        "team2",
                        "date",
                        "court",
                        "Score"
                    ]
                ],
                width="stretch",
                hide_index=True
            )

            st.metric(
                "Matches with Recorded Results",
                len(results)
            )

        else:

            st.info(
                "No match results have been recorded yet."
            )

    else:

        st.info(
            "There are no matches available yet."
        )

    st.divider()

    st.subheader("Record or Update Results")

    st.write(
        "Use the AI Assistant to record match scores "
        "or update an existing result."
    )

    st.button(
        "⚽ Record Results with AI",
        width="stretch",
        on_click=queue_prompt,
        args=("Help me record a match result.",)
    )

    show_page_navigation()


# =====================================================
# 19. STANDINGS
# =====================================================

elif page == "Standings":

    st.title("🏆 Tournament Standings")

    st.caption(
        "View current tournament rankings and team performance."
    )

    st.divider()

    try:

        standings_result = tools.standings()

        st.subheader("Current Rankings")

        rows = []

        for line in str(standings_result).splitlines()[1:]:

            parts = line.split()

            if (
                len(parts) >= 9
                and all(p.lstrip("-").isdigit() for p in parts[-8:])
            ):

                rows.append(
                    [" ".join(parts[:-8])]
                    + [int(p) for p in parts[-8:]]
                )

        if rows:

            st.dataframe(
                pd.DataFrame(
                    rows,
                    columns=[
                        "Team", "P", "W", "D", "L",
                        "GF", "GA", "GD", "Pts"
                    ]
                ),
                width="stretch",
                hide_index=True
            )

        else:

            st.code(str(standings_result))

    except Exception as error:

        st.error(
            f"Unable to retrieve standings: {error}"
        )

    st.divider()

    st.info(
        "Standings are calculated by your Python tools module."
    )

    st.button(
        "🔄 Refresh Standings",
        width="stretch",
        on_click=navigate_to,
        args=("Standings",)
    )

    show_page_navigation()


# =====================================================
# 20. ANALYTICS
# =====================================================

elif page == "Analytics":

    st.title("📊 Tournament and Agent Analytics")

    st.caption(
        "Monitor tournament activity and AI agent performance."
    )

    st.divider()

    trace = load_trace()

    st.subheader("Tournament Statistics")

    a, b, c, d = st.columns(4)

    a.metric("Total Teams", total_teams)
    b.metric("Total Matches", total_matches)
    c.metric("Completed Matches", completed_matches)
    d.metric("Upcoming Matches", upcoming_matches)

    st.divider()

    st.subheader("AI Agent Performance")

    if not trace:

        st.info(
            "No agent activity recorded yet. "
            "Start using the AI Assistant."
        )

    else:

        calls = pd.DataFrame([
            item for item in trace
            if item.get("type") == "tool"
        ])

        replies = pd.DataFrame([
            item for item in trace
            if item.get("type") == "reply"
        ])

        feedback = [
            item["score"]
            for item in trace
            if item.get("type") == "feedback"
        ]

        blocked = sum(
            1 for item in trace
            if item.get("type") == "blocked"
        )

        requests = sum(
            1 for item in trace
            if item.get("type") == "user"
        )

        a, b, c, d = st.columns(4)

        a.metric("Agent Requests", requests)
        b.metric("Tool Calls", len(calls))

        failed = 0

        if not calls.empty and "result" in calls.columns:

            failed = int(
                calls["result"]
                .astype(str)
                .str.startswith("Failed")
                .sum()
            )

        c.metric("Failed Tool Calls", failed)

        d.metric(
            "Average Rating",
            f"{sum(feedback) / len(feedback):.1f}"
            if feedback else "N/A"
        )

        st.caption(
            f"Requests blocked by safety guardrails: {blocked}"
        )

        st.divider()

        if not calls.empty and "tool" in calls.columns:

            st.subheader("Agent Tool Usage")

            st.bar_chart(
                calls["tool"].value_counts()
            )

        if not replies.empty and "seconds" in replies.columns:

            st.subheader("Agent Response Time")

            response_times = pd.to_numeric(
                replies["seconds"],
                errors="coerce"
            ).dropna()

            if not response_times.empty:

                st.line_chart(
                    response_times.reset_index(drop=True)
                )

        if feedback:

            st.subheader("User Feedback")

            st.metric(
                "Average User Rating",
                f"{sum(feedback) / len(feedback):.2f} / 5"
            )

        # ---------------------------------------------
        # SAFE ACTIVITY LOG DISPLAY
        # ---------------------------------------------

        st.subheader("Agent Activity Log")

        trace_df = pd.DataFrame(trace).iloc[::-1].copy()

        for column in trace_df.columns:

            trace_df[column] = trace_df[column].apply(
                lambda value: (
                    json.dumps(
                        value,
                        ensure_ascii=False,
                        default=str
                    )
                    if isinstance(
                        value,
                        (dict, list, tuple, set)
                    )
                    else str(value)
                    if value is not None
                    else ""
                )
            )

        st.dataframe(
            trace_df,
            width="stretch",
            hide_index=True
        )

    st.divider()

    st.subheader("Analytics Navigation")

    c1, c2, c3 = st.columns(3)

    with c1:

        st.button(
            "🏠 Dashboard",
            width="stretch",
            on_click=navigate_to,
            args=("Tournament Dashboard",)
        )

    with c2:

        st.button(
            "🏆 Manage Tournament",
            width="stretch",
            on_click=navigate_to,
            args=("Teams",)
        )

    with c3:

        st.button(
            "🤖 AI Assistant",
            width="stretch",
            on_click=navigate_to,
            args=("AI Assistant",)
        )


# =====================================================
# 21. FOOTER
# =====================================================

st.markdown("""
<div class="footer">
🏆 Sports Tournament Manager Agent
<br>
DAT404 | Intelligent and Generative Agents
<br>
Powered by Python, Streamlit, SQLite and Ollama
</div>
""", unsafe_allow_html=True)