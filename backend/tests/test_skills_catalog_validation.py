from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.job_orders import JobAssignmentWorkerOut, JobOrderCreate
from app.schemas.workers import WorkerProfileIn


def _job_payload(required_skills: list[str]) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "title": "Developer Shift",
        "job_type": "Warehouse Worker",
        "location_address": "SG",
        "location_lat": 1.3,
        "location_lng": 103.8,
        "required_skills": required_skills,
        "shifts": [
            {
                "starts_at": now.isoformat(),
                "ends_at": now.isoformat(),
                "workers_required": 1,
            }
        ],
    }


def test_job_required_skills_are_canonicalized_and_deduped():
    body = JobOrderCreate(**_job_payload(["  web development ", "Web Development", "API Integration"]))
    assert body.required_skills == ["Web Development", "API Integration"]


def test_job_required_skills_reject_unknown_values():
    with pytest.raises(ValidationError):
        JobOrderCreate(**_job_payload(["Unknown Skill"]))


def test_worker_profile_skills_are_canonicalized_and_deduped():
    body = WorkerProfileIn(skills=["  devops ", "DevOps", "API Integration"])
    assert body.skills == ["DevOps", "API Integration"]


def test_worker_profile_skills_reject_unknown_values():
    with pytest.raises(ValidationError):
        WorkerProfileIn(skills=["Not In Catalogue"])


def test_job_assignment_worker_out_supports_worker_skills_payload():
    row = JobAssignmentWorkerOut(
        assignment_id=1,
        shift_id=1,
        shift_starts_at=datetime.now(timezone.utc),
        shift_ends_at=datetime.now(timezone.utc),
        worker_profile_id=2,
        worker_name="Worker",
        assignment_status="applied",
        worker_skills=["Web Development"],
        worker_certifications=["Forklift Operator"],
    )
    assert row.worker_skills == ["Web Development"]
    assert row.worker_certifications == ["Forklift Operator"]
