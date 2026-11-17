# Quiz skill: data and grounding design

Status: proposal, 2026-11-18. Milestone M5. Nothing here is built.

The failure to design against: a small local model that writes a quiz will sometimes invent questions the source never supports, or phrase a true fact with the wrong answer key. A quiz that teaches something false is worse than no quiz. The screenvoice narration work showed the same thing: the model's rewrite was where meaning got lost, and a metric that compares the output against the source caught it. So the rule is that no question is shown unless it is checked against the text it came from.

## Question kinds, in the order they are built

1. **Cloze (fill in the blank).** Built without the model. Pick a sentence from the source, blank out a key term (a word of four or more letters that is not a common word), and keep the sentence as the quote. Grounding is guaranteed because the question is the source. Build this first, and it already works with no model at all.
2. **Short answer.** The model gets one chunk and returns JSON with `question`, `answer` and `quote`. The runtime checks the output before it is stored (next section).
3. **True or false.** The model restates a sentence from the chunk as true, or the runtime negates a key term for a false version. Only the first is model-written, and it is checked the same way.

Multiple choice is left out for now, because the wrong options are where small models invent things.

## Checks before a question is stored

For a model-written question:
1. `quote` must be a verbatim substring of the chunk after whitespace is normalized.
2. The key terms of `answer` (words of four or more letters, first five letters compared) must appear in the quote, at least 60 percent of them. This is the same kind of coverage measure used in the narration evaluation, and it is a proxy for meaning, not meaning.
3. The question must not be answered by its own text (no key term of the answer appears in the question).
4. Failing any check, sample again, up to 3 tries, then drop the chunk and count it as rejected. Never show an unchecked question.

If a source has fewer than 2 usable chunks (task Q4 uses a note that just says "Hi."), the skill says there is not enough material and creates nothing.

## Grading

- Cloze: normalized exact match, with a small allowance for case, plurals and one typo. No model involved.
- Short answer: first the key-term overlap between the user's answer and the stored answer and quote. If that is unclear, a model judge sees the question, the stored answer, the quote and the user's answer and returns a structured verdict (`correct` or `incorrect`) with a one-line reason. Judge verdicts are logged so they can be compared with hand labels.
- The verdict is a structured field, never parsed from free text. The word "incorrect" contains "correct".

## Scheduling

Leitner boxes: five boxes, review intervals of 1, 2, 4, 8 and 16 days. A right answer moves a card up a box, a wrong one sends it back to box 1. It is simpler and easier to explain to a user than SM-2, and there is no data yet to justify anything more elaborate. Revisit when there are real reviews to look at.

## Storage

One SQLite file in the user's data folder (`%LOCALAPPDATA%\HelperBoi\` on Windows, `~/.local/share/helperboi/` on Linux and WSL).

```sql
CREATE TABLE sources   (id INTEGER PRIMARY KEY, path TEXT NOT NULL, content_hash TEXT NOT NULL, added_at TEXT NOT NULL);
CREATE TABLE chunks    (id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                        ord INTEGER NOT NULL, text TEXT NOT NULL, hash TEXT NOT NULL);
CREATE TABLE questions (id INTEGER PRIMARY KEY, chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
                        kind TEXT NOT NULL CHECK (kind IN ('cloze','short','truefalse')),
                        prompt TEXT NOT NULL, answer TEXT NOT NULL, quote TEXT NOT NULL,
                        model TEXT, created_at TEXT NOT NULL, retired INTEGER NOT NULL DEFAULT 0);
CREATE TABLE cards     (question_id INTEGER PRIMARY KEY REFERENCES questions(id) ON DELETE CASCADE,
                        box INTEGER NOT NULL DEFAULT 1, due_at TEXT NOT NULL, streak INTEGER NOT NULL DEFAULT 0, lapses INTEGER NOT NULL DEFAULT 0);
CREATE TABLE reviews   (id INTEGER PRIMARY KEY, question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
                        asked_at TEXT NOT NULL, response TEXT NOT NULL, correct INTEGER NOT NULL,
                        grader TEXT NOT NULL CHECK (grader IN ('exact','overlap','judge')), latency_ms INTEGER);
```

- Chunk text is stored, because the quote check needs it. Deleting the source folder does not delete these copies. `helperboi quiz delete <source>` does, and `helperboi quiz export` writes everything as JSON. The profile never leaves the machine.
- When a source file changes (its hash differs), questions whose quote no longer appears in any chunk are retired, not deleted, so the history stays.

## What is measured (milestone M5)

- **Grounding rate:** share of questions shown that pass the checks. By construction it is 100 percent for those shown, so the numbers that matter are the rejection rate (how often the model fails the checks) and a hand check of 30 shown questions for questions that pass but are still wrong.
- **Grading agreement:** the judge's verdicts against hand labels on 30 answers, with right, wrong and partly-right answers deliberately mixed.
- Tasks Q1 to Q4 and M1 in `eval/tasks.json`.

## Not designed yet

Spaced repetition across sessions as a scheduled reminder, quizzes from PDFs and web pages (needs text extraction and the taint rule in docs/THREAT-MODEL.md), and any scoring of how good a question is for learning.
