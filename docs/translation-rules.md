# Translation Rules For Markdown Technical Documents

These rules apply when translating Markdown technical documents, especially files under `docs/`.

## Goal
- Produce a faithful Chinese translation, not a rewritten summary.
- Preserve technical meaning, constraints, risk boundaries, implementation detail, and document structure.
- Output must be complete Markdown that can replace the source file directly.

## Core Principles
- Technical correctness comes before fluency.
- Prefer preserving English technical terms over forcing a Chinese equivalent.
- Do not summarise, omit, merge, or restructure content.
- Preserve the original strength of requirement language.
- Do not add translator notes, explanations, or extra framing.

## Terminology Policy
- By default, preserve English for product names, framework names, SDK names, protocol names, model names, platform names, cloud service names, CLI names, library names, package names, module names, class names, function names, method names, variable names, field names, environment variable names, API names, event names, error codes, config keys, filenames, directory names, repository names, and tool names.
- Preserve all code identifiers, commands, URLs, paths, relative links, and code block contents.
- When Chinese readability helps but pure translation may drift, use `中文 + English` on first mention, then keep usage consistent.
- If a term is uncertain, keep the English term instead of guessing.
- Do not over-localise terms such as `agent`, `runtime`, `orchestration`, `worker`, `sandbox`, `policy`, `guardrail`, `stream`, `consumer`, `checkpoint`, `dispatch`, `replay`, `proposal`, `resume`, `hook`, `handoff`, `isolation`, `tenancy`, `posture`, `blast radius`, `drift`, `plan`, `apply`, `destroy`, `validate`, `lint`, `diff`, `trace`, and `audit trail`.

## Normative Language
- Preserve normative strength exactly:
  - `must` -> `必须`
  - `should` -> `应` or `应该`
  - `may` -> `可以` or `可能`
  - `can` -> `可以` or `能够`
  - `never` -> `绝不能` or equivalent strong prohibition
  - `recommended` -> `推荐`
  - `optional` -> `可选`
  - `required` -> `必需` or `必须`
- Do not weaken risk statements, prohibitions, or hard constraints.

## Technical Fidelity
- Preserve all architecture layers, process steps, comparisons, constraints, examples, pros and cons, risk notes, and implementation details.
- Do not compress detailed explanation into short summary text.
- Preserve distinctions such as `only if`, `at least`, `separate`, `never directly`, and similar boundary markers.

## Markdown Fidelity
- Preserve heading levels, block quotes, lists, numbering, tables, code blocks, horizontal rules, emphasis, inline code, links, and anchor targets.
- Link targets and relative paths must remain unchanged.
- Code block language markers must remain unchanged.
- Mermaid code blocks should remain unchanged unless the user explicitly asks to translate diagram labels.
- Table structure, column order, and row completeness must be preserved.

## Code And Config
- Do not modify code semantics.
- Do not translate JSON, YAML, TOML, or code keys and identifiers.
- Comments inside code may be translated only if doing so does not distort the original code example.

## Output Rules
- Output only the translated complete Markdown.
- Do not include any preface, summary, explanation, or closing note.

## Translation Checklist
- Preserve all sections, paragraphs, lists, tables, code blocks, and links.
- Preserve requirement strength and risk boundaries.
- Preserve English technical terms wherever Chinese wording may drift.
- Keep terminology consistent within the same document.
- Do not alter code, paths, URLs, or identifiers.
- Ensure the result is a complete Markdown document, not a partial translation.
