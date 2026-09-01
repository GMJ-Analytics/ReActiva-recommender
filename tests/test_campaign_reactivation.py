import unittest
from unittest.mock import patch

import pandas as pd

from reactiva.campaigns.orchestrator import (
    create_campaign_from_monthly_recommendations,
    find_reactivated_previous_campaign_purchases,
)


# ============================================================
# TEST HELPERS
# ============================================================


def build_previous_campaign(
    customer_ids,
):
    return pd.DataFrame(
        {
            "Customer ID":
                customer_ids,
        }
    )


def build_transactions(
    rows,
):
    return pd.DataFrame(
        rows,
        columns=[
            "Customer ID",
            "Purchase Date",
        ],
    )


# ============================================================
# REACTIVATION DETECTION
# ============================================================


class TestPreviousCampaignReactivation(
    unittest.TestCase
):

    def test_recent_purchase_reactivates_previous_campaign_customer(self):
        previous_campaign = (
            build_previous_campaign(
                [
                    "CUST-001",
                ]
            )
        )

        transactions = (
            build_transactions(
                [
                    {
                        "Customer ID":
                            "CUST-001",
                        "Purchase Date":
                            "2026-08-30",
                    },
                ]
            )
        )

        result = (
            find_reactivated_previous_campaign_purchases(
                transactions_df=
                    transactions,
                previous_campaign_df=
                    previous_campaign,
                reference_date=
                    "2026-09-01",
                inactivity_days=
                    270,
            )
        )

        self.assertEqual(
            len(result),
            1,
        )

        self.assertEqual(
            result.iloc[0][
                "Customer ID"
            ],
            "CUST-001",
        )

        self.assertEqual(
            pd.Timestamp(
                result.iloc[0][
                    "Purchase Date"
                ]
            ),
            pd.Timestamp(
                "2026-08-30"
            ),
        )

    def test_exact_270_day_boundary_remains_inactive(self):
        reference_date = (
            pd.Timestamp(
                "2026-09-01"
            )
        )

        cutoff_date = (
            reference_date
            - pd.Timedelta(
                days=270
            )
        )

        previous_campaign = (
            build_previous_campaign(
                [
                    "CUST-001",
                ]
            )
        )

        transactions = (
            build_transactions(
                [
                    {
                        "Customer ID":
                            "CUST-001",
                        "Purchase Date":
                            cutoff_date,
                    },
                ]
            )
        )

        result = (
            find_reactivated_previous_campaign_purchases(
                transactions_df=
                    transactions,
                previous_campaign_df=
                    previous_campaign,
                reference_date=
                    reference_date,
                inactivity_days=
                    270,
            )
        )

        self.assertTrue(
            result.empty
        )

    def test_purchase_inside_270_day_window_reactivates_customer(self):
        reference_date = (
            pd.Timestamp(
                "2026-09-01"
            )
        )

        purchase_date = (
            reference_date
            - pd.Timedelta(
                days=269
            )
        )

        previous_campaign = (
            build_previous_campaign(
                [
                    "CUST-001",
                ]
            )
        )

        transactions = (
            build_transactions(
                [
                    {
                        "Customer ID":
                            "CUST-001",
                        "Purchase Date":
                            purchase_date,
                    },
                ]
            )
        )

        result = (
            find_reactivated_previous_campaign_purchases(
                transactions_df=
                    transactions,
                previous_campaign_df=
                    previous_campaign,
                reference_date=
                    reference_date,
                inactivity_days=
                    270,
            )
        )

        self.assertEqual(
            len(result),
            1,
        )

    def test_recent_purchase_of_customer_outside_previous_campaign_is_ignored(self):
        previous_campaign = (
            build_previous_campaign(
                [
                    "CUST-001",
                ]
            )
        )

        transactions = (
            build_transactions(
                [
                    {
                        "Customer ID":
                            "CUST-001",
                        "Purchase Date":
                            "2025-01-01",
                    },
                    {
                        "Customer ID":
                            "CUST-999",
                        "Purchase Date":
                            "2026-08-31",
                    },
                ]
            )
        )

        result = (
            find_reactivated_previous_campaign_purchases(
                transactions_df=
                    transactions,
                previous_campaign_df=
                    previous_campaign,
                reference_date=
                    "2026-09-01",
                inactivity_days=
                    270,
            )
        )

        self.assertTrue(
            result.empty
        )

    def test_latest_purchase_controls_reactivation(self):
        previous_campaign = (
            build_previous_campaign(
                [
                    "CUST-001",
                ]
            )
        )

        transactions = (
            build_transactions(
                [
                    {
                        "Customer ID":
                            "CUST-001",
                        "Purchase Date":
                            "2025-01-01",
                    },
                    {
                        "Customer ID":
                            "CUST-001",
                        "Purchase Date":
                            "2026-08-20",
                    },
                ]
            )
        )

        result = (
            find_reactivated_previous_campaign_purchases(
                transactions_df=
                    transactions,
                previous_campaign_df=
                    previous_campaign,
                reference_date=
                    "2026-09-01",
                inactivity_days=
                    270,
            )
        )

        self.assertEqual(
            len(result),
            1,
        )

        self.assertEqual(
            pd.Timestamp(
                result.iloc[0][
                    "Purchase Date"
                ]
            ),
            pd.Timestamp(
                "2026-08-20"
            ),
        )

    def test_future_purchase_is_ignored(self):
        previous_campaign = (
            build_previous_campaign(
                [
                    "CUST-001",
                ]
            )
        )

        transactions = (
            build_transactions(
                [
                    {
                        "Customer ID":
                            "CUST-001",
                        "Purchase Date":
                            "2025-01-01",
                    },
                    {
                        "Customer ID":
                            "CUST-001",
                        "Purchase Date":
                            "2026-09-15",
                    },
                ]
            )
        )

        result = (
            find_reactivated_previous_campaign_purchases(
                transactions_df=
                    transactions,
                previous_campaign_df=
                    previous_campaign,
                reference_date=
                    "2026-09-01",
                inactivity_days=
                    270,
            )
        )

        self.assertTrue(
            result.empty
        )


# ============================================================
# MONTHLY ORCHESTRATOR INTEGRATION
# ============================================================


class TestMonthlyCampaignReactivationIntegration(
    unittest.TestCase
):

    def test_confirmed_reactivation_is_passed_as_new_purchase(self):
        recommendations = pd.DataFrame(
            [
                {
                    "Customer ID":
                        "CUST-002",
                }
            ]
        )

        previous_campaign = pd.DataFrame(
            [
                {
                    "Customer ID":
                        "CUST-001",
                }
            ]
        )

        transactions = (
            build_transactions(
                [
                    {
                        "Customer ID":
                            "CUST-001",
                        "Purchase Date":
                            "2026-08-30",
                    },
                    {
                        "Customer ID":
                            "CUST-002",
                        "Purchase Date":
                            "2025-01-01",
                    },
                ]
            )
        )

        fake_service_result = {
            "created":
                True,
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
            ),
            patch(
                "reactiva.campaigns.orchestrator."
                "read_csv_from_s3",
                return_value=
                    previous_campaign,
            ),
            patch(
                "reactiva.campaigns.orchestrator."
                "load_operational_transactions",
                return_value=
                    transactions,
            ),
            patch(
                "reactiva.campaigns.orchestrator."
                "create_monthly_campaign",
                return_value=
                    fake_service_result,
            ) as mocked_create_campaign,
        ):
            result = (
                create_campaign_from_monthly_recommendations(
                    reference_date=
                        "2026-09-01",
                    bucket=
                        "fake-bucket",
                    dataset_uri=
                        "fake-dataset.csv",
                )
            )

        self.assertEqual(
            result[
                "campaign_id"
            ],
            "REACTIVA-2026-09",
        )

        mocked_create_campaign.assert_called_once()

        new_purchases_df = (
            mocked_create_campaign
            .call_args
            .kwargs[
                "new_purchases_df"
            ]
        )

        self.assertEqual(
            len(
                new_purchases_df
            ),
            1,
        )

        self.assertEqual(
            new_purchases_df.iloc[0][
                "Customer ID"
            ],
            "CUST-001",
        )

        self.assertEqual(
            pd.Timestamp(
                new_purchases_df.iloc[0][
                    "Purchase Date"
                ]
            ),
            pd.Timestamp(
                "2026-08-30"
            ),
        )


if __name__ == "__main__":
    unittest.main()