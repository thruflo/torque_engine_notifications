# -*- coding: utf-8 -*-

import os
import datetime
import json
import requests
import transaction

from sqlalchemy import create_engine
from pyramid_basemodel import bind_engine, save, Session

from . import constants
from . import orm
from . import repo
from . import util

env = os.environ
NOTIFICATION_SINGLE_ENDPOINT = env.get('NOTIFICATION_SINGLE_ENDPOINT', None)

DEFAULTS = {
    'torque_engine_notifications.api_key': os.environ.get('TORQUE_ENGINE_NOTIFICATIONS_API_KEY'),
}

def post_notification_dispatch(dispatch):

    headers = {}
    for item in c.ENGINE_API_KEY_NAMES:
        key = '{0}'.format(item)
        headers[key] = DEFAULTS['torque_engine_notifications.api_key']

    _ = requests.post(
                    NOTIFICATION_SINGLE_ENDPOINT,
                    headers=headers,
                    data=json.dumps(
                        {'dispatch_id': dispatch.id}))

def dispatch_user_notifications(user, user_notifications):
    """ 4. for each channel loop and either write out a single or a batch dispatch task with the
        Dispatcher ids e.g: /dispatch_email, /dispatch_sms and etc.
    """

    raise NotImplementedError('XXX how is this using channels???')

    for ch in constants.CHANNELS.values():
        # XXX check for preferences e.g: and user.channel == ch
        to_dispatch = [d for d in user_notifications if d.category == ch]
        for dispatch in to_dispatch:
            post_notification_dispatch(dispatch)
        else:
            print 'nothing here', to_dispatch
    Session.flush()


def run():
    # Bind to the database.
    engine = create_engine(os.environ['DATABASE_URL'])
    bind_engine(engine, should_create=False)

    # Prepare.
    notification_cls = orm.Notification
    dispatch_cls = orm.Dispatch
    preferences_factory = repo.PreferencesFactory()
    now = datetime.datetime.utcnow()

    # Run the algorithm.
    with transaction.manager:

        # XXX this is core business logic!
        # put it in the bloody repo!

        # 1. ignore all the notifications from the Notification table that have read field set.
        unread_notifications = dispatch_cls.query.join(notification_cls).filter(notification_cls.read == None)

        # 2. get all of the non duplicated user ids who are due to dispatch and have not been sent.
        due_to_dispatch = unread_notifications.filter(dispatch_cls.due <= now).filter(dispatch_cls.sent == None)
        user_ids_to_dispatch = set()
        for dispatch in due_to_dispatch.all():
            user_ids_to_dispatch.add(dispatch.notification.user_id)

        # 3. for each user id get all of the notifications grouped by channel
        for user_id in user_ids_to_dispatch:
            # Build the NotificationPreference object so we can get the preferences.
            prefs = orm.Preferences.query.filter_by(user_id=user_id).all()[-1]
            # If we don't have a notification preference object, we just create it on the fly.
            if prefs is None:
                prefs = preferences_factory(user_id)
            user_notifications = due_to_dispatch.filter(notification_cls.user_id == user_id).all()
            dispatch_user_notifications(prefs, user_notifications)


if __name__ == '__main__':
    run()
