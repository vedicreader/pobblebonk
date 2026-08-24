# Release notes

<!-- do not remove -->

## 0.0.1

First release. One module on [honker](https://github.com/russellromney/honker).

honker brings the queue, the scheduler table, the retries and the streams with a cursor per
reader. pobblebonk adds the three things it has not got: a pile you add to over a week, a gate
that stops a fire when its pile is empty, and the callback a fire runs.

- `Pob.on` registers a callback, `Pob.add` writes the schedule, `Pob.tick` is what cron calls.
  `honker_scheduler_tick` is a SQL function, so there is still no daemon.
- `push`, `items` and `used`: reading a pile never empties it, so a run that raised loses nothing.
- `note` and `drain`: honker's stream, one cursor per reader.
- `catchup='once'` cancels the fires a shut laptop missed, keeping the latest.
