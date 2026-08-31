from __future__ import annotations

import logging

import pandas as pd

from reactiva.config import (
    DATASET_URI,
    S3_BUCKET,
)
from reactiva.campaigns.campaign import (
    CAMPAIGN_COLUMNS,
)
from reactiva.campaigns.orchestrator import (
    INACTIVITY_DAYS,
    load_operational_transactions,
)
from reactiva.campaigns.sender import (
    process_due_campaign_emails,
)
from reactiva.campaigns.storage import (
    CAMPAIGN_ACTIVE_KEY,
    CAMPAIGN_REPORTS_PREFIX,
    read_csv_from_s3,
    write_csv_to_s3,
)


logger = logging.getLogger(__name__)


# ============================================================
# REPORT CONFIGURATION
# ============================================================

SEND_REPORTS_PREFIX = (
    f"{CAMPAIGN_REPORTS_PREFIX}/send_events"
)


# ============================================================
# TIME HELPERS
# ============================================================

def normalize_execution_time(
    execution_time=None,
) -> pd.Timestamp:
    """
    Returns a timezone-naive timestamp for campaign business logic.

    The Lambda layer is responsible for supplying the current
    Asia/Kolkata local time. Removing timezone information here
    keeps comparisons compatible with Purchase Date values stored
    in the transaction datasets.
    """
    if execution_time is None:
        return pd.Timestamp.now()

    parsed = pd.Timestamp(
        execution_time
    )

    if pd.isna(parsed):
        raise ValueError(
            "execution_time is invalid"
        )

    if parsed.tzinfo is not None:
        parsed = parsed.tz_localize(
            None
        )

    return parsed


# ============================================================
# SEND REPORT KEY
# ============================================================

def build_send_report_key(
    campaign_id: str,
    execution_time,
) -> str:
    """
    Creates one technical report key per send-service execution.

    Example:
        campaigns/reports/send_events/
        REACTIVA-2026-09_2026-09-01T090000.csv
    """
    execution_time = (
        normalize_execution_time(
            execution_time
        )
    )

    safe_campaign_id = (
        str(campaign_id)
        .strip()
        .replace("/", "_")
        .replace("\\", "_")
    )

    timestamp = (
        execution_time.strftime(
            "%Y-%m-%dT%H%M%S"
        )
    )

    return (
        f"{SEND_REPORTS_PREFIX}/"
        f"{safe_campaign_id}_"
        f"{timestamp}.csv"
    )


# ============================================================
# ACTIVE CAMPAIGN
# ============================================================

def load_active_campaign(
    bucket: str = S3_BUCKET,
    s3_client=None,
) -> pd.DataFrame:
    """
    Loads campaign_active.csv using the canonical campaign schema.
    """
    campaign_df = read_csv_from_s3(
        bucket=bucket,
        key=CAMPAIGN_ACTIVE_KEY,
        expected_columns=CAMPAIGN_COLUMNS,
        s3_client=s3_client,
    )

    if campaign_df.empty:
        raise RuntimeError(
            "There is no active campaign to process"
        )

    return campaign_df


def _write_and_verify_active_campaign(
    campaign_df: pd.DataFrame,
    bucket: str,
    s3_client=None,
) -> pd.DataFrame:
    """
    Persists campaign_active.csv and verifies the resulting row count
    and canonical schema.

    storage.py already performs the configured critical S3 retries.
    """
    write_csv_to_s3(
        df=campaign_df,
        bucket=bucket,
        key=CAMPAIGN_ACTIVE_KEY,
        s3_client=s3_client,
    )

    verified_df = read_csv_from_s3(
        bucket=bucket,
        key=CAMPAIGN_ACTIVE_KEY,
        expected_columns=CAMPAIGN_COLUMNS,
        s3_client=s3_client,
    )

    if len(
        verified_df
    ) != len(
        campaign_df
    ):
        raise RuntimeError(
            "Active campaign verification failed "
            "after S3 write"
        )

    return verified_df


# ============================================================
# EVENT REPORT
# ============================================================

def persist_send_events(
    events_df: pd.DataFrame,
    campaign_id: str,
    execution_time,
    bucket: str,
    s3_client=None,
) -> str | None:
    """
    Persists the events produced during one send-service execution.

    No report is created when no customer was due for processing.
    """
    if (
        events_df is None
        or events_df.empty
    ):
        return None

    report_key = build_send_report_key(
        campaign_id=campaign_id,
        execution_time=execution_time,
    )

    write_csv_to_s3(
        df=events_df,
        bucket=bucket,
        key=report_key,
        s3_client=s3_client,
    )

    return report_key


# ============================================================
# DAILY SEND SERVICE
# ============================================================

def process_campaign_send_run(
    sender_email: str,
    execution_time=None,
    bucket: str = S3_BUCKET,
    dataset_uri: str = DATASET_URI,
    inactivity_days: int = INACTIVITY_DAYS,
    store_name: str = "ReActiva",
    unsubscribe_url_builder=None,
    s3_client=None,
    ses_client=None,
    region_name: str | None = None,
) -> dict:
    """
    Executes one ReActiva campaign send run.

    Flow:
        1. Load campaign_active.csv.
        2. Load historical + consolidated transactions.
        3. Identify campaign rows due now.
        4. Recheck customer inactivity before every send/retry.
        5. Send through SES when still eligible.
        6. Update campaign statuses.
        7. Persist and verify campaign_active.csv.
        8. Persist a technical event report.

    The function does not create campaigns and does not execute GBoost.
    It only processes the campaign that already exists.
    """
    if not sender_email:
        raise ValueError(
            "sender_email is required"
        )

    execution_time = (
        normalize_execution_time(
            execution_time
        )
    )

    campaign_df = load_active_campaign(
        bucket=bucket,
        s3_client=s3_client,
    )

    campaign_ids = {
        str(value).strip()
        for value in campaign_df[
            "Campaign ID"
        ].dropna()
        if str(value).strip()
    }

    if len(campaign_ids) != 1:
        raise RuntimeError(
            "campaign_active.csv must contain exactly "
            "one Campaign ID"
        )

    campaign_id = next(
        iter(campaign_ids)
    )

    campaign_months = {
        str(value).strip()
        for value in campaign_df[
            "Campaign Month"
        ].dropna()
        if str(value).strip()
    }

    if len(campaign_months) != 1:
        raise RuntimeError(
            "campaign_active.csv must contain exactly "
            "one Campaign Month"
        )

    campaign_month = next(
        iter(campaign_months)
    )

    execution_month = (
        execution_time.strftime(
            "%Y-%m"
        )
    )

    if campaign_month != execution_month:
        raise RuntimeError(
            "Active campaign does not belong to "
            f"the execution month. "
            f"Active={campaign_month}, "
            f"Execution={execution_month}"
        )

    transactions_df = (
        load_operational_transactions(
            bucket=bucket,
            dataset_uri=dataset_uri,
            s3_client=s3_client,
        )
    )

    updated_campaign_df, events_df = (
        process_due_campaign_emails(
            campaign_df=campaign_df,
            transactions_df=transactions_df,
            sender_email=sender_email,
            execution_time=execution_time,
            inactivity_days=inactivity_days,
            store_name=store_name,
            unsubscribe_url_builder=
                unsubscribe_url_builder,
            ses_client=ses_client,
            region_name=region_name,
        )
    )

    # If nobody was due, the active campaign has not changed.
    if events_df.empty:
        logger.info(
            "Campaign send run completed with no due customers "
            "campaign=%s execution_time=%s",
            campaign_id,
            execution_time.isoformat(),
        )

        return {
            "campaign_id":
                campaign_id,
            "campaign_month":
                campaign_month,
            "execution_time":
                execution_time,
            "processed":
                0,
            "sent":
                0,
            "failed":
                0,
            "cancelled_reactivated":
                0,
            "retry_scheduled":
                0,
            "report_key":
                None,
            "campaign":
                campaign_df,
            "events":
                events_df,
        }

    verified_campaign_df = (
        _write_and_verify_active_campaign(
            campaign_df=
                updated_campaign_df,
            bucket=
                bucket,
            s3_client=
                s3_client,
        )
    )

    report_key = persist_send_events(
        events_df=events_df,
        campaign_id=campaign_id,
        execution_time=execution_time,
        bucket=bucket,
        s3_client=s3_client,
    )

    event_counts = (
        events_df[
            "Event"
        ]
        .value_counts()
        .to_dict()
    )

    result = {
        "campaign_id":
            campaign_id,
        "campaign_month":
            campaign_month,
        "execution_time":
            execution_time,
        "processed":
            int(
                len(events_df)
            ),
        "sent":
            int(
                event_counts.get(
                    "SENT",
                    0,
                )
            ),
        "failed":
            int(
                event_counts.get(
                    "FAILED",
                    0,
                )
            ),
        "cancelled_reactivated":
            int(
                event_counts.get(
                    "CANCELLED_REACTIVATED",
                    0,
                )
            ),
        "retry_scheduled":
            int(
                event_counts.get(
                    "RETRY_SCHEDULED",
                    0,
                )
            ),
        "report_key":
            report_key,
        "campaign":
            verified_campaign_df,
        "events":
            events_df,
    }

    logger.info(
        "Campaign send run completed "
        "campaign=%s processed=%s sent=%s failed=%s "
        "cancelled=%s retries=%s",
        campaign_id,
        result["processed"],
        result["sent"],
        result["failed"],
        result["cancelled_reactivated"],
        result["retry_scheduled"],
    )

    return result