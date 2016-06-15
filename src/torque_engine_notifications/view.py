# -*- coding: utf-8 -*-

"""Expose work engine `notify/:user_id` webhook. This allows us to dispatch
  ntorque tasks to actually send notifications.
"""

import logging
logger = logging.getLogger(__name__)

import colander

from . import repo

class NotifySchema(colander.Schema):
    latest_hash = colander.SchemaNode(
        colander.String(),
        validator=colander.Length(min=20, max=20),
    )

def notify_view(request, **kwargs):
    """Webhook to notify a user by sending either a single or batch message."""

    # Compose.
    schema = kwargs.get('schema', NotifySchema())
    lookup = kwargs.get('lookup', repo.LookupUser())

    # Decode JSON.
    try:
        json = request.json
    except ValueError as err:
        request.response.status_int = 400
        return {'error': str(err)}

    # Validate.
    try:
        appstruct = schema.deserialize(json)
    except colander.Invalid as err:
        request.response.status_int = 400
        return {'error': err.asdict()}

    # Get the user and their notification preferences.
    user_id = request.matchdict['user_id']
    user = lookup(user_id)
    if not user:
        request.response.status_int = 404
        return {'error': u'User not found.'}
    preferences = user.notification_preferences
    if not preferences:
        request.response.status_int = 404
        return {'error': u'User does not have notification preferences.'}

    # If notifications have been switched off, then exit.
    if preferences.frequency == constants.FREQUENCIES['never']:
        dispatches = []
    else: # We're away!
        dispatches = request.notifications.notify(user, preferences=preferences)

    return {'dispatched': dispatches}

def includeme(config):
    """Expose ``/notify/:user_id``."""

    config.add_route('notify', 'notify/{user_id:\d+}')
    config.add_view(notify_view, route_name='notify', request_method='POST'
            renderer='json')
