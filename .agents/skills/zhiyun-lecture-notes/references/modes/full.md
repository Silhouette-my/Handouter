# Mode · full

Create a **complete polished lecture text**: preserve essentially all substantive course information, while aggressively removing oral redundancy and rewriting spoken language into concise, readable prose.

This mode is deliberately different from `verbatim`:

- `verbatim` stays close to what the teacher said and mainly cleans transcription noise/filler.
- `full` keeps the **information coverage** of the lecture, but not the teacher's every spoken formulation.

## What to preserve

Keep every substantive item that affects understanding or course meaning:

- concepts, claims, definitions, formulas, derivations, examples, counterexamples, Q&A, comparisons, conditions, exceptions, uncertainty, negation, teacher corrections, explicit requirements, and unique explanatory details;
- important reasoning steps even when they were expressed informally;
- meaningful examples and anecdotes when they illustrate a technical/conceptual point.

Do not compress the lecture into a summary. Removing redundant wording is allowed; removing unique information is not.

## De-oralization and redundancy removal

Rewrite spoken language much more strongly than `verbatim`:

- remove filler and discourse scaffolding such as repeated “这个/那个/然后/就是说/大家可以看到/我们再来看一下” when they add no meaning;
- remove false starts, abandoned sentence openings, repeated self-rephrasing, duplicated conclusions, repeated rhetorical questions, and repeated transitions;
- when several consecutive utterances restate the same point, merge them into one precise statement while preserving any unique qualifier/example from each occurrence;
- turn conversational fragments into complete written sentences; resolve obvious pronouns or ellipsis only when the referent is clear from nearby evidence;
- simplify wordy spoken constructions and repeated setup, but do not silently strengthen claims or erase uncertainty/negation;
- keep teacher emphasis as content when the repetition itself signals importance, but express that emphasis once in clear prose rather than copying the repetition.

The target should read like a carefully edited complete lecture manuscript, not like a transcript and not like a newly authored textbook.

## Paragraphing and section structure

- **Never map ASR/VAD segments directly to paragraphs.** Timing segments are evidence boundaries only.
- First merge neighboring segments into coherent semantic units, then write paragraphs from those units.
- A paragraph should normally develop one micro-topic or one continuous reasoning step. Combine multiple short utterances that belong to the same point.
- Start a new paragraph when the argument moves to a new sub-point, a new example begins, a comparison changes side, a derivation changes stage, a question/answer changes function, or the teacher explicitly pivots topics.
- Prefer medium-length paragraphs with internal sentence flow. Avoid one-sentence-per-segment fragmentation and avoid giant undifferentiated blocks.
- Use headings/subheadings for real topic boundaries in long lectures. **Preserve the actual lecture order**, not merely a broad progression: do not move examples, Q&A, corrections or course requirements, and do not combine distant passages into a new taxonomy. Only adjacent redundant formulations may be merged in place.
- Lists are appropriate for genuinely parallel items, enumerated criteria, procedures, or contrasts; do not convert ordinary prose into bullets merely to shorten it.

## Fidelity boundary

- Correct obvious ASR homophones only when course evidence is strong; otherwise mark `[待核对：原词]`.
- Do not introduce untaught background as teacher content. If outside explanation is explicitly allowed, keep it visibly separate according to the common/format modules.
- Do not duplicate raw ASR or create raw-vs-polished comparison tables.
