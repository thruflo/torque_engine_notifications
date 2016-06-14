# -*- coding: utf-8 -*-

"""XXX"""

import logging
logger = logging.getLogger(__name__)

import collections

from pyramid_simpleauth import model as sa_model

from . import repo

ROLE_MAPPING_NAME = u'torque_engine_notifications.role_mapping'

class NotificationHandler(object):
    """Handle events by dispatching notifications. Instances of this class are
      registered as handlers for work engine events.
    """

    def __init__(self, roles, mapping, delay=None, bcc=None, **kwargs):
        self.roles = roles
        self.mapping = mapping
        self.spawn_kwargs = dict(delay=delay, bcc=bcc)
        self.notify = kwargs.get('notify', repo.Notify)
        self.get_user = kwargs.get('get_user', sa_model.get_existing_user)

    def __call__(self, request, context, event, op, **kwargs):
        """Get all the users who need to be notified about the event out of the
          role mapping and notify them.
        """

        # Unpack.
        mapping = self.mapping
        notify = self.notify
        roles = self.roles
        spawn_kwargs = self.spawn_kwargs

        # Prepare.
        all_notifications = []
        all_dispatches = []
        dispatch_results = []

        # Build a mapping of `user: roles`. Note that the return value from
        # `role_mapping.get(role)` can be:
        # i. a context relative attribute name in the form of a string starting
        #   with a `.`, like `.user`
        # ii. a username -- in the form of a string starting with `@`
        #   like `@thruflo`
        # iii. a function that returns a user or users
        users_to_roles = collections.defaultdict(list)
        role_mapping = request.role_mapping(context)
        for role in roles:
            value = role_mapping.get(role)
            if not value:
                continue
            if isinstance(value, basestring):
                if value.startswith('.'): # e.g.: .user
                    user = getattr(context, value[1:], None)
                elif value.startswith('@'): # e.g.: @thruflo
                    user = self.get_user(username=value[1:])
                if user:
                    users_to_roles[user].append(role)
            elif callable(value):
                users = value(request, context, role=role)
                if users:
                    if not hasattr(users, '__iter__'):
                        users = [users]
                    for user in users:
                        users_to_roles[user].append(role)

        # Notify the users :)
        for user, roles in users_to_roles.items():
            notifications, dispatches = notify(
                user,
                event,
                mapping,
                roles=roles,
                **spawn_kwargs,
            )
            if notifications:
                all_notifications += notifications
            if dispatches:
                all_dispatches += dispatches
            if notifications and dispatches:
                dispatch_results += request.notifications.dispatch(notifications)

        # Returning a list of all the dispatched messages in the form of JSON
        # serialisable dicts -- useful for testing.
        return {
            'notifications': all_notifications,
            'dispatches': all_dispatches,
            'results': dispatch_results,
        }

def notify_directive(config, interface, events, roles, mapping, **kwargs):
    """Configuration directive to register a notification event subscriber."""

    # Support single or multiple roles.
    if isinstance(roles, basestring):
        roles = [roles]

    o = engine_constants.OPERATIONS
    notify = Notifier(roles, mapping, **kwargs)

    def register():
        config.add_engine_subscriber(interface, events, o.NOTIFY, notify)

    discriminator = (
        u'torque_engine_notifications',
        u'notification',
        interface,
        events,
        roles,
    )
    intr = config.introspectable(
        category_name=u'torque_engine_notifications',
        discriminator=discriminator[1:],
        title=u'Notification',
        type_name=u'notify',
    )
    intr['value'] = (
        interface,
        events,
        o.NOTIFY,
        roles,
    )
    config.action(discriminator, register, introspectables=(intr,))

def register_role_mapping(config, interface, mapping):
    """Configuration directive to register a role mapping for a given interface."""

    def register():
        registry = config.registry
        registry.registerUtility(mapping, interface, name=ROLE_MAPPING_NAME)

    discriminator = (
        u'torque_engine_notifications',
        u'role_mapping',
        interface,
    )
    intr = config.introspectable(
        category_name=u'torque_engine_notifications',
        discriminator=discriminator[1:],
        title=u'Role Mapping',
        type_name=u'role_mapping',
    )
    intr['value'] = (
        interface,
        mapping,
    )
    config.action(discriminator, register, introspectables=(intr,))

def get_role_mapping(request, context):
    """Request method to get the role mapping registered for a given context."""

    registry = request.registry
    return registry.queryUtility(context, ROLE_MAPPING_NAME)

def includeme(config):
    """Handle `/events` requests and provide subscription directive."""

    # `config.notify` directive.
    o = engine_constants.OPERATIONS
    o.register('NOTIFY')
    config.add_directive('notify', notify_directive)

    # `config.role_mapping` directive.
    config.add_directive('role_mapping', register_role_mapping)

    # `request.role_mapping` method.
    config.add_request_method('role_mapping', get_role_mapping)
