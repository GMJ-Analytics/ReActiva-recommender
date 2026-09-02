"""Operational runner for Evidently data-drift monitoring."""

from __future__ import annotations

import os
from pathlib import Path

import boto3
import pandas as pd

from ..config import DATASET_URI, S3_BUCKET
from ..data.load_data import cargar_datos_as3, descargar_datos_des3
from ..features.build_features import build_customer_features
from .drift import evaluate_data_drift, save_drift_outputs


WINDOW_DAYS = 90
S3_PREFIX = "monitoring/evidently"

if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    LOCAL_OUTPUT_DIR = Path(
        "/tmp/reactiva/monitoring/evidently/latest"
    )
else:
    LOCAL_OUTPUT_DIR = Path(
        "artifacts/monitoring/evidently/latest"
    )


def _build_monitoring_windows(
    df: pd.DataFrame,
    window_days: int = WINDOW_DAYS,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    """Build consecutive reference and current temporal windows."""
    if "Purchase Date" not in df.columns:
        raise KeyError("Dataset must contain 'Purchase Date'.")

    data = df.copy()

    data["Purchase Date"] = pd.to_datetime(
        data["Purchase Date"],
        errors="coerce",
    )

    invalid_dates = data["Purchase Date"].isna().sum()

    if invalid_dates:
        raise ValueError(
            f"Dataset contains {invalid_dates} invalid Purchase Date values."
        )

    max_date = data["Purchase Date"].max()

    current_start = max_date - pd.Timedelta(days=window_days)
    reference_start = max_date - pd.Timedelta(days=window_days * 2)

    reference = data[
        (data["Purchase Date"] > reference_start)
        & (data["Purchase Date"] <= current_start)
    ].copy()

    current = data[
        (data["Purchase Date"] > current_start)
        & (data["Purchase Date"] <= max_date)
    ].copy()

    metadata = {
        "source_max_date": max_date.date().isoformat(),
        "reference_start": reference_start.date().isoformat(),
        "reference_end": current_start.date().isoformat(),
        "current_start": current_start.date().isoformat(),
        "current_end": max_date.date().isoformat(),
        "window_days": str(window_days),
    }

    return reference, current, metadata


def _append_history(
    new_df: pd.DataFrame,
    history_key: str,
) -> pd.DataFrame:
    """Append the current monitoring result to its S3 history."""
    history_df = descargar_datos_des3(
        history_key,
        S3_BUCKET,
    )

    if history_df.empty:
        combined = new_df.copy()
    else:
        combined = pd.concat(
            [history_df, new_df],
            ignore_index=True,
        )

    cargar_datos_as3(
        combined,
        history_key,
        S3_BUCKET,
    )

    return combined


def run_data_drift_monitoring(
    dataset_uri: str = DATASET_URI,
    window_days: int = WINDOW_DAYS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run one complete drift-monitoring cycle."""
    if not dataset_uri:
        raise ValueError("DATASET_URI is not configured.")

    raw_df = pd.read_csv(dataset_uri)

    reference_raw, current_raw, window_metadata = (
        _build_monitoring_windows(
            raw_df,
            window_days=window_days,
        )
    )

    reference_features = build_customer_features(reference_raw)
    current_features = build_customer_features(current_raw)

    summary_df, features_df, report_dict = evaluate_data_drift(
        reference_features,
        current_features,
    )

    for column, value in window_metadata.items():
        summary_df[column] = value

        if not features_df.empty:
            features_df[column] = value

    output_paths = save_drift_outputs(
        summary_df=summary_df,
        features_df=features_df,
        report_dict=report_dict,
        output_dir=LOCAL_OUTPUT_DIR,
    )

    latest_summary_key = (
        f"{S3_PREFIX}/latest/drift_summary.csv"
    )
    latest_features_key = (
        f"{S3_PREFIX}/latest/drift_features.csv"
    )
    latest_report_key = (
        f"{S3_PREFIX}/latest/drift_report.json"
    )

    cargar_datos_as3(
        summary_df,
        latest_summary_key,
        S3_BUCKET,
    )

    cargar_datos_as3(
        features_df,
        latest_features_key,
        S3_BUCKET,
    )

    summary_history_key = (
        f"{S3_PREFIX}/history/drift_summary_history.csv"
    )
    features_history_key = (
        f"{S3_PREFIX}/history/drift_features_history.csv"
    )

    _append_history(
        summary_df,
        summary_history_key,
    )

    if not features_df.empty:
        _append_history(
            features_df,
            features_history_key,
        )

    run_id = summary_df.iloc[0]["run_id"]

    s3 = boto3.client("s3")

    s3.upload_file(
        str(output_paths["report"]),
        S3_BUCKET,
        latest_report_key,
    )

    historical_report_key = (
        f"{S3_PREFIX}/history/{run_id}/drift_report.json"
    )

    s3.upload_file(
        str(output_paths["report"]),
        S3_BUCKET,
        historical_report_key,
    )

    print(
        "Evidently monitoring completed | "
        f"run_id={run_id} | "
        f"status={summary_df.iloc[0]['status']} | "
        f"drift_share={summary_df.iloc[0]['drift_share']} | "
        f"reference_rows={summary_df.iloc[0]['reference_rows']} | "
        f"current_rows={summary_df.iloc[0]['current_rows']}"
    )

    return summary_df, features_df


if __name__ == "__main__":
    run_data_drift_monitoring()