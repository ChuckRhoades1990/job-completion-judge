"""Direct-mode tests for JobCompletionJudge (LLM mocked)."""

from tests.direct.conftest import to_hex

C = "contracts/job_completion_judge.py"
SCOPE = "Supply and lay 20m2 hybrid vinyl plank in kitchen; fit scotia; remove old lino."

OK = '{"complete": true, "unmet_items": [], "reason": "All items evidenced."}'
BAD = '{"complete": false, "unmet_items": ["scotia"], "reason": "Scotia not fitted."}'


def _setup(direct_vm, direct_deploy, alice, bob):
    c = direct_deploy(C)
    direct_vm.sender = alice
    job_id = c.create_job(to_hex(bob), SCOPE)
    return c, job_id


def test_create_job(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, job_id = _setup(direct_vm, direct_deploy, direct_alice, direct_bob)
    assert job_id == "job-1"
    j = c.get_job(job_id)
    assert j["status"] == "open"
    assert j["customer"] == to_hex(direct_alice)
    assert c.get_job_count() == 1


def test_scope_too_short(direct_vm, direct_deploy, direct_alice, direct_bob):
    c = direct_deploy(C)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Scope too short"):
        c.create_job(to_hex(direct_bob), "floor")


def test_complete_verdict(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, job_id = _setup(direct_vm, direct_deploy, direct_alice, direct_bob)
    direct_vm.mock_llm(r".*inspector.*", OK)
    direct_vm.sender = direct_bob
    assert c.submit_completion(job_id, "Laid 20m2 hybrid, scotia fitted, lino removed.") == "complete"
    assert c.get_job(job_id)["unmet_items"] == []


def test_incomplete_then_dispute(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, job_id = _setup(direct_vm, direct_deploy, direct_alice, direct_bob)
    direct_vm.mock_llm(r".*inspector.*", BAD)
    direct_vm.sender = direct_bob
    assert c.submit_completion(job_id, "Laid 20m2 hybrid, lino removed.") == "incomplete"
    assert c.get_job(job_id)["unmet_items"] == ["scotia"]

    direct_vm.clear_mocks()
    direct_vm.mock_llm(r".*inspector.*", OK)
    assert c.dispute(job_id, "Photo note: scotia fitted on all edges.") == "complete"
    with direct_vm.expect_revert("Already disputed"):
        c.dispute(job_id, "again")


def test_only_contractor_submits(direct_vm, direct_deploy, direct_alice, direct_bob):
    c, job_id = _setup(direct_vm, direct_deploy, direct_alice, direct_bob)
    with direct_vm.expect_revert("Only the contractor can submit"):
        c.submit_completion(job_id, "done")


def test_outsider_cannot_dispute(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    c, job_id = _setup(direct_vm, direct_deploy, direct_alice, direct_bob)
    direct_vm.mock_llm(r".*inspector.*", OK)
    direct_vm.sender = direct_bob
    c.submit_completion(job_id, "all done")
    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("Only job parties can dispute"):
        c.dispute(job_id, "x")
