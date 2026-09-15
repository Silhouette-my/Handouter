# Common · Writing

Produce UTF-8 Markdown for a student reader, not an execution log.

- First line should be a reader-facing title.
- Use clear heading hierarchy and natural semantic paragraphs. **ASR/VAD segment boundaries are never paragraph boundaries by themselves**; merge adjacent fragments before deciding paragraph structure. Lists/tables are for structure, not decoration.
- Preserve actual lecture order in verbatim/full/deep; only summary may regroup by topic. Follow common/presentation for the upfront assessment callout, course information, one real time/source fold per chapter, and the final unresolved-check fold.
- Use LaTeX for mathematics. Use Mermaid only when it genuinely clarifies structure and the selected mode permits that level of detail.
- Do not include internal processing statistics, raw JSON paths, agent/tool chatter, or implementation details unless the selected format module explicitly asks for visible provenance.
- Keep terminology consistent. Do not globally replace filler-like words if they carry negation, uncertainty, reference, or logical qualification.
- Separate teacher content from any explicitly allowed external/background explanation.
- Put supported course metadata in the required closed `课程信息` fold, not a generic “materials/process” preface. Keep assessment requirements visible in the upfront important callout.
- Only when unresolved terms, missing evidence or conflicts exist, add one final closed `<details><summary>待核对</summary>…</details>` block. Do not use a visible `## 待核对` section or repeat the list outside the fold.
