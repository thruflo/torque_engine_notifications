# -*- coding: utf-8 -*-

"""Provides a Pyramid configuration entry point to register the notification
  configuration directives, provide the `request.notifications` dispatch api
  and expose the work engine `/notify` route.

  I.e.: everything that's needed to enable the notification system.
"""

from . import config
from . import dispatch
from . import view

def includeme(config):
    modules = (
        config,
        dispatch,
        view,
    )
    for x in modules:
        config.include(x)
