# Mode · verbatim

Create a faithful, readable transcript that stays close to what was actually said in class.

## Content fidelity

- Preserve the lecture's chronological order, examples, derivations, Q&A, qualifications, uncertainty, teacher self-corrections, and meaningful conversational transitions.
- Keep the teacher's phrasing when it carries tone, emphasis, reasoning, or rhetorical intent. Do not compress multiple substantive utterances into a shorter summary.
- Remove only transcription noise, meaningless filler, obvious stutters, accidental repeated fragments, and punctuation/segmentation artifacts.
- Correct obvious ASR homophones only when the course evidence is strong; otherwise mark `[待核对：原词]`.
- Do not add untaught background as if the teacher said it, and do not turn the transcript into a textbook or topic summary.

## Paragraphing

- **Never treat one ASR/VAD segment as one paragraph.** Segment boundaries are evidence/timing boundaries, not writing boundaries.
- Merge adjacent fragments that form one complete sentence or one continuous thought.
- Start a new paragraph when the micro-topic clearly changes, a question/answer turn begins, an example starts or ends, a derivation enters a new step, or the speaker deliberately pivots to a new point.
- Keep natural conversational continuity. A paragraph may contain several consecutive utterances if they belong to the same thought.
- Avoid both extremes: do not output one sentence per paragraph, and do not create page-long blocks that hide topic changes.

## Output shape

- Use headings only to help navigation through long lectures; headings must not reorder the lecture.
- The upfront assessment callout is a digest only; keep the original discussion and correction sequence in the body. Follow common/presentation for course metadata, one time/source fold per chapter and the final unresolved-check fold.
- Produce a single readable transcript, not a raw-vs-polished comparison table and not duplicated raw ASR.
