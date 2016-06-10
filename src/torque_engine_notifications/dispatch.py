# -*- coding: utf-8 -*-

"""Dispatch notifications."""

from datetime import datetime

from pyramid import path as pm_path

from . import repo
from . import util

class NotificationDispatcher(object):
    """Utility that provides an api to:

      - ``dispatch()`` notifications; and
      - ``send()`` notification dispatches
    """

    channels = ('email', 'sms',) # 'pigeon'

    def __init__(self, request):
        self.request = request
        self.now = datetime.utcnow
        self.from_email = site_email(request)
        # XXX swap these out acording to the environment.
        self.due_dispatches = repo.QueryDueDispatches()
        self.email_sender = request.send_email
        self.sms_sender = NotImplemented
        self.resolve = pm_path.DottedNameResolver().resolve

    def dispatch(self, notifications):
        """Dispatches a notification directly without waiting for the
          background process.
        """

        results = []

        dt = self.utcnow()
        for n in notifications:
            for d in self.due_dispatches(n, dt):
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

    def send_email(self, spec, data):
        email = request.render_email(
            data['from_address'],
            data['to_address']
            data['subject']
            data['spec']
            data,
            bcc=data['bcc_address'],
        )
        return self.email_sender(email)

    def send_sms(self, spec, data):
        sms = NotImplemented
        return self.sms_sender(sms)

def includeme(config):
    config.include('pyramid_postmark')
    config.add_request_method(NotificationDispatcher, 'notifications', reify=True)
