# AGENTS.md

## General
- Keep code simple, with a strong focus on readability and maintainability.
- Use Chinese for all code comments.
- Use Chinese for all generated documentation and Markdown documents unless the user explicitly requests otherwise.
- Use Chinese for all non-code content unless the user explicitly requests otherwise.
- No em dashes in comments and documentation.
- Use Python 3.13 syntax.

## Functions
- Keep each function concise, easy to read, and clearly named.
- Avoid functions that handle multiple responsibilities unless there is a sensible trade-off.
- Prioritise readability, maintainability, reusability, and testability.

## Docstrings
- Keep module-level and script top-level docstrings to a single line.
- Use Google-style docstrings.
- Do not include types for arguments.
- Keep docstrings concise and include only what is necessary.
- Function and class docstrings may be multi-line when needed, but they must stay concise.
- Follow the example format below when a multi-line docstring is necessary.

### Docstrings Example
```python
def function_with_pep484_type_annotations(param1: int, param2: str) -> bool:
    """Example function with PEP 484 type annotations.

    Important note.

    Args:
        param1: The first parameter.
        param2: The second parameter.

    Returns:
        The return value. True for success, False otherwise.

    """
```



## Translation
- When a task involves translating Markdown technical documents, read and follow [`docs/translation-rules.md`](./docs/translation-rules.md) before making any translation changes.
