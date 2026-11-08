# Security

The skills are text an agent reads; the code that runs is under `scripts/` (validation, eval
runner) and `skills/*/evals/vectors/` (test vectors with reference implementations), in CI and on
your machine.

Report a vulnerability through GitHub's private vulnerability reporting on this repository
(Security tab, "Report a vulnerability"). Do not open a public issue for it. You will get an
answer within seven days.

In scope: code execution or data exposure through the scripts or vectors, a workflow that runs
untrusted code with write permissions, a skill that instructs an agent to do something unsafe
with money or personal data. Out of scope: the behaviour of the coding agents themselves.
