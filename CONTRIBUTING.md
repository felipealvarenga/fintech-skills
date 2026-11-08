# Contributing

One skill per folder under `skills/`, with `SKILL.md` and `evals/evals.json`. Skills whose output
is a number (amounts, schedules, matches) also ship `evals/vectors/` with a reference
implementation and a pytest file that can run against any implementation through an environment
variable.

Before opening a pull request:

```sh
python scripts/validate.py          # frontmatter, evals shape, plugin manifest
python -m pytest -q skills          # vectors against the references
```

Rules for a skill:

- Frontmatter has `name` equal to the folder name and a `description` that says when to use the
  skill, what triggers it and what it is not for. Keep it under 1024 characters.
- Every rule is testable. If you cannot write the test, rewrite the rule.
- No vendor API documentation. Vendors ship their own plugins; link to them.
- No tax rates, statutory rounding or legal conclusions. Say that an accountant or lawyer confirms
  those, and keep the engineering part.
- No real customer data, account numbers or identifiers in examples or vectors.
- At least six evals (`scripts/validate.py` checks), one of them adversarial (the prompt asks for
  the unsafe thing), each with concrete expectations a grader can check in a transcript.
- Plain English. Short sentences. Tables for comparisons.

Changing a vector is a reviewed change with a reason in the pull request.
