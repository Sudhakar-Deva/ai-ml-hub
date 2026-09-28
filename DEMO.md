# Demo Guide — Claims Assistant

A step-by-step script for presenting this project from the UI, in plain language.

Each step has three parts:
- **Click:** what to do on screen
- **Look at:** what to point at
- **Say:** words you can use as they are, or put in your own words

Each step also has a short **"What this means"** box. Read those once before the demo so you understand what you're showing. You don't need to say them out loud.

---

## Part 1: Understand the project in 5 minutes

### What is this app?

An assistant for **insurance claim adjusters** (the people who decide whether an insurance claim gets paid).

The adjuster types a question, such as *"Is water damage from a burst pipe covered?"*. The app:
1. **Searches** 6 insurance policy documents for the relevant paragraph
2. **Hands that paragraph to an AI**, which writes the answer
3. **Shows where the answer came from** (which document, which section)
4. **Says "I don't know"** if the documents don't contain the answer

### The simplest way to picture it

Think of a **librarian and a writer** working together:

| Role | In the app | Its job |
|---|---|---|
| 📚 **Librarian** | The search part ("retrieval") | Finds the right pages in the documents |
| ✍️ **Writer** | The AI model | Reads only those pages and writes the answer |

**The key idea of the whole demo:** if the librarian brings the **wrong page**, even the best writer in the world gives a wrong answer. Hiring a better writer doesn't help; you need a better librarian.

### The problem this demo solves

- The app answered simple questions well, like *"Is water damage covered?"*
- But it got questions with **codes** wrong, like *"Does exclusion **E-17** apply under form **HO-0304**?"*
- The team lead said: *"Let's switch to a better AI model."*
- **What this project showed:** the AI wasn't the problem. The **search** was bringing the wrong pages. Fixing the search raised the score from **8 out of 12 to 11 out of 12**.

### A few words you'll hear (plain meanings)

| Word | Plain meaning |
|---|---|
| **Policy** | The insurance contract |
| **Endorsement / Form** | An add-on document that changes the policy. Each has a code like **HO-0304** (homeowners) or **DP-0110** (dwelling fire) |
| **Exclusion** | Something the policy does **not** pay for. Each one has a code like **E-17** |
| **Claim** | A customer asking the insurance company to pay for damage |
| **Adjuster** | The person who checks the claim and decides the payout |
| **Chunk** | A small piece of a document, around one paragraph. Documents are cut into chunks so the app can search them |
| **Retrieval / Search** | Finding the right chunks for a question (the librarian) |
| **Citation** | The "source" shown after an answer, like a footnote |
| **Top-3 / Top-5** | The 3 or 5 best search results |

### The one fact that makes this interesting

**E-17 means opposite things in two different documents:**

| Document | What E-17 says about a burst water pipe |
|---|---|
| **HO-0304** (homeowners) | ✅ **Covered**: the exclusion does NOT apply |
| **DP-0110** (dwelling fire) | ❌ **Not covered**: the exclusion applies |

So if the app finds the E-17 paragraph from the **wrong document**, it gives the **opposite answer**, and a claim gets wrongly paid or wrongly refused. That's why finding the exact right paragraph matters so much.

---

## Part 2: Before the demo (arrive 10 minutes early)

### Start the app

Open **two terminal windows**.

**Terminal 1**, the backend (the "brain"):
```bash
cd ~/Desktop/python/ai-ml-hub/backend
source ../.venv/bin/activate
export ANONYMIZED_TELEMETRY=False
uvicorn app.main:app --reload --port 8000
```

**Terminal 2**, the website (the screen you show):
```bash
cd ~/Desktop/python/ai-ml-hub/frontend
yarn dev
```

Then open **http://localhost:5173** in your browser.

### Warm it up

- **Click each tab's button once**, and **ask one question** in the Ask tab.
- **Why:** the first answer is slow (about 25 seconds) because the app is loading. After that, answers take about 7–10 seconds.
- **Then wait 1 minute without clicking.** The free AI account allows only a limited amount of use per minute, and this lets it reset.

### Keep these questions ready to copy and paste

| Where | Question to paste |
|---|---|
| Search tab | `is water damage from a burst supply line excluded under E-17?` |
| Ask, question 1 | `Does exclusion E-17 apply under form HO-0304 ed. 03-24 when a supply line ruptures and floods the kitchen?` |
| Ask, question 2 | `Same loss on a dwelling fire risk — is E-17 excluded under DP-0110 ed. 02-24?` |
| Ask, question 3 | `What is the reserve-setting threshold for claim CLM-2024-88431?` |

---

## Part 3: The demo script (about 12 minutes)

The screen has **5 tabs** at the top: **Search · Ask · Inspect · hit-rate@3 · Bench (wk3)**. We'll use them in this order: **Ask → Bench → Search → Inspect → hit-rate@3**.

---

### 🎤 Opening (30 seconds)

**Say:**
> "This is an assistant for insurance claim adjusters. It answers questions using only our 6 policy documents, it shows exactly which paragraph each answer came from, and if the answer isn't in the documents, it says so instead of guessing.
>
> It had a problem: simple questions worked, but questions with exclusion codes like E-17 went wrong. The suggestion was to switch to a better AI model. I'll show you, with numbers, that the AI wasn't the problem, and what actually fixed it."

---

### Step 1: Ask tab, show what the app does (2 minutes)

**Click:** the **Ask** tab. Paste **question 1**, click **Ask**, and wait about 10 seconds.

**Look at:** the answer says **"No, E-17 does not apply… covered"**, and ends with something in square brackets like `[structure_aware:HO-0304:... | HO-0304 ed. 03-24 | SECTION I — EXCLUSIONS / E-17]`.

**Say:**
> "It says the damage is covered. The text in square brackets at the end is the source: which document and which section it came from. The app also checks that this source really exists, so the AI can't invent one."

**Click:** paste **question 2** and click **Ask**.

**Look at:** this time the answer is **"Yes, it is excluded"**, from **DP-0110**.

**Say:**
> "Same code, E-17, but in a different policy document the answer is the opposite. That's why finding the exact right paragraph matters. The wrong one means paying or refusing a claim wrongly."

**Click:** paste **question 3** and click **Ask**.

**Look at:** the answer starts with **`INSUFFICIENT_CONTEXT`**.

**Say:**
> "This information isn't in our documents; it lives in a different system. So the app refuses instead of making something up. In insurance, a made-up answer about coverage can become a legal problem."

> 💡 **What this means:** The app is designed to refuse when the answer isn't in the documents. The AI is given strict instructions: *answer only from these paragraphs, cite every sentence, and if the answer isn't there, say so.*

⏳ **Tip:** each answer takes a few seconds. Keep talking while it loads.

---

### Step 2: Bench (wk3) tab, how the documents were cut up (1 minute)

**Click:** the **Bench (wk3)** tab, then **Run all 8 questions × 2 chunkers**.

**Look at:** two big numbers, **8/8** and **8/8**.

**Say:**
> "Before the app can search documents, it cuts them into small pieces. I tried two ways. The first cuts every 1,000 characters, like cutting a page with a ruler. The second cuts along the document's own sections and keeps each exclusion row together with its document code. Both found the right answer for all 8 test questions. I kept the second one, because every piece carries its document name, and that's what makes the sources you just saw possible."

> 💡 **What this means:** Picture cutting a recipe book into cards. Cutting every 10 lines might split one recipe across two cards. Cutting by recipe keeps each recipe whole. The second method is "cutting by recipe".

---

### Step 3: Search tab, the filter (1.5 minutes)

**Click:** the **Search** tab.
1. Paste the **Search question**.
2. In the first dropdown, keep **structure_aware**. In the second, choose **dense**.
3. In the small **"policy_line filter"** box, type **`dwelling_fire`**.
4. Click **Search**.

**Look at:** two lists side by side.
- **Left (no filter):** the top results are **E-20, E-19, E-21**. None of them is E-17!
- **Right (filtered to dwelling fire):** the #1 result is **DP-0110 … E-17**.

**Say:**
> "On the right, I told the search to look only inside dwelling-fire documents, and the top result changed to the right one. That's a filter.
>
> But look at the left. I asked about E-17, and it gave me E-20, E-19 and E-21: all about water, but not what I asked for. **That's the real bug.** Let me show you where it comes from."

> 💡 **What this means:** A filter is like telling the librarian "only look in the red books". The left list shows the librarian bringing books on the right topic but not the exact page asked for.

---

### Step 4: Inspect tab with "dense", finding the cause (3 minutes)

This is **the most important step** of the demo.

**Click:** the **Inspect** tab. Choose **dense** in the dropdown. **Do NOT tick the checkbox.** Click **Inspect all 12**.

**Look at:** the score boxes at the top: **R = 4, G = 0, Not-In-Corpus = 0, pass = 8**.

**Say:**
> "I wrote 12 real questions an adjuster would ask, and for each one I know exactly which paragraph holds the answer. 8 worked and 4 failed.
>
> For each failure I asked one question: did the search find the right paragraph or not?
> - **R** means the search did *not* find it. The AI never even saw the right paragraph.
> - **G** means the search *did* find it, but the AI still answered wrong.
>
> **All 4 failures are R. Zero are G.** The AI never got the right paragraph. So switching to a better AI would have fixed **zero** of these 4. It's like hiring a better writer when the librarian keeps bringing the wrong book."

**Click:** scroll down to the red card labelled **G01**.

**Look at:** on the left, the 3 paragraphs the search found. On the right, **"not in the top-3"**.

**Say:**
> "Here's the question 'does E-17 apply under HO-0304'. The search brought back an E-17 paragraph, but from **DP-0110**, the wrong document, where the answer is the opposite. It looks like the AI's mistake, but the AI was simply given the wrong page."

**Look at:** the small **"exact token"** labels on the red cards.

**Say:**
> "Every failure has a code in the question, like E-17 or HO-0304. Every question written in normal English passed. So the search is bad at exact codes. That tells us exactly what to fix."

> 💡 **What this means: why is the search bad at codes?** The search understands **meaning**, not exact spelling. To it, "E-17" and "E-19" look almost identical, like how "car" and "automobile" mean the same thing. That's great for normal sentences but bad for codes, where one digit changes everything.
>
> **R** = **R**etrieval (search) problem. **G** = **G**eneration (AI writing) problem. **Not-In-Corpus** = the answer isn't in any document.

---

### Step 5: Inspect tab with "hybrid", the fix (1.5 minutes)

**Click:** change the dropdown to **hybrid**, then click **Inspect all 12** again.

**Look at:** **R drops from 4 to 1.** Each result now shows two small labels like **`dense #9`** and **`bm25 #2`**.

**Say:**
> "I added a second kind of search next to the first one. The first understands **meaning**. The new one, called **BM25**, matches **exact words**, like pressing Ctrl+F. It knows that 'E-17' is a rare, specific word and ranks it highly.
>
> Then I combine the two result lists. I don't add up their scores, because they're measured in different units, like adding kilograms to kilometres. I combine them by **position**: if a paragraph ranks near the top in either list, it ends up near the top overall. This method is called **Reciprocal Rank Fusion**.
>
> I changed only this one thing: same documents, same AI, same 12 questions. So we know this change caused the improvement."

> 💡 **What this means:** It's like asking two librarians, one who understands topics and one who's great at finding exact words, then taking the books both rank highly. "Hybrid" means using both together.
>
> **Why change only one thing?** If you change two things and the score goes up, you can't tell which one helped. Changing one thing at a time is what makes the result trustworthy.

---

### Step 6: hit-rate@3 tab, the final score and the cost (2 minutes)

**Click:** the **hit-rate@3** tab, then **Measure dense vs hybrid**.

**Look at:**
- The two big numbers: **dense 8/12 → hybrid 11/12**
- The small **"p50"** number under each (about **7 ms → 9 ms**)
- In the table, questions **G01, G02, G05** change from ❌ to ✅

**Say:**
> "Before: the right paragraph was in the top 3 results for 8 out of 12 questions. After: 11 out of 12. That's 3 more questions correct, a 25-point improvement.
>
> The cost: each search got about one millisecond slower, a thousandth of a second. The AI itself takes several seconds to write an answer, so this cost is tiny. That's why I shipped the change.
>
> One question is still wrong: **G06**. Its paragraph gets mixed together with four other rows of the table, which hides it. That's a problem with how the document is cut into pieces, not with the search, so it's the next thing to fix, measured the same way."

> 💡 **What this means:** **hit-rate@3** = "out of 12 questions, how often was the correct paragraph in the top 3 results?" **p50** = the typical (middle) time a search takes. **ms** = milliseconds (1 ms = 1/1000 of a second).

---

### 🎤 Closing (30 seconds)

**Say:**
> "To sum up: the suggestion was to switch to a better AI, but that would have fixed **none** of the 4 failures. By checking **where** each failure came from, I found the real problem was the search, not the AI. One targeted change took the score from **8 to 11 out of 12**, for almost no extra time. And every claim in this project is backed by a number."

---

## Part 4: Questions you might get, with simple answers

| If they ask… | You can say… |
|---|---|
| **"Why not just use a better AI model?"** | "The AI never received the right paragraph in any of the 4 failures. A better AI still can't answer from a page it never saw." |
| **"What is BM25?"** | "A classic keyword search, like Ctrl+F but smarter. It gives extra weight to rare words, and codes like E-17 are rare words." |
| **"Why not just add the two search scores together?"** | "They're measured on different scales, like kilograms and kilometres. Adding them lets one side win every time. So I combine them by position in the list instead." |
| **"What is a reranker? Why didn't you use one?"** | "A reranker re-sorts the results the search already found. But for one failing question, the right paragraph wasn't found at all, not even in the top 25. You can't re-sort something that isn't in the list." |
| **"Did you try anything else?"** | "Yes, a method called MMR that makes results more varied. It made the score worse every time, because it pushed out the correct document to add variety. So I didn't use it." |
| **"How did you pick the 12 test questions?"** | "I wrote them from the documents, the way adjusters really type questions, **before** running any searches. Half contain codes like E-17, because that's where the problem was." |
| **"Which AI model is this?"** | "gpt-oss-120b, running on Groq. The search improvements don't depend on which AI is used." |
| **"What happens if the answer isn't in the documents?"** | "It refuses and says what's missing. You saw that with question 3." |
| **"Why does it matter so much in insurance?"** | "A wrong 'yes, you're covered' means paying money that shouldn't be paid. A wrong 'no' means refusing a customer who should be paid, which can become a legal problem." |
| **"Is the answer always exactly the same?"** | "The wording may differ slightly each time, but the decision and the source stay the same." |

**If you don't know an answer**, it's fine to say: *"Good question. I'll check and get back to you."*

---

## Part 5: Things to avoid on the day ⚠️

| Don't | Why |
|---|---|
| **Don't tick the checkbox** in the Inspect tab ("run the answer pass") | It asks the AI 12 questions at once. The free AI account only allows a small amount of use per minute, so it would load for **about 3 minutes**. |
| **Don't click Ask many times quickly** | Same reason: you'd hit the per-minute limit and see a long loading spinner. Pause between questions. |
| **Don't quote exact milliseconds** | Timing changes slightly every run. Say "about one millisecond slower". |
| **Don't restart the servers during the demo** | The first answer after a restart takes about 25 seconds. |

**If something is slow**, just say: *"The free AI account has a speed limit per minute. It'll come back in a moment."*

**If something breaks**, check the two terminal windows are still running, then refresh the browser page.

---

## Part 6: One-page cheat sheet

```
OPENING  → "Assistant for adjusters. Answers from 6 documents, shows the source,
            refuses if unsure. Codes like E-17 were going wrong."

1. ASK       Q1 → covered (HO-0304) + source in [brackets]
             Q2 → excluded (DP-0110) — same code, opposite answer!
             Q3 → INSUFFICIENT_CONTEXT — refuses instead of guessing

2. BENCH     8/8 vs 8/8 — kept "cut by section" so each piece knows its document

3. SEARCH    dense + filter "dwelling_fire" → top result changes
             Left list: asked E-17, got E-20/E-19/E-21 → THE BUG

4. INSPECT   dense → R=4, G=0 → search problem, NOT the AI
   (no tick) Show G01: E-17 from the WRONG document
             All failures have codes ("exact token")

5. INSPECT   hybrid → R drops 4 → 1
             Meaning search + keyword search (BM25), combined by position

6. HIT-RATE  8/12 → 11/12, about 1 ms slower → shipped
             G06 still broken → cutting problem → next fix

CLOSING  → "A better AI would have fixed 0 of 4. Finding WHERE it failed
            fixed 3 of 4 with one change."
```

---

## Part 7: Only if asked about the later weeks

The screen only covers the search part of the project (Weeks 3 and 4). If someone asks about the other parts, here's a simple way to describe each:

| Week | Plain description | What to show |
|---|---|---|
| **Week 5** | "Recording every question and answer so we can go back and read what went wrong, like a flight recorder." | The tools are built; the recordings haven't been reviewed yet. |
| **Week 6** | "Checking whether an AI 'grader' agrees with a human. Simple checks (is the claim number in the right format?) are done with plain code, because code never makes mistakes on those." | Open `evals/w6/judges/judge_v0.txt` and `judge_v1.txt`: 6 fuzzy scores became 1 clear pass/fail question. |
| **Week 7** | "Comparing two designs: one where the AI decides each step itself (an 'agent'), and one with fixed steps (a 'workflow'). The fixed one is usually cheaper and more predictable, so the AI deciding should be used only when it's really needed. The agent also has safety limits so it can't run forever." | In a terminal (from `backend/`): `python -m app.agents.agent --claim CLM-2026-10007 --max-iters 2`. It stops cleanly after 2 steps, showing the safety limit working. |
