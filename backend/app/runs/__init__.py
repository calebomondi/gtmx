"""Server-owned agent runs: persisted run rows, an append-only event log that
clients replay and follow, and a manager that executes run segments as tasks
independent of any connection."""
