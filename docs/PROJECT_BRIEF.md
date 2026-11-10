# Official brief, rules, and deadlines

Sources: Technical Phase Brief (Google Doc `1vVODvnIPy1TnPHBqHeBQ32WBEY1cgH4nQiGdGErH6Fc`, last modified 10 Nov 2026, 12:14 EAT); shortlist email from Hany Zuhudi, 9 Nov 2026, 19:02 EAT; kickoff recap email, 10 Nov 2026, 13:14 EAT; official README template. If this summary disagrees with an official original, prefer the original and record the discrepancy in `docs/DECISIONS.md`.

## Challenge

> How should a blood-bank information system for Africa work, and how can AI make it better without taking decisions away from people?

In 24 hours the team builds **one workflow**, well, on realistic synthetic data, and shows where it sits in a wider system. Our assigned area is **redistribution**:

> Suggests moving units that will expire at one site to a site that is running short, and shows what that saves.

## Official times (EAT, UTC+3) and WAT (UTC+1)

Build window: **Tuesday 10 November 2026, 12:00 EAT to Wednesday 11 November 2026, 12:00 EAT**.

| EAT | WAT (Lagos / Kinshasa; confirm Morocco) | What |
|---|---|---|
| Tue 11:45 | 09:45 | Kickoff call opens |
| Tue 12:00 | 10:00 | Build clock starts |
| Tue 14:00 | 12:00 | Roster and GitHub link due on the check-in form |
| Tue 15:00–16:00 | 13:00–14:00 | Optional blood-service Q&A (Ted Nyaoke, Richard Odongo) |
| Tue 20:00 | 18:00 | Check-in 1: two lines on what works and what is blocking you |
| Wed 06:00 | 04:00 | Check-in 2: same two lines |
| Wed 10:00 | 08:00 | Brief tip: record the demo video by this time |
| Wed 12:00 | 10:00 | **Submissions close** |
| Wed by 20:00 | 18:00 | Five finalists told by email |
| Thu 12 Nov | | Finalists: rehearsal (recap: slots 10:00–13:00 EAT) |
| Fri 13 Nov | | Showcase. Recap: 07:00–14:00 EAT, Nairobi and online. Winner: USD 5,000 |

Zambia is typically CAT (UTC+2, EAT minus 1 hour). Confirm with Blessings and Brayan.

This planning pack was prepared to be used from **Tue 15:30 EAT** (13:30 WAT) onward. The 14:00 roster deadline may already have passed by then; if the GitHub link is not in, treat it as urgent.

The recap email left finalist notification as `[TIME]`. The brief and shortlist email both say Wednesday by 20:00 EAT.

## Quoted rules

> All code must be written between Tuesday 12:00 and Wednesday 12:00. Open-source libraries and frameworks are fine. Code written before the hackathon, by you or anyone else, is not. You may plan, read and set up tools before 12:00 on Tuesday.

> Use one GitHub repository per team, shared with us by 14:00 on Tuesday and public by the deadline. Commit as you go. One large commit at the end will be checked closely.

> You may use ChatGPT, Claude, Copilot, Cursor or similar tools. List which ones and what for in your README. Every team member should be able to explain how your solution works. Using AI will not cost you points. Hiding it, or submitting work you cannot explain, will.

Kickoff recap:

> Everything you submit must be built during the 24 hours. Pre-existing projects will be disqualified.

> Use the synthetic starter dataset. If you bring in other data, cite where it came from. No real patient or donor data.

> The submission form closes at 12:00 on Wednesday. Late submissions are not accepted unless you reported a technical problem to us before 12:00.

## Every submission must have

- A **working prototype of one workflow** on the starter dataset (or other synthetic / openly licensed, cited data). A clickable mock-up alone is not enough.
- **One AI or data feature compared with a simple baseline**, with both numbers shown.
- **A person in control.** Any recommendation that moves blood needs Accept, Change or Reject.
- **A fallback** if the AI is wrong or offline.
- An **architecture diagram**.
- A **README** using the official template, and a **demo video of 3 minutes or less**.

## What AI must never do (quoted)

> - Release a unit for transfusion or decide blood group compatibility without a qualified person.
> - Override a laboratory result or a quarantine.
> - Contact a donor or patient with a message no person has approved.
> - Rank patients for blood on anything other than clinical need.
> - Present a guess as a fact. Every prediction shows its uncertainty.

## How the five finalists are chosen

Each criterion is scored 1 to 5 and weighted to a total out of 100.

| Criterion | Weight | A high score shows |
|---|---|---|
| Working prototype | 25 | The workflow runs end to end on the data, and the demo shows it working, not described. |
| Technical depth and architecture | 20 | Sensible design choices, clean data flows, and the team knows where it could fail. |
| AI and data approach | 15 | Beats a simple baseline with numbers shown, explains itself, keeps a person in control, and has a fallback. |
| Blood-system problem and user | 15 | A specific problem for a named user, using blood-service terms and processes correctly. |
| Fit for African conditions and scale | 15 | Works with weak power and connectivity, can be set up for another site or country, and could connect to existing systems. |
| Demo and readiness to present | 10 | A clear 3-minute video and a team that is ready to present on Friday. |

When totals are within 2 points, the panel looks first at the working prototype score. The panel may also consider who can present in person in Nairobi. The panel's decision is final.

## Deliverables (submission form)

Public GitHub README, demo video ≤ 3 minutes (YouTube unlisted or Drive anyone-with-the-link), optional live demo and test logins, slides, architecture diagram, baseline vs AI result, AI-tool declaration, Friday attendance (in person / online).

**Slide-count conflict:** the Technical Phase Brief says "Up to 8 slides." The kickoff recap says "A pitch deck of 8 to 10 slides, using the template provided." Decision: stay within **8 slides** and use the official template, unless organisers clarify otherwise. See `docs/DEMO_AND_SUBMISSION.md`.

## What this team is building

See `docs/ARCHITECTURE.md` and `docs/IMPLEMENTATION_PLAN.md`. Tier 1 is the evaluation's must-ship review-queue workflow. Tier 2 is the ambitious stretch the team is choosing to pursue because it will stay online through the window. Honesty rules are unchanged.
