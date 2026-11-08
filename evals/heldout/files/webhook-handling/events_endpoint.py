"""Provider events endpoint."""
import logging
from flask import request

log = logging.getLogger(__name__)
HANDLED = {"payment.completed"}


def events():
    event = request.get_json()
    log.info("event received: %s", event)
    if event["type"] not in HANDLED:
        return "unhandled", 500
    mark_paid(event["data"]["order_id"])
    return "", 200
