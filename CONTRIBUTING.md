# Contributing

One skill per folder under `skills/`: `SKILL.md`, `evals/evals.json` and `evals/vectors/` with a
reference implementation and a pytest file that runs against any implementation through an
environment variable. The eval shape, the install rule and the vectors table are in
[evals/README.md](evals/README.md); `scripts/validate.py` enforces the minimum.

Before opening a pull request:

```sh
pip install -r requirements-dev.txt
python scripts/validate.py          # frontmatter, evals shape, plugin manifest, generated docs
python -m pytest -q                 # vectors against the references, runner tests
npm ci && npm run test:ts           # TypeScript vectors
```

Rules for a skill:

- Frontmatter has `name` equal to the folder name and a `description` that says when to use the
  skill, what triggers it and what it is not for. Keep it under 1024 characters.
- Every rule is testable. If you cannot write the test, rewrite the rule.
- No vendor API documentation. Vendors ship their own plugins; link to them.
- No tax rates, statutory rounding or legal conclusions. Say that an accountant or lawyer confirms
  those, and keep the engineering part.
- No real customer data, account numbers or identifiers in examples or vectors.
- Seven evals (three build, three judgment, at least one adversarial that asks for the unsafe
  thing), each with expectations a grader can check in the transcript and the produced files.
- Plain English. Short sentences. Tables for comparisons.

Changing a vector or an eval is a reviewed change with a reason in the pull request. A graded run
goes in a new folder under `evals/results/`; old folders are never edited.
