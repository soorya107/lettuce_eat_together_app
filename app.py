"""Streamlit UI for the food recommendation system.

Run with:  streamlit run app.py
"""
import pandas as pd
import streamlit as st
from datetime import date

from recommender import DATA_PATH, FoodRecommender, Preferences
from family import FamilyMember
from calorie_goals import ACTIVITY_FACTORS, estimate_daily_goal
from database import (
    add_family_note, add_food_entry, authenticate, family_notes, food_entries,
    get_user, init_db, list_members, register_account, remove_food_entry,
    save_profile,
)

st.set_page_config(page_title="Lettuce Eat Together", page_icon="🥬", layout="wide")

DIET_LABELS = {
    "non-veg": "Non-vegetarian (eat everything)",
    "veg": "Vegetarian",
    "vegan": "Vegan",
}
DIET_ICONS = {"vegan": "🌱 Vegan", "veg": "🥕 Vegetarian", "non-veg": "🍗 Non-veg"}

st.markdown("""
<style>
:root { --ink:#19352b; --muted:#718078; --green:#26764f; --green-dark:#185738; --lime:#dff2a5; --canvas:#f7f8f1; --line:#e6e9da; --tomato:#e7755b; }
html, body, [class*="css"] { font-family:'Segoe UI',Arial,sans-serif; color:var(--ink); }
.stApp { background:radial-gradient(ellipse at 88% 0%,#edf4df 0,transparent 34%),var(--canvas); }
.block-container { max-width:1360px; padding-top:2rem; padding-bottom:3rem; }
h1,h2,h3 { font-family:'Segoe UI',Arial,sans-serif !important; color:var(--ink); letter-spacing:-.035em; font-weight:750 !important; }
h1 { font-size:2.15rem !important; }
[data-testid="stSidebar"] { background:#edf3ec; border-right:1px solid var(--line); }
[data-testid="stSidebar"] > div:first-child { padding-top:1.5rem; }
[data-testid="stSidebar"] [data-testid="stMetric"] { padding:12px 14px; border-radius:14px; box-shadow:none; }
[data-testid="stSidebar"] [data-testid="stMetricValue"] { font-size:1.45rem; }
[data-testid="stSidebar"] details summary { font-weight:700; color:var(--ink); }
.sidebar-brand { display:flex; align-items:center; gap:11px; margin-bottom:18px; }
.sidebar-mark { display:flex; align-items:center; justify-content:center; width:44px; height:44px; border-radius:15px; color:#fff; background:linear-gradient(135deg,#185738,#6a9d48); font-size:1.45rem; box-shadow:0 5px 12px #18573825; }
.sidebar-name { color:var(--ink); font-size:1.05rem; line-height:1.15; font-weight:800; }
.sidebar-sub { color:var(--muted); font-size:.76rem; margin-top:3px; }
.sidebar-section { color:var(--muted); text-transform:uppercase; letter-spacing:.13em; font-size:.68rem; font-weight:800; margin:14px 0 5px; }
.sidebar-empty { padding:14px; background:#fff; border:1px solid var(--line); border-radius:14px; color:var(--muted); font-size:.88rem; }
[data-testid="stTabs"] [data-baseweb="tab-list"] { gap:8px; border-bottom:1px solid var(--line); }
[data-testid="stTabs"] button[role="tab"] { border-radius:12px 12px 0 0; padding:12px 16px; color:var(--muted); font-weight:700; }
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { color:var(--green-dark); border-bottom:3px solid var(--green); }
[data-testid="stMetric"] { background:#fff; border:1px solid var(--line); border-radius:16px; padding:16px 18px; box-shadow:0 3px 12px #233b2910; }
[data-testid="stMetricLabel"] { color:var(--muted); font-weight:600; }
[data-testid="stMetricValue"] { color:var(--ink); font-family:'Segoe UI',Arial,sans-serif; font-weight:800; }
[data-testid="stVerticalBlockBorderWrapper"] { border-color:var(--line) !important; border-radius:18px !important; background:#fff; }
.stButton > button, .stFormSubmitButton > button { border-radius:12px; font-weight:700; border:1px solid #dce8de; transition:all .18s ease; }
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] { background:var(--green); border-color:var(--green); color:#fff; }
.stButton > button:hover, .stFormSubmitButton > button:hover { border-color:var(--green); color:var(--green-dark); }
[data-testid="stProgressBar"] > div > div { background:var(--green); border-radius:99px; }
[data-testid="stProgressBar"] > div { background:#e6eee6; border-radius:99px; }
.hero { background:linear-gradient(112deg,#173e2e 0%,#27744c 62%,#76a85e 100%); border-radius:28px; padding:32px 36px; color:white; margin:4px 0 25px; box-shadow:0 16px 38px #1c805b24; position:relative; overflow:hidden; }
.hero:after { content:' '; position:absolute; width:240px;height:240px;border-radius:50%;background:#ffffff12;right:-40px;top:-115px; }
.hero:before { content:'🥬'; position:absolute; right:8%; bottom:-26px; font-size:7rem; opacity:.20; transform:rotate(-18deg); filter:grayscale(.15); }
.hero-kicker { font-size:.76rem; text-transform:uppercase; letter-spacing:.16em; font-weight:700; color:#d8f4d4; }
.hero-title { font:800 2.05rem 'Segoe UI',Arial,sans-serif; letter-spacing:-.04em; margin:9px 0 6px; color:white; }
.hero-copy { color:#e2f0e4; margin:0; font-size:1rem; }
.eyebrow { text-transform:uppercase; letter-spacing:.12em; color:var(--green); font-size:.72rem; font-weight:800; }
.daily-note { padding:12px 16px; border-radius:14px; background:#edf4e4; border:1px solid #dce8ce; color:#395b42; font-size:.92rem; }
@media (max-width: 720px) { .block-container {padding:1rem;} .hero {padding:24px;} .hero-title {font-size:1.6rem;} }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_recommender(catalogue_modified: int) -> FoodRecommender:
    # Include the catalogue timestamp in the cache key so added recipes appear
    # without requiring users to clear Streamlit's resource cache manually.
    return FoodRecommender()


def show_macros(row: pd.Series) -> None:
    """Macro breakdown for one dish, per 100g."""
    scale = 100 / row["serving_g"]

    st.caption("Per 100 g")
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Calories", f"{row['calories']*scale:.0f} kcal")
    h2.metric("Protein", f"{row['protein_g']*scale:.1f} g")
    h3.metric("Carbs", f"{row['carbs_g']*scale:.1f} g")
    h4.metric("Fat", f"{row['fat_g']*scale:.1f} g")

    st.caption("Estimated values — not a certified nutrition label.")


def show_cards(df: pd.DataFrame, columns: int = 3) -> None:
    if df.empty:
        st.warning("No dishes match these filters. Try relaxing some of them.")
        return
    cols = st.columns(columns)
    for k, row in df.iterrows():
        with cols[k % columns].container(border=True):
            st.subheader(row["name"])
            st.caption(f"{row['cuisine']} • {str(row['course']).title()} • {DIET_ICONS[row['diet']]}")
            spice = "●" * int(row["spice"]) or "none"
            st.write(f"{row['calories']} kcal  ·  {row['prep_time']} min prep  ·  Spice: {spice}")
            if row["match"] > 0:
                st.progress(min(int(row["match"]), 100), text=f"Match {row['match']}%")
            st.caption(row["why"])
            pairing = str(row.get("pairing", "")).strip()
            if pairing:
                st.markdown(f"**Serve with:** {pairing}")
            recipe_steps = str(row.get("recipe_steps", "")).strip()
            if recipe_steps:
                with st.expander("Quick recipe"):
                    st.write(recipe_steps)
            with st.expander("🔬 View macros"):
                show_macros(row)


init_db()
auth_user = st.session_state.get("auth_user")
if auth_user:
    auth_user = get_user(auth_user["id"])
    if auth_user is None:
        st.session_state.pop("auth_user", None)

if not auth_user:
    st.markdown("""
    <section class="hero">
      <div class="hero-kicker">🥬 Lettuce Eat Together · Family food diary</div>
      <div class="hero-title">Good food. Good goals. Great company.</div>
      <p class="hero-copy">Log your meals, follow your own calorie goal, and cheer on your household—one bite at a time.</p>
    </section>
    """, unsafe_allow_html=True)
    sign_in_tab, create_account_tab = st.tabs(["Sign in", "Create account / Join family"])
    with sign_in_tab:
        with st.form("sign_in_form", clear_on_submit=False):
            login_username = st.text_input("Username")
            login_password = st.text_input("Password", type="password")
            login_clicked = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if login_clicked:
            user = authenticate(login_username, login_password)
            if user:
                st.session_state.auth_user = user
                st.rerun()
            st.error("Username or password is incorrect.")
    with create_account_tab:
        st.caption("Create the first account to start a household, or enter a family invite code to join one.")
        with st.form("create_account_form", clear_on_submit=False):
            display_name = st.text_input("Your name")
            new_username = st.text_input("Choose a username", help="3–30 characters: letters, numbers, dot, dash, underscore.")
            new_password = st.text_input("Create password", type="password", help="Use at least 8 characters.")
            confirm_password = st.text_input("Confirm password", type="password")
            household_name = st.text_input("Family name", help="Required only when creating a new household.")
            invite_code = st.text_input("Family invite code", help="Leave blank to create a new household.")
            create_clicked = st.form_submit_button("Create account", type="primary", use_container_width=True)
        if create_clicked:
            if new_password != confirm_password:
                st.error("The passwords do not match.")
            else:
                try:
                    user = register_account(
                        display_name=display_name, username=new_username,
                        password=new_password, household_name=household_name,
                        invite_code=invite_code,
                    )
                    st.session_state.auth_user = user
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
    st.stop()

rec = load_recommender(DATA_PATH.stat().st_mtime_ns)
member_records = list_members(auth_user["household_id"])
family_members = [
    FamilyMember(
        name=row["display_name"], diet=row["diet"], allergies=row["allergies"],
        liked=row["liked"], calorie_goal_kcal=row["calorie_goal_kcal"],
        current_weight_kg=row["current_weight_kg"], goal_weight_kg=row["goal_weight_kg"],
        goal_pace=row["goal_pace"], activity_level=row["activity_level"],
        age_years=row["age_years"], height_cm=row["height_cm"],
        calorie_formula=row["calorie_formula"], user_id=row["id"],
    )
    for row in member_records
]


class HouseholdView:
    def __init__(self, members):
        self.members = members

    def names(self):
        return [member.name for member in self.members]

    def get(self, name):
        return next((member for member in self.members if member.name.lower() == name.lower()), None)


family = HouseholdView(family_members)

st.markdown("""
<section class="hero">
  <div class="hero-kicker">🥬 Lettuce Eat Together · Your family, in one fresh view</div>
  <div class="hero-title">A little progress, a lot of together.</div>
  <p class="hero-copy">See today’s meals, calorie goals, and family progress at a glance. No food left behind.</p>
</section>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ sidebar: manage family
with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand">
      <div class="sidebar-mark">🥬</div>
      <div><div class="sidebar-name">Lettuce Eat Together</div><div class="sidebar-sub">Your family food diary</div></div>
    </div>
    <div class="sidebar-section">Household dashboard</div>
    """, unsafe_allow_html=True)

    if family.members:
        st.caption(f"{auth_user['household_name']} · signed in as **{auth_user['display_name']}**")
        quick_member_name = st.selectbox(
            "Family snapshot", family.names(),
            index=family.names().index(auth_user["display_name"])
            if auth_user["display_name"] in family.names() else 0,
            key=f"sidebar_daily_member_{auth_user['id']}",
        )
        quick_member = family.get(quick_member_name)
        today_rows = [
            entry for entry in food_entries(auth_user["household_id"], date.today())
            if entry.get("member") == quick_member_name
        ]
        eaten_today = sum(float(entry.get("calories", 0)) for entry in today_rows)
        quick_goal_info = estimate_daily_goal(quick_member)
        quick_goal = (
            quick_goal_info["target_kcal"]
            if quick_goal_info and quick_goal_info["target_kcal"] is not None
            else quick_member.calorie_goal_kcal
        )
        if quick_goal:
            st.metric("Calories today", f"{eaten_today:,.0f} / {quick_goal:,} kcal")
            st.progress(
                min(eaten_today / quick_goal, 1.0),
                text=f"{max(0, quick_goal - round(eaten_today)):,} kcal remaining",
            )
            st.caption(
                f"{DIET_ICONS[quick_member.diet]}  ·  "
                f"{quick_goal_info['pace'] if quick_goal_info else 'Personal target'}"
            )
        else:
            st.metric("Calories today", f"{eaten_today:,.0f} kcal")
            st.caption("Add profile details to calculate a daily goal.")
        st.caption(f"{len(family.members)} family member{'s' if len(family.members) != 1 else ''}")
    else:
        st.markdown(
            '<div class="sidebar-empty">Your household dashboard will appear here after you add a member.</div>',
            unsafe_allow_html=True,
        )

    with st.expander("✎  My profile & preferences", expanded=not family.members):
        st.caption("Only your own profile and food preferences are editable here.")
        with st.form(f"edit_profile_{auth_user['id']}", clear_on_submit=False):
            diet_options = list(DIET_LABELS)
            diet = st.selectbox(
                "Eating style", diet_options, format_func=DIET_LABELS.get,
                index=diet_options.index(auth_user["diet"])
                if auth_user["diet"] in diet_options else 0,
                key=f"profile_diet_{auth_user['id']}",
            )
            st.caption("CALORIE GOAL PROFILE · optional")
            weight_cols = st.columns(2)
            current_weight = weight_cols[0].number_input(
                "Current kg", min_value=0.0, max_value=400.0,
                value=float(auth_user["current_weight_kg"] or 0), step=0.1,
                key=f"profile_current_weight_{auth_user['id']}",
            )
            goal_weight = weight_cols[1].number_input(
                "Goal kg", min_value=0.0, max_value=400.0,
                value=float(auth_user["goal_weight_kg"] or 0), step=0.1,
                key=f"profile_goal_weight_{auth_user['id']}",
            )
            pace_options = ["Maintain weight", "Lose 0.2 kg/week", "Lose 0.5 kg/week",
                            "Gain 0.2 kg/week", "Gain 0.5 kg/week"]
            old_pace = auth_user["goal_pace"] or "Maintain weight"
            goal_pace = st.selectbox(
                "Goal pace", pace_options,
                index=pace_options.index(old_pace) if old_pace in pace_options else 0,
                key=f"profile_pace_{auth_user['id']}",
            )
            same_weight = current_weight > 0 and goal_weight > 0 and abs(current_weight - goal_weight) < 0.01
            pace_for_save = goal_pace if current_weight > 0 and goal_weight > 0 else None
            if same_weight:
                pace_for_save = "Maintain weight"
                st.caption("Matching current and goal weights automatically sets maintenance.")
            activity_options = ["Choose activity level", *ACTIVITY_FACTORS]
            old_activity = auth_user["activity_level"] or "Choose activity level"
            activity_choice = st.selectbox(
                "Activity level", activity_options,
                index=activity_options.index(old_activity) if old_activity in activity_options else 0,
                key=f"profile_activity_{auth_user['id']}",
            )
            detail_cols = st.columns(2)
            age_years = detail_cols[0].number_input(
                "Age", min_value=0, max_value=120, value=int(auth_user["age_years"] or 0),
                step=1, key=f"profile_age_{auth_user['id']}",
            )
            height_cm = detail_cols[1].number_input(
                "Height cm", min_value=0.0, max_value=250.0,
                value=float(auth_user["height_cm"] or 0), step=0.5,
                key=f"profile_height_{auth_user['id']}",
            )
            formula_options = ["Choose equation", "Female formula", "Male formula", "Manual target only"]
            old_formula = auth_user["calorie_formula"] or "Choose equation"
            formula_choice = st.selectbox(
                "Equation", formula_options,
                index=formula_options.index(old_formula) if old_formula in formula_options else 0,
                help="Choose the equation that fits, or use a manual target.",
                key=f"profile_formula_{auth_user['id']}",
            )
            calorie_goal = st.number_input(
                "Manual target (kcal, optional)", min_value=0, max_value=6000,
                value=int(auth_user["calorie_goal_kcal"] or 0), step=50,
                help="Fallback if an automatic estimate isn't available.",
                key=f"profile_manual_goal_{auth_user['id']}",
            )
            allergies = st.multiselect(
                "Allergies / dislikes", rec.ingredients(), default=auth_user["allergies"],
                key=f"profile_allergies_{auth_user['id']}",
            )
            liked = st.multiselect(
                "Favorite dishes", rec.dish_names(), default=auth_user["liked"],
                key=f"profile_liked_{auth_user['id']}",
            )
            submitted = st.form_submit_button("Save my profile", type="primary", use_container_width=True)
            if submitted:
                auth_user = save_profile(
                    auth_user["id"], diet=diet, allergies=allergies, liked=liked,
                    calorie_goal_kcal=int(calorie_goal) if calorie_goal else None,
                    current_weight_kg=float(current_weight) if current_weight else None,
                    goal_weight_kg=float(goal_weight) if goal_weight else None,
                    goal_pace=pace_for_save,
                    activity_level=activity_choice if activity_choice != "Choose activity level" else None,
                    age_years=int(age_years) if age_years else None,
                    height_cm=float(height_cm) if height_cm else None,
                    calorie_formula=formula_choice if formula_choice in {"Female formula", "Male formula"} else None,
                )
                st.session_state.auth_user = auth_user
                st.success("Profile saved.")
                st.rerun()

    if family.members:
        with st.expander("Household members", expanded=False):
            for m in family.members:
                st.write(f"**{m.name}** · {DIET_ICONS[m.diet]}")
        if auth_user["role"] == "owner":
            with st.expander("Invite family members", expanded=False):
                st.caption("Share this code with relatives so they can join your household.")
                st.code(auth_user["invite_code"])

    with st.expander("Recommendation settings", expanded=False):
        n_results = st.slider("Dishes to show", 3, 15, 6)

    if st.button("Sign out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# --------------------------------------------------------------------- tabs
tab_diary, tab_family, tab_individual, tab_similar = st.tabs(
    ["☀️ Today’s table", "🍲 Family picks", "🙂 My picks", "🔎 Find similar"]
)

with tab_family:
    if not family.members:
        st.info("Add family members in the sidebar to get dishes everyone can eat.")
    else:
        cuisine_choice = st.selectbox(
            "Choose a cuisine first",
            ["Any cuisine", *rec.cuisines()],
            key="family_recommendation_cuisine",
            help="Your family suggestions will be filtered to this cuisine.",
        )
        selected_cuisine = None if cuisine_choice == "Any cuisine" else cuisine_choice
        all_allergies = sorted({a for m in family.members for a in m.allergies})
        st.caption(
            f"Members: {', '.join(family.names())}  ·  "
            f"Avoiding for everyone: **{', '.join(all_allergies) or 'nothing'}**"
        )

        diets_present = sorted({m.diet for m in family.members})
        if len(diets_present) == 1:
            st.write(f"Everyone in the family eats **{diets_present[0]}**, so here's one shared list:")
            show_cards(rec.recommend_for_family(
                family.members, n=n_results, cuisine=selected_cuisine
            ))
        else:
            st.write(
                "Your family has mixed diets, so dishes are grouped by diet "
                "instead of forcing everyone onto the strictest one. "
                "Allergies are still excluded for everyone."
            )
            spread = rec.recommend_family_spread(
                family.members,
                n=max(3, n_results // len(diets_present)),
                cuisine=selected_cuisine,
            )
            for diet, df in spread.items():
                who = ", ".join(m.name for m in family.members if m.diet == diet)
                st.subheader(f"{DIET_ICONS[diet]} — for {who}")
                show_cards(df, columns=3)

            with st.expander("Also show: one dish the whole family could share"):
                st.caption("This respects the strictest diet in the family, so options may be limited.")
                show_cards(rec.recommend_for_family(
                    family.members, n=n_results, cuisine=selected_cuisine
                ))

with tab_individual:
    if not family.members:
        st.info("Add family members in the sidebar first.")
    else:
        cuisine_choice = st.selectbox(
            "Choose a cuisine first",
            ["Any cuisine", *rec.cuisines()],
            key="personal_recommendation_cuisine",
        )
        member_name = st.selectbox("Choose a family member", family.names())
        member = family.get(member_name)
        cuisine_filter = [] if cuisine_choice == "Any cuisine" else [cuisine_choice]
        prefs = Preferences(
            diet=member.diet, liked=member.liked,
            exclude_ingredients=member.allergies,
            cuisines=cuisine_filter,
        )
        show_cards(rec.recommend(prefs, n=n_results))

with tab_similar:
    cuisine_choice = st.selectbox(
        "Choose a cuisine first",
        ["Any cuisine", *rec.cuisines()],
        key="similar_recommendation_cuisine",
    )
    dish_options = rec.dish_names()
    if cuisine_choice != "Any cuisine":
        dish_options = sorted(
            rec.df.loc[rec.df["cuisine"] == cuisine_choice, "name"].tolist()
        )
    dish = st.selectbox("Choose a dish", dish_options)
    st.write(f"Dishes similar to **{dish}**:")
    similar_prefs = Preferences(
        cuisines=[] if cuisine_choice == "Any cuisine" else [cuisine_choice]
    )
    show_cards(rec.similar_to(dish, n=n_results, prefs=similar_prefs))

with tab_diary:
    st.markdown('<div class="eyebrow">Your daily dashboard · fresh from the family table</div>', unsafe_allow_html=True)
    st.subheader("Today at a glance")
    st.markdown('<div class="daily-note">🥗 Every family member has their own goal. Add what you ate, then give each other a little encouragement.</div>', unsafe_allow_html=True)
    st.caption("The shared diary shows family meals and nutrition totals. Each person controls their own food entries. Estimates are approximate, for adults, and do not include exercise calories.")
    if not family.members:
        st.info("Add family members in the sidebar to start the shared diary.")
    else:
        date_area = st.columns([2, 1])
        diary_day = date_area[1].date_input("Choose date", value=date.today(), key="diary_day")
        date_area[0].markdown(f"### {diary_day.strftime('%A, %B %d')}")
        day_entries = food_entries(auth_user["household_id"], diary_day)

        family_calories = sum(
            float(entry.get("calories", 0)) for entry in day_entries
        )
        family_log_count = len(day_entries)
        active_members = len({entry.get("member") for entry in day_entries})
        overview = st.columns(3)
        overview[0].metric("Family calories logged", f"{family_calories:,.0f} kcal")
        overview[1].metric("Foods logged", f"{family_log_count}")
        overview[2].metric("Family members active", f"{active_members} / {len(family.members)}")

        st.markdown("#### Each member's daily progress")
        for member in family.members:
            member_rows = [entry for entry in day_entries if entry.get("member") == member.name]
            totals = {
                key: sum(float(entry.get(key, 0)) for entry in member_rows)
                for key in ("calories", "protein_g", "carbs_g", "fat_g")
            }
            goal_info = estimate_daily_goal(member)
            automatic_goal = (
                goal_info["target_kcal"]
                if goal_info and goal_info["target_kcal"] is not None
                else None
            )
            goal = automatic_goal if automatic_goal is not None else member.calorie_goal_kcal
            with st.container(border=True):
                st.markdown(f"**{member.name}**")
                cols = st.columns(3)
                cols[0].metric(
                    "Daily calorie goal",
                    f"{goal:,} kcal" if goal else "Not set",
                )
                cols[1].metric("Calories eaten", f"{totals['calories']:.0f} kcal")
                remaining = max(0, goal - round(totals["calories"])) if goal else None
                cols[2].metric(
                    "Calories remaining",
                    f"{remaining:,} kcal" if remaining is not None else "—",
                )
                macro_cols = st.columns(3)
                macro_cols[0].metric("Protein", f"{totals['protein_g']:.1f} g")
                macro_cols[1].metric("Carbs", f"{totals['carbs_g']:.1f} g")
                macro_cols[2].metric("Fat", f"{totals['fat_g']:.1f} g")
                if goal:
                    st.progress(
                        min(totals["calories"] / goal, 1.0),
                        text=(
                            f"{totals['calories']:.0f} of {goal} kcal eaten "
                            f"({totals['calories'] / goal:.0%})"
                        ),
                    )
                    if goal_info:
                        st.caption(
                            f"Calculated from profile · maintenance: "
                            f"{goal_info['maintenance_kcal']:,} kcal/day · "
                            f"pace: {goal_info['pace']} · activity included."
                        )
                elif goal_info and goal_info["target_kcal"] is None:
                    st.warning(
                        "The estimate is below 1,000 kcal/day, so it is hidden. "
                        "Change the pace or use a clinician-guided target."
                    )
                else:
                    st.caption(
                        "Add current and goal weight, adult age, height, equation, "
                        "and activity level in the sidebar to calculate a goal."
                    )

        st.markdown("#### Add food to today's diary")
        with st.form("add_food_log", clear_on_submit=True):
            st.caption(f"Logging food for **{auth_user['display_name']}**")
            left, right = st.columns(2)
            with left:
                meal = st.selectbox("Meal", ["Breakfast", "Lunch", "Dinner", "Snack"])
            with right:
                food_name = st.selectbox("Food from catalogue", rec.dish_names(), key="log_food")
                servings = st.number_input("Servings", min_value=0.25, max_value=12.0,
                                           value=1.0, step=0.25)
            selected_food = rec.df.loc[rec.df["name"] == food_name].iloc[0]
            st.caption(
                f"Per serving ({selected_food['serving_g']} g): "
                f"{selected_food['calories']} kcal · {selected_food['protein_g']} g protein · "
                f"{selected_food['carbs_g']} g carbs · {selected_food['fat_g']} g fat"
            )
            save_food = st.form_submit_button("Add to diary")
            if save_food:
                add_food_entry(
                    household_id=auth_user["household_id"], user_id=auth_user["id"],
                    day=diary_day, meal=meal, food=food_name,
                    servings=float(servings), serving_g=float(selected_food["serving_g"]),
                    calories=float(selected_food["calories"]),
                    protein_g=float(selected_food["protein_g"]),
                    carbs_g=float(selected_food["carbs_g"]), fat_g=float(selected_food["fat_g"]),
                )
                st.success(f"Added {food_name} to your diary.")
                st.rerun()

        if day_entries:
            st.markdown("#### Shared family meals")
            meal_names = ["Breakfast", "Lunch", "Dinner", "Snack"]
            meal_cols = st.columns(4)
            for index, meal_name in enumerate(meal_names):
                meal_items = [e for e in day_entries if e.get("meal") == meal_name]
                meal_kcal = sum(float(e.get("calories", 0)) for e in meal_items)
                meal_cols[index].metric(meal_name, f"{meal_kcal:.0f} kcal", f"{len(meal_items)} foods")

            for meal_name in meal_names:
                meal_items = [e for e in day_entries if e.get("meal") == meal_name]
                if not meal_items:
                    continue
                with st.expander(f"{meal_name} · {len(meal_items)} foods", expanded=True):
                    display_rows = [{
                        "Family member": e.get("member"), "Food": e.get("food"),
                        "Servings": e.get("servings"), "Calories": f"{float(e.get('calories', 0)):.0f} kcal",
                        "Protein": f"{float(e.get('protein_g', 0)):.1f} g",
                        "Carbs": f"{float(e.get('carbs_g', 0)):.1f} g",
                        "Fat": f"{float(e.get('fat_g', 0)):.1f} g",
                    } for e in meal_items]
                    st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)
                    remove_cols = st.columns(min(3, len(meal_items)))
                    for i, entry in enumerate(meal_items):
                        if entry.get("user_id") == auth_user["id"]:
                            with remove_cols[i % len(remove_cols)]:
                                if st.button(
                                    f"Remove my {entry.get('food')}",
                                    key=f"remove_log_{entry.get('id')}",
                                ):
                                    remove_food_entry(entry.get("id", ""), auth_user["id"])
                                    st.rerun()
        else:
            st.info("No foods logged for this date yet.")

        st.markdown("#### Family encouragement")
        other_members = [m for m in family.members if m.user_id != auth_user["id"]]
        if other_members:
            with st.form("family_encouragement", clear_on_submit=True):
                to_member_name = st.selectbox("Send encouragement to", [m.name for m in other_members])
                encouragement = st.selectbox("Message", [
                    "Nice job keeping track today!",
                    "Want to plan a meal together tomorrow?",
                    "Thanks for sharing your food log with the family.",
                    "Small steps add up. Keep going at your own pace.",
                ])
                personal_note = st.text_input("Add a short note (optional)", max_chars=120)
                send_encouragement = st.form_submit_button("Share encouragement")
                if send_encouragement:
                    message = f"{encouragement} {personal_note.strip()}".strip()
                    recipient_member = family.get(to_member_name)
                    add_family_note(
                        household_id=auth_user["household_id"],
                        sender_id=auth_user["id"], recipient_id=recipient_member.user_id,
                        day=diary_day, message=message,
                    )
                    st.success("Encouragement shared with the family.")
                    st.rerun()
        else:
            st.caption("Invite another family member to share encouragement here.")
        day_notes = family_notes(auth_user["household_id"], diary_day)
        if day_notes:
            for note in reversed(day_notes):
                st.info(f"**{note.get('sender')} → {note.get('recipient')}:** {note.get('message')}")
