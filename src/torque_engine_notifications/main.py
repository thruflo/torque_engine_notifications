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

POLL_DELAY = os.environ.get('TORQUE_ENGINE_NOTIFICATIONS_POLL_DELAY', 90)
DISPATCH_TIMEOUT = os.environ.get('TORQUE_ENGINE_NOTIFICATIONS_DISPATCH_TIMEOUT', 20)

class SpawnAndDispatch(object):
    """Spawn and then send any due dispatches."""

    def __init__(self, request, **kwargs):
        self.request = request
        self.last_dispatched = kwargs.get('last_dispatched', repo.LastDispatched())
        self.preferences_with_dispatches = kwargs.get('preferences_with_dispatches',
                repo.PreferencesWithUnsentDispatches())
        self.preferences_with_notifications = kwargs.get('preferences_with_notifications',
                repo.PreferencesWithDueUnspawnedNotifications())
        self.spawn_outstanding = kwargs.get('spawn_outstanding',
                repo.SpawnOutstandingNotifications(request))

    def __call__(self):
        """Spawn dispatches for any notifications that are due and have not been
          spawned. Then send any unsent dispatches.
        """

        # Get the notification preferences for all the users who have
        # notifications that have not been spawned.
        now = datetime.utcnow()
        for preferences in self.preferences_with_notifications(now):
            # Get the last time we dispatched to them
            user_id = prefs.user_id
            last = self.last_dispatched(user_id, default=preferences.created)
            # If that plus the frequency is less than now then
            # spawn dispatches to send the outstanding notifications.
            delta = constants.DELTAS[prefs.frequency]
            due = last + dateutil.relativedelta(seconds=delta)
            if due < now:
                self.spawn_outstanding(user_id, now)

        # That done, get all the users with dispatches that are due and use the
        # torque client to dispatch a background task to notify them.
        # Note that the task records the ``preferences.latest_hash.value`` which
        # we check in the view to make sure that the task hasn't been superceeded.
        # This is by no means foolproof but it does give us some protection
        # against transient task errors sending duplicate notifications.
        engine = self.request.torque.engine
        timeout = DISPATCH_TIMEOUT
        for preferences in self.preferences_with_dispatches(): # now
            path = 'notify/{0}'.format(preferences.user_id)
            hash_value = preferences.latest_hash.get_next_value()
            data = {'latest_hash': hash_value,}
            engine.dispatch(path, data=data, timeout=timeout)

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
    return request
