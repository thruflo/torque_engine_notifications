# -*- coding: utf-8 -*-

"""Provides two console script entry points to dispatch due notifications:

  - `poll` runs as an ongoing background process
  - `dispatch` runs once and exits

  It's generally more efficient to use `poll` as it avoids repeating the
  application configuration / setup.
"""

import logging
logger = logging.getLogger(__name__)

import dateutil
import os
import time
import transaction

from datetime import datetime

from pyramid import threadlocal

from ntorque import util as nt_util
from ntorque.work import ntw_main

from . import constants
from . import repo

POLL_DELAY = os.environ.get('TORQUE_ENGINE_NOTIFICATIONS_POLL_DELAY', 20)

class SpawnAndDispatch(object):
    """Spawn dispatches for any unspawned but due notifications."""

    def __init__(self, client, **kwargs):
        self.client = client
        self.due_preferences = kwargs.get('due_prefs', repo.DuePreferences())
        self.last_dispatched = kwargs.get('last_dispatched', repo.LastDispatched())
        self.spawn_outstanding = kwargs.get('spawn', repo.SpawnOutstandingNotifications())
        self.users_with_due_dispatches = kwargs.get('users_due', repo.UsersWithDueDispatches())

    def __call__(self):
        """Spawn and then send any due notification dispatches.

          XXX add indexes based on these queries.
        """

        # Get the notification preferences for all the users who have
        # notifications that have not been spawned.
        now = datetime.utcnow()
        for preferences in self.due_preferences():
            # Get the last time we dispatched to them
            user_id = prefs.user_id
            last = self.last_dispatched(user_id)
            # If that plus the frequency is less than now then
            # spawn their outstanding notifications.
            delta = constants.DELTAS[prefs.frequency]
            due = last + dateutil.relativedelta(seconds=delta)
            if due < now:
                self.spawn_outstanding(user_id)

        # That done, get all the users with dispatches that are due and
        # use the torque client to dispatch a task to notify them.
        for user_id in self.user_ids_with_due_dispatches():
            self.client.dispatch('notify/{0}'.format(user_id))

def dispatch():
    """Console script entry point that dispatches any due notifications and
      then exits. (You would run this regularly, e.g.: using cron or something
      like the heroku scheduler).
    """

    request = bootstrap()
    dispatcher = Dispatcher(request)
    return wrap_in_tx(dispatcher)

def poll():
    """Console script entry point that polls forever for new notifications
      to dispatch. (You would run this as an ongoing background process).
    """

    request = bootstrap()
    dispatcher = Dispatcher(request)
    try:
        while True:
            t1 = time.time()
            nt_util.call_in_process(wrap_in_tx, dispatcher)
            t2 = time.time()
            elapsed = t2 - t1
            delay = POLL_DELAY - elapsed
            if delay > 0:
                time.sleep(delay)
    except KeyboardInterrupt:
        pass

def wrap_in_tx(target, *args, **kwargs):
    """Call ``target(*args, **kwargs)`` within a transaction."""

    with transaction.manager:
        return target(*args, **kwargs)

def bootstrap():
    """Bootstrap the pyramid environment and return a configured
      torque engine client.
    """

    bootstrapper = ntw_main.Bootstrap()
    config = bootstrapper()
    config.include('pyramid_torque_engine.client')
    config.commit()
    request = threadlocal.get_current_request()
    return request.torque.engine
