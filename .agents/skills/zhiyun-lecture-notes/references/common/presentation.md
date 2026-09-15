# Common · Lecture order, assessment callout, and collapsible provenance

These rules apply to every selected output, including both clean and traceable.

## Lecture order

- **Except for summary, preserve the actual order of the lecture.** This includes verbatim, full, and deep. Follow the order in which the teacher introduces concepts, examples, questions, corrections, and course requirements; do not impose a new textbook taxonomy or move later material into earlier thematic chapters.
- Natural paragraphs may combine adjacent segments. This does not permit merging distant passages, moving an example ahead of its introduction, or relocating course administration to the end because it seems less central.
- deep adds explanations of the local reasoning while staying in place; depth does not mean reordering. Any allowed supplement stays beside the relevant passage and is explicitly labelled.
- summary alone may regroup by theme. The mandatory front assessment callout is a navigation aid, not permission to reorder the chronological body of other modes.

## Start of every document

Use this order: reader-facing title → assessment callout when supported → folded course information → main text. summary starts its main text with `## 本讲速览` after these front elements.

If the materials mention homework, quizzes, tests, exams, group assignments/projects, or course assessment, collect the relevant requirements **before the main text in an always-visible important callout**:

> [!IMPORTANT]
> **作业、测验与考核重点**
> - Summarize the actual task, scope, due date, submission format, group responsibilities, grading weights, exam permissions/restrictions, and penalties that the evidence supports.
> - Preserve uncertain arrangements, conflicting versions and the teacher's final correction. Do not invent missing dates, percentages, exam topics or rules.

This is a syntax illustration, not text to copy verbatim. Keep blank quoted lines as `>` when separating paragraphs inside the callout. It remains a readable blockquote where alert styling is unsupported. Do not collapse the important requirements themselves.

- Read the whole lecture before finalizing the callout, including requirements mentioned near the end.
- If there are no relevant requirements, omit the callout; do not invent a section or claim that no assessment exists merely because it was not mentioned.
- Keep the full discussion at its original position in verbatim/full/deep; the upfront digest does not replace it. In verbatim retain the teacher's correction process in the chronological body, while the callout clearly states the corrected requirement.
- Add an adjacent closed `<details>` labelled `重点事项时间与来源`, mapping callout items to their actual evidence. Keep all timing and source IDs inside that fold.

Course metadata goes in a closed fold before the main text:

```html
<details>
<summary>课程信息</summary>
<p>课程：仅填写材料确认的信息<br>讲次、讲者、日期：有可靠来源才填写；缺失则省略或标明未知。</p>
</details>
```

Do not infer a speaker identity, biography, course date or grading policy from context. Course metadata is not an execution report: omit processing statistics, tool names, local machine paths and internal JSON filenames.

## Time and sources for each chapter

- For **each main chapter (`##` heading)**, put one closed `<details>` block labelled `本章时间与来源` immediately after its heading. Aggregate the chapter's real time range(s) and source references in this single fold.
- Do not add source folds after individual natural paragraphs, list items, table rows or `###` subsections. They share their parent chapter's fold. Keep the course-information fold separate; the upfront assessment callout can share one evidence fold for all its items.
- Use actual start/end values from segments. Preserve the available precision and label them as sentence/VAD ranges, not word-exact times. PPT occurrence times alone do not prove when a sentence was spoken.
- For adjacent source segments, give the enclosing supported range and relevant IDs. For disjoint sources (especially summary), list the separate ranges within the chapter fold; do not create one continuous span that implies the intervening material supports the chapter.
- If any relevant timing is absent or unreliable, explicitly say `时间：未知（材料未提供可靠时间）` and cite available segment IDs or transcript locations. Never distribute time by word count, infer a precise time from slide order, or invent confidence/speaker data.
- Chapters about course administration follow the same rule: one fold per chapter, not per item. For a labelled supplement without a classroom counterpart, note `课堂时间：不适用（补充说明）` in the chapter's shared fold and distinguish it from the supported material, rather than inventing a spoken time.

Example syntax only; substitute verified values, and do not copy these illustrative times into real notes:

```html
<details>
<summary>本章时间与来源</summary>
<p>时间：00:12:34.500–00:13:10.200（句段/VAD 范围）<br>来源：seg-0041–seg-0044</p>
</details>
```

Keep the chapter's body outside the fold. Do not use `open`, wrap the final HTML in a code fence, or leave timing/source IDs in the visible summary label. Escape literal `<`, `>` and `&` in metadata values. Use blank lines around the HTML blocks so Markdown body text renders normally. Invisible HTML comments do not replace the chapter's user-expandable fold.

## Final unresolved checks

When unresolved terms, conflicting evidence or missing material remain, put the final checklist inside one closed `<details>` block labelled `待核对`. Do not add a visible `## 待核对` chapter or repeat the checklist outside the fold. Omit the block if there are no unresolved items.

```html
<details>
<summary>待核对</summary>
<ol>
<li>填写实际疑点、需要核实的原因，以及已有的时间范围或来源；未知时间明确标注。</li>
</ol>
</details>
```

This is a syntax illustration, not a fabricated pending item. Keep any evidence for these items inside the same final fold; do not create an additional source fold for each item. Important unresolved assessment requirements must still be mentioned in the upfront visible assessment callout, so collapsing the final checklist does not hide an actionable uncertainty.
