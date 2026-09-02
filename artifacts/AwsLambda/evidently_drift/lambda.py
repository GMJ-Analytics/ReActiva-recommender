from __future__ import annotations

import logging

from reactiva.monitoring.run_drift_monitoring import (
    WINDOW_DAYS,
    run_data_drift_monitoring,
)


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ============================================================
# LAMBDA HANDLER
# ============================================================

def lambda_handler(event, context):
    """
    Run the ReActiva Evidently data-drift monitor.

    EventBridge can invoke this Lambda automatically using the
    default 90-day monitoring window.

    A custom window may also be supplied for controlled executions:

        {
            "window_days": 90
        }

    Any unhandled exception is intentionally re-raised so AWS Lambda
    records the invocation as failed.
    """
    event = event or {}

    window_days = int(
        event.get(
            "window_days",
            WINDOW_DAYS,
        )
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
        "Evidently drift monitoring started "
        "window_days=%s request_id=%s",
        window_days,
        request_id,
    )

    try:
        summary_df, features_df = run_data_drift_monitoring(
            window_days=window_days,
        )

        summary = summary_df.iloc[0]

        response = {
            "status": "SUCCESS",
            "monitoring_status": str(
                summary["status"]
            ),
            "run_id": str(
                summary["run_id"]
            ),
            "reference_rows": int(
                summary["reference_rows"]
            ),
            "current_rows": int(
                summary["current_rows"]
            ),
            "total_columns": int(
                summary["total_columns"]
            ),
            "drifted_columns": (
                int(summary["drifted_columns"])
                if not summary_df[
                    "drifted_columns"
                ].isna().iloc[0]
                else None
            ),
            "drift_share": (
                float(summary["drift_share"])
                if not summary_df[
                    "drift_share"
                ].isna().iloc[0]
                else None
            ),
            "features_evaluated": int(
                len(features_df)
            ),
            "window_days": window_days,
        }

        logger.info(
            "Evidently drift monitoring completed "
            "run_id=%s status=%s drift_share=%s",
            response["run_id"],
            response["monitoring_status"],
            response["drift_share"],
        )

        return response

    except Exception:
        logger.exception(
            "Evidently drift monitoring failed "
            "window_days=%s request_id=%s",
            window_days,
            request_id,
        )

        raise