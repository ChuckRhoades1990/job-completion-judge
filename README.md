# JobCompletionJudge

An Intelligent Contract for **trustless sign-off on trade jobs** (flooring, painting, plumbing, any scoped work), built on [GenLayer](https://genlayer.com).

## The problem
"Is the job done?" is the most common dispute between customers and tradespeople. Ordinary smart contracts can't answer it because the answer lives in natural language: a scope of work and a completion report. GenLayer validators, each running a different LLM, can.

## How it works
1. **Customer** calls `create_job(contractor, scope)` with the agreed written scope.
2. **Contractor** calls `submit_completion(job_id, report)` when finished.
3. Validators judge whether the report evidences *every* scope item. The verdict (`complete` / `incomplete`), the list of unmet items and a short reason are stored on-chain.
4. Either party may call `dispute(job_id, evidence)` **once** to add evidence and trigger a fresh judgement.

### Consensus design
The judgement runs in `gl.vm.run_nondet_unsafe` with a custom validator function. Validators must agree on:
- the boolean `complete` verdict, and
- whether the unmet-items list is empty.

The free-text `reason` is allowed to differ between models, so wording differences don't cause disagreement while the decision itself stays strict. Anything not clearly evidenced is treated as unmet.

## Methods
| Method | Type | Who |
|---|---|---|
| `create_job(contractor: str, scope: str) -> str` | write | customer |
| `submit_completion(job_id: str, report: str) -> str` | write | contractor only |
| `dispute(job_id: str, evidence: str) -> str` | write | customer or contractor, once |
| `get_job(job_id: str) -> dict` | view | anyone |
| `get_job_count() -> int` | view | anyone |

## Deployment
Deployed on **GenLayer Studio (studionet)**:
`0xedB61B73cE7514D900E7c88f676dA32cCCfD7Fe9`

## Run the tests
```bash
pip install -r requirements.txt
genvm-lint check contracts/job_completion_judge.py
python -m pytest tests/direct -v
```
Direct-mode tests mock the LLM and cover: job creation, scope validation, complete and incomplete verdicts, the dispute flow (including the single-dispute limit) and access control.

## Example
Scope: *"Supply and lay 20m2 hybrid vinyl plank in kitchen; fit scotia; remove old lino."*
Report: *"Laid 20m2 hybrid, lino removed."* → `incomplete`, unmet: `["scotia"]`
Dispute evidence: *"Scotia fitted on all edges."* → `complete`

## License
MIT
