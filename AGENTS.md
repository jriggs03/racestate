# Repository instructions

Optimize for James understanding every important line.
Read docs/design-principles.md and docs/architecture.md before changing boundaries.
Use Python, SQL, Bash and minimal browser JS initially. Do not introduce a
framework, broker, service, language or abstraction without a concrete problem.
Implement one issue at a time. Prefer explicit control flow and focused functions.
Explain significant architecture changes and alternatives before implementing them.
Test event ordering, malformed data, persistence and failure behavior when touched.
Run `python3 -m unittest discover -s tests -v` before reporting success.
Keep the simulation label visible. Never describe synthetic results as live F1 data.
Do not claim unrun tests, measured performance, deployment or recovery guarantees.
