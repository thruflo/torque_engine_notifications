# -*- coding: utf-8 -*-

"""Pyramid framework extensions to provide:

  i. ``config.notify`` and ``config.role_mapping`` directives
  ii. ``request.role_mapping`` and ``request.dispatch_mapping`` methods

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

  ``request.dispatch_mapping(context, dispatch_mapping_name)`` gets
  the config registered against a notification, so that it can be used
  when spawning dispatches.
"""

import logging
logger = logging.getLogger(__name__)

import collections

from pyramid_simpleauth import model as sa_model

from . import constants
from . import dispatch
from . import repo

ROLE_MAPPING_NAME = u'torque_engine_notifications.role_mapping'
DISPATCH_MAPPING_NAME = u'torque_engine_notifications.dispatch_mapping'

def get_dispatch_mapping_name(event, role, name=None):
    parts = [DISPATCH_MAPPING_NAME, event, role]
    if name:
        parts.append(name)
    return u'::'.join(parts)

class AugmentDispatchMapping(object):
    """Expand the given dispatch instructions into a full dictionary and
      patch it with directly provided bcc and subject defaults.
    """

    def __init__(self, registry):
        self.registry = registry
        self.site_email = dispatch.site_email(None, settings=registry.settings)

    def __call__(self, mapping, bcc=None, subject=None):
        """Now, we want to end up with a structure like:

              {
                'email': {
                  'view': 'dotted.path.to.view.function',
                  'spec': 'templates:asset/spec.mako',
                  'batch_spec': 'templates:asset/spec.mako',
                },
                'sms': {
                  'view': 'dotted.path.to.view.function',
                  'spec': 'templates:asset/spec.mako',
                  'batch_spec': 'templates:asset/spec.mako',
                },
                'meta': {
                  'bcc_address': None | 'user@domain.com',
                  'subject': None | '10 Top Tips that will blow your mind.',
                },
              }

          From statements in the form:

              config.notify(IBill, s.PAID, 'customer', ...)

          Where the ``...`` can be:

              'template_:spec'
              'dotted.path.to-view', 'template:spec'
              'dotted.path.to-view', 'template:spec', 'batch_item:spec'

          Or the full dictionary syntax above. N.b.: the SMS defaults to the
          plain text version of the email.
        """

        # First prepare the metadata.
        meta = {
            'bcc_address': bcc,
            'subject': subject,
        }
        if bcc is True:
            meta['bcc_address'] = self.site_email

        # Prepare.
        channels = {}
        view = NotImplemented # XXX default view
        spec = NotImplemented # XXX default spec
        batch_spec = NotImplemented # XXX default view

        # Expand the shorthand versions:
        is_shorthand = False
        if isinstance(mapping, basestring):
            spec = mapping
            is_shorthand = True
        elif hasattr(mapping, '__getitem__'):
            if len(mapping) == 1:
                spec = mapping
            else:
                view = mapping[0]
                spec = mapping[1]
                if len(mapping) > 2:
                    batch_spec = mapping[2]
            is_shorthand = True
        if is_shorthand:
            channels = {
                constants.DEFAULT_CHANNEL: {
                    'view': view,
                    'spec': spec,
                    'batch_spec': batch_spec,
                }
            }
        elif mapping.has_key(constants.DEFAULT_CHANNEL):
            channels = mapping
        else:
            channels = {
                constants.DEFAULT_CHANNEL: mapping,
            }

        # So at this point we should have a dictionary as the mapping
        # with at least the values for the default channel, which
        # we copy over the other channels if necessary.
        for channel in constants.CHANNELS:
            if channel == constants.DEFAULT_CHANNEL:
                continue
            channels[channel] = channels[constants.DEFAULT_CHANNEL]

        # And return the augmented mapping data.
        channels.update({'meta': meta})
        return channels

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

def notify_directive(config, interface, events, roles, mapping, name=None,
        bcc=None, subject=None, delay=0):
    """Configuration directive to register a notification event subscriber."""

    # Unpack.
    o = engine_constants.OPERATIONS
    augment_mapping = AugmentDispatchMapping(config.registry)

    # Support single or multiple events and roles.
    if isinstance(events, basestring):
        events = (events,)
    if isinstance(roles, basestring):
        roles = (roles,)

    # Patch the bcc address and subject into the mapping.
    dispatch_mapping = augment_mapping(mapping, bcc=bcc, subject=subject)

    registrations = {}
    for event in events:
        for role in roles:
            handler = NotificationHandler(role, delay=delay)
            mapping_name = get_dispatch_mapping_name(event, role, name=name)
            registrations[mapping_name] = RegistrationEnclosure(
                config,
                interface,
                event,
                dispatch_mapping,
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
            config.action(
                discriminator,
                registrations[mapping_name],
                introspectables=(intr,),
            )

def get_dispatch_mapping(request, context, event, role, name=None):
    registry = request.registry
    dispatch_mapping_name = get_dispatch_mapping_name(event, role, name=name)
    return registry.queryUtility(context, dispatch_mapping_name)

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
    """Register notification directives and request methods."""

    # `config.notify` directive and `request.dispatch_mapping` method.
    o = engine_constants.OPERATIONS
    o.register('NOTIFY')
    config.add_directive('notify', notify_directive)
    config.add_request_method('dispatch_mapping', get_dispatch_mapping)

    # `config.role_mapping` directive and `request.role_mapping` method.
    config.add_directive('role_mapping', register_role_mapping)
    config.add_request_method('role_mapping', get_role_mapping)
