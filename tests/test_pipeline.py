from app.pipeline import run_pipeline


SAMPLE = """FICTIONAL TEST AGREEMENT
Between Example Company
and Example Union
Located in Test City, Ontario
Covering 10 employees
Effective January 1, 2024
Expires December 31, 2026

ARTICLE 1 - MANAGEMENT RIGHTS
The Employer shall provide employees with safety equipment.
Management may schedule the work week.

ARTICLE 2 - EMPLOYEE BENEFITS
Employees shall receive three weeks of paid vacation.
Employees may request parental leave.
Employees shall not be required to work during an approved medical leave.
The Union shall notify the Employer of a change in stewards.

APPENDIX A - NON-CORE SCHEDULE
Example classification table
"""


def test_full_pipeline_builds_requested_measures():
    result = run_pipeline(SAMPLE, 11)
    assert result["cleaning"]["removed_line_count"] == 2
    assert len(result["sections"]) >= 3
    assert result["measures"]["contract_level_measures"]["number_of_clauses"] >= 5
    assert result["measures"]["contract_level_measures"]["number_of_worker_rights"] >= 2
    assert result["measures"]["agent_variables"]["firm_obligations"] >= 1
    assert result["measures"]["worker_right_topic_variables"]["vacations"] >= 1


def test_metadata_is_provisional_but_traceable():
    result = run_pipeline(SAMPLE, 2)
    metadata = result["metadata"]
    assert metadata["province_or_territory"] == "Ontario"
    assert metadata["number_of_employees_covered"] == 10
    assert metadata["effective_date"] == "January 1, 2024"
    assert metadata["expiry_date"] == "December 31, 2026"
    assert metadata["evidence"]["number_of_employees_covered"]


def test_each_target_step_stops_cleanly():
    assert "cleaning" in run_pipeline(SAMPLE, 2)
    assert "sections" in run_pipeline(SAMPLE, 3)
    assert "sentences" in run_pipeline(SAMPLE, 4)
    assert "parsed_sentences" in run_pipeline(SAMPLE, 5)
    assert "measures" in run_pipeline(SAMPLE, 10)
    assert "methodology_note" in run_pipeline(SAMPLE, 11)
