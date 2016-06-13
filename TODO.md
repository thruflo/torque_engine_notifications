
# 1

Could we have an optional shorthand so this is long form:

    def get_roles_mapping(request, bill):
        """Returns a role mapping for the bill"""
        return {'customer': [bill.user]}
    config.add_roles_mapping(IBill, get_roles_mapping)

For:

    config.add_roles_mapping(IBill, {'customer': ['user']})

# 2

This:

    def customer_notification(request, context, spec, to):
        subject = u'Your bill from Opendesk'
        tmpl_vars, us = extract_data_us(request, context, to)
        email = request.render_email(us, to, subject, spec, tmpl_vars, bcc=us, **kwargs)
        return request.send_email(email)

To:

    def notify_customer_on_new_bill(request, context, user, role_name, event, state_or_action):
        tmpl_vars = dict(subject=u'Your bill from Opendesk')
        return tmpl_vars

Or:

    def notify_customer_on_new_bill(request, context, *args):
        return {}

Or:

    Nothing! yey, use a default noop view!

In the framework:

- default to not bcc'ing us, unless the config has bcc=True or bcc='<address>' (True uses a global setting to info@...)
- get the `to` address from the recipient user
- `spec` is as configured
- get `subject, tmpl_vars` from the view
- obviously the tmpl_vars need the request (this is already automatic with pyramid_postmark?)
- `tmpl_vars.setdefault('context', context)`
- `tmpl_vars.setdefault('user', user)` # the recipient
- `tmpl_vars.setdefault('role_name', role_name)`
- `tmpl_vars.setdefault('event', event)`
- `tmpl_vars.setdefault('state_or_action', state_or_action)`
- plus use `$resource_name [was $action | is now $state]` to setdefault the subject

# 3

Switch param order:

    config.add_notification(IBill, 'customer', s.PAID, ...)

To:

    config.add_notification(IBill, s.PAID, 'customer', ...)

# 3.bdhajdksa

Rename the `notification_email_single_view` stuff to `notification_single_view`
with `channel` as a validated param.

Rename `send_email_from_notification_dispatch` to `send_notification_dispatch`
and pass channel through.

Expand `send_notification_dispatch` to accomodate stuff listed above and then
at the end, pass `tmpl_vars, spec` to a `send_[email|sms]` function that actually
does the postmark / twillio dispatch.

# 4

Implement `notification_email_batch_view`!

Batch templates:

- start with a global template for batch "partial"
- this just returns the rectangle listing item that works with the generic data:

    `[ $resource_name [was $action | is now $state] ]`
    with the right hyperlinks

That goes into a globally registered / default batch template which has header and footer.

    [ brand header ]
    for item in notifications: render partial
    [ thanks! footer ]

^ Using the same header and footer as the single templates inherit from.

Then allow this to be overriden in the `dispatch_mapping` with a specific batch item partial.

# 4b

N.b.: things that should be DEFAULT_SETTINGS backed by env var configurable in
notifications.includeme:

- base template (`<%inherit name="${ notifications.base_tmpl }">`)
- batch template (which inherits from the base template normally)
- default batch item partial
- from and bcc addresses

- postmark and twillio config!

(N.b.: pass `notifications` as a namespace in to the template rendering!)

# 5

Yey! Now we get minimal configuration statements:

    config.add_notification(IBill, s.PAID, 'customer', template_spec)

Rules:

- do some nasty parsing of the args to see what you've been given
- defaults to email
- if just a string, it's a spec
- if a view and a string, it's a view + spec pair

Examples (the `...` in `config.add_notification(IBill, s.PAID, 'customer', ...)`:

    'template_:spec'

    'dotted.path.to-view', 'template:spec'

    'dotted.path.to-view', 'template:spec', 'batch_item:spec'

    ... full dict syntax as per existing ...

Plus `bcc=`

# 5.879

Stuff that needs to be tested:

* configuration statement leading to single notification dispatch
* batch dispatch based on:
  - delay
  - preference frequency
* configuration statement defaults and overrides
* channel (assert sms is NotImplemented at the moment)

# 6

All these global registrations and an example resource reg with progressive complexity
into a clear module docstring / package readme.

# 6.463278462397846289463289

Actually implement sms:
https://www.twilio.com/docs/api/rest/sending-messages

# 7 

Can we identify the dependencies / how tightly coupled are we?

- repo -> are all the utilities standalone?
- orm -> what does the model depend on?
- etc.
