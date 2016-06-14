
See `main.SpawnAndDispatch`:
- impl the queries
- index any hot db fields

Then see `config.notify_directive`
- patch the mapping

Then implement the view
- the `notify` route with a single view
- single and batch

Then carry on from there by:
- getting a basic test to pass
- driving the `config.notify(...)` syntax so we get the idea API
  and implicit defaults
