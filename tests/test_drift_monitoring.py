import os
import tempfile
import unittest
from pathlib import Path

import pandas as pd


# Ensure config can be imported in isolated test environments.
os.environ.setdefault(
    "DATASET_URI",
    "s3://fake-bucket/fake-dataset.csv",
)
os.environ.setdefault(
    "S3_BUCKET",
    "fake-bucket",
)


from reactiva.monitoring.drift import (  # noqa: E402
    _prepare_frames,
    evaluate_data_drift,
    save_drift_outputs,
)
from reactiva.monitoring.run_drift_monitoring import (  # noqa: E402
    _build_monitoring_windows,
)


class TestPrepareFrames(unittest.TestCase):

    def test_resets_customer_id_index(self):
        reference = pd.DataFrame(
            {
                "feature_a": [1, 2, 3],
                "feature_b": [4, 5, 6],
            },
            index=[
                "CUST001",
                "CUST002",
                "CUST003",
            ],
        )

        current = pd.DataFrame(
            {
                "feature_a": [2, 3, 4],
                "feature_b": [5, 6, 7],
            },
            index=[
                "CUST010",
                "CUST011",
                "CUST012",
            ],
        )

        reference_prepared, current_prepared, columns = (
            _prepare_frames(
                reference,
                current,
            )
        )

        self.assertEqual(
            list(reference_prepared.index),
            [0, 1, 2],
        )

        self.assertEqual(
            list(current_prepared.index),
            [0, 1, 2],
        )

        self.assertEqual(
            columns,
            [
                "feature_a",
                "feature_b",
            ],
        )

    def test_excluded_columns_are_removed(self):
        reference = pd.DataFrame(
            {
                "feature": [1, 2],
                "Customer ID": ["A", "B"],
            }
        )

        current = pd.DataFrame(
            {
                "feature": [3, 4],
                "Customer ID": ["C", "D"],
            }
        )

        reference_prepared, _, columns = (
            _prepare_frames(
                reference,
                current,
                exclude_columns=[
                    "Customer ID",
                ],
            )
        )

        self.assertEqual(
            columns,
            ["feature"],
        )

        self.assertNotIn(
            "Customer ID",
            reference_prepared.columns,
        )


class TestDriftEvaluation(unittest.TestCase):

    def test_insufficient_data_is_reported(self):
        reference = pd.DataFrame(
            {
                "x": range(20),
            }
        )

        current = pd.DataFrame(
            {
                "x": range(10),
            }
        )

        summary, features, report = (
            evaluate_data_drift(
                reference,
                current,
            )
        )

        self.assertEqual(
            summary.iloc[0]["status"],
            "INSUFFICIENT_DATA",
        )

        self.assertTrue(
            features.empty
        )

        self.assertEqual(
            report["status"],
            "INSUFFICIENT_DATA",
        )

    def test_clear_distribution_shift_detects_drift(self):
        reference = pd.DataFrame(
            {
                "x": range(100),
            }
        )

        current = pd.DataFrame(
            {
                "x": range(50, 150),
            }
        )

        summary, features, _ = (
            evaluate_data_drift(
                reference,
                current,
            )
        )

        self.assertEqual(
            summary.iloc[0]["status"],
            "DRIFT",
        )

        self.assertEqual(
            int(
                summary.iloc[0][
                    "drifted_columns"
                ]
            ),
            1,
        )

        self.assertTrue(
            bool(
                features.iloc[0][
                    "drift_detected"
                ]
            )
        )

    def test_outputs_are_saved(self):
        reference = pd.DataFrame(
            {
                "x": range(100),
            }
        )

        current = pd.DataFrame(
            {
                "x": range(50, 150),
            }
        )

        summary, features, report = (
            evaluate_data_drift(
                reference,
                current,
            )
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = save_drift_outputs(
                summary_df=summary,
                features_df=features,
                report_dict=report,
                output_dir=tmp_dir,
            )

            self.assertTrue(
                Path(
                    paths["summary"]
                ).exists()
            )

            self.assertTrue(
                Path(
                    paths["features"]
                ).exists()
            )

            self.assertTrue(
                Path(
                    paths["report"]
                ).exists()
            )


class TestMonitoringWindows(unittest.TestCase):

    def test_builds_consecutive_90_day_windows(self):
        dates = pd.date_range(
            start="2026-01-01",
            end="2026-08-31",
            freq="D",
        )

        df = pd.DataFrame(
            {
                "Purchase Date": dates,
                "Customer ID": [
                    f"CUST{i:06d}"
                    for i in range(
                        len(dates)
                    )
                ],
            }
        )

        reference, current, metadata = (
            _build_monitoring_windows(
                df,
                window_days=90,
            )
        )

        self.assertEqual(
            metadata[
                "source_max_date"
            ],
            "2026-08-31",
        )

        self.assertEqual(
            metadata[
                "reference_end"
            ],
            metadata[
                "current_start"
            ],
        )

        self.assertEqual(
            metadata[
                "window_days"
            ],
            "90",
        )

        self.assertFalse(
            reference.empty
        )

        self.assertFalse(
            current.empty
        )

        self.assertLessEqual(
            reference[
                "Purchase Date"
            ].max(),
            current[
                "Purchase Date"
            ].min(),
        )

    def test_invalid_purchase_dates_are_rejected(self):
        df = pd.DataFrame(
            {
                "Purchase Date": [
                    "2026-01-01",
                    "invalid-date",
                ],
                "Customer ID": [
                    "CUST001",
                    "CUST002",
                ],
            }
        )

        with self.assertRaises(
            ValueError
        ):
            _build_monitoring_windows(
                df
            )


if __name__ == "__main__":
    unittest.main()