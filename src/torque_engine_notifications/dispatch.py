# -*- coding: utf-8 -*-

"""Provides a ``request.notifications`` api to dispatch notifications.

  The default implementations use Postmarkapp.com to send emails
  and Twilio to send SMS messages.
"""

import json
from datetime import datetime

from twilio import rest as tw_rest

from pyramid import path as pm_path
from pyramid import renderers
from pyramid_weblayer import tx

from . import repo

DEFAULTS = {
    'twilio.account_sid': os.environ.get('TWILIO_ACCOUNT_SID'),
    'twilio.auth_token': os.environ.get('TWILIO_AUTH_TOKEN'),
    'twilio.from_address': os.environ.get('TWILIO_FROM_ADDRESS'),
}

def site_email(request):
    settings = request.registry.settings
    site_email = settings.get('site.email')
    site_title = settings.get('site.title')
    return u'{0} <{1}>'.format(site_title, site_email)

def site_mobile(request):
    settings = request.registry.settings
    return settings.get('twilio.from_address')

class PostmarkEmailSender(object):
    """Send an email using the postmarkapp.com service."""

    def __init__(self, request, **kwargs):
        self.request = request
        self.from_address = site_email(request)
        self.send = kwargs.get('send', request.send_email)

    def __call__(self, spec, data):
        request = self.request
        email = request.render_email(
            self.from_address,
            data['to_address']
            data['subject']
            data['spec']
            data,
            bcc=data['bcc_address'],
        )
        self.send(email)
        email_data = email.to_json_message()
        return {
            'type': 'email',
            'data': email_data,
        }

class StubEmailSender(object):
    """Render and print an email, rather than actually sending it."""

    def __init__(self, request):
        self.sender = PostmarkEmailSender(request, send=self.log)

    def __call__(self, spec, data):
        return self.sender(spec, data)

    def log(self, email):
        email_data = email.to_json_message()
        logger.info(('StubEmailSender', 'would send email'))
        logger.info(json.dumps(email_data, indent=2))
        return {
            'type': 'email',
            'data': email_data,
        }

class TwilioAPI(request):
    """Configure a Twilio rest api client to send SMSs with and provide
      a `send_sms` method that dispatches when the current transaction succeeds.
    """

    def __init__(self, request):
        settings = request.registry.settings
        account_sid = settings['twilio.account_sid']
        auth_token = settings['twilio.auth_token']
        self.client = tw_rest.TwilioRestClient(account_sid, auth_token)
        self.join_tx = tx.join_to_transaction

    def send_sms(self, **kwargs):
        tx.join_to_transaction(self.send_sms_immediately, **kwargs)

    def send_sms_immediately(self, **kwargs):
        return self.client.messages.create(**kwargs)

class TwilioSMSSender(object):
    """Send an SMS using Twilio."""

    def __init__(self, request, **kwargs):
        self.request = request
        self.from_address = site_mobile(request)
        self.render = renderers.render
        self.send = kwargs.get('send', request.twilio.send_sms)

    def __call__(self, spec, data):
        request = self.request
        sms_body = self.render(spec, data, request=request)
        sms_data = {
            'from_': self.from_address,
            'to': data['to_address'],
            'body': sms_body,
        }
        self.send(**sms_data)
        return {
            'type': 'sms',
            'data': sms_data,
        }

class StubEmailSender(object):
    """Render and print an email, rather than actually sending it."""

    def __init__(self, request):
        self.sender = TwilioSMSSender(request, send=self.log)

    def __call__(self, spec, data):
        return self.sender(spec, data)

    def log(self, **sms_data):
        logger.info(('StubEmailSender', 'would send sms'))
        logger.info(json.dumps(sms_data, indent=2))
        return {
            'type': 'sms',
            'data': sms_data,
        }

class Dispatcher(object):
    """Utility that provides an api to:

      - ``dispatch()`` notifications; and
      - ``send()`` notification dispatches
    """

    channels = ('email', 'sms',) # 'pigeon'

    def __init__(self, request, **kwargs):
        self.request = request
        self.now = datetime.utcnow
        self.resolve = pm_path.DottedNameResolver().resolve
        # Swap out utilities according to the environment.
        is_testing = request.environ.get('paste.testing', False)
        if is_testing:
            self.send_email = kwargs.get('send_email', StubEmailSender(request))
            self.send_sms = kwargs.get('send_sms', StubSMSSender(request))
        else:
            self.send_email = kwargs.get('send_email', PostmarkEmailSender(request))
            self.send_sms = kwargs.get('send_sms', TwilioSMSSender(request))
        self.query_due = kwargs.get('query_due', repo.QueryDueDispatches())
        self.notification_data = kwargs.get('notification_data', repo.NotificationJSON())
        self.dispatch_data = kwargs.get('dispatch_data', repo.DispatchJSON())

    def dispatch(self, notifications):
        """Dispatches a notification directly without waiting for the
          background process.
        """

        results = []
        now = self.utcnow()

        for notification in notifications:
            for dispatch in self.query_due(notification, now):
                r = self.send(dispatch)
                results.append(r)

        return results

    def send(self, dispatch):
        """Coerce information from the notification dispatch and send using
          the appropriate channel.

          N.b.: no verification if it *should* be sent is made.
        """

        # Unpack.
        notification = dispatch.notification
        event = notification.event
        target = event.parent

        # Resolve the view function and call it to get the data.
        view = self.resolve(dispatch.view)
        data = view(request, target, dispatch, event, event.action) # XXX changed API

        # If necessary, patch in some defaults.
        defaults = dispatch.__json__()
        default_subject = u'{0} {1}'.format(event.target, event.action)
        defaults = {
            'subject': default_subject,
            'to_address': dispatch.address,
            'bcc_address': dispatch.bcc,
            'target': target,
            'event': event,
            'action': event.action,
        }
        for k, v in defaults.items():
            data.setdefault(k, v)

        # Corral the information we need from the dispatch.
        channel = dispatch.category
        assert channel in self.channels
        sender = getattr(self, 'send_{0}'.format(channel))
        spec = dispatch.single_spec

        # Send.
        message_data = sender(spec, data)

        # Mark the dispatch as sent.
        # XXX what semantics are we providing -- e.g.: scenarios where the sending
        # fails in the background?
        dispatch.sent = self.utcnow()
        self.session.add(dispatch)

        # Return a bunch of information that's useful for ftesting / debugging.
        return {
            'message': message_data,
            'dispatch': self.dispatch_data(dispatch),
            'notification': self.notification_data(notification),
        }

def includeme(config):
    """Apply default settings, configure postmark and twilio clients and
      provide the `request.notifications` api.
    """

    # Settings.
    setting = config.get_settings()
    for k, value in DEFAULTS.items():
        settings.setdefault(k, value)

    # Clients.
    config.include('pyramid_postmark')
    config.add_request_method(TwilioAPI, 'twilio', reify=True)

    # API.
    config.add_request_method(Dispatcher, 'notifications', reify=True)
