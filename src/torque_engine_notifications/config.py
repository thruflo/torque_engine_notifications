# -*- coding: utf-8 -*-

"""XXX"""

import logging
logger = logging.getLogger(__name__)

from . import repo

class Notifier(object):
    """XXX haven't gone through this one yet."""

    def __init__(self, interface, role, dispatch_mapping, delay=None, bcc=None):
        self.interface = interface
        self.role = role
        self.dispatch_mapping = dispatch_mapping
        self.delay = delay
        self.bcc = bcc
        self.notification_factory = repo.NotificationFactory

    def __call__(self, request, context, event, op, **kwargs):
        """"""

        # # Unpack.
        # dispatch_mapping = self.dispatch_mapping
        # notification_factory = self.notification_factory(request)
        # delay = self.delay
        # bcc = self.bcc
        # interface = self.interface
        # role = self.role

        # # Prepare.
        # notifications = []

        # # get relevant information.
        # interested_users_func = get_role_mapping(request, interface)
        # interested_users = interested_users_func(request, context)
        # for user in interested_users[role]:
        #     # Just user is a shorthand for context.user.
        #     if user == 'user':
        #         user = context.user
        #     # create the notifications.
        #     notification = notification_factory(event, user, dispatch_mapping, delay, bcc)
        #     notifications.append(notification)

        # # Tries to optimistically send the notification.
        # dispatch_notifications(request, notifications)
        raise NotImplementedError

def add_notification(config, interface, events, role, mapping, **kwargs):
    """Configuration directive to register a notification event subscriber."""

    o = engine_constants.OPERATIONS
    notify = Notifier(interface, role, mapping, **kwargs)

    def register():
        config.add_engine_subscriber(interface, events, o.NOTIFY, notify)

    discriminator = (
        'torque_engine_notifications',
        'notification',
        interface,
        events,
        role,
    )
    config.action(discriminator, register)

def register_role_mapping(config, interface, mapping):
    """Configuration directive to register a role mapping for a given interface."""

    registry = config.registry
    mapping = registry.role_mapping

    def register():
        role_mapping[interface] = mapping

    discriminator = ('torque_engine_notifications', 'role_mapping', interface,)
    config.action(discriminator, register)

def get_role_mapping(request, interface):
    """Request method to get the role mapping registered for a given interface."""

    registry = request.registry
    mapping = registry.role_mapping
    return mapping.get(interface)

def includeme(config):
    """Handle `/events` requests and provide subscription directive."""

    # `config.notify` directive.
    o = engine_constants.OPERATIONS
    o.register('NOTIFY')
    config.add_directive('notify', add_notification)

    # `config.role_mapping` directive.
    config.registry.role_mapping = {}
    config.add_directive('role_mapping', register_role_mapping)

    # `request.role_mapping` method.
    config.add_request_method('role_mapping', get_role_mapping)
