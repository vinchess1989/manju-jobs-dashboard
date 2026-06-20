"""Shared fixtures for the manju_jobs test suite."""
import json
import os
import pytest


SAMPLE_JOBS = [
    {
        "url": "https://example.com/job/1",
        "title": "Legal Trainee",
        "company": "Acme Oy",
        "location": "Oulu Region, Finland",
        "matches_requirements": "yes",
        "reason": "Entry-level legal role in Oulu.",
        "user_reason": "testing reason",
        "user_review": "pending",
        "visited": "yes",
        "source": "linkedin",
        "id": "aabbccdd",
        "posted_date": "2026-06-01",
        "deadline": "Open until filled",
    },
    {
        "url": "https://example.com/job/2",
        "title": "Senior Lawyer",
        "company": "Big Corp",
        "location": "Helsinki Region, Finland",
        "matches_requirements": "no",
        "reason": "Senior role — rejected.",
        "user_reason": "",
        "user_review": "pending",
        "visited": "yes",
        "source": "duunitori",
        "id": "11223344",
        "posted_date": "2026-05-20",
        "deadline": "2026-07-01",
    },
    {
        "url": "https://example.com/job/3",
        "title": "Contract Administrator",
        "company": "Nordic Corp",
        "location": "Oulu Region, Finland",
        "matches_requirements": "maybe",
        "reason": "Adjacent role, may suit candidate.",
        "user_reason": "",
        "user_review": "done",
        "visited": "yes",
        "source": "indeed",
        "id": "aabb1122",
        "posted_date": "2026-06-10",
        "deadline": "N/A",
    },
]


@pytest.fixture
def jobs_file(tmp_path):
    """Write SAMPLE_JOBS to a temp jobs.json and return its path."""
    path = tmp_path / "jobs.json"
    path.write_text(json.dumps(SAMPLE_JOBS, indent=2), encoding="utf-8")
    return str(path)


@pytest.fixture
def req_file(tmp_path):
    """Write a minimal requirements file and return its path."""
    content = "## Hard Rejections\n* Senior roles.\n"
    path = tmp_path / "job_requirements.md"
    path.write_text(content, encoding="utf-8")
    return str(path)
