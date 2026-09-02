import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


# ============================================================
# TEST ENVIRONMENT
# ============================================================

os.environ.setdefault(
    "DATASET_URI",
    "s3://fake-bucket/fake-dataset.csv",
)
os.environ.setdefault(
    "S3_BUCKET",
    "fake-bucket",
)


# ============================================================
# LOAD LAMBDA MODULE
# ============================================================

LAMBDA_PATH = (
    Path(__file__).resolve().parents[1]
    / "artifacts"
    / "AwsLambda"
    / "evidently_drift"
    / "lambda.py"
)

spec = importlib.util.spec_from_file_location(
    "reactiva_evidently_lambda",
    LAMBDA_PATH,
)

evidently_lambda = (
    importlib.util.module_from_spec(
        spec
    )
)

spec.loader.exec_module(
    evidently_lambda
)


# ============================================================
# HELPERS
# ============================================================

def build_monitoring_result(
    status="OK",
    drift_share=0.2,
    drifted_columns=1,
):
    summary_df = pd.DataFrame(
        [
            {
                "run_id": "drift_test_001",
                "status": status,
                "reference_rows": 1027,
                "current_rows": 714,
                "total_columns": 5,
                "drifted_columns": drifted_columns,
                "drift_share": drift_share,
            }
        ]
    )

    features_df = pd.DataFrame(
        [
            {
                "column": "days_since_last_purchase",
                "drift_detected": True,
            },
            {
                "column": "cat_count_Accessories",
                "drift_detected": False,
            },
            {
                "column": "cat_count_Clothing",
                "drift_detected": False,
            },
            {
                "column": "cat_count_Footwear",
                "drift_detected": False,
            },
            {
                "column": "total_purchases",
                "drift_detected": False,
            },
        ]
    )

    return summary_df, features_df


# ============================================================
# LAMBDA HANDLER
# ============================================================

class TestEvidentlyLambda(
    unittest.TestCase
):

    def test_default_window_is_used(self):
        monitoring_result = (
            build_monitoring_result()
        )

        with patch.object(
            evidently_lambda,
            "run_data_drift_monitoring",
            return_value=monitoring_result,
        ) as monitoring_mock:
            response = (
                evidently_lambda.lambda_handler(
                    {},
                    None,
                )
            )

        monitoring_mock.assert_called_once_with(
            window_days=90,
        )

        self.assertEqual(
            response["status"],
            "SUCCESS",
        )

        self.assertEqual(
            response["window_days"],
            90,
        )

    def test_custom_window_is_forwarded(self):
        monitoring_result = (
            build_monitoring_result()
        )

        with patch.object(
            evidently_lambda,
            "run_data_drift_monitoring",
            return_value=monitoring_result,
        ) as monitoring_mock:
            response = (
                evidently_lambda.lambda_handler(
                    {
                        "window_days": 60,
                    },
                    None,
                )
            )

        monitoring_mock.assert_called_once_with(
            window_days=60,
        )

        self.assertEqual(
            response["window_days"],
            60,
        )

    def test_success_response_contains_monitoring_metrics(self):
        monitoring_result = (
            build_monitoring_result(
                status="OK",
                drift_share=0.2,
                drifted_columns=1,
            )
        )

        with patch.object(
            evidently_lambda,
            "run_data_drift_monitoring",
            return_value=monitoring_result,
        ):
            response = (
                evidently_lambda.lambda_handler(
                    {},
                    None,
                )
            )

        self.assertEqual(
            response["run_id"],
            "drift_test_001",
        )

        self.assertEqual(
            response["monitoring_status"],
            "OK",
        )

        self.assertEqual(
            response["reference_rows"],
            1027,
        )

        self.assertEqual(
            response["current_rows"],
            714,
        )

        self.assertEqual(
            response["total_columns"],
            5,
        )

        self.assertEqual(
            response["drifted_columns"],
            1,
        )

        self.assertEqual(
            response["drift_share"],
            0.2,
        )

        self.assertEqual(
            response["features_evaluated"],
            5,
        )

    def test_insufficient_data_can_return_null_drift_metrics(self):
        monitoring_result = (
            build_monitoring_result(
                status="INSUFFICIENT_DATA",
                drift_share=None,
                drifted_columns=None,
            )
        )

        with patch.object(
            evidently_lambda,
            "run_data_drift_monitoring",
            return_value=monitoring_result,
        ):
            response = (
                evidently_lambda.lambda_handler(
                    {},
                    None,
                )
            )

        self.assertEqual(
            response["monitoring_status"],
            "INSUFFICIENT_DATA",
        )

        self.assertIsNone(
            response["drifted_columns"]
        )

        self.assertIsNone(
            response["drift_share"]
        )

    def test_monitoring_error_is_reraised(self):
        with patch.object(
            evidently_lambda,
            "run_data_drift_monitoring",
            side_effect=RuntimeError(
                "simulated monitoring error"
            ),
        ):
            with self.assertRaises(
                RuntimeError
            ):
                evidently_lambda.lambda_handler(
                    {},
                    None,
                )


if __name__ == "__main__":
    unittest.main()