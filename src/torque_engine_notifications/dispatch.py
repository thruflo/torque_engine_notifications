# -*- coding: utf-8 -*-

"""Dispatch notifications."""

import json

from datetime import datetime

from pyramid import path as pm_path

from . import repo
from . import util

class PostmarkEmailSender(object):
    """Send an email using the postmarkapp.com service."""

    def __init__(self, request):
        self.request = request

    def __call__(self, spec, data):
        request = self.request
        email = request.render_email(
            data['from_address'],
            data['to_address']
            data['subject']
            data['spec']
            data,
            bcc=data['bcc_address'],
        )
        return request.send_email(email)

class StubEmailSender(object):
    """Render and print an email, rather than actually sending it."""

    def __init__(self, request):
        self.request = request

    def __call__(self, spec, data):
        request = self.request
        email = request.render_email(
            data['from_address'],
            data['to_address']
            data['subject']
            data['spec']
            data,
            bcc=data['bcc_address'],
        )
        email_data = email.to_json_message()
        logger.info(('StubEmailSender', 'would send email'))
        logger.info(json.dumps(email_data, indent=2))
        return email_data

### TODO: a real ``SMSSender``.

class StubSMSSender(object):
    """Render and print an SMS, rather than actually sending it."""

    def __init__(self, request):
        self.request = request

    def __call__(self, spec, data):
        request = self.request
        sms = NotImplemented
        sms_data = NotImplemented
        logger.info(('StubSMSSender', 'would send sms'))
        logger.info(json.dumps(sms_data, indent=2))
        return sms_data

class Dispatcher(object):
    """Utility that provides an api to:

      - ``dispatch()`` notifications; and
      - ``send()`` notification dispatches
    """

    channels = ('email', 'sms',) # 'pigeon'

    def __init__(self, request, **kwargs):
        self.request = request
        self.now = datetime.utcnow
        self.from_email = site_email(request)
        self.resolve = pm_path.DottedNameResolver().resolve
        # Swap out utilities according to the environment.
        is_testing = request.environ.get('paste.testing', False)
        if is_testing:
            self.send_email = kwargs.get('send_email', PostmarkEmailSender(request))
            self.send_sms = kwargs.get('send_sms', NotImplemented)
        else:
            self.send_email = kwargs.get('send_email', StubEmailSender(request))
            self.send_sms = kwargs.get('send_sms', StubSMSSender(request))
        self.query_due = kwargs.get('query_due', repo.QueryDueDispatches())

    def dispatch(self, notifications):
        """Dispatches a notification directly without waiting for the
          background process.
        """

        results = []

        dt = self.utcnow()
        for n in notifications:
            for d in self.query_due(n, dt):
                r = self.send(d)
                results.append(r)

        return results

    def send(self, dispatch):
        """Coerce information from the notification dispatch and send using
          the appropriate channel.

          N.b.: no verification if it *should* be sent is made.
        """

        # Unpack.
        event = dispatch.notification.event
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
            'from_address': self.from_email,
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
        return_value = sender(spec, data)

        # Mark the dispatch as sent.
        # XXX what semantics are we providing -- e.g.: scenarios where the sending
        # fails in the background?
        dispatch.sent = self.utcnow()
        self.session.add(dispatch)
        return return_value

def includeme(config):
    config.include('pyramid_postmark')
    config.add_request_method(Dispatcher, 'notifications', reify=True)
