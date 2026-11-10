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

## Recording and slides ownership

Dan leads recording and slide design. Everyone reviews factual claims. Timi and Blessings sign off on architecture and evaluation slides. Do not add unverified pitch metrics to slides.
