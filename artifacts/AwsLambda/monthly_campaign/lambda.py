from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from reactiva.campaigns.orchestrator import (
    create_campaign_from_monthly_recommendations,
)


# ============================================================
# CONFIGURATION
# ============================================================

BUSINESS_TIMEZONE = "Asia/Kolkata"


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ============================================================
# DATE
# ============================================================

def _get_reference_date(event=None):
    """
    Returns the business date used by the monthly campaign job.

    EventBridge normally invokes the Lambda automatically and the
    current date in Asia/Kolkata is used.

    A reference_date may also be supplied explicitly for controlled
    executions or tests:

        {
            "reference_date": "2026-09-01"
        }
    """
    if event and event.get("reference_date"):
        return event["reference_date"]

    india_now = datetime.now(
        ZoneInfo(BUSINESS_TIMEZONE)
    )

    return india_now.date().isoformat()


# ============================================================
# LAMBDA HANDLER
# ============================================================

def lambda_handler(event, context):
    """
    Creates the monthly ReActiva campaign.

    Flow:
        recommendations_YYYY-MM.csv
            ->
        validate current campaign month
            ->
        apply customer campaign restrictions
            ->
        generate deterministic coupons
            ->
        distribute customers across days 1-5
            ->
        persist campaign_active.csv
            ->
        persist customer campaign state
            ->
        persist exclusions report when applicable

    A recommendation file from a previous month is never reused.

    Any unhandled exception is intentionally re-raised so AWS Lambda
    records the invocation as failed.
    """
    reference_date = _get_reference_date(
        event
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
        "Monthly campaign job started "
        "reference_date=%s request_id=%s",
        reference_date,
        request_id,
    )

    try:
        result = (
            create_campaign_from_monthly_recommendations(
                reference_date=reference_date,
            )
        )

        campaign_df = result[
            "campaign"
        ]

        exclusions_df = result[
            "exclusions"
        ]

        response = {
            "status": "SUCCESS",
            "created": bool(
                result["created"]
            ),
            "campaign_id": result[
                "campaign_id"
            ],
            "customers_in_campaign": int(
                len(campaign_df)
            ),
            "customers_excluded": int(
                len(exclusions_df)
            ),
        }

        logger.info(
            "Monthly campaign job completed "
            "campaign=%s created=%s customers=%s excluded=%s",
            response["campaign_id"],
            response["created"],
            response["customers_in_campaign"],
            response["customers_excluded"],
        )

        return response

    except Exception:
        logger.exception(
            "Monthly campaign job failed "
            "reference_date=%s request_id=%s",
            reference_date,
            request_id,
        )

        raise