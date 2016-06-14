# -*- coding: utf-8 -*-

"""Shared constant values."""

import sys

CHANNELS = {
    'email': u'EMAIL',
    'sms': u'SMS',
    # 'pigeon': u'PIGEON',
}

_frequencies = {
    'immediately': (u'IMMEDIATELY', 0),
    'hourly': (u'HOURLY', 60 * 60),
    'daily': (u'DAILY', 60 * 60 * 24),
    'never': (u'NEVER', sys.maxint),
}
FREQUENCIES = dict(((k, v[0]) for k, v in _frequencies.items()))
DELTAS = dict(((v[0], v[1]) for k, v in _frequencies.items()))
