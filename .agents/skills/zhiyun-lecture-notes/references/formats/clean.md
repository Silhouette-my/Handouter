# Format · clean

Optimize the final Markdown for reading rather than auditing.

- Keep timing and `seg/occ` IDs inside the closed HTML details folds required by common/presentation. Keep internal JSON paths, processing statistics, agent/tool chatter and handoff implementation details out of reader content.
- Do not add generic “materials”, “processing”, or “how this note was generated” sections.
- Course information belongs in a closed `课程信息` fold. Each main chapter (`##`) gets one closed `本章时间与来源` fold after its heading, containing its real interval(s) or an explicit unknown-time statement and concise evidence identifiers.
- Do not repeat source folds for natural paragraphs, list items, table rows or subsections. Invisible HTML comments cannot replace the chapter fold. Assessment requirements remain visible in the upfront important callout.
- The final unresolved checklist, when needed, belongs in one closed `待核对` fold; do not expose a separate `## 待核对` chapter.
