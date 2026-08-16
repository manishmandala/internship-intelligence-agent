"""
Tests for the parsing/classification pipeline.

Several of these are regression tests for real bugs found while running the
collector against live SpaceX/Anduril/Lucid data during development:
- "intern" as a plain substring matched "Internal Systems" / "International"
- classify_role_category let a single incidental keyword in a long
  description (company-overview boilerplate) outvote a title with no
  relevant keywords at all.
- bare "C" / "R" skill matching fired on things like "8 U.S.C. 1101" and
  "our R&D team".
"""
from __future__ import annotations

from src.analysis.skills import extract_skills
from src.parsers.classifiers import classify_industry, classify_role_category
from src.parsers.job_parser import build_job_posting, is_internship_posting
from src.parsers.text_utils import (
    classify_employment_type,
    html_to_text,
    split_qualifications,
)


class TestIsInternshipPosting:
    def test_matches_plain_intern_title(self):
        assert is_internship_posting("Mechanical Engineering Intern")

    def test_matches_co_op_title(self):
        assert is_internship_posting("Naval Architect Co-op - Winter 2027")

    def test_does_not_match_internal_systems(self):
        # Regression test: "intern" is a substring of "Internal", which
        # must NOT count as an internship posting.
        assert not is_internship_posting("Full Stack Software Engineer, Internal Systems")

    def test_does_not_match_international(self):
        assert not is_internship_posting("International Trade Compliance Manager")

    def test_does_not_match_internet(self):
        assert not is_internship_posting("Internet Infrastructure Engineer")

    def test_matches_internship_program_title(self):
        assert is_internship_posting("Recruiting Coordinator, Intern Program")


class TestClassifyRoleCategory:
    def test_title_keyword_wins_over_empty_description(self):
        category = classify_role_category("Mechanical Design Engineer Intern", "")
        assert category == "mechanical_design"

    def test_title_with_no_keywords_and_incidental_body_mention_is_other(self):
        # Regression test: a recruiting-coordinator posting whose long
        # description happens to mention "autonomous flight" once (as
        # company-overview boilerplate) must not be classified as a
        # robotics/hardware role.
        description = (
            "We are looking for a Recruiting Coordinator to support our "
            "internship program. About the company: we build autonomous "
            "flight systems that change the world."
        )
        category = classify_role_category("Recruiting Coordinator, Intern Program", description)
        assert category == "other"

    def test_repeated_body_mentions_can_still_classify_when_title_is_empty(self):
        description = "robotics robotics embedded systems mechatronics perception"
        category = classify_role_category("", description)
        assert category == "robotics_ai_hardware"


class TestClassifyIndustry:
    def test_matches_aerospace_keywords(self):
        category = classify_industry("SpaceX", "Propulsion Intern", "Work on rocket propulsion systems")
        assert category == "aerospace_defense"

    def test_defaults_to_other_with_no_signal(self):
        category = classify_industry("Acme Corp", "Generic Intern", "Do generic things")
        assert category == "other"


class TestSkillExtraction:
    def test_extracts_solidworks_and_python(self):
        skills = extract_skills("Experience with SolidWorks and Python required.")
        assert "SolidWorks" in skills
        assert "Python" in skills

    def test_extracts_cplusplus(self):
        skills = extract_skills("Proficiency in C++ is a plus.")
        assert "C++" in skills

    def test_bare_c_does_not_match_legal_boilerplate(self):
        # Regression test: "8 U.S.C. 1101(a)(15)" must not register "C".
        text = "Must be eligible to work under 8 U.S.C. 1101(a)(15) provisions."
        skills = extract_skills(text)
        assert "C" not in skills

    def test_bare_c_matches_explicit_language_phrasing(self):
        skills = extract_skills("Strong skills in C/C++ required.")
        assert "C" in skills

    def test_bare_r_does_not_match_r_and_d(self):
        # Regression test: "our R&D team" must not register "R".
        skills = extract_skills("Join our R&D team building next-gen hardware.")
        assert "R" not in skills

    def test_bare_r_matches_explicit_language_phrasing(self):
        skills = extract_skills("Experience with Python, R for data analysis.")
        assert "R" in skills

    def test_gd_and_t_variants(self):
        assert "GD&T" in extract_skills("Strong understanding of GD&T is required.")
        assert "GD&T" in extract_skills("Strong understanding of GD & T is required.")

    def test_empty_text_returns_empty_list(self):
        assert extract_skills("") == []
        assert extract_skills(None) == []


class TestTextUtils:
    def test_html_to_text_strips_tags(self):
        # html_to_text uses a newline separator between tag boundaries
        # (not just block-level ones) because job descriptions rely on
        # list/paragraph structure being preserved as lines for
        # split_qualifications()'s heading detection to work.
        html = "<div><p>Hello <b>World</b></p></div>"
        assert html_to_text(html) == "Hello\nWorld"

    def test_html_to_text_preserves_paragraph_and_list_structure(self):
        html = "<p>About the role</p><ul><li>Design parts</li><li>Test parts</li></ul>"
        text = html_to_text(html)
        assert text.splitlines() == ["About the role", "Design parts", "Test parts"]

    def test_html_to_text_handles_empty_input(self):
        assert html_to_text("") == ""
        assert html_to_text(None) == ""

    def test_classify_employment_type_intern(self):
        assert classify_employment_type("Mechanical Engineering Intern", "") == "Internship"

    def test_classify_employment_type_co_op(self):
        assert classify_employment_type("Manufacturing Co-op", "") == "Co-op"

    def test_classify_employment_type_unknown(self):
        assert classify_employment_type("Software Engineer", "") == "Unknown"

    def test_split_qualifications_finds_headed_sections(self):
        text = (
            "About the role\n"
            "We build cool things.\n"
            "Basic Qualifications\n"
            "Currently pursuing a degree in Mechanical Engineering\n"
            "Preferred Qualifications\n"
            "Experience with SolidWorks\n"
        )
        required, preferred = split_qualifications(text)
        assert "Mechanical Engineering" in required
        assert "SolidWorks" in preferred


class TestBuildJobPosting:
    def test_returns_none_for_non_internship_title(self):
        job = build_job_posting(
            company="Acme", title="Senior Software Engineer", url="https://acme.com/1",
            source="greenhouse", location="Columbus, OH", description_text="Full-time role.",
        )
        assert job is None

    def test_returns_none_for_missing_required_fields(self):
        assert build_job_posting(
            company="", title="Intern", url="https://acme.com/1", source="greenhouse", location="OH",
        ) is None

    def test_builds_valid_job_posting(self):
        job = build_job_posting(
            company="Acme",
            title="Mechanical Engineering Intern",
            url="https://acme.com/1",
            source="greenhouse",
            location="Columbus, OH",
            description_text="Work with SolidWorks and Python. Basic Qualifications: pursuing a BS in ME.",
            industry_hint="industrial_energy",
        )
        assert job is not None
        assert job.company == "Acme"
        assert job.employment_type == "Internship"
        assert job.industry_category == "industrial_energy"
        assert job.role_category == "mechanical_design"
        assert "SolidWorks" in job.required_skills
        assert job.job_hash  # was computed
