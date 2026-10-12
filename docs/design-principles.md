# Design principles

1. **Understandability first.** James should explain every thread, queue, table,
   event and important function. Prefer explicit control flow, descriptive names,
   small functions and ordinary data structures. Comments explain reasons.
2. **Ship one path.** Complete source → worker → state → API → website before
   adding infrastructure. Keep one repository and one deployable application initially.
3. **One owner per mutable state.** A single state writer makes order and
   consistency understandable. Readers receive copies. Explain every lock.
4. **Make uncertainty visible.** Show source, freshness, missing readings and
   disconnections. Never infer official gaps or physical positions from toy data.
5. **Keep the website fast and focused.** Small payloads, bounded polling and
   no frontend build system initially. Selected driver is the first customization;
   movable/hideable panels come after the MVP.
6. **Measure before optimizing.** Profile under a repeatable workload, then
   change the bottleneck. Threads suit blocking I/O; Python threads do not imply
   parallel CPU execution. Use processes for CPU work when needed.
7. **Bound resource use.** Put explicit limits on queues, batches, requests and
   retained history. State what happens when capacity is exhausted.
8. **Test behavior at boundaries.** Prioritize duplicate/out-of-order input,
   malformed events, isolated snapshots, restart and worker failure over tests
   that merely repeat implementation details.
9. **No decorative infrastructure.** No Kafka, Kubernetes, Redis, deep class
   hierarchies or generic plugin systems without demonstrated need.
10. **Document architectural choices.** Before a significant change, explain the
    problem, alternatives and tradeoffs. A Go rewrite is a later option backed
    by profiling, with the same event contract and acceptance tests.

Review gate for each slice: can James trace one event end to end, explain the
failure behavior, run it locally and change one thing without guessing?
