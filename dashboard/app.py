"""
Streamlit dashboard for the Internship Intelligence Agent.

Run with (from the project root, virtual environment activated):

    streamlit run dashboard/app.py

This is a read/write view onto the same SQLite database `src/main.py`
writes to - it is safe to leave a collection run going in one terminal
and the dashboard open in a browser tab at the same time (WAL mode is
enabled in src/database/db.py for exactly this reason).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow `streamlit run dashboard/app.py` to import the `src`/`config`
# packages the same way `python -m src.main` does, regardless of the
# working directory Streamlit was launched from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st

from src.analysis.stats import (
    approaching_deadlines,
    newly_discovered,
    top_companies,
    top_skills,
    top_skills_in_high_fit_roles,
)
from src.database import repository
from src.database.db import initialize_database
from src.database.models import STATUS_VALUES

st.set_page_config(
    page_title="Internship Intelligence Agent",
    page_icon="🔧",
    layout="wide",
)

initialize_database()


@st.cache_data(ttl=30)
def load_jobs() -> pd.DataFrame:
    jobs = repository.get_all_jobs()
    if not jobs:
        return pd.DataFrame()
    df = pd.DataFrame(jobs)
    df["required_skills_display"] = df["required_skills"].apply(lambda s: ", ".join(s))
    return df


def _multiselect_options(df: pd.DataFrame, column: str) -> list[str]:
    return sorted(v for v in df[column].dropna().unique().tolist() if v)


def render_sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filters")

    keyword = st.sidebar.text_input("Search title/company/description")

    companies = st.sidebar.multiselect("Company", _multiselect_options(df, "company"))
    industries = st.sidebar.multiselect("Industry", _multiselect_options(df, "industry_category"))
    role_categories = st.sidebar.multiselect("Role category", _multiselect_options(df, "role_category"))
    locations = st.sidebar.multiselect("Location", _multiselect_options(df, "location"))
    employment_types = st.sidebar.multiselect(
        "Internship vs Co-op", _multiselect_options(df, "employment_type")
    )
    statuses = st.sidebar.multiselect("My status", STATUS_VALUES)

    min_score = st.sidebar.slider("Minimum fit score", 0, 100, 0)
    active_only = st.sidebar.checkbox("Only show active/still-listed postings", value=True)
    flagged_only = st.sidebar.checkbox("Only show flagged (noteworthy) postings", value=False)

    filtered = df.copy()
    if keyword:
        keyword_lower = keyword.lower()
        mask = (
            filtered["title"].str.lower().str.contains(keyword_lower, na=False)
            | filtered["company"].str.lower().str.contains(keyword_lower, na=False)
            | filtered["description"].str.lower().str.contains(keyword_lower, na=False)
        )
        filtered = filtered[mask]
    if companies:
        filtered = filtered[filtered["company"].isin(companies)]
    if industries:
        filtered = filtered[filtered["industry_category"].isin(industries)]
    if role_categories:
        filtered = filtered[filtered["role_category"].isin(role_categories)]
    if locations:
        filtered = filtered[filtered["location"].isin(locations)]
    if employment_types:
        filtered = filtered[filtered["employment_type"].isin(employment_types)]
    if statuses:
        filtered = filtered[filtered["status"].isin(statuses)]
    filtered = filtered[filtered["fit_score"] >= min_score]
    if active_only:
        filtered = filtered[filtered["is_active"]]
    if flagged_only:
        filtered = filtered[filtered["is_flagged"]]

    return filtered


def render_jobs_table(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No postings match the current filters.")
        return

    display_df = df.sort_values("fit_score", ascending=False)[
        [
            "id", "fit_score", "company", "title", "location", "employment_type",
            "role_category", "industry_category", "status", "url", "last_checked",
            "application_deadline", "required_skills_display", "notes", "is_flagged",
        ]
    ].rename(columns={"required_skills_display": "skills"})

    st.caption(f"{len(display_df)} posting(s) - edit Status/Notes directly in the table, then click Save changes.")

    edited_df = st.data_editor(
        display_df,
        key="jobs_editor",
        hide_index=True,
        width="stretch",
        height=520,
        disabled=[
            "id", "fit_score", "company", "title", "location", "employment_type",
            "role_category", "industry_category", "url", "last_checked",
            "application_deadline", "skills", "is_flagged",
        ],
        column_config={
            "url": st.column_config.LinkColumn("Application URL", display_text="Open ->"),
            "fit_score": st.column_config.ProgressColumn("Fit", min_value=0, max_value=100, format="%d"),
            "status": st.column_config.SelectboxColumn("Status", options=STATUS_VALUES),
            "notes": st.column_config.TextColumn("Notes", width="medium"),
            "is_flagged": st.column_config.CheckboxColumn("Flagged"),
            "last_checked": st.column_config.TextColumn("Last checked"),
        },
    )

    if st.button("Save changes", type="primary"):
        changes = 0
        original_by_id = display_df.set_index("id")
        for _, row in edited_df.iterrows():
            job_id = int(row["id"])
            original = original_by_id.loc[job_id]
            if row["status"] != original["status"]:
                repository.update_job_status(job_id, row["status"])
                changes += 1
            if row["notes"] != original["notes"]:
                repository.update_job_notes(job_id, row["notes"] or "")
                changes += 1
        st.cache_data.clear()
        st.success(f"Saved {changes} change(s).")
        st.rerun()


def render_job_detail(df: pd.DataFrame) -> None:
    if df.empty:
        return
    st.subheader("Posting detail / fit explanation")
    options = {
        f"[{row.fit_score}] {row.company} - {row.title}": row.id
        for row in df.sort_values("fit_score", ascending=False).itertuples()
    }
    choice = st.selectbox("Select a posting to inspect", list(options.keys()))
    job = repository.get_job_by_id(options[choice])
    if not job:
        return

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"**{job['title']}** at **{job['company']}** - {job['location']}")
        st.markdown(f"[Open application]({job['url']})")
        st.markdown("**Description**")
        st.text(job["description"][:3000] or "(no description text captured)")
        if job["qualifications"]:
            st.markdown("**Required qualifications**")
            st.text(job["qualifications"][:1500])
        if job["preferred_qualifications"]:
            st.markdown("**Preferred qualifications**")
            st.text(job["preferred_qualifications"][:1500])
    with col2:
        st.metric("Overall fit score", job["fit_score"])
        explanation = job["score_explanation"]
        st.markdown(f"- **Role fit** ({job['score_role_fit']}): {explanation.get('role_fit', '')}")
        st.markdown(f"- **Industry fit** ({job['score_industry_fit']}): {explanation.get('industry_fit', '')}")
        st.markdown(f"- **Eligibility fit** ({job['score_eligibility_fit']}): {explanation.get('eligibility_fit', '')}")
        st.markdown(f"- **Skills fit** ({job['score_skills_fit']}): {explanation.get('skills_fit', '')}")
        st.markdown(f"- **Location fit** ({job['score_location_fit']}): {explanation.get('location_fit', '')}")
        if job["required_skills"]:
            st.markdown("**Detected skills:** " + ", ".join(job["required_skills"]))
        if job["is_flagged"]:
            st.warning("Flagged: " + "; ".join(job["flag_reasons"]))


def render_insights(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No data yet - run a collection first: `python -m src.main`")
        return

    jobs = df.to_dict("records")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Highest-fit opportunities")
        top = df.sort_values("fit_score", ascending=False).head(10)
        st.dataframe(
            top[["fit_score", "company", "title", "location", "url"]],
            hide_index=True,
            width="stretch",
            column_config={"url": st.column_config.LinkColumn("URL", display_text="Open ->")},
        )

        st.markdown("### Newly discovered (last 3 days)")
        recent = newly_discovered(jobs, within_days=3, limit=10)
        if recent:
            st.dataframe(
                pd.DataFrame(recent)[["date_found", "company", "title", "fit_score"]],
                hide_index=True, width="stretch",
            )
        else:
            st.caption("No postings discovered in the last 3 days.")

        st.markdown("### Applications approaching a deadline")
        deadlines = approaching_deadlines(jobs, within_days=14, limit=10)
        if deadlines:
            st.dataframe(
                pd.DataFrame(deadlines)[["application_deadline", "company", "title", "fit_score"]],
                hide_index=True, width="stretch",
            )
        else:
            st.caption("No known deadlines within the next 14 days.")

    with col2:
        st.markdown("### Companies appearing most frequently")
        companies_df = pd.DataFrame(top_companies(jobs, limit=10), columns=["Company", "Postings"])
        st.bar_chart(companies_df.set_index("Company"))

        st.markdown("### Most common skills overall")
        skills_df = pd.DataFrame(top_skills(jobs, limit=12), columns=["Skill", "Count"])
        st.bar_chart(skills_df.set_index("Skill"))

        st.markdown("### Skills most common in high-fit roles (score >= 70)")
        high_fit_skills_df = pd.DataFrame(
            top_skills_in_high_fit_roles(jobs, min_score=70, limit=12), columns=["Skill", "Count"]
        )
        if not high_fit_skills_df.empty:
            st.bar_chart(high_fit_skills_df.set_index("Skill"))
        else:
            st.caption("Not enough high-fit postings yet.")


def render_sources_status() -> None:
    from config.companies import active_companies, unsupported_companies

    with st.expander("Source status (which companies are actively collected)"):
        supported = active_companies()
        unsupported = unsupported_companies()
        st.markdown(f"**Active sources ({len(supported)}):** " + ", ".join(c.name for c in supported))
        st.markdown(
            f"**Unsupported ({len(unsupported)} - no reliable public API found):** "
            + ", ".join(c.name for c in unsupported)
        )
        runs = repository.get_recent_runs(limit=5)
        if runs:
            st.markdown("**Recent collection runs:**")
            st.dataframe(pd.DataFrame(runs), hide_index=True, width="stretch")


def main() -> None:
    st.title("🔧 Internship Intelligence Agent")
    st.caption(
        "Mechanical engineering / manufacturing / product & program management / "
        "consulting / robotics & AI internships, scored for an Ohio State ME "
        "student (class of 2029)."
    )

    df = load_jobs()

    if df.empty:
        st.warning(
            "No jobs in the database yet. Run a collection from the project root:\n\n"
            "`python -m src.main`"
        )
        render_sources_status()
        return

    tab_all, tab_insights = st.tabs(["All internships", "Insights"])

    with tab_all:
        filtered = render_sidebar_filters(df)
        render_jobs_table(filtered)
        st.divider()
        render_job_detail(filtered)

    with tab_insights:
        render_insights(df)

    render_sources_status()


if __name__ == "__main__":
    main()
