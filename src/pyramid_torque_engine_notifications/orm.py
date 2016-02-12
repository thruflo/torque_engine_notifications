# -*- coding: utf-8 -*-

"""
"""

__all__ = [
    'Notification',
    'NotificationDispatch',
    'NotificationPreference',
]

import os

from datetime import datetime

from sqlalchemy import event
from sqlalchemy import orm
from sqlalchemy import schema
from sqlalchemy import sql
from sqlalchemy import types
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext import associationproxy as proxy
from sqlalchemy.ext import declarative
from sqlalchemy.ext import hybrid

import pyramid_basemodel as bm
from pyramid_simpleauth import model as simpleauth_model

# XXX make settings configurable.
from pyramid_torque_engine.orm import ActivityEvent


class NotificationDispatch(bm.Base, bm.BaseMixin):
    """A notification dispatch to an user, holds information about how to deliver
    and when."""

    __tablename__ = 'notifications_dispatch'

    # Has a due date.
    due = schema.Column(types.DateTime)

    # Has a sent date.
    sent = schema.Column(types.DateTime)

    # has a Notification.
    notification_id = schema.Column(
        types.Integer,
        schema.ForeignKey('notifications.id'),
    )

    # bcc info
    bcc = schema.Column(types.Unicode(96))
    # view  -> function to decode things
    view = schema.Column(types.Unicode(96))
    # simple for the moment, either single or batch text. XXX use ENUM.
    type_ = schema.Column(types.Unicode(96))
    # dotted path for the asset spec.
    single_spec = schema.Column(types.Unicode(96))
    batch_spec = schema.Column(types.Unicode(96))
    # simple for the moment, either email or sms. XXX use ENUM.
    category = schema.Column(types.Unicode(96))
    # email or telephone number
    address = schema.Column(types.Unicode(96))

class Notification(bm.Base, bm.BaseMixin):
    """A notification about an event that should be sent to an user."""

    __tablename__ = 'notifications'

    # has an user.
    user_id = schema.Column(
        types.Integer,
        schema.ForeignKey('auth_users.id'),
    )

    user = orm.relationship(
        simpleauth_model.User,
        backref='notification',
    )

    # Has a read date.
    read = schema.Column(types.DateTime)

    notification_dispatch = orm.relationship(
        NotificationDispatch,
        backref='notification')

    # has an Activity event.
    # One to many
    event_id = schema.Column(
        types.Integer,
        schema.ForeignKey('activity_events.id'),
    )
    event = orm.relationship(
        ActivityEvent,
        backref=orm.backref(
            'notification',
        ),
    )

    def __json__(self, request=None):
        """Represent the event as a JSON serialisable dict."""

        data = {
            'id': self.id,
            'user_id': self.user_id,
            'created_at': self.created.isoformat(),
            'read_at': self.read.isoformat(),
            'event_id': self.event_id,
        }
        return data

class NotificationPreference(bm.Base, bm.BaseMixin):
    """Encapsulate user's notification preferences."""

    __tablename__ = 'notification_preferences'

    # Belongs to a user.
    user_id = schema.Column(types.Integer, schema.ForeignKey('auth_users.id'))
    user = orm.relationship(simpleauth_model.User, single_parent=True,
            backref=orm.backref('notification_preference', single_parent=True, uselist=False))

    # Optional notification preferences.
    # simple for the moment, either sms or email text. XXX use ENUM.
    channel = schema.Column(types.Unicode(96))
    # simple for the moment, either daily or weekly. XXX use ENUM.
    frequency = schema.Column(types.Unicode(96))

    def __json__(self, request=None):
        return {
            'id': self.id,
            'frequency': self.frequency,
            'channel': self.channel,
            'user_id': self.user_id,
        }
