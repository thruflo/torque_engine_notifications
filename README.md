
[![Build Status](https://travis-ci.org/thruflo/torque_engine_notifications.svg?branch=master)](https://travis-ci.org/thruflo/torque_engine_notifications)

## torque_engine_notifications

Let's say you're a Python web developer. Then -- just for sake of argument -- say that you happen to like using both the [Pyramid][] web framework and [nTorque][] task queue. Then -- running with the hypothetical -- say for some obscure reason you liked the idea of a dual-queue work engine system using configurable finite state machines *so much* that you based your *entire* application architecture on the highly specific, fast moving and undocumented [pyramid_torque_engine][].

Well, what a coincidence! Having got that far, it's only reasonable that you should tire of manually configuring hooks and subscribers every time you need to dispatch a notification.
