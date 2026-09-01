import unittest
from unittest.mock import patch

import pandas as pd

from reactiva.campaigns.orchestrator import (
    INACTIVITY_DAYS,
    TOP_RECOMMENDATIONS,
    MONTHLY_RECOMMENDATION_REQUIRED_COLUMNS,
    build_monthly_recommendation_key,
    create_campaign_from_monthly_recommendations,
    generate_monthly_recommendations,
    load_canonical_transactions,
    load_monthly_recommendations,
    normalize_reference_date,
    validate_monthly_recommendations,
)


# ============================================================
# TEST HELPERS
# ============================================================


def build_canonical_dataframe():
    """
    Creates a minimal canonical transaction dataset.
    """
    return pd.DataFrame(
        [
            {
                "Transaction ID": "TX-001",
                "Customer ID": "CUST-001",
                "Purchase Date": "2025-01-01",
                "Category": "Clothing",
                "Item Purchased": "Shirt",
                "Customer Full Name": "Cliente Uno",
                "Customer Email": "uno@example.com",
            },
            {
                "Transaction ID": "TX-002",
                "Customer ID": "CUST-002",
                "Purchase Date": "2025-02-01",
                "Category": "Footwear",
                "Item Purchased": "Sneakers",
                "Customer Full Name": "Cliente Dos",
                "Customer Email": "dos@example.com",
            },
            {
                "Transaction ID": "TX-003",
                "Customer ID": "CUST-003",
                "Purchase Date": "2026-08-30",
                "Category": "Accessories",
                "Item Purchased": "Backpack",
                "Customer Full Name": "Cliente Tres",
                "Customer Email": "tres@example.com",
            },
        ]
    )


def build_recommendation_dataframe():
    """
    Creates the output expected from the GBoost recommender
    before monthly metadata is added.
    """
    return pd.DataFrame(
        [
            {
                "Customer Name": "Cliente Uno",
                "Customer Email": "uno@example.com",
                "Customer ID": "CUST-001",
                "Location": "Delhi",
                "Current Season": "Monsoon",
                "Recommendations": [
                    "Shirt",
                    "Sneakers",
                    "Backpack",
                ],
                "Date": pd.Timestamp(
                    "2026-09-01 00:10:00"
                ),
            }
        ]
    )


def build_monthly_recommendations(
    campaign_month="2026-09",
    reference_date="2026-09-01",
):
    """
    Creates a complete monthly recommendation output.
    """
    recommendations = (
        build_recommendation_dataframe()
    )

    recommendations["Campaign Month"] = (
        campaign_month
    )

    recommendations["Reference Date"] = (
        reference_date
    )

    return recommendations[
        MONTHLY_RECOMMENDATION_REQUIRED_COLUMNS
    ].copy()


# ============================================================
# REFERENCE DATE / KEY
# ============================================================


class TestMonthlyReferenceDate(
    unittest.TestCase
):

    def test_reference_date_is_normalized(self):
        result = normalize_reference_date(
            "2026-09-01 15:45:22"
        )

        self.assertEqual(
            result,
            pd.Timestamp("2026-09-01"),
        )

    def test_monthly_key_uses_requested_month(self):
        key = build_monthly_recommendation_key(
            "2026-09-15"
        )

        self.assertEqual(
            key,
            (
                "recommender/monthly/"
                "recommendations_2026-09.csv"
            ),
        )


# ============================================================
# CANONICAL TRANSACTION DATASET
# ============================================================


class TestCanonicalTransactions(
    unittest.TestCase
):

    def test_canonical_dataset_is_loaded_and_dates_are_parsed(self):
        canonical = (
            build_canonical_dataframe()
        )

        with patch(
            "reactiva.campaigns.orchestrator."
            "pd.read_csv",
            return_value=
                canonical.copy(),
        ) as read_mock:
            result = (
                load_canonical_transactions(
                    dataset_uri=
                        "fake-dataset.csv"
                )
            )

        read_mock.assert_called_once_with(
            "fake-dataset.csv"
        )

        self.assertEqual(
            len(result),
            3,
        )

        self.assertTrue(
            pd.api.types.is_datetime64_any_dtype(
                result["Purchase Date"]
            )
        )

        self.assertEqual(
            set(
                result["Transaction ID"]
            ),
            {
                "TX-001",
                "TX-002",
                "TX-003",
            },
        )

    def test_missing_required_column_is_rejected(self):
        canonical = (
            build_canonical_dataframe()
            .drop(
                columns=[
                    "Item Purchased"
                ]
            )
        )

        with patch(
            "reactiva.campaigns.orchestrator."
            "pd.read_csv",
            return_value=
                canonical,
        ):
            with self.assertRaises(
                ValueError
            ):
                load_canonical_transactions(
                    dataset_uri=
                        "fake-dataset.csv"
                )

    def test_invalid_purchase_date_is_rejected(self):
        canonical = (
            build_canonical_dataframe()
        )

        canonical.loc[
            2,
            "Purchase Date",
        ] = "not-a-date"

        with patch(
            "reactiva.campaigns.orchestrator."
            "pd.read_csv",
            return_value=
                canonical,
        ):
            with self.assertRaises(
                ValueError
            ):
                load_canonical_transactions(
                    dataset_uri=
                        "fake-dataset.csv"
                )

    def test_dataset_uri_is_required(self):
        with self.assertRaises(
            ValueError
        ):
            load_canonical_transactions(
                dataset_uri=""
            )


# ============================================================
# MONTHLY RECOMMENDATION VALIDATION
# ============================================================


class TestMonthlyRecommendationValidation(
    unittest.TestCase
):

    def test_valid_current_month_recommendations_pass(self):
        recommendations = (
            build_monthly_recommendations()
        )

        validate_monthly_recommendations(
            recommendations_df=recommendations,
            reference_date="2026-09-01",
        )

    def test_previous_month_recommendations_are_rejected(self):
        recommendations = (
            build_monthly_recommendations(
                campaign_month="2026-08",
                reference_date="2026-08-01",
            )
        )

        with self.assertRaises(
            RuntimeError
        ):
            validate_monthly_recommendations(
                recommendations_df=recommendations,
                reference_date="2026-09-01",
            )

    def test_output_without_recommendations_is_rejected(self):
        recommendations = (
            build_monthly_recommendations()
        )

        recommendations[
            "Recommendations"
        ] = "[]"

        with self.assertRaises(
            RuntimeError
        ):
            validate_monthly_recommendations(
                recommendations_df=recommendations,
                reference_date="2026-09-01",
            )


# ============================================================
# MONTHLY GBOOST ORCHESTRATION
# ============================================================


class TestMonthlyRecommendationGeneration(
    unittest.TestCase
):

    def test_gboost_is_called_with_monthly_business_parameters(self):
        operational_df = (
            build_canonical_dataframe()
        )

        recommendations_df = (
            build_recommendation_dataframe()
        )

        written = {}

        def fake_write(
            df,
            bucket,
            key,
            s3_client=None,
        ):
            written["df"] = (
                df.copy()
            )

            written["bucket"] = (
                bucket
            )

            written["key"] = (
                key
            )

        def fake_read(
            bucket,
            key,
            expected_columns=None,
            s3_client=None,
        ):
            return (
                written["df"].copy()
            )

        with (
            patch(
                "reactiva.campaigns.orchestrator."
                "load_operational_transactions",
                return_value=
                    operational_df,
            ),
            patch(
                "reactiva.campaigns.orchestrator."
                "recommend_user_based_inactive_customers",
                return_value=
                    recommendations_df,
            ) as recommender_mock,
            patch(
                "reactiva.campaigns.orchestrator."
                "write_csv_to_s3",
                side_effect=
                    fake_write,
            ),
            patch(
                "reactiva.campaigns.orchestrator."
                "read_csv_from_s3",
                side_effect=
                    fake_read,
            ),
        ):
            result = (
                generate_monthly_recommendations(
                    reference_date=
                        "2026-09-01",
                    bucket=
                        "fake-bucket",
                    dataset_uri=
                        "fake-dataset.csv",
                )
            )

        recommender_mock.assert_called_once()

        args, kwargs = (
            recommender_mock.call_args
        )

        pd.testing.assert_frame_equal(
            args[0],
            operational_df,
        )

        self.assertEqual(
            kwargs["k"],
            TOP_RECOMMENDATIONS,
        )

        self.assertEqual(
            kwargs["inactivity_days"],
            INACTIVITY_DAYS,
        )

        self.assertFalse(
            kwargs["persist_predictions"]
        )

        self.assertEqual(
            kwargs["reference_date"],
            pd.Timestamp("2026-09-01"),
        )

        self.assertEqual(
            written["key"],
            (
                "recommender/monthly/"
                "recommendations_2026-09.csv"
            ),
        )

        self.assertEqual(
            set(
                result[
                    "recommendations"
                ][
                    "Campaign Month"
                ]
            ),
            {
                "2026-09"
            },
        )

        self.assertEqual(
            set(
                result[
                    "recommendations"
                ][
                    "Reference Date"
                ]
            ),
            {
                "2026-09-01"
            },
        )

    def test_empty_gboost_result_aborts_monthly_recommendations(self):
        operational_df = (
            build_canonical_dataframe()
        )

        with (
            patch(
                "reactiva.campaigns.orchestrator."
                "load_operational_transactions",
                return_value=
                    operational_df,
            ),
            patch(
                "reactiva.campaigns.orchestrator."
                "recommend_user_based_inactive_customers",
                return_value=
                    pd.DataFrame(),
            ),
        ):
            with self.assertRaises(
                RuntimeError
            ):
                generate_monthly_recommendations(
                    reference_date=
                        "2026-09-01",
                    bucket=
                        "fake-bucket",
                    dataset_uri=
                        "fake-dataset.csv",
                )


# ============================================================
# CURRENT MONTH RECOMMENDATIONS
# ============================================================


class TestCurrentMonthlyRecommendations(
    unittest.TestCase
):

    def test_current_month_recommendations_are_loaded_from_exact_key(self):
        recommendations = (
            build_monthly_recommendations()
        )

        requested = {}

        def fake_read(
            bucket,
            key,
            expected_columns=None,
            s3_client=None,
        ):
            requested["key"] = key

            return (
                recommendations.copy()
            )

        with patch(
            "reactiva.campaigns.orchestrator."
            "read_csv_from_s3",
            side_effect=fake_read,
        ):
            result = (
                load_monthly_recommendations(
                    reference_date=
                        "2026-09-15",
                    bucket=
                        "fake-bucket",
                )
            )

        self.assertEqual(
            requested["key"],
            (
                "recommender/monthly/"
                "recommendations_2026-09.csv"
            ),
        )

        pd.testing.assert_frame_equal(
            result,
            recommendations,
        )

    def test_missing_current_month_recommendations_abort(self):
        def fake_read(
            bucket,
            key,
            expected_columns=None,
            s3_client=None,
        ):
            return pd.DataFrame(
                columns=(
                    expected_columns
                    or []
                )
            )

        with patch(
            "reactiva.campaigns.orchestrator."
            "read_csv_from_s3",
            side_effect=fake_read,
        ):
            with self.assertRaises(
                RuntimeError
            ):
                load_monthly_recommendations(
                    reference_date=
                        "2026-09-01",
                    bucket=
                        "fake-bucket",
                )

    def test_previous_month_recommendations_cannot_be_reused(self):
        august_recommendations = (
            build_monthly_recommendations(
                campaign_month=
                    "2026-08",
                reference_date=
                    "2026-08-01",
            )
        )

        with patch(
            "reactiva.campaigns.orchestrator."
            "read_csv_from_s3",
            return_value=
                august_recommendations,
        ):
            with self.assertRaises(
                RuntimeError
            ):
                load_monthly_recommendations(
                    reference_date=
                        "2026-09-01",
                    bucket=
                        "fake-bucket",
                )


# ============================================================
# CAMPAIGN CREATION FROM MONTHLY RECOMMENDATIONS
# ============================================================


class TestCampaignFromMonthlyRecommendations(
    unittest.TestCase
):

    def test_campaign_uses_only_loaded_current_month_recommendations(self):
        recommendations = (
            build_monthly_recommendations()
        )

        expected_result = {
            "created": True,
            "campaign_id":
                "REACTIVA-2026-09",
            "campaign":
                pd.DataFrame(),
            "history":
                pd.DataFrame(),
            "customer_status":
                pd.DataFrame(),
            "exclusions":
                pd.DataFrame(),
        }

        with (
            patch(
                "reactiva.campaigns.orchestrator."
                "load_monthly_recommendations",
                return_value=
                    recommendations,
            ) as load_mock,
            patch(
                "reactiva.campaigns.orchestrator."
                "read_csv_from_s3",
                return_value=
                    pd.DataFrame(
                        columns=[
                            "Customer ID",
                        ]
                    ),
            ),
            patch(
                "reactiva.campaigns.orchestrator."
                "load_operational_transactions",
                return_value=
                    pd.DataFrame(
                        columns=[
                            "Customer ID",
                            "Purchase Date",
                        ]
                    ),
            ),
            patch(
                "reactiva.campaigns.orchestrator."
                "create_monthly_campaign",
                return_value=
                    expected_result,
            ) as campaign_mock,
        ):
            result = (
                create_campaign_from_monthly_recommendations(
                    reference_date=
                        "2026-09-01",
                    bucket=
                        "fake-bucket",
                )
            )

        load_mock.assert_called_once_with(
            reference_date=
                pd.Timestamp("2026-09-01"),
            bucket=
                "fake-bucket",
            s3_client=None,
        )

        campaign_mock.assert_called_once()

        _, kwargs = (
            campaign_mock.call_args
        )

        pd.testing.assert_frame_equal(
            kwargs[
                "recommendations_df"
            ],
            recommendations,
        )

        self.assertEqual(
            kwargs[
                "campaign_date"
            ],
            pd.Timestamp("2026-09-01"),
        )

        self.assertEqual(
            kwargs["bucket"],
            "fake-bucket",
        )

        new_purchases_df = (
            kwargs[
                "new_purchases_df"
            ]
        )

        self.assertTrue(
            new_purchases_df.empty
        )

        self.assertEqual(
            list(
                new_purchases_df.columns
            ),
            [
                "Customer ID",
                "Purchase Date",
            ],
        )

        self.assertEqual(
            result,
            expected_result,
        )


if __name__ == "__main__":
    unittest.main()