# -*- coding: utf-8 -*-

"""Create, access, update and represent the ORM classes."""

__all__ = [
    'DispatchJSON',
    'GetDispatchAddress',
    'GetOrCreatePreferences',
    'LastDispatched',
    'LookupDispatch',
    'Notify',
    'NotificationFactory',
    'NotificationJSON',
    'PreferencesFactory',
    'PreferencesJSON',
    'PreferencesWithDueUnspawnedNotifications',
    'PreferencesWithUnsentDispatches',
    'QueryDueDispatches',
    'SpawnDispatches',
    'SpawnOutstandingNotifications',
]

import logging
logger = logging.getLogger(__name__)

from datetime import datetime
from dateutil import relativedelta

import pyramid_basemodel as bm

from . import constants
from . import orm

class Notify(object):
    """Create a notification and iff the user's notification preferences are
      *immediate* then also spawn the necessary dispatch(es).
    """

    def __init__(self, request, **kwargs):
        self.request = request
        self.factory = kwargs.get('factory', NotificationFactory())
        self.get_preferences = kwargs.get('get_prefs', GetOrCreatePreferences())
        self.spawn = kwargs.get('spawn', SpawnDispatches(request))

    def __call__(self, user, event, role, name=None, delay=0):
        """Create and conditionally spawn."""

        # Create.
        notification = self.factory(user, event, role, name=name, delay=delay)

        # If we should send immediately then spawn the dispatches.
        preferences = self.get_preferences(user)
        if preferences.send_immediately:
            dispatches = self.spawn(notification, preferences=preferences)
            return notification, dispatches

        # Otherwise our work is done.
        return notification, None

class NotificationFactory(object):
    """Create and save a ``Notification``."""

    def __init__(self, **kwargs):
        self.model_cls = kwargs.get('model_cls', orm.Notification)
        self.session = kwargs.get('session', bm.Session)

    def __call__(self, user, event, role, name=None, delay=0):
        """Create, save, flush and return a ``Notification``."""

        # Unpack.
        session = self.session
        request = self.request

        # Prepare.
        now = datetime.utcnow()
        due = now + relativedelta(seconds=delay)

        # Create the notification.
        inst = self.model_cls()
        inst.user = user
        inst.event = event
        inst.role = role
        inst.name = name
        inst.due = due

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
            },
            'read': inst.read,
            'role': inst.role,
            'name': inst.name,
            'due': inst.due,
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
        self.hash_cls = kwargs.get('hash_cls', orm.PreferencesHash)
        self.session = kwargs.get('session', bm.Session)

    def __call__(self, user, **props):
        """Create, save, flush and return."""

        # Unpack.
        model_cls = self.model_cls
        session = self.session

        # Prepare.
        latest_hash = self.hash_cls()
        latest_hash.bump()

        # Create.
        inst = model_cls(**props)
        inst.user = user
        inst.latest_hash = latest_hash

        # Save and return.
        session.add(inst)
        session.add(latest_hash)
        session.flush()
        return inst

class PreferencesWithDueUnspawnedNotifications(object):
    """Get the preferences for all the users who have due and unspawned notifications."""

    def __init__(self, request, **kwargs):
        self.model_cls = kwargs.get('model_cls', orm.Preferences)
        self.notification_cls = kwargs.get('notification_cls', orm.Notification)

    def __call__(self, now):
        """Query preferences, joined to filtered notifications through the
          shared ``user_id`` value.
        """

        # Unpack.
        model_cls = self.model_cls
        notification_cls = self.notification_cls

        # Build query.
        through_user_id = notification_cls.user_id==model_cls.user_id
        query = model_cls.query.join(notification_cls, through_user_id)
        query = query.filter(notification_cls.spawned==None)
        query = query.filter(notification_cls.read==None)
        query = query.filter(notification_cls.due<now)

        # Return the query as a generator.
        return query

class PreferencesWithUnsentDispatches(object):
    """Get the preferences for all the users who have unsent dispatches."""

    def __init__(self, request, **kwargs):
        self.model_cls = kwargs.get('model_cls', orm.Preferences)
        self.notification_cls = kwargs.get('notification_cls', orm.Notification)
        self.dispatch_cls = kwargs.get('dispatch_cls', orm.Dispatch)

    def __call__(self, now):
        """Query preferences, joined to filtered notifications through the
          shared ``user_id`` value.
        """

        # Unpack.
        model_cls = self.model_cls
        notification_cls = self.notification_cls
        dispatch_cls = self.dispatch_cls

        # Build query.
        through_user_id = notification_cls.user_id==model_cls.user_id
        through_notification_id = dispatch_cls.notification_id==notification_cls.id
        query = model_cls.query.join(notification_cls, through_user_id)
        query = model_cls.query.join(dispatch_cls, through_notification_id)
        query = query.filter(dispatch_cls.sent==None)

        # Return the query as a generator.
        return query

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

class SpawnOutstandingNotifications(object):
    """Spawn dispatches for all of a user's due and unspawned notifications.

      N.b.: we ignore notifications that are more than two days old -- that
      way we minimise edge cases where someone switches on their
      notifications and gets spammed with old events.
    """

    def __init__(self, request, **kwargs):
        self.model_cls = kwargs.get('model_cls', orm.Notification)
        self.spawn = kwargs.get('spawn', SpawnDispatches(request))

    def __call__(self, user_id, now):
        """"""

        # Unpack.
        model_cls = self.model_cls

        # Build query.
        query = model_cls.query.filter_by(user_id=user_id)
        query = query.filter_by(spawned=None, read=None)
        query = query.filter(model_cls.due<now)
        query = query.order_by(model_cls.created.asc())

        # Spawn the dispatches, returning a dict of ``notification: dispatches``
        # in case useful for testing.
        results = {}
        for notification in query:
            dispatches = self.spawn(notification)
            results[notification] = dispatches
        return results

class SpawnDispatches(object):
    """Spawn dispatches for a notification."""

    def __init__(self, request, **kwargs):
        self.request = request
        self.get_address = kwargs.get('get_address', GetDispatchAddress())
        self.model_cls = kwargs.get('model_cls', orm.Dispatch)

    def __call__(self, notification, preferences=None):
        """Given a notification, spawn the necessary notification dispatches."""

        # Unpack.
        request = self.request
        get_address = self.get_address
        model_cls = self.model_cls

        # Get the prefs, role mapping and dispatch mapping.
        if preferences is None:
            user = notification.user
            preferences = user.notification_preferences
        event = notification.event
        context = event.parent
        role = notification.role
        name = notification.name
        dispatch_mapping = request.dispatch_mapping(context, event, role, name)

        # If there's nothing to send, we're golden.
        if not dispatch_mapping:
            return
        channel = preferences.channel
        config = dispatch_mapping.get(channel, None)
        if not config:
            return

        # Otherwise prepare...
        meta = dispatch_mapping.get('meta')
        to_address = get_address(notification.user, channel)

        # ... and spawn the dispatch.
        inst = model_cls()
        inst.view = config['view']
        inst.spec = config['spec']
        inst.batch_spec = config['batch_spec']
        inst.bcc_address = meta.get('bcc_address')
        inst.subject = meta.get('subject')
        inst.channel = channel
        inst.to_address = to_address
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
        raise NotImplementedError(
            'no due anymore, what about also checking not send etc.?'
        )
        return query

class LastDispatched(object):
    """Get the latest sent date of any dispatch to this user."""

    def __init__(self, **kwargs):
        self.model_cls = kwargs.get('model_cls', orm.Dispatch)
        self.notification_cls = kwargs.get('notification_cls', orm.Notification)

    def __call__(self, user_id, default=None):
        """Query and return the ``sent`` value. Returns the ``default`` value
          if no dispatch has been sent to this user.
        """

        # Unpack.
        model_cls = self.model_cls
        notification_cls = self.notification_cls

        # Prepare a query for dispatches sent to this user.
        query = model_cls.query.filter(model_cls.sent!=None)
        query = query.join(notification_cls,
                model_cls.notification_id==notification_cls.id)
        query = query.filter(notification_cls.user_id==user_id)

        # Get the most recent and return when it was sent.
        query = query.order_by(model_cls.sent.desc())
        inst = query.first()
        if inst:
            return inst.sent

        # If there was dispatch, return the default value.
        return default

class DispatchJSON(object):
    """JSON Represention of a the dispatch of a notification."""

    def __init__(self, request):
        self.request = request

    def __call__(self, inst):
        return {
            'id': inst.id,
            'type': inst.class_slug,
            'batch_spec': inst.batch_spec,
            'bcc_address': inst.bcc_address,
            'channel': inst.channel,
            'notification': {
                'type': 'notifications',
                'id': inst.notification_id
            },
            'sent': inst.sent,
            'spec': inst.spec,
            'to_address': inst.to_address,
            'view': inst.view,
        }
