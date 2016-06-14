"""

  XXX
      -> goes to a *single* webhook that either batches or singles depending
      on the number of dispatches, i.e.: that's handled elsewhere
      (n.b.: also group by channel)

"""



# # -*- coding: utf-8 -*-

# """Expose `/notifications/dispatch/single` and `/notifications/dispatch/batch`."""

# import logging
# logger = logging.getLogger(__name__)

# import colander

# from . import repo

# class SingleDispatchSchema(colander.Schema):
#     dispatch_id = colander.SchemaNode(
#         colander.Integer(),
#     )

# def single_dispatch_view(request):
#     """View to handle a single notification dispatch"""

#     schema = SingleDispatchSchema()
#     lookup = repo.LookupDispatch()

#     # Decode JSON.
#     try:
#         json = request.json
#     except ValueError as err:
#         request.response.status_int = 400
#         return {'error': str(err)}

#     # Validate.
#     try:
#         appstruct = schema.deserialize(json)
#     except colander.Invalid as err:
#         request.response.status_int = 400
#         return {'error': err.asdict()}

#     # Get the dispatch.
#     dispatch_id = appstruct['dispatch_id']
#     dispatch = lookup(dispatch_id)
#     if not dispatch:
#         request.response.status_int = 404
#         return {'error': u'Notification dispatch not found.'}

#     # Send it.
#     dispatch = request.notifications.send(dispatch)
#     return {'dispatched': [dispatch]}

# def batch_dispatch_view(request):
#     """View to handle a batch of dispatches."""

#     raise NotImplementedError

# def includeme(config):
#     """Expose the ``/notifications`` route with single and batch views."""

#     # Expose the route.
#     config.add_route('notifications', '/notifications/dispatch')

#     # Expose the two views.
#     kw = dict(renderer='json', request_method='POST', route_name='notifications')
#     config.add_view(single_dispatch_view, name='single', **kw)
#     config.add_view(batch_dispatch_view, name='batch', **kw)
