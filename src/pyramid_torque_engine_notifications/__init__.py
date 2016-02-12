# -*- coding: utf-8 -*-

"""Provides a ``includeme()`` pyramid configuration entry point."""

import logging
logger = logging.getLogger(__name__)

import os

from pyramid import authorization
from pyramid import security
from pyramid.settings import asbool

import notification as n

from . import auth

DEFAULTS = {
    'notification.api_key': os.environ.get('PYRAMID_NOTIFICATION_API_KEY'),
}


class IncludeMe(object):
    """Set up the state change event subscription system and provide an
      ``add_engine_subscriber`` directive.
    """

    def __init__(self, **kwargs):
        self.add_notification = kwargs.get('add_notification', n.add_notification)
        self.add_roles_mapping = kwargs.get('add_roles_mapping', n.add_roles_mapping)
        self.get_roles_mapping = kwargs.get('get_roles_mapping', n.get_roles_mapping)

    def __call__(self, config):
        """Handle `/events` requests and provide subscription directive."""

        # Dispatch the notifications.
        config.add_request_method(n.dispatch_notifications, 'dispatch_notifications', reify=True)

        # Adds a notification to the resource.
        config.add_directive('add_notification', self.add_notification)
        config.registry.roles_mapping = {}

        # Adds / gets role mapping.
        config.add_directive('add_roles_mapping', self.add_roles_mapping)
        config.add_directive('get_roles_mapping', self.get_roles_mapping)

        # Operator user to receive admin related emails.
        config.add_request_method(n.get_operator_user, 'operator_user', reify=True)

        # Email sender.
        config.include('pyramid_postmark')

        # Expose webhook views to notifications such as single / batch emails / sms's.
        config.add_route('notification_single', '/notifications/single')
        config.add_view(n.notification_single_view, renderer='json',
                request_method='POST', route_name='notification_single')

        config.add_route('notification_batch', '/notifications/batch')
        config.add_view(n.notification_batch_view, renderer='json',
                request_method='POST', route_name='notification_batch')


includeme = IncludeMe().__call__
