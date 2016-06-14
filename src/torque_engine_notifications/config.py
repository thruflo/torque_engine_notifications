# -*- coding: utf-8 -*-

"""Pyramid framework extensions to provide:

  i. ``config.notify`` and ``config.role_mapping`` directives
  ii. ``request.role_mapping`` method

  ``config.notify(interface, events, roles, mapping)`` is a high
  level directive that uses the underlying ``add_engine_subscriber``
  machinery to subscribe to the ``events`` on contexts providing
  ``interface`` and handle them by sending notifications to the
  users registered as having the given ``roles`` optionally using
  the template specs and view functions defined in the ``mapping``.

  ``config.role_mapping(interface, mapping)`` registers a mapping
  of `role: users` for a given interface, where `users` is a data
  structure that provides enough information to get the users who
  have the given role for contexts providing the interface.

  ``request.role_mapping(context)`` get the role registered role
  mapping for a given context.
"""

import logging
logger = logging.getLogger(__name__)

import collections

from pyramid_simpleauth import model as sa_model

from . import repo

ROLE_MAPPING_NAME = u'torque_engine_notifications.role_mapping'

def get_dispatch_mapping_name(event, roles, name=None):
    role_str = u','.format(sorted(roles))
    parts = [event, role_str]
    if name:
        parts.append(name)
    return u'::'.join(parts)

class NotificationHandler(object):
    """Handle events by dispatching notifications. Instances of this class are
      registered as handlers for work engine events.
    """

    def __init__(self, role, delay=0, **kwargs):
        self.role = role
        self.delay = delay
        self.notify = kwargs.get('notify', repo.Notify)
        self.get_user = kwargs.get('get_user', sa_model.get_existing_user)

    def __call__(self, request, context, event, op, **kwargs):
        """Get all the users who need to be notified about the event out of the
          role mapping and notify them.
        """

        # Unpack.
        delay = self.delay
        mapping = self.mapping
        notify = self.notify(request)
        role = self.role

        # Prepare.
        all_notifications = []
        all_dispatches = []
        dispatch_results = []

        # Build a list of users. Note that the return value from
        # `role_mapping.get(role)` can be:
        # i. a context relative attribute name in the form of a string starting
        #   with a `.`, like `.user`
        # ii. a username -- in the form of a string starting with `@`
        #   like `@thruflo`
        # iii. a function that returns a user or users
        users = []
        role_mapping = request.role_mapping(context)
        value = role_mapping.get(role)
        if not value:
            pass
        elif isinstance(value, basestring):
            if value.startswith('.'): # e.g.: .user
                user = getattr(context, value[1:], None)
            elif value.startswith('@'): # e.g.: @thruflo
                user = self.get_user(username=value[1:])
            if user:
                users.append(user)
        elif callable(value):
            retval = value(request, context, role=role)
            if retval:
                if not hasattr(users, '__iter__'):
                    users = [retval]
                else:
                    users = retval

        # Notify the users :)
        for user in users:
            notifications, dispatches = notify(
                user,
                event,
                role=role,
                delay=delay,
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

class RegistrationEnclosure(object):
    """We use instances of this class as the config.action registration
      callable in the notify_directive below instead of the usual
      inline `def register` function in order to avoid clobbering local
      variables when we loop through the `for event in events`.

      (Otherwise all registrations would only ever get the last value
      of `event`).
    """

    def __init__(self, config, interface, event, mapping, name, operation, handler):
        self.config = config
        self.interface = interface
        self.event = event
        self.mapping = mapping
        self.name = name
        self.operation = operation
        self.handler = handler

    def __call__(self):
        """Unpack and perform the configuration actions."""

        # Unpack.
        config = self.config
        interface = self.interface
        event = self.event
        mapping = self.mapping
        name = self.name
        operation = self.operation
        handler = self.handler

        # Register the dispatch mapping as a named utility. This allows us
        # to look it up when spawning a notification's dispatches, which
        # allows us to seamlessly update config code whilst notifications
        # are in the database and have the notifications spawned into
        # dispatches with the *new config values* (e.g.: for spec, view
        # function, etc.) as long as the mapping name still matches.
        registry = config.registry
        registry.registerUtility(mapping, interface, name=name)
        config.add_engine_subscriber(interface, event, operation, handler)

def notify_directive(config, interface, events, roles, mapping, bcc=None, delay=0, name=None):
    """Configuration directive to register a notification event subscriber."""

    # Unpack.
    o = engine_constants.OPERATIONS

    # Support single or multiple events and roles.
    if isinstance(events, basestring):
        events = (events,)
    if isinstance(roles, basestring):
        roles = (roles,)

    # Patch the bcc address into the mapping.
    raise NotImplementedError(
        """
          More than just the bcc, we need to implement our defaults and
          build up the explicit mapping accordingly.
        """
    )

    registrations = {}
    for event in events:
        for role in roles:
            handler = NotificationHandler(role, delay=delay)
            mapping_name = get_dispatch_mapping_name(event, role, name=name)
            registrations[mapping_name] = RegistrationEnclosure(
                config,
                interface,
                event,
                mapping,
                mapping_name,
                o.NOTIFY,
                handler,
            )
            discriminator = (
                u'torque_engine_notifications',
                u'notification',
                interface,
                mapping_name,
            )
            intr = config.introspectable(
                category_name=u'torque_engine_notifications',
                discriminator=discriminator[1:],
                title=u'Notification',
                type_name=u'notify',
            )
            intr['value'] = (
                interface,
                event,
                o.NOTIFY,
                role,
            )
            config.action(discriminator, registrations[mapping_name], introspectables=(intr,))

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
