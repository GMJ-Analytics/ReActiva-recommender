import unittest
from unittest.mock import patch

import pandas as pd

from reactiva.campaigns.campaign import (
    CAMPAIGN_COLUMNS,
    CUSTOMER_STATUS_COLUMNS,
    STATUS_PENDING,
    STATUS_SENT,
    build_monthly_campaign,
)
from reactiva.campaigns.service import (
    create_monthly_campaign,
)
from reactiva.campaigns.storage import (
    CAMPAIGN_ACTIVE_KEY,
    CAMPAIGN_HISTORY_KEY,
    CUSTOMER_CAMPAIGN_STATUS_KEY,
)


# ============================================================
# TEST HELPERS
# ============================================================


def build_recommendations_dataframe(
    customer_ids=None,
):
    """
    Creates a valid recommendation matrix for service tests.
    """
    if customer_ids is None:
        customer_ids = [
            "CUST-001",
            "CUST-002",
        ]

    rows = []

    for index, customer_id in enumerate(
        customer_ids,
        start=1,
    ):
        rows.append(
            {
                "Customer ID":
                    customer_id,
                "Customer Name":
                    f"Cliente {index}",
                "Customer Email":
                    f"cliente{index}@example.com",
                "Recommendations": [
                    "Shirt",
                    "Sneakers",
                    "Backpack",
                ],
                "Date":
                    "2026-09-01 00:10:00",
            }
        )

    return pd.DataFrame(
        rows
    )


def build_customer_status_dataframe(
    rows=None,
):
    """
    Builds a canonical customer status DataFrame.
    """
    if rows is None:
        return pd.DataFrame(
            columns=CUSTOMER_STATUS_COLUMNS
        )

    return pd.DataFrame(
        rows,
        columns=CUSTOMER_STATUS_COLUMNS,
    )


def build_status_row(
    customer_id,
    opt_out=False,
    campaigns_in_cycle=0,
    skip_next=False,
    last_campaign_month=None,
):
    return {
        "Customer ID":
            customer_id,
        "Opt Out":
            opt_out,
        "Opt Out Date":
            None,
        "Campaigns In Current Cycle":
            campaigns_in_cycle,
        "Skip Next Campaign":
            skip_next,
        "Last Reactivation Date":
            None,
        "Last Campaign Month":
            last_campaign_month,
    }


def build_existing_campaign(
    campaign_date,
    customer_ids=None,
):
    """
    Builds a valid campaign using the production campaign builder.
    """
    recommendations = (
        build_recommendations_dataframe(
            customer_ids=customer_ids
        )
    )

    campaign_df, _ = (
        build_monthly_campaign(
            recommendations_df=
                recommendations,
            campaign_date=
                campaign_date,
        )
    )

    return campaign_df


# ============================================================
# IN-MEMORY S3
# ============================================================


class InMemoryS3:
    """
    Minimal fake persistence layer used to replace
    read_csv_from_s3/write_csv_to_s3 during tests.
    """

    def __init__(self):
        self.files = {}
        self.writes = []

    def set_file(
        self,
        key,
        dataframe,
    ):
        self.files[key] = (
            dataframe.copy()
        )

    def read_csv_from_s3(
        self,
        bucket,
        key,
        expected_columns=None,
        s3_client=None,
    ):
        if key not in self.files:
            if expected_columns is None:
                return pd.DataFrame()

            return pd.DataFrame(
                columns=expected_columns
            )

        dataframe = (
            self.files[key].copy()
        )

        if expected_columns is not None:
            missing_columns = [
                column
                for column
                in expected_columns
                if column
                not in dataframe.columns
            ]

            if missing_columns:
                raise ValueError(
                    "Missing expected columns: "
                    f"{missing_columns}"
                )

        return dataframe

    def write_csv_to_s3(
        self,
        df,
        bucket,
        key,
        s3_client=None,
    ):
        self.writes.append(
            key
        )

        self.files[key] = (
            df.copy()
        )


# ============================================================
# SERVICE TESTS
# ============================================================


class TestCampaignService(
    unittest.TestCase
):

    def setUp(self):
        self.bucket = (
            "fake-reactiva-bucket"
        )

        self.storage = (
            InMemoryS3()
        )

    def _run_service(
        self,
        recommendations_df,
        campaign_date,
        new_purchases_df=None,
    ):
        """
        Runs create_monthly_campaign with the in-memory S3.
        """
        with (
            patch(
                "reactiva.campaigns.service."
                "read_csv_from_s3",
                side_effect=
                    self.storage
                    .read_csv_from_s3,
            ),
            patch(
                "reactiva.campaigns.service."
                "write_csv_to_s3",
                side_effect=
                    self.storage
                    .write_csv_to_s3,
            ),
        ):
            return create_monthly_campaign(
                recommendations_df=
                    recommendations_df,
                bucket=
                    self.bucket,
                campaign_date=
                    campaign_date,
                new_purchases_df=
                    new_purchases_df,
            )

    # --------------------------------------------------------
    # FIRST CAMPAIGN
    # --------------------------------------------------------

    def test_first_campaign_is_created_and_persisted(self):
        recommendations_df = (
            build_recommendations_dataframe()
        )

        result = self._run_service(
            recommendations_df=
                recommendations_df,
            campaign_date=
                "2026-09-01",
        )

        self.assertTrue(
            result["created"]
        )

        self.assertEqual(
            result["campaign_id"],
            "REACTIVA-2026-09",
        )

        self.assertIn(
            CAMPAIGN_ACTIVE_KEY,
            self.storage.files,
        )

        active = self.storage.files[
            CAMPAIGN_ACTIVE_KEY
        ]

        self.assertEqual(
            len(active),
            2,
        )

        self.assertEqual(
            set(active["Status"]),
            {
                STATUS_PENDING
            },
        )

        self.assertIn(
            CUSTOMER_CAMPAIGN_STATUS_KEY,
            self.storage.files,
        )

        status_df = self.storage.files[
            CUSTOMER_CAMPAIGN_STATUS_KEY
        ]

        self.assertEqual(
            set(
                status_df[
                    "Customer ID"
                ]
            ),
            {
                "CUST-001",
                "CUST-002",
            },
        )

    # --------------------------------------------------------
    # IDEMPOTENCY
    # --------------------------------------------------------

    def test_same_month_campaign_is_reused_without_recreation(self):
        existing_campaign = (
            build_existing_campaign(
                campaign_date=
                    "2026-09-01"
            )
        )

        self.storage.set_file(
            CAMPAIGN_ACTIVE_KEY,
            existing_campaign,
        )

        recommendations_df = (
            build_recommendations_dataframe(
                customer_ids=[
                    "CUST-999"
                ]
            )
        )

        result = self._run_service(
            recommendations_df=
                recommendations_df,
            campaign_date=
                "2026-09-20",
        )

        self.assertFalse(
            result["created"]
        )

        self.assertEqual(
            result["campaign_id"],
            "REACTIVA-2026-09",
        )

        pd.testing.assert_frame_equal(
            result["campaign"],
            existing_campaign,
        )

        pd.testing.assert_frame_equal(
            self.storage.files[
                CAMPAIGN_ACTIVE_KEY
            ],
            existing_campaign,
        )

    # --------------------------------------------------------
    # ARCHIVE PREVIOUS CAMPAIGN
    # --------------------------------------------------------

    def test_previous_campaign_is_archived_before_new_active(self):
        august_campaign = (
            build_existing_campaign(
                campaign_date=
                    "2026-08-01"
            )
        )

        august_campaign.loc[
            :,
            "Status",
        ] = STATUS_SENT

        self.storage.set_file(
            CAMPAIGN_ACTIVE_KEY,
            august_campaign,
        )

        recommendations_df = (
            build_recommendations_dataframe()
        )

        result = self._run_service(
            recommendations_df=
                recommendations_df,
            campaign_date=
                "2026-09-01",
        )

        self.assertTrue(
            result["created"]
        )

        history = self.storage.files[
            CAMPAIGN_HISTORY_KEY
        ]

        self.assertEqual(
            set(
                history[
                    "Campaign ID"
                ]
            ),
            {
                "REACTIVA-2026-08"
            },
        )

        active = self.storage.files[
            CAMPAIGN_ACTIVE_KEY
        ]

        self.assertEqual(
            set(
                active[
                    "Campaign ID"
                ]
            ),
            {
                "REACTIVA-2026-09"
            },
        )

        history_write_index = (
            self.storage.writes.index(
                CAMPAIGN_HISTORY_KEY
            )
        )

        active_write_index = (
            self.storage.writes.index(
                CAMPAIGN_ACTIVE_KEY
            )
        )

        self.assertLess(
            history_write_index,
            active_write_index,
        )

    # --------------------------------------------------------
    # ARCHIVE FAILURE SAFETY
    # --------------------------------------------------------

    def test_archive_failure_preserves_previous_active_campaign(self):
        august_campaign = (
            build_existing_campaign(
                campaign_date=
                    "2026-08-01"
            )
        )

        self.storage.set_file(
            CAMPAIGN_ACTIVE_KEY,
            august_campaign,
        )

        recommendations_df = (
            build_recommendations_dataframe()
        )

        original_write = (
            self.storage
            .write_csv_to_s3
        )

        def failing_write(
            df,
            bucket,
            key,
            s3_client=None,
        ):
            if key == CAMPAIGN_HISTORY_KEY:
                raise RuntimeError(
                    "Simulated history archive failure"
                )

            return original_write(
                df=df,
                bucket=bucket,
                key=key,
                s3_client=s3_client,
            )

        with (
            patch(
                "reactiva.campaigns.service."
                "read_csv_from_s3",
                side_effect=
                    self.storage
                    .read_csv_from_s3,
            ),
            patch(
                "reactiva.campaigns.service."
                "write_csv_to_s3",
                side_effect=
                    failing_write,
            ),
        ):
            with self.assertRaises(
                RuntimeError
            ):
                create_monthly_campaign(
                    recommendations_df=
                        recommendations_df,
                    bucket=
                        self.bucket,
                    campaign_date=
                        "2026-09-01",
                )

        self.assertIn(
            CAMPAIGN_ACTIVE_KEY,
            self.storage.files,
        )

        pd.testing.assert_frame_equal(
            self.storage.files[
                CAMPAIGN_ACTIVE_KEY
            ],
            august_campaign,
        )

        self.assertNotIn(
            CAMPAIGN_HISTORY_KEY,
            self.storage.files,
        )

    # --------------------------------------------------------
    # HISTORY DEDUPLICATION
    # --------------------------------------------------------

    def test_history_does_not_duplicate_same_campaign_customer(self):
        august_campaign = (
            build_existing_campaign(
                campaign_date=
                    "2026-08-01"
            )
        )

        august_campaign.loc[
            :,
            "Status",
        ] = STATUS_SENT

        self.storage.set_file(
            CAMPAIGN_ACTIVE_KEY,
            august_campaign,
        )

        self.storage.set_file(
            CAMPAIGN_HISTORY_KEY,
            august_campaign.copy(),
        )

        recommendations_df = (
            build_recommendations_dataframe()
        )

        self._run_service(
            recommendations_df=
                recommendations_df,
            campaign_date=
                "2026-09-01",
        )

        history = self.storage.files[
            CAMPAIGN_HISTORY_KEY
        ]

        duplicates = (
            history.duplicated(
                subset=[
                    "Campaign ID",
                    "Customer ID",
                ]
            )
        )

        self.assertFalse(
            duplicates.any()
        )

        self.assertEqual(
            len(history),
            len(august_campaign),
        )

    # --------------------------------------------------------
    # CAMPAIGN OUTCOMES
    # --------------------------------------------------------

    def test_previous_sent_campaign_updates_customer_cycle(self):
        august_campaign = (
            build_existing_campaign(
                campaign_date=
                    "2026-08-01",
                customer_ids=[
                    "CUST-001"
                ],
            )
        )

        august_campaign.loc[
            :,
            "Status",
        ] = STATUS_SENT

        self.storage.set_file(
            CAMPAIGN_ACTIVE_KEY,
            august_campaign,
        )

        recommendations_df = (
            build_recommendations_dataframe(
                customer_ids=[
                    "CUST-001"
                ]
            )
        )

        result = self._run_service(
            recommendations_df=
                recommendations_df,
            campaign_date=
                "2026-09-01",
        )

        status_df = result[
            "customer_status"
        ]

        customer = (
            status_df[
                status_df[
                    "Customer ID"
                ]
                == "CUST-001"
            ]
            .iloc[0]
        )

        self.assertEqual(
            int(
                customer[
                    "Campaigns In Current Cycle"
                ]
            ),
            1,
        )

        self.assertEqual(
            customer[
                "Last Campaign Month"
            ],
            "2026-08",
        )

    # --------------------------------------------------------
    # PURCHASE RESET
    # --------------------------------------------------------

    def test_new_purchase_resets_existing_campaign_state(self):
        initial_status = (
            build_customer_status_dataframe(
                [
                    build_status_row(
                        customer_id=
                            "CUST-001",
                        opt_out=True,
                        campaigns_in_cycle=3,
                        skip_next=True,
                        last_campaign_month=
                            "2026-08",
                    )
                ]
            )
        )

        self.storage.set_file(
            CUSTOMER_CAMPAIGN_STATUS_KEY,
            initial_status,
        )

        recommendations_df = (
            build_recommendations_dataframe(
                customer_ids=[
                    "CUST-001"
                ]
            )
        )

        purchases_df = pd.DataFrame(
            [
                {
                    "Customer ID":
                        "CUST-001",
                    "Purchase Date":
                        "2026-08-30",
                }
            ]
        )

        result = self._run_service(
            recommendations_df=
                recommendations_df,
            campaign_date=
                "2026-09-01",
            new_purchases_df=
                purchases_df,
        )

        status_df = result[
            "customer_status"
        ]

        customer = (
            status_df[
                status_df[
                    "Customer ID"
                ]
                == "CUST-001"
            ]
            .iloc[0]
        )

        self.assertFalse(
            bool(
                customer[
                    "Opt Out"
                ]
            )
        )

        self.assertFalse(
            bool(
                customer[
                    "Skip Next Campaign"
                ]
            )
        )

        self.assertEqual(
            int(
                customer[
                    "Campaigns In Current Cycle"
                ]
            ),
            0,
        )

        self.assertEqual(
            customer[
                "Last Reactivation Date"
            ],
            "2026-08-30T00:00:00",
        )

    # --------------------------------------------------------
    # PAUSE CONSUMPTION
    # --------------------------------------------------------

    def test_pause_is_consumed_only_after_new_campaign_is_created(self):
        initial_status = (
            build_customer_status_dataframe(
                [
                    build_status_row(
                        customer_id=
                            "CUST-001",
                        campaigns_in_cycle=3,
                        skip_next=True,
                        last_campaign_month=
                            "2026-08",
                    ),
                    build_status_row(
                        customer_id=
                            "CUST-002",
                        campaigns_in_cycle=0,
                        skip_next=False,
                    ),
                ]
            )
        )

        self.storage.set_file(
            CUSTOMER_CAMPAIGN_STATUS_KEY,
            initial_status,
        )

        recommendations_df = (
            build_recommendations_dataframe(
                customer_ids=[
                    "CUST-001",
                    "CUST-002",
                ]
            )
        )

        result = self._run_service(
            recommendations_df=
                recommendations_df,
            campaign_date=
                "2026-09-01",
        )

        campaign_df = result[
            "campaign"
        ]

        self.assertEqual(
            set(
                campaign_df[
                    "Customer ID"
                ]
            ),
            {
                "CUST-002"
            },
        )

        exclusions = result[
            "exclusions"
        ]

        paused_exclusion = (
            exclusions[
                exclusions[
                    "Customer ID"
                ]
                == "CUST-001"
            ]
            .iloc[0]
        )

        self.assertEqual(
            paused_exclusion[
                "Reason"
            ],
            "PAUSED_AFTER_3_SENT",
        )

        status_df = result[
            "customer_status"
        ]

        paused_customer = (
            status_df[
                status_df[
                    "Customer ID"
                ]
                == "CUST-001"
            ]
            .iloc[0]
        )

        self.assertEqual(
            int(
                paused_customer[
                    "Campaigns In Current Cycle"
                ]
            ),
            0,
        )

        self.assertFalse(
            bool(
                paused_customer[
                    "Skip Next Campaign"
                ]
            )
        )


if __name__ == "__main__":
    unittest.main()