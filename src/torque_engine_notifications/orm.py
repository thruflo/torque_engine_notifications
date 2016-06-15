# -*- coding: utf-8 -*-

"""Model classes encapsulating ``Notification``s, their ``Dispatch``
  and a user's notification ``Preferences``.
"""

__all__ = [
    'Dispatch',
    'Notification',
    'Preferences',
    'PreferencesHash',
]

import os

from datetime import datetime

from sqlalchemy import orm
from sqlalchemy import schema
from sqlalchemy import types

import pyramid_basemodel as bm
import pyramid_basemodel.util as bm_util

from . import constants

class Preferences(bm.Base, bm.BaseMixin):
    """Encapsulate a user's notification preferences."""

    __tablename__ = 'notification_preferences'

    # Belongs (one-to-one) to a user.
    user_id = schema.Column(
        types.Integer,
        schema.ForeignKey('auth_users.id'),
        nullable=False,
    )
    user = orm.relationship(
        'pyramid_simpleauth.model.User',
        single_parent=True,
        backref=orm.backref(
            'preferences',
            single_parent=True,
            uselist=False,
        )
    )

    # Record the channel they'd like to be notified through and how
    # often they want to be notified.
    channel = schema.Column(
        types.Unicode(6),
        default=constants['email'],
        nullable=False,
    )
    frequency = schema.Column(
        types.Unicode(96),
        default=constants['immediately'],
        nullable=False,
    )

    # Flag properties.
    def disabled(self):
        return self.frequency == constants.FREQUENCIES['never']

    def enabled(self):
        return not self.enabled

    def send_immediately(self):
        return self.frequency == constants.FREQUENCIES['immediately']

class PreferencesHash(bm.Base):
    """Seperate out a frequently updated hash property from the preferences
      table, so that it's more performant to keep updating it.
    """

    __tablename__ = 'notification_pref_hashes'

    # Has a primary key id but we don't bother with the other bm.BaseMixin
    # column, in order to keep the table as simple as possible.
    id = schema.Column(
        types.Integer,
        primary_key=True,
    )

    # Belongs (one-to-one) to a user's preferences and is eager loaded
    # whenever the preferences are.
    preferences_id = schema.Column(
        'p_id',
        types.Integer,
        schema.ForeignKey('notification_preferences.id'),
        nullable=False,
    )
    preferences = orm.relationship(
        Preferences,
        single_parent=True,
        backref=orm.backref(
            'latest_hash',
            single_parent=True,
            uselist=False,
            lazy='joined'
        )
    )

    # Has a random 10-bytes-of-entropy digest value, something like
    # `da39a3ee5e6b4b0d3255`, which should be enough entropy to change
    # whenever it's bumped (doesn't need to be globally unique).
    value = schema.Column(
        'v',
        types.Unicode(20),
        nullable=False,
    )

    def bump(self):
        self.value = bm_util.generate_random_digest(num_bytes=10)
        return self.value

    def get_next_value(self):
        return self.bump()

class Notification(bm.Base, bm.BaseMixin):
    """Notify a user about an event."""

    __tablename__ = 'notifications'

    # Notify a user.
    user_id = schema.Column(
        types.Integer,
        schema.ForeignKey('auth_users.id'),
        nullable=False,
    )
    user = orm.relationship(
        'pyramid_simpleauth.model.User',
        backref=orm.backref(
            'notifications,
            single_parent=True,
        )
    )

    # About an event.
    event_id = schema.Column(
        types.Integer,
        schema.ForeignKey('activity_events.id'),
        nullable=False,
    )
    event = orm.relationship(
        'pyramid_torque_engine.orm.ActivityEvent',
        backref=orm.backref(
            'notifications,
            single_parent=True,
        ),
    )

    # Record the role that the user matched when creating this
    # notification and any discriminating name of the config rule.
    # This allows template rendering to adapt according to the role
    # *and* for the dispatch mapping to be looked up by
    # `context, event, role, name` at spawn time so that we always
    # spawn dispatches with the latest config.
    role = schema.Column(
        types.Unicode(64),
    )
    name = schema.Column(
        types.Unicode(32),
    )

    # When is this notification due to be spawned?
    due = schema.Column(
        types.DateTime,
        nullable=False,
        index=True,
    )

    # When *was* it spawned?
    spawned = schema.Column(
        types.DateTime,
        index=True,
    )

    # Potentially record when it was read. (Notifications that are read before
    # they're spawned need not be dispatched -- because the user has already
    # seen them).
    read = schema.Column(
        types.DateTime,
        index=True,
    )

class Dispatch(bm.Base, bm.BaseMixin):
    """Encapsulate the dispatch of a notification."""

    __tablename__ = 'notification_dispatches'

    # Belongs to a notification.
    notification_id = schema.Column(
        types.Integer,
        schema.ForeignKey('notifications.id'),
        nullable=False,
    )
    notification = orm.relationship(
        Notification,
        backref=orm.backref(
            'dispatches',
            single_parent=True,
        )
    )

    # How should it be sent?
    channel = schema.Column(
        types.Unicode(6),
        nullable=False,
        index=True,
    )
    view = schema.Column(
        types.Unicode(128),
        nullable=False,
    )
    spec = schema.Column(
        types.Unicode(255),
        nullable=False,
    )
    batch_spec = schema.Column(
        types.Unicode(255),
        nullable=False,
    )

    # Optional default subject.
    subject = schema.Column(
        types.Unicode(255),
    )

    # To whom? Note that these can be email, phone number -- whatever
    # primary identifier the channel requires.
    to_address = schema.Column(
        types.Unicode(255),
        nullable=False,
    )
    bcc_address = schema.Column(
        types.Unicode(255),
    )

    # When was it sent?
    sent = schema.Column(
        types.DateTime,
        index=True,
    )
