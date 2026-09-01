from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from reactiva.campaigns.orchestrator import (
    generate_monthly_recommendations,
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
    Returns the business date used by the monthly recommendation job.

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
    Monthly ReActiva recommendation job.

    Flow:
        accumulated canonical transactions
            ->
        one Gradient Boosting training execution
            ->
        predictions for all customers inactive >= 270 days
            ->
        recommendations_YYYY-MM.csv in S3

    The GBoost model is trained once per execution, not once per
    customer.

    Any unhandled exception is intentionally re-raised so AWS Lambda
    reports the invocation as failed and the configured AWS retry /
    monitoring mechanism can react accordingly.
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
        "Monthly recommendations job started "
        "reference_date=%s request_id=%s",
        reference_date,
        request_id,
    )

    try:
        result = generate_monthly_recommendations(
            reference_date=reference_date,
        )

        recommendations_df = result[
            "recommendations"
        ]

        response = {
            "status": "SUCCESS",
            "campaign_month": result[
                "campaign_month"
            ],
            "reference_date": (
                result["reference_date"]
                .strftime("%Y-%m-%d")
            ),
            "recommendations_key": result[
                "recommendations_key"
            ],
            "customers_recommended": int(
                len(recommendations_df)
            ),
        }

        logger.info(
            "Monthly recommendations job completed "
            "month=%s customers=%s key=%s",
            response["campaign_month"],
            response["customers_recommended"],
            response["recommendations_key"],
        )

        return response

    except Exception:
        logger.exception(
            "Monthly recommendations job failed "
            "reference_date=%s request_id=%s",
            reference_date,
            request_id,
        )

        raise