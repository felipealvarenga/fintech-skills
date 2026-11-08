"""Payment endpoint."""
import logging

log = logging.getLogger("payments")


def charge(request, processor):
    log.info("charge request %s", request.json)
    result = processor.charge(request.json)
    log.info("charge response %s", result)
    return result
