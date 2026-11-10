# Damu Grid — 3-minute demo video script (DG-37)

Record by **Wed 11 Nov 2026, 10:00 EAT** (08:00 Kinshasa). Target **2:50**; the hard limit is 3:00. Narration is about 390 words, roughly 140 words a minute. Show the running app, not slides, except at 2:15–2:40 if the Evaluation screen is not working.

**Honesty rules for the recording:** say "synthetic" early; never say "lives saved", "money saved", "released for transfusion" or "approved for compatibility". Show only what runs at the recording commit; skip anything that doesn't.

---

## Setup before recording (10 minutes)

1. **Backend:** the prototype from #50 (`backend/prototype.py`), or Timi's FastAPI (#51) if it is merged and the frontend is switched to it. Delete `data/processed/prototype.sqlite` and restart the prototype so the queue is fresh.
2. **App:** `cd frontend && pnpm dev`, browser at `localhost:3000`, zoom 125%, notifications off, other tabs closed.
3. **Fixture** (computed by the prototype on a fresh database; check it before recording):
   - Unit `U2609-KSM-050343-RBC`, B+ red cells, expires 7 Nov 2026
   - From **HSP-016** Migori County Referral Hospital (3G) → **HSP-018** Western Rift Teaching and Referral Hospital
   - 5.31 h by road, recipient gap 9, sender keeps 1
4. **Second tab** on `/queue`, opened *before* accepting; it is used for the blocked-move shot.
5. **Recording commit:** write the SHA in `docs/DEMO_AND_SUBMISSION.md` at the 09:30 freeze.

**If the prototype still computes only one card**, record accept, change and reject as three short takes. Reset the database between takes (stop, delete `prototype.sqlite`, restart) and cut them together. Say "on a fresh snapshot" in the change take.

**Model off needs its own take too:** the prototype's fallback mode currently offers the same single unit, so after it is accepted the fallback queue is empty. Record the 1:55 shot on a fresh database (or before the accept take).

---

## Script

### 0:00–0:20 · The problem — *screen: login page, then the review queue*

> This is Damu Grid, built for the stock coordinator at a regional blood centre. In the synthetic starter year we were given, 23 percent of red cell and whole blood units were wasted, while 12 percent of requested red cells were never issued. Only 177 of 35,000 transfers moved blood between sites on purpose.

*Action:* choose **Regional stock coordinator**. The queue loads.

### 0:20–0:50 · One computed card — *screen: the card*

> Every morning Damu Grid shows a short queue. This card is computed from the closing stock on 31 October. B-positive red cells at Migori expire on 7 November. Western Rift, five hours away, has an estimated gap of nine units, and Migori keeps its reserve. The card shows the stock date, travel time, and an uncertainty label: this is an estimate, not a clinical probability.

*Action:* point at expiry, gap, reserve, travel time, "Stock as of", uncertainty. Open **Unit IDs**.

### 0:50–1:30 · A person decides — *screen: dialogs, decisions panel, second tab*

> Nothing moves until a person decides. I accept, with a reason. The units are now reserved for this move and recorded in the audit trail. Accepting is not dispatch, and it is not a release for transfusion.

*Action:* **Accept** → type "Western Rift confirmed it can receive today" → **Ctrl+Enter**. The decisions panel shows "Accepted: units reserved".

> If someone else acts on the same units first, Damu Grid blocks it.

*Action:* switch to the second tab → **Accept** the same card → the conflict message appears.

> Changes and rejections need a reason too, and every one is logged.

*Action:* (second take, or the second card) **Change** → new destination + reason; **Reject** → "Receiving hospital refused".

### 1:30–1:55 · Dispatch and receipt — *screen: Dispatch, then Receive, then the move page*

> The sending officer rechecks the physical units and dispatches. The receiving officer confirms arrival. If the cool-box evidence is missing, Damu Grid holds the units for the safety officer. Software never clears a hold.

*Action:* **Switch role → Sending officer** → tick the three checks → **Confirm dispatch**. **Switch role → Receiving officer** → **Not sure** → **Confirm receipt** → toast "held for the safety officer's review" → open the move page and show the audit trail.

### 1:55–2:15 · Model off — *screen: queue with the switch*

> If the forecast is wrong or offline, the coordinator switches the model off. A simple nearest-site rule fills the queue, with the same safety checks and the same approval, and the work continues.

*Action:* **Switch role → coordinator** → toggle **Model off** → the fallback card shows "Fallback rule · model off".

### 2:15–2:40 · Does it beat a baseline? — *screen: Evaluation page (or slide 06)*

> The forecast behind those gaps is tested against a 28-day average on held-out weeks from July to October. Its seven-day error is 2.47 units against 2.79 for the baseline, eleven percent lower, over 4,352 hospital, blood group and week observations. Synthetic data, a retrospective test.

*Action:* show the verdict and the table. If `/evaluation/forecast` is still broken, show slide 06 instead and do not claim the screen works.

### 2:40–2:55 · Architecture and close — *screen: architecture diagram (slide 05)*

> Damu Grid is a small module beside existing blood bank systems: a web app, an API, and a data pipeline over the official CSVs. It works with the model off and shows data age for slow sites. It never releases blood or decides compatibility. Team Damu Grid, from DR Congo, Morocco, Nigeria and Zambia.

---

## Shot list (tick while recording)

- [ ] "Synthetic" said before 0:20
- [ ] Computed card with expiry, gap, reserve, travel, data age, uncertainty
- [ ] Accept with a reason → reserved; audit mentioned
- [ ] Blocked action (conflict) shown with its real message
- [ ] Change and reject, each with a reason (or the documented subset)
- [ ] Dispatch → receipt → held for safety review; "not a release for transfusion"
- [ ] Model off → fallback card
- [ ] Forecast vs baseline numbers with period and sample size
- [ ] Ends before 3:00; measured duration: ____
- [ ] Uploaded (YouTube unlisted or Drive, anyone with the link can view); link: ____

## Where the numbers come from

- 23%, 12%, 177 of 35,181: `slides/DECK_DRAFT.md` method notes (recomputed in the window from `data/raw/`).
- 2.474 vs 2.792, 4,352 observations: `python -m forecasting.evaluate` (#47).
- Fixture card: `backend/prototype.py` (#50) on a fresh database. Re-check before recording; if the backend changes, update the fixture lines above.
