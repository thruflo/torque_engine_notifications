
Then see `config.notify_directive`
- patch the mapping

Then implement the view
- the `notify` route with a single view
- single and batch
- noop unless the task data has the correct `latest_dispatch_task` hash

Then carry on from there by:
- getting a basic test to pass
- driving the `config.notify(...)` syntax so we get the idea API
  and implicit defaults
- edge cases around send failure
  - n.b.: because we make one single-or-batch dispatch per task
    we could look at the algorithm for marking dispatches as sent
    i.e.: do we want:
    - sent on tx commit with actual send a fire and forget?
    - sent on successful api client response, after which we commit?
    - some kind of double step paxos style thingamy?
    - send on tx commit but a rollback if the api client request fails?
    - ...
