
What do we need to do here?

* go through and tidy up the orm and repo

* what is the overall algorithm
* can we document it?

* can we documate the ideal engine-user api?
  - make it as implicit as possible, i.e.: there's a naming convention based on
    some global config?
  - make the view function generic unless it needs to be overridden?
  - ...?

* can we then write blind tests for this syntax?
* then fix up the impl so the tests pass?

* look at the main driver:
  - can it just execute directly?
  - if using views, could it use tasks?
