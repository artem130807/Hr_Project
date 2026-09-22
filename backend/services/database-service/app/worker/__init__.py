"""HR backend Huey worker.

This package is the only place that binds background jobs to Huey.
Business logic lives in ``app.tasks``, ``app.events``, ``app.erp`` — tasks here
are thin adapters (lock + asyncio bridge + schedule).

Consumer::

    huey_consumer app.worker.app.huey -w 2 -k thread
"""
