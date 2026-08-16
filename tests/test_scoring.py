"""Tests for the rule-based scoring engine."""
from __future__ import annotations

import json

from src.database.models import JobPosting
from src.scoring.location import classify_us_location
from src.scoring.scorer import RuleBasedScorer


def make_job(**overrides) -> JobPosting:
    defaults = dict(
        company="TestCo",
        title="Mechanical Engineering Intern",
        url="https://example.com/1",
        source="greenhouse",
        job_hash="hash",
        location="Columbus, OH",
        role_category="mechanical_design",
        industry_category="aerospace_defense",
        required_skills=["SolidWorks", "CAD"],
    )
    defaults.update(overrides)
    return JobPosting(**defaults)


class TestClassifyUsLocation:
    def test_recognizes_us_state_abbreviation(self):
        assert classify_us_location("Columbus, OH") == "us"

    def test_recognizes_full_state_name(self):
        assert classify_us_location("Austin, Texas") == "us"

    def test_recognizes_united_states_phrase(self):
        assert classify_us_location("Remote - United States") == "us"

    def test_recognizes_non_us_country(self):
        assert classify_us_location("King Abdullah Economic City, Saudi Arabia") == "non_us"

    def test_recognizes_non_us_country_uk(self):
        assert classify_us_location("London, United Kingdom") == "non_us"

    def test_unknown_for_ambiguous_location(self):
        assert classify_us_location("") == "unknown"
        assert classify_us_location("Somewhere") == "unknown"


class TestRuleBasedScorer:
    def setup_method(self):
        self.scorer = RuleBasedScorer(candidate_grad_year=2029)

    def test_score_populates_all_fields(self):
        job = make_job()
        scored = self.scorer.score(job)

        assert 0 <= scored.fit_score <= 100
        assert 0 <= scored.score_role_fit <= 100
        assert 0 <= scored.score_industry_fit <= 100
        assert 0 <= scored.score_eligibility_fit <= 100
        assert 0 <= scored.score_skills_fit <= 100
        assert 0 <= scored.score_location_fit <= 100
        explanation = json.loads(scored.score_explanation)
        assert "role_fit" in explanation
        assert "location_fit" in explanation

    def test_relevant_role_and_industry_scores_higher_than_other(self):
        relevant = self.scorer.score(make_job(role_category="mechanical_design", industry_category="aerospace_defense"))
        irrelevant = self.scorer.score(make_job(role_category="other", industry_category="other", job_hash="hash2"))
        assert relevant.fit_score > irrelevant.fit_score

    def test_us_location_scores_higher_than_non_us(self):
        us_job = self.scorer.score(make_job(location="Columbus, OH"))
        intl_job = self.scorer.score(make_job(location="Shenzhen, China", job_hash="hash2"))
        assert us_job.score_location_fit > intl_job.score_location_fit
        assert us_job.fit_score > intl_job.fit_score

    def test_matching_grad_year_scores_highest_eligibility(self):
        job = make_job(qualifications="Open to students graduating in 2029.")
        scored = self.scorer.score(job)
        assert scored.score_eligibility_fit == 100

    def test_grad_year_too_early_lowers_eligibility_score(self):
        # Posting targets 2026 grads; candidate graduates in 2029 - three
        # years later than what the posting is looking for.
        job = make_job(qualifications="Must be graduating between December 2025 and June 2026.")
        scored = self.scorer.score(job)
        assert scored.score_eligibility_fit < 75

    def test_no_grad_year_mentioned_is_neutral(self):
        job = make_job(qualifications="Currently pursuing a degree in engineering.")
        scored = self.scorer.score(job)
        assert scored.score_eligibility_fit == 75

    def test_high_value_skills_score_higher_than_generic_skills(self):
        high_value = self.scorer.score(make_job(required_skills=["SolidWorks", "ANSYS", "CAD"]))
        generic = self.scorer.score(make_job(required_skills=["Excel", "Communication"], job_hash="hash2"))
        assert high_value.score_skills_fit > generic.score_skills_fit

    def test_high_fit_score_sets_flag(self):
        job = make_job(
            role_category="mechanical_design",
            industry_category="aerospace_defense",
            location="Columbus, OH",
            required_skills=["SolidWorks", "CAD", "ANSYS"],
            qualifications="Open to students graduating in 2029.",
        )
        scored = self.scorer.score(job)
        assert scored.fit_score >= 85
        assert scored.is_flagged is True
        assert any("fit score" in reason.lower() for reason in scored.flag_reasons)

    def test_selective_language_sets_flag(self):
        job = make_job(description="This is a highly selective, limited positions leadership program.")
        scored = self.scorer.score(job)
        assert scored.is_flagged is True
        assert any("selective" in r.lower() for r in scored.flag_reasons)

    def test_approaching_deadline_sets_flag(self):
        from datetime import datetime, timedelta, timezone
        deadline = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(timespec="seconds")
        job = make_job(application_deadline=deadline)
        scored = self.scorer.score(job)
        assert scored.is_flagged is True
        assert any("deadline" in r.lower() for r in scored.flag_reasons)

    def test_no_flags_for_average_unremarkable_posting(self):
        job = make_job(
            role_category="other",
            industry_category="other",
            location="",
            required_skills=[],
            job_hash="unremarkable",
        )
        scored = self.scorer.score(job)
        assert scored.is_flagged is False
        assert scored.flag_reasons == []
