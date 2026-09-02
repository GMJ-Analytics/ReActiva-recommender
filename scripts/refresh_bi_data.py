"""Synchronize Power BI monitoring data from Amazon S3."""

from __future__ import annotations

import os
from pathlib import Path

import boto3
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "dashboard" / "data"

S3_BUCKET = os.getenv("BI_S3_BUCKET", "rawdatafp")

S3_FILES = {
    "monitoring/evidently/history/drift_summary_history.csv": (
        DATA_DIR / "drift_summary_history.csv"
    ),
    "monitoring/evidently/history/drift_features_history.csv": (
        DATA_DIR / "drift_features_history.csv"
    ),
    "campaigns/campaign_active.csv": (
        DATA_DIR / "campaign_active.csv"
    ),
}

EXPECTED_COLUMNS = {
    "drift_summary_history.csv": {
        "run_id",
        "evaluated_at_utc",
        "status",
        "reference_rows",
        "current_rows",
        "total_columns",
        "drifted_columns",
        "drift_share",
        "dataset_drift_threshold",
        "window_days",
    },
    "drift_features_history.csv": {
        "run_id",
        "evaluated_at_utc",
        "column",
        "drift_score",
        "drift_method",
        "drift_threshold",
        "drift_detected",
        "window_days",
    },
        "campaign_active.csv": {
        "Campaign ID",
        "Campaign Month",
        "Customer ID",
        "Customer Full Name",
        "Customer Email",
        "Recommendation 1",
        "Recommendation 2",
        "Recommendation 3",
        "Discount Percent",
        "Coupon Code",
        "Scheduled Day",
        "Status",
        "Retry Count",
        "Sent At",
        "Reactivated At",
        "Coupon Status",
        "Coupon Redeemed At",
    },
}


def validate_csv(path: Path) -> None:
    """Validate that a downloaded CSV contains the expected BI columns."""
    dataframe = pd.read_csv(path)

    expected_name = path.name.removesuffix(".tmp")
    expected = EXPECTED_COLUMNS[expected_name]
    
    missing = expected.difference(dataframe.columns)

    if missing:
        raise ValueError(
            f"{path.name} is missing required columns: "
            f"{sorted(missing)}"
        )


def download_file(
    s3_client,
    s3_key: str,
    destination: Path,
) -> None:
    """Download and validate one S3 CSV before replacing the local copy."""
    temporary_path = destination.with_suffix(
        destination.suffix + ".tmp"
    )

    try:
        s3_client.download_file(
            S3_BUCKET,
            s3_key,
            str(temporary_path),
        )

        validate_csv(temporary_path)

        temporary_path.replace(destination)

        print(
            f"OK | s3://{S3_BUCKET}/{s3_key} "
            f"-> {destination.relative_to(REPO_ROOT)}"
        )

    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def refresh_bi_data() -> None:
    """Download the latest monitoring history required by Power BI."""
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    s3_client = boto3.client("s3")

    print("Updating Power BI data from S3...")

    for s3_key, destination in S3_FILES.items():
        download_file(
            s3_client=s3_client,
            s3_key=s3_key,
            destination=destination,
        )

    print("Power BI monitoring data updated successfully.")


if __name__ == "__main__":
    refresh_bi_data()