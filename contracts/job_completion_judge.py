# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
JobCompletionJudge — trustless sign-off for trade jobs.

A customer and a contractor agree a written scope of work. When the job is
done the contractor submits a completion report. GenLayer validators (each
running a different LLM) judge whether the report satisfies the agreed
scope, and the verdict is recorded on-chain. Either party can dispute once,
adding extra evidence, which triggers a fresh judgement.

Equivalence: validators must agree on the boolean `complete` verdict and the
list of unmet items count; the free-text reason may differ between models.
"""
import json
from dataclasses import dataclass
from genlayer import *


@allow_storage
@dataclass
class Job:
    id: str
    customer: Address
    contractor: Address
    scope: str
    report: str
    dispute_note: str
    status: str  # open | submitted | complete | incomplete
    reason: str
    unmet: str  # JSON list of unmet scope items
    disputed: bool


STATUS_OPEN = "open"
STATUS_SUBMITTED = "submitted"
STATUS_COMPLETE = "complete"
STATUS_INCOMPLETE = "incomplete"


class JobCompletionJudge(gl.Contract):
    jobs: TreeMap[str, Job]
    job_count: u256

    def __init__(self):
        self.job_count = u256(0)

    # ── helpers ───────────────────────────────────────────────────────────

    def _get(self, job_id: str) -> Job:
        if job_id not in self.jobs:
            raise gl.vm.UserError("Job not found")
        return self.jobs[job_id]

    def _judge(self, scope: str, report: str, dispute_note: str) -> dict:
        prompt = f"""You are an impartial building-trades inspector.

AGREED SCOPE OF WORK:
{scope}

CONTRACTOR COMPLETION REPORT:
{report}

ADDITIONAL DISPUTE EVIDENCE (may be empty):
{dispute_note}

Decide if the completion report shows that EVERY item in the agreed scope
was delivered. Treat anything not clearly evidenced as unmet.

Respond ONLY with JSON:
{{"complete": bool, "unmet_items": [str], "reason": str}}"""

        def leader_fn() -> dict:
            res = gl.nondet.exec_prompt(prompt, response_format="json")
            unmet = res.get("unmet_items", []) or []
            return {
                "complete": bool(res.get("complete", False)),
                "unmet_items": [str(x) for x in unmet],
                "reason": str(res.get("reason", ""))[:500],
            }

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            mine = leader_fn()
            theirs = leader_result.calldata
            return mine["complete"] == theirs["complete"] and (
                len(mine["unmet_items"]) == 0
            ) == (len(theirs["unmet_items"]) == 0)

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

    def _apply_verdict(self, job: Job) -> None:
        verdict = self._judge(job.scope, job.report, job.dispute_note)
        job.status = STATUS_COMPLETE if verdict["complete"] else STATUS_INCOMPLETE
        job.reason = verdict["reason"]
        job.unmet = json.dumps(verdict["unmet_items"])

    # ── writes ────────────────────────────────────────────────────────────

    @gl.public.write
    def create_job(self, contractor: str, scope: str) -> str:
        if len(scope.strip()) < 10:
            raise gl.vm.UserError("Scope too short")
        self.job_count = u256(int(self.job_count) + 1)
        job_id = f"job-{int(self.job_count)}"
        self.jobs[job_id] = Job(
            id=job_id,
            customer=gl.message.sender_address,
            contractor=Address(contractor),
            scope=scope,
            report="",
            dispute_note="",
            status=STATUS_OPEN,
            reason="",
            unmet="[]",
            disputed=False,
        )
        return job_id

    @gl.public.write
    def submit_completion(self, job_id: str, report: str) -> str:
        job = self._get(job_id)
        if gl.message.sender_address != job.contractor:
            raise gl.vm.UserError("Only the contractor can submit")
        if job.status != STATUS_OPEN:
            raise gl.vm.UserError("Job already submitted")
        job.report = report
        job.status = STATUS_SUBMITTED
        self._apply_verdict(job)
        return job.status

    @gl.public.write
    def dispute(self, job_id: str, evidence: str) -> str:
        job = self._get(job_id)
        sender = gl.message.sender_address
        if sender != job.customer and sender != job.contractor:
            raise gl.vm.UserError("Only job parties can dispute")
        if job.status not in (STATUS_COMPLETE, STATUS_INCOMPLETE):
            raise gl.vm.UserError("Nothing to dispute yet")
        if job.disputed:
            raise gl.vm.UserError("Already disputed")
        job.disputed = True
        job.dispute_note = evidence
        self._apply_verdict(job)
        return job.status

    # ── views ─────────────────────────────────────────────────────────────

    @gl.public.view
    def get_job(self, job_id: str) -> dict:
        job = self._get(job_id)
        return {
            "id": job.id,
            "customer": job.customer.as_hex,
            "contractor": job.contractor.as_hex,
            "scope": job.scope,
            "report": job.report,
            "dispute_note": job.dispute_note,
            "status": job.status,
            "reason": job.reason,
            "unmet_items": json.loads(job.unmet),
            "disputed": job.disputed,
        }

    @gl.public.view
    def get_job_count(self) -> int:
        return int(self.job_count)
