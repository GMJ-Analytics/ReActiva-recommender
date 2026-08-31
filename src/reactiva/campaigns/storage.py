from __future__ import annotations

import io
import logging
import time

import boto3
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError


logger = logging.getLogger(__name__)


# ============================================================
# S3 CAMPAIGN PATHS
# ============================================================

CAMPAIGN_ACTIVE_KEY = "campaigns/campaign_active.csv"
CAMPAIGN_HISTORY_KEY = "campaigns/campaign_history.csv"
CUSTOMER_CAMPAIGN_STATUS_KEY = "campaigns/customer_campaign_status.csv"
CAMPAIGN_REPORTS_PREFIX = "campaigns/reports"


# ============================================================
# HELPERS
# ============================================================

def _get_s3_client(s3_client=None):
    """
    Returns the provided S3 client or creates a default boto3 client.
    """
    return s3_client or boto3.client("s3")


def _put_object_with_retry(
    bucket: str,
    key: str,
    body,
    content_type: str,
    max_attempts: int = 5,
    base_delay_seconds: float = 1.0,
    s3_client=None,
) -> None:
    """
    Writes an object to S3 with progressive retries.

    Critical campaign files must not silently fail. After exhausting
    all attempts, the exception is propagated to the caller so the
    campaign process can be aborted safely.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    client = _get_s3_client(s3_client)
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
            )

            logger.info(
                "S3 write completed bucket=%s key=%s attempt=%s",
                bucket,
                key,
                attempt,
            )
            return

        except (ClientError, BotoCoreError) as error:
            last_error = error

            logger.warning(
                "S3 write failed bucket=%s key=%s attempt=%s/%s error=%s",
                bucket,
                key,
                attempt,
                max_attempts,
                error,
            )

            if attempt < max_attempts:
                delay = base_delay_seconds * attempt
                time.sleep(delay)

    raise RuntimeError(
        f"Could not write s3://{bucket}/{key} "
        f"after {max_attempts} attempts"
    ) from last_error


# ============================================================
# READ
# ============================================================

def read_csv_from_s3(
    bucket: str,
    key: str,
    expected_columns: list[str] | None = None,
    s3_client=None,
) -> pd.DataFrame:
    """
    Reads a CSV from S3.

    If the object does not exist yet, returns an empty DataFrame.
    This is useful during the first campaign execution, when history
    or customer status files may not have been created yet.

    If expected_columns is provided, the file is validated before
    being returned.
    """
    client = _get_s3_client(s3_client)

    try:
        response = client.get_object(
            Bucket=bucket,
            Key=key,
        )

    except ClientError as error:
        error_code = (
            error.response
            .get("Error", {})
            .get("Code")
        )

        if error_code in {
            "NoSuchKey",
            "404",
            "NotFound",
        }:
            return pd.DataFrame(
                columns=expected_columns or []
            )

        raise

    content = (
        response["Body"]
        .read()
        .decode("utf-8")
    )

    if not content.strip():
        return pd.DataFrame(
            columns=expected_columns or []
        )

    df = pd.read_csv(
        io.StringIO(content)
    )

    if expected_columns is not None:
        missing_columns = [
            column
            for column in expected_columns
            if column not in df.columns
        ]

        if missing_columns:
            raise ValueError(
                f"S3 file '{key}' is missing required columns: "
                f"{missing_columns}"
            )

    return df


# ============================================================
# WRITE CSV
# ============================================================

def write_csv_to_s3(
    df: pd.DataFrame,
    bucket: str,
    key: str,
    max_attempts: int = 5,
    base_delay_seconds: float = 1.0,
    s3_client=None,
) -> None:
    """
    Serializes a DataFrame as CSV and writes it to S3.

    Campaign critical writes use five attempts by default,
    following the retry policy defined for Issue #60.
    """
    buffer = io.StringIO()

    df.to_csv(
        buffer,
        index=False,
    )

    _put_object_with_retry(
        bucket=bucket,
        key=key,
        body=buffer.getvalue(),
        content_type="text/csv; charset=utf-8",
        max_attempts=max_attempts,
        base_delay_seconds=base_delay_seconds,
        s3_client=s3_client,
    )


# ============================================================
# WRITE REPORT
# ============================================================

def write_report_to_s3(
    content: str,
    bucket: str,
    key: str,
    max_attempts: int = 5,
    base_delay_seconds: float = 1.0,
    s3_client=None,
) -> None:
    """
    Writes a technical campaign report to S3.
    """
    _put_object_with_retry(
        bucket=bucket,
        key=key,
        body=content,
        content_type="text/plain; charset=utf-8",
        max_attempts=max_attempts,
        base_delay_seconds=base_delay_seconds,
        s3_client=s3_client,
    )