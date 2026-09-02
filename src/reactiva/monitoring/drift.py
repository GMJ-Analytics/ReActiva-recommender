"""Data drift monitoring utilities based on Evidently.

This module compares a validated reference dataset against current data and
produces structured outputs suitable for operational monitoring and BI.

It is intentionally decoupled from model training, recommendation generation,
campaign execution and AWS orchestration.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

import numpy as np
import pandas as pd
from evidently import Report
from evidently.presets import DataDriftPreset


DEFAULT_MIN_REFERENCE_ROWS = 100
DEFAULT_MIN_CURRENT_ROWS = 50


def _build_run_id() -> str:
    """Generate a unique identifier for one drift evaluation."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"drift_{timestamp}_{uuid4().hex[:8]}"


def _json_serializable(value: Any) -> Any:
    """Convert NumPy and pandas values into JSON-compatible Python values."""
    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, (np.floating,)):
        return float(value)

    if isinstance(value, (np.bool_,)):
        return bool(value)

    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()

    if isinstance(value, np.ndarray):
        return value.tolist()

    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _prepare_frames(
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    exclude_columns: Iterable[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Keep comparable columns and remove explicitly excluded variables."""
    if not isinstance(reference_df, pd.DataFrame):
        raise TypeError("reference_df must be a pandas DataFrame")

    if not isinstance(current_df, pd.DataFrame):
        raise TypeError("current_df must be a pandas DataFrame")

    excluded = set(exclude_columns or [])

    common_columns = [
        column
        for column in reference_df.columns
        if column in current_df.columns and column not in excluded
    ]

    if not common_columns:
        raise ValueError(
            "No common monitoring columns remain after applying exclusions."
        )

    reference = (
        reference_df[common_columns]
        .copy()
        .reset_index(drop=True)
    )

    current = (
        current_df[common_columns]
        .copy()
        .reset_index(drop=True)
    )

    return reference, current, common_columns


def _is_drift_detected(
    score: float | None,
    method: str | None,
    threshold: float | None,
) -> bool | None:
    """Interpret Evidently's feature-level drift score."""
    if score is None or threshold is None:
        return None

    method_normalized = (method or "").lower()

    if "p_value" in method_normalized or "p-value" in method_normalized:
        return score < threshold

    return score > threshold


def _extract_metrics(
    report_dict: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Extract dataset-level and feature-level drift metrics."""
    dataset_metric: dict[str, Any] = {}
    feature_metrics: list[dict[str, Any]] = []

    for metric in report_dict.get("metrics", []):
        config = metric.get("config", {})
        metric_type = config.get("type", "")
        value = metric.get("value")

        if metric_type.endswith("DriftedColumnsCount"):
            dataset_metric = {
                "drifted_columns": int(value.get("count", 0)),
                "drift_share": float(value.get("share", 0.0)),
                "dataset_drift_threshold": float(
                    config.get("drift_share", 0.5)
                ),
            }

        elif metric_type.endswith("ValueDrift"):
            score = float(value) if value is not None else None
            threshold = config.get("threshold")
            threshold = float(threshold) if threshold is not None else None
            method = config.get("method")

            feature_metrics.append(
                {
                    "column": config.get("column"),
                    "drift_score": score,
                    "drift_method": method,
                    "drift_threshold": threshold,
                    "drift_detected": _is_drift_detected(
                        score=score,
                        method=method,
                        threshold=threshold,
                    ),
                }
            )

    return dataset_metric, feature_metrics


def evaluate_data_drift(
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    exclude_columns: Iterable[str] | None = None,
    min_reference_rows: int = DEFAULT_MIN_REFERENCE_ROWS,
    min_current_rows: int = DEFAULT_MIN_CURRENT_ROWS,
    run_id: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Evaluate data drift between reference and current datasets.

    Returns
    -------
    summary_df
        One-row dataframe containing the global monitoring status.
    features_df
        One row per monitored feature.
    report_dict
        Raw Evidently report converted to a dictionary.
    """
    reference, current, monitoring_columns = _prepare_frames(
        reference_df=reference_df,
        current_df=current_df,
        exclude_columns=exclude_columns,
    )

    evaluation_run_id = run_id or _build_run_id()
    evaluated_at_utc = datetime.now(timezone.utc).isoformat()

    reference_rows = len(reference)
    current_rows = len(current)

    if (
        reference_rows < min_reference_rows
        or current_rows < min_current_rows
    ):
        summary_df = pd.DataFrame(
            [
                {
                    "run_id": evaluation_run_id,
                    "evaluated_at_utc": evaluated_at_utc,
                    "status": "INSUFFICIENT_DATA",
                    "reference_rows": reference_rows,
                    "current_rows": current_rows,
                    "total_columns": len(monitoring_columns),
                    "drifted_columns": None,
                    "drift_share": None,
                    "dataset_drift_threshold": None,
                }
            ]
        )

        features_df = pd.DataFrame(
            columns=[
                "run_id",
                "evaluated_at_utc",
                "column",
                "drift_score",
                "drift_method",
                "drift_threshold",
                "drift_detected",
            ]
        )

        report_dict = {
            "status": "INSUFFICIENT_DATA",
            "reason": (
                "Not enough rows to perform a reliable drift evaluation."
            ),
            "reference_rows": reference_rows,
            "current_rows": current_rows,
            "min_reference_rows": min_reference_rows,
            "min_current_rows": min_current_rows,
            "monitoring_columns": monitoring_columns,
        }

        return summary_df, features_df, report_dict

    report = Report([DataDriftPreset()])
    snapshot = report.run(current, reference)
    report_dict = snapshot.dict()

    dataset_metric, feature_metrics = _extract_metrics(report_dict)

    drifted_columns = dataset_metric.get("drifted_columns", 0)
    drift_share = dataset_metric.get("drift_share", 0.0)
    dataset_threshold = dataset_metric.get(
        "dataset_drift_threshold",
        0.5,
    )

    status = "DRIFT" if drift_share >= dataset_threshold else "OK"

    summary_df = pd.DataFrame(
        [
            {
                "run_id": evaluation_run_id,
                "evaluated_at_utc": evaluated_at_utc,
                "status": status,
                "reference_rows": reference_rows,
                "current_rows": current_rows,
                "total_columns": len(monitoring_columns),
                "drifted_columns": drifted_columns,
                "drift_share": drift_share,
                "dataset_drift_threshold": dataset_threshold,
            }
        ]
    )

    features_df = pd.DataFrame(feature_metrics)

    if not features_df.empty:
        features_df.insert(0, "evaluated_at_utc", evaluated_at_utc)
        features_df.insert(0, "run_id", evaluation_run_id)

    return summary_df, features_df, report_dict


def save_drift_outputs(
    summary_df: pd.DataFrame,
    features_df: pd.DataFrame,
    report_dict: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Path]:
    """Save drift monitoring outputs for downstream consumers."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    summary_path = output_path / "drift_summary.csv"
    features_path = output_path / "drift_features.csv"
    report_path = output_path / "drift_report.json"

    summary_df.to_csv(summary_path, index=False)
    features_df.to_csv(features_path, index=False)

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(
            report_dict,
            file,
            indent=2,
            ensure_ascii=False,
            default=_json_serializable,
        )

    return {
        "summary": summary_path,
        "features": features_path,
        "report": report_path,
    }