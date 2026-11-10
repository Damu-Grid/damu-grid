# Demo and submission

Follow the official Technical Phase Brief and the 10 November 2026 kickoff recap from hany@talo.africa. If a later official message changes a rule, update this file and `docs/DECISIONS.md`.

## Slide count conflict

- Brief: "up to 8 slides" and use the official Google Slides template.
- Kickoff recap: "8 to 10 slides".

**Decision (ADR-001):** stay at **eight slides** and use the official template. Do not invent a ninth or tenth unless organisers confirm in writing that 10 is allowed. The official template is in the Applicant's Kit: Google Slides `1Nzz_kXVY6IlkHtiii3Rc2qIEDN9lGqjh_kcmtM-LYQ8`.

Suggested eight-slide story (titles can tighten; keep evidence honest):

1. Problem and named user (regional stock coordinator).
2. Workflow in one diagram (suggest → review → reserve → dispatch → receipt).
3. Suggestion card anatomy and eligibility gates.
4. Demo path (what judges will see).
5. AI/data approach and baseline table (synthetic; both numbers).
6. Architecture and African operating conditions (fallback, connectivity, config).
7. Limitations, what we will not claim, Friday attendance.
8. Team, AI-tool declaration pointer, repo and video links.

## Video

- Limit: **3 minutes** (recap also says "3 minutes max"). Time the rehearsal.
- Record **by Wednesday 11 November 2026, 10:00 EAT**.
- Show running software, not slides as a substitute for the prototype.
- Use the script in `docs/IMPLEMENTATION_PLAN.md`. If a Tier 2 feature is not actually running, skip it.
- Say "synthetic official starter dataset" early. Do not claim clinical clearance, money or lives saved, or real Kenyan operational facts.
- End before 3:00. Leave a few seconds of slack.

Store the file (or an export) under `slides/` and put the shareable link in the README. Permissions: anyone with the link can view.

## Submission form checklist

Complete **before Wednesday 11 November 2026, 12:00 EAT**. Prefer submit by 11:00 EAT.

- [ ] Public GitHub repository URL (this repo, once published by the team).
- [ ] All application code committed in the official window; incremental commits as evidence.
- [ ] README follows the official template, including AI-tool declaration and baseline results (computed, or an honest "not yet computed" is unacceptable at submit time — compute or say the work did not finish).
- [ ] Architecture diagram.
- [ ] Demo video link, viewable, ≤ 3 minutes.
- [ ] Pitch deck link, official template, eight slides, viewable.
- [ ] Confirmation that a team representative will attend the Friday 13 November 2026, 16:00–18:00 EAT session.
- [ ] No secrets in the repo (no `.env`, no API keys).
- [ ] Dataset terms respected: synthetic labelled; official CSVs not presented as real Kenyan facts.
- [ ] Never claimed clinical clearance or transfusion decision support.

One person (agreed at the 06:00 check-in) fills the form. Everyone else stays off the submit button. After submit, do not assume late edits will be accepted.

## Friday session

Friday 13 November 2026, 16:00–18:00 EAT. The recap says a 3-minute recap plus 7 minutes for questions, and that the video is a backup if the live demo fails. Confirm the live format if organisers send a later note. Prepare a fallback: recorded video plus a local Docker or documented run.

## DG-39 readiness record

Inspected 10 November 2026 against foundation commit `5db0537`. This is a blocker register, not a completed rehearsal or submission. Dependencies: [DG-37 / #38](https://github.com/Damu-Grid/damu-grid/issues/38) (video) and [DG-38 / #39](https://github.com/Damu-Grid/damu-grid/issues/39) (README). Update evidence against the actual recording commit when these land.

| Gate | Current evidence or blocker | Owner to resolve |
|---|---|---|
| Running workflow and clean-start commands | BLOCKED: application folders contain planning READMEs only at the inspected commit. No running UI/API to rehearse. | Timi, Brayan, Dan |
| Forecast table | BLOCKED: no in-window evaluator or generated results in this checkout. Do not paste metrics from the attached pitch. | Blessings |
| Architecture diagram | PRESENT: Mermaid diagrams in `docs/ARCHITECTURE.md`; planned design, still requires comparison with implemented behaviour. | Timi and Blessings |
| Official README | BLOCKED: application commands, measured results and video links remain unfinished. Codex's work in this change is declared. | Everyone |
| Video (#38) | BLOCKED: no recording, duration measurement or viewable link supplied. | Dan |
| Eight slides (#37) | BLOCKED: no completed official-template deck or verified view-only link supplied. | Dan; Timi and Blessings review |
| Public repository | UNVERIFIED: a human must check visibility and anonymous access before submission. | Agreed submitter |
| Secrets and history | PARTIAL: tracked environment filename check finds only `.env.example`. Full secret/history scan has not run; gitleaks is unavailable locally. The documented `.github/workflows/ci.yml` is absent at this commit, so CI protection is not evidenced. | Timi / repository maintainer |
| Submission speaker / operator | BLOCKED: name and backup not yet agreed; record at 06:00 EAT. | Everyone |
| Friday attendance | BLOCKED: named representative and in-person/online mode unconfirmed. `PROJECT_BRIEF.md` also lists a wider showcase window; verify the team's actual slot against the latest official communication. | Everyone |
| Rehearsal and freeze | BLOCKED: no timed rehearsal or frozen commit yet. Use the record below. | Dan and agreed submitter |

### Freeze and handoff (Wednesday 11 November 2026)

| EAT (UTC+3) | South Africa / Zambia (UTC+2) | Required record |
|---|---|---|
| 06:00 | 05:00 | Agree form operator, backup, speaker and Tier 2 cut list. |
| 09:30 | 08:30 | Freeze feature merges for recording; record commit SHA. Critical fixes need a rerun of affected demo steps. |
| 10:00 | 09:00 | Recording complete; duration at most 180 seconds, preferably 170–175 seconds. |
| 11:00 | 10:00 | Preferred early submission, only if required evidence is complete. |
| 11:15 | 10:15 | Submission freeze; only documentation/access fixes. Do not wait until this freeze to submit a ready entry. |
| 12:00 | 11:00 | Official deadline; report any technical problem before it. |

These are team checkpoints, not automatically enforced GitHub merge restrictions.

### Rehearsal evidence to fill

Run the timed story in `IMPLEMENTATION_PLAN.md` from a clean start. Record fixture IDs rather than selecting a convenient unrepeatable card. Leave unperformed steps unchecked and state the blocker.

- Recording commit SHA: **pending**
- Start/run command verified by a second teammate: **pending**
- Coordinator, sender and receiver demo identities (no passwords): **pending**
- Fixture suggestion/unit/move IDs and reset procedure: **pending**
- [ ] Open a computed card; show synthetic label, as-of, expiry, reserve, gap and uncertainty.
- [ ] Accept, Change and Reject (or document the demonstrated subset); show new state and audit.
- [ ] Attempt an invalid action and show the actual block/error.
- [ ] Dispatch and confirm receipt; say receipt is not transfusion release.
- [ ] Show both recomputed forecast results, evaluation period and sample size.
- [ ] Toggle model off; demonstrate eligible fallback and human approval.
- [ ] Time the complete recording and verify sound/text are understandable.
- Measured duration and reviewer: **pending**
- Failed steps, skipped Tier 2 features and assigned fixes: **pending**
- Final recording link: **pending**
- Final eight-slide link: **pending**

### Human submission handoff

- Form operator / backup / speaker: **pending team agreement at 06:00 EAT**
- Friday representative / attendance mode / confirmed slot: **pending**
- [ ] Review the exact recording commit, README, results and AI-tool declarations.
- [ ] Run a secret scan over the working tree and complete Git history; record command, tool version, commit and outcome without copying any discovered secrets into this document. Resolve findings before making the repository public.
- [ ] Confirm no tracked `.env` files except a names-only `.env.example`; inspect staged changes too.
- [ ] Verify public repository, video and slides in a signed-out browser; record reviewer and time.
- [ ] Verify the recording's running behaviour matches the submitted commit; rerun affected steps after critical fixes.
- [ ] Agreed human operator submits the official form once and retains confirmation.
- Submission confirmation reference and actual EAT time: **pending**

No checklist entry authorises an agent to publish the repository, change access settings, submit the form, or contact anyone. Do not tick a gate based on a plan or a tool's availability alone.

Repeatable filename check from the repository root (lists paths only):

```bash
git ls-files -- '*.env*' '*credentials*' '*.pem' '*.key'
git diff --cached --name-only
git rev-parse HEAD
```

Inspect every returned path; `.env.example` must contain names/placeholders only. This is a filename check, not a content or history secret scan. Record the separate secret scanner's result in the handoff above.

## Recording and slides ownership

Dan leads recording and slide design. Everyone reviews factual claims. Timi and Blessings sign off on architecture and evaluation slides. Do not add unverified pitch metrics to slides.
