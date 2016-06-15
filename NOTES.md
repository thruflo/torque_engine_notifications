
Finally on first pass blind refactor:
- need to impl `request.notifications.notify(user_id)`
  - single and batch doesn't quite fit with current senders
  - need to look at how the batch template fragments are compiled
- actually set stuff to sent...
- plus... need to implement the global defaults in the augment mapping /
  batch rendering (and we should ideally have a global batch and single
  layout configured)

Then carry on from there by:
- getting a basic test to pass
- driving the `config.notify(...)` syntax to verify the API works as expected
  - cut out to README as we go
- edge cases around send failure
  - n.b.: because we make one single-or-batch dispatch per task
    we could look at the algorithm for marking dispatches as sent
    i.e.: do we want:
    - sent on tx commit with actual send a fire and forget?
    - sent on successful api client response, after which we commit?
    - some kind of double step paxos style thingamy?
    - send on tx commit but a rollback if the api client request fails?
