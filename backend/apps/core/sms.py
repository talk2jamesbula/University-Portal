"""SMS delivery. SMS_BACKEND picks the provider; the default just logs messages.

SMS_BACKEND=console     # development: messages go to the log
SMS_BACKEND=termii      # Termii (https://termii.com), needs TERMII_API_KEY and TERMII_SENDER_ID
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def normalise_phone(phone):
    """Nigerian numbers in international format without "+": 0803... -> 234803..."""
    digits = "".join(ch for ch in phone or "" if ch.isdigit())
    if digits.startswith("0") and len(digits) == 11:
        digits = "234" + digits[1:]
    return digits if len(digits) >= 10 else ""


def send_sms(phone, message):
    """Send one SMS. Returns True if handed to the provider. Never raises."""
    to = normalise_phone(phone)
    if not to:
        return False
    backend = settings.SMS_BACKEND
    try:
        if backend == "termii":
            response = requests.post(
                "https://api.ng.termii.com/api/sms/send",
                json={
                    "api_key": settings.TERMII_API_KEY,
                    "to": to,
                    "from": settings.TERMII_SENDER_ID,
                    "sms": message,
                    "type": "plain",
                    "channel": "generic",
                },
                timeout=15,
            )
            response.raise_for_status()
        else:
            logger.info("SMS to %s: %s", to, message)
        return True
    except Exception:
        logger.exception("Could not send SMS to %s", to)
        return False
