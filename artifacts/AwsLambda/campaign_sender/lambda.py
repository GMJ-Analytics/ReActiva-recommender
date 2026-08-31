from __future__ import annotations

import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from reactiva.campaigns.send_service import (
    process_campaign_send_run,
)
from reactiva.campaigns.sender import (
    build_unsubscribe_url_builder,
)


# ============================================================
# CONFIGURATION
# ============================================================

BUSINESS_TIMEZONE = "Asia/Kolkata"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ============================================================
# EXECUTION TIME
# ============================================================

def _get_execution_time(event=None):
    """
    Returns the execution time used by the campaign send service.

    Production:
        Uses current India business time.

    Manual/testing execution:
        An explicit execution_time can be supplied in the event.

    Example:
        {
            "execution_time": "2026-09-01 09:00:00"
        }
    """
    if (
        event
        and event.get("execution_time")
    ):
        return event["execution_time"]

    india_now = datetime.now(
        ZoneInfo(
            BUSINESS_TIMEZONE
        )
    )

    return india_now


# ============================================================
# ENVIRONMENT
# ============================================================

def _get_sender_email() -> str:
    """
    Reads the SES verified sender address from the Lambda
    environment.
    """
    sender_email = os.getenv(
        "SES_SENDER_EMAIL"
    )

    if (
        sender_email is None
        or not sender_email.strip()
    ):
        raise RuntimeError(
            "SES_SENDER_EMAIL environment variable "
            "is required"
        )

    return sender_email.strip()


def _get_unsubscribe_url_builder():
    """
    Builds the unsubscribe URL callback used by the campaign sender.

    Both values are Lambda environment variables:

        UNSUBSCRIBE_BASE_URL
        UNSUBSCRIBE_SECRET

    The secret is never included directly in the generated URL.
    It is used only to create the HMAC token.
    """
    base_url = os.getenv(
        "UNSUBSCRIBE_BASE_URL"
    )

    secret = os.getenv(
        "UNSUBSCRIBE_SECRET"
    )

    if (
        base_url is None
        or not base_url.strip()
    ):
        raise RuntimeError(
            "UNSUBSCRIBE_BASE_URL environment variable "
            "is required"
        )

    if (
        secret is None
        or not secret.strip()
    ):
        raise RuntimeError(
            "UNSUBSCRIBE_SECRET environment variable "
            "is required"
        )

    return build_unsubscribe_url_builder(
        base_url=base_url.strip(),
        secret=secret.strip(),
    )


# ============================================================
# LAMBDA HANDLER
# ============================================================

def lambda_handler(
    event,
    context,
):
    """
    Executes one daily ReActiva campaign send run.

    Responsibilities:
        - Load the active campaign.
        - Load current operational transactions.
        - Recheck inactivity before sending.
        - Build a signed unsubscribe URL per customer.
        - Send due emails using Amazon SES.
        - Handle retries and invalid addresses.
        - Persist updated campaign statuses.
        - Persist the technical send report.

    This Lambda does NOT:
        - Train GBoost.
        - Generate recommendations.
        - Create the monthly campaign.
    """
    execution_time = (
        _get_execution_time(
            event
        )
    )

    sender_email = (
        _get_sender_email()
    )

    unsubscribe_url_builder = (
        _get_unsubscribe_url_builder()
    )

    request_id = (
        getattr(
            context,
            "aws_request_id",
            None,
        )
        if context is not None
        else None
    )

    logger.info(
        "Starting ReActiva campaign sender "
        "execution_time=%s request_id=%s",
        execution_time,
        request_id,
    )

    try:
        result = (
            process_campaign_send_run(
                sender_email=
                    sender_email,
                execution_time=
                    execution_time,
                unsubscribe_url_builder=
                    unsubscribe_url_builder,
                region_name=
                    os.getenv(
                        "AWS_REGION"
                    ),
            )
        )

        response = {
            "status":
                "SUCCESS",
            "campaign_id":
                result["campaign_id"],
            "campaign_month":
                result["campaign_month"],
            "execution_time":
                result[
                    "execution_time"
                ].strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            "processed":
                int(
                    result["processed"]
                ),
            "sent":
                int(
                    result["sent"]
                ),
            "failed":
                int(
                    result["failed"]
                ),
            "cancelled_reactivated":
                int(
                    result[
                        "cancelled_reactivated"
                    ]
                ),
            "retry_scheduled":
                int(
                    result[
                        "retry_scheduled"
                    ]
                ),
            "report_key":
                result["report_key"],
        }

        logger.info(
            "ReActiva campaign sender completed "
            "campaign=%s processed=%s sent=%s "
            "failed=%s cancelled=%s retries=%s",
            response[
                "campaign_id"
            ],
            response[
                "processed"
            ],
            response[
                "sent"
            ],
            response[
                "failed"
            ],
            response[
                "cancelled_reactivated"
            ],
            response[
                "retry_scheduled"
            ],
        )

        return response

    except Exception:
        logger.exception(
            "ReActiva campaign sender failed "
            "execution_time=%s request_id=%s",
            execution_time,
            request_id,
        )

        raise