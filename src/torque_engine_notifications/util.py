# -*- coding: utf-8 -*-

"""Utility functions."""

def site_email(request):
    settings = request.registry.settings
    site_email = settings.get('site.email')
    site_title = settings.get('site.title')
    return u'{0} <{1}>'.format(site_title, site_email)
