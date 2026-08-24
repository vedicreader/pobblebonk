# Release notes

<!-- do not remove -->

## 0.0.1

First release.

The clock and the notebook for an agent: a durable queue, schedules, the lists you add to over a
week, and the notes waiting for you, all in one SQLite vault.

- `core`: the vault, and the `Store` base the four tables share. Opens without the usearch
  extensions, so a tick pays nothing for search.
- `queue`: at-least-once work with retries, leases and a dead letter. Lifted from vishalakshi's
  `jobs`, with what each run answered now kept in `job_runs.result`.
- `clock`: durations, cron in a named zone, and a catch-up policy of `once`, `all` or `skip`.
- `lists`, `inbox`: the piles a fire reads, and notes with a cursor per reader.
- `schedule`: the standing instruction, and a tick four processes can run at once.
- `run`: `AcpRunner`, which drives any ACP agent for one fire and keeps its session.
- `cli`: `pob tick`, and the commands for looking.
