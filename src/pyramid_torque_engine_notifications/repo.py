# -*- coding: utf-8 -*-

"""Create and lookup notifications."""

__all__ = [
    'NotificationFactory',
    'LookupNotification',
    'LookupNotificationDispatch',
    'NotificationPreferencesFactory',
    'get_or_create_notification_preferences',
]

import logging
logger = logging.getLogger(__name__)

import json
import pyramid_basemodel as bm

from . import orm
from . import util

import datetime
from dateutil.relativedelta import relativedelta


class NotificationFactory(object):
    """Boilerplate to create and save ``Notification``s."""

    def __init__(self, request, **kwargs):
        self.request = request
        self.jsonify = kwargs.get('jsonify', DefaultJSONifier(request))
        self.notification_cls = kwargs.get('notification_cls', orm.Notification)
        self.notification_dispatch_cls = kwargs.get('notification_dispatch_cls',
                orm.NotificationDispatch)
        self.notification_preference_factory = kwargs.get('notification_preference_factory',
                NotificationPreferencesFactory())
        self.session = kwargs.get('session', bm.Session)

    def __call__(self, event, user, dispatch_mapping, delay=None, bcc=None):
        """Create and store a notification and a notification dispatch."""

        # Unpack.
        session = self.session
        request = self.request

        # Create notification.
        notification = self.notification_cls(user=user, event=event)
        session.add(notification)
        due = datetime.datetime.now()
        email = user.best_email.address

        # Get or create user preferences.
        preference = get_or_create_notification_preferences(user)
        timeframe = preference.frequency

        # If daily normalise to 20h of each day.
        if timeframe == 'daily':
            if due.hour > 20:
                due = datetime.datetime(due.year, due.month, due.day + 1, 20)
            else:
                due = datetime.datetime(due.year, due.month, due.day, 20)

        # If hourly normalise to the next hour.
        elif timeframe == 'hourly':
            due = datetime.datetime(due.year, due.month, due.day, due.hour + 1, 0)

        # Check if there's a delay in minutes add to it.
        if delay:
            delay = relativedelta(minutes=delay)
            due = due + delay
        if bcc:
            if bcc is True or bcc == '':
                bcc = util.extract_us(request)

        # Create a notification dispatch for each channel.
        for k, v in dispatch_mapping.items():
            notification_dispatch = self.notification_dispatch_cls(notification=notification,
                    due=due, category=k, view=v['view'], bcc=bcc,
                    single_spec=v['single'], batch_spec=v['batch'], address=email)
            session.add(notification_dispatch)

        # Save to the database.
        session.flush()

        return notification

class LookupNotificationDispatch(object):
    """Lookup notifications dispatch."""

    def __init__(self, **kwargs):
        self.model_cls = kwargs.get('model_cls', orm.NotificationDispatch)

    def __call__(self, id_):
        """Lookup by notifiction dispatch id."""

        return self.model_cls.query.get(id_)

    def by_notification_id(self, id_, type=u'email'):
        """Lookup all notification dispatches that belong to
        the notification id and type."""

        return self.model_cls.query.filter_by(notification_id=id_).all()

def get_or_create_notification_preferences(user):
    """Gets or creates the notification preferences for the user."""
    notification_preference_factory = NotificationPreferencesFactory()
    preference = user.notification_preference
    if preference is None:
        preference = notification_preference_factory(user.id)
        bm.Session.add(user)
    return preference

class NotificationPreferencesFactory(object):
    """Boilerplate to create and save ``Notification preference``s."""

    def __init__(self, **kwargs):
        self.notification_preference_cls = kwargs.get('notification_preference_cls',
                orm.NotificationPreference)
        self.session = kwargs.get('session', bm.Session)

    def __call__(self, user_id, frequency=None, channel='email'):
        """Create and store a notification and a notification dispatch."""

        # Unpack.
        session = self.session

        # Create notification.
        notification_preference = self.notification_preference_cls(
                user_id=user_id, frequency=frequency, channel=channel)

        # Save to the database.
        session.add(notification_preference)
        session.flush()

        return notification_preference
