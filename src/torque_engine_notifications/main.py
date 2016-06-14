# -*- coding: utf-8 -*-

"""Provides the main polling entrypoint to dispatch notifications that are
  now due to be sent.

  There are two ways of using:

  a. via the `main()` function / ` command line via the
  Main console script entry point.
"""

import logging
logger = logging.getLogger(__name__)

import os
import time
import transaction

from ntorque import util as nt_util
from ntorque.work import ntw_main

from . import repo

POLL_DELAY = os.environ.get('TORQUE_ENGINE_NOTIFICATIONS_POLL_DELAY', 15)

def bootstrap():
    """Bootstrap the pyramid environment."""

    bootstrapper = ntw_main.Bootstrap()
    config = bootstrapper()
    config.commit()
    return config

def wrap_in_tx(target, *args, **kwargs):
    """Call ``target(*args, **kwargs)`` within a transaction."""

    with transaction.manager:
        return target(*args, **kwargs)

def poll():
    """Poll forever for new notifications to dispatch."""

    config = bootstrap()
    dispatcher = Dispatcher()
    try:
        while True:
            t1 = time.time()
            r = nt_util.call_in_process(wrap_in_tx, dispatcher)
            logger.info(r)
            t2 = time.time()
            elapsed = t2 - t1
            delay = POLL_DELAY - elapsed
            if delay > 0:
                time.sleep(delay)
    except KeyboardInterrupt:
        pass

def dispatch():
    """Dispatch due notifications."""

    config = bootstrap()
    dispatcher = Dispatcher()
    r = wrap_in_tx(dispatcher)
    logger.info(r)

class Dispatcher(object):
    """"""

    def __init__(self):
        pass

    def __call__(self):
        pass
