# -*- coding: utf-8 -*-

"""Create and lookup notifications."""

__all__ = [
    'DispatchJSON',
    'GetDispatchAddress',
    'GetOrCreatePreferences',
    'LookupDispatch',
    'Notify',
    'NotificationFactory',
    'NotificationJSON',
    'PreferencesFactory',
    'PreferencesJSON',
    'QueryDueDispatches',
    'SpawnDispatches',
]

import logging
logger = logging.getLogger(__name__)

from datetime import datetime
from dateutil import relativedelta

import pyramid_basemodel as bm

from . import constants
from . import orm
from . import util

class Notify(object):
    """Create a notification and iff the user's notification preferences are
      *immediate* then also spawn the necessary dispatch(es).
    """

    def __init__(self, **kwargs):
        self.factory = kwargs.get('factory', NotificationFactory())
        self.get_prefs = kwargs.get('get_prefs', GetOrCreatePreferences())
        self.spawn = kwargs.get('spawn', SpawnDispatches())

    def __call__(self, user, event, mapping, **spawn_kwargs):
        """Create and conditionally spawn."""

        # Create.
        notification = self.factory(user, event)

        # If we should send immediately then spawn the dispatches.
        prefs = self.get_prefs(user)
        if prefs.send_immediately:
            dispatches = self.spawn(notification, prefs, mapping, **spawn_kwargs)
            return notification, dispatches

        # Otherwise our work is done.
        return notification, None

class NotificationFactory(object):
    """Create and save a ``Notification``."""

    def __init__(self, **kwargs):
        self.model_cls = kwargs.get('model_cls', orm.Notification)
        self.session = kwargs.get('session', bm.Session)

    def __call__(self, user, event):
        """Create, save, flush and return a ``Notification``."""

        # Unpack.
        session = self.session
        request = self.request

        # Create the notification.
        inst = self.model_cls()
        inst.user = user
        inst.event = event

        # Save, flush and return.
        session.add(inst)
        session.flush()
        return inst

class NotificationJSON(object):
    """JSON Represention of a notification."""

    def __init__(self, request):
        self.request = request

    def __call__(self, inst):
        return {
            'id': inst.id,
            'type': inst.class_slug,
            'event': {
                'type': 'activity_events',
                'id': inst.event_id,
            }
            'read': inst.read,
            'spawned': inst.spawned,
            'user': {
                'type': 'auth_users',
                'id': inst.user_id,
            },
        }

class GetOrCreatePreferences(object):
    """Get or creates the notification preferences for a user."""

    def __init__(self, **kwargs):
        self.factory = kwargs.get('factory', PreferencesFactory)

    def __call__(self, user):
        prefs = user.notification_preferences
        if not prefs:
            prefs = self.factory(user)
        return prefs

class PreferencesFactory(object):
    """Create and save a user's notification ``Preferences``."""

    def __init__(self, **kwargs):
        self.model_cls = kwargs.get('model_cls', orm.Preferences)
        self.session = kwargs.get('session', bm.Session)

    def __call__(self, user, **props):
        """Create, save, flush and return."""

        # Unpack.
        model_cls = self.model_cls
        session = self.session

        # Create.
        inst = model_cls(**props)
        inst.user = user

        # Save and return.
        session.add(inst)
        session.flush()
        return inst

class PreferencesJSON(object):
    """JSON Represention of a user's notification preferences."""

    def __init__(self, request):
        self.request = request

    def __call__(self, inst):
        return {
            'id': inst.id,
            'type': inst.class_slug,
            'frequency': inst.frequency,
            'channel': inst.channel,
            'user': {
                'type': 'auth_users',
                'id': inst.user_id,
            }
        }

class SpawnDispatches(object):
    """Spawn dispatches for a notification."""

    def __init__(self, **kwargs):
        self.get_address = kwargs.get('get_address', GetDispatchAddress())
        self.model_cls = kwargs.get('model_cls', orm.Dispatch)

    def __call__(self, notification, prefs, mapping, delay=None, bcc=None):
        """Given a notification, the current user notification preferences and the
          configured dispatch mapping, spawn the necessary notification dispatches.
        """

        # Unpack.
        get_address = self.get_address
        model_cls = self.model_cls

        # If there's nothing to send, we're golden.
        config = mapping.get(prefs.channel, None)
        if not config:
            return

        # Otherwise prepare...
        channel = prefs.channel
        address = get_address(notification.user, channel)
        now = datetime.utcnow()
        due = now
        if delay:
            due += relativedelta(seconds=delay)

        # ... and spawn the dispatch.
        inst = model_cls(address=address, channel=channel, due=due)
        inst.view = config['view']
        inst.spec = config['spec']
        inst.batch_spec = = config['batch_spec']
        inst.notification = notification

        # Record that the notification has been dealt with.
        notification.spawned = now

        # Save to the database.
        session.add(inst)
        session.add(notification)
        session.flush()

        # Return a list of the dispatches spawned.
        dispatches = [inst]
        return dispatches

class GetDispatchAddress(object):
    """Given a ``user`` and their notification ``prefs``, figure out the address
      to dispatch to.
    """

    def __call__(self, user, channel):
        """Currently we only support the user's preferred email."""

        if channel != constants.CHANNELS['email']:
            raise NotImplementedError

        return user.best_email.address

class LookupDispatch(object):
    """Lookup notifications dispatch."""

    def __init__(self, **kwargs):
        self.model_cls = kwargs.get('model_cls', orm.Dispatch)

    def __call__(self, id_):
        return self.model_cls.query.get(id_)

class QueryDueDispatches(object):
    """Get a notification's due dispatches."""

    def __init__(self, **kwargs):
        self.model_cls = kwargs.get('model_cls', orm.Dispatch)

    def __call__(self, notification, dt):
        model_cls = self.model_cls
        query = model_cls.query.filter_by(notification_id=notification.id)
        query = query.filter(model_cls.due<dt)
        return query

class DispatchJSON(object):
    """JSON Represention of a the dispatch of a notification."""

    def __init__(self, request):
        self.request = request

    def __call__(self, inst):
        return {
            'id': inst.id,
            'type': inst.class_slug,
            'batch_spec': inst.batch_spec
            'bcc_address': inst.bcc_address,
            'channel': inst.channel,
            'due': inst.due,
            'notification': {
                'type': 'notifications',
                'id': inst.notification_id
            },
            'sent': inst.sent,
            'spec': inst.spec
            'to_address': inst.to_address,
            'view': inst.view,
        }
