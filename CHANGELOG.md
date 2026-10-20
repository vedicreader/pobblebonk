# Release notes

<!-- do not remove -->

## 0.0.5
A schedule's `retry_after` payload key, a duration, replaces the doubling delay before a retry: `add('nightly', cron='0 3 * * *', retries=2, retry_after='1h')` gives a failed night one more try an hour later. `add` and `update` reject a value that is not a duration.

## 0.0.4
long jobs: `Pob(lease=)` renews a fire's claim while its callback runs; `fire.beat()`, `fire.worker`, `fire.note(body)`.
`add(batch=)` and `update(batch=)` so a fire takes only that many items. `drop_item(id)` deletes an open item.

## 0.0.3
heartbeat to **croak** at the scheduled time 

## 0.0.2
index examples

## 0.0.1
initial release of pobblebonk. **croak**
