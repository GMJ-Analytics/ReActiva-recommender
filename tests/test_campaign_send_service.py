import unittest
from unittest.mock import patch

import pandas as pd
from botocore.exceptions import ClientError

from reactiva.campaigns.campaign import (
    CAMPAIGN_COLUMNS,
    STATUS_CANCELLED_REACTIVATED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SENT,
)
from reactiva.campaigns.send_service import (
    build_send_report_key,
    process_campaign_send_run,
)
from reactiva.campaigns.storage import (
    CAMPAIGN_ACTIVE_KEY,
)


# ============================================================
# TEST HELPERS
# ============================================================


def build_campaign_dataframe(
    scheduled_day=1,
    status=STATUS_PENDING,
    retry_count=0,
    last_attempt_at=None,
    customer_email="cliente@example.com",
):
    """
    Creates one valid active campaign row.
    """
    row = {
        column: None
        for column in CAMPAIGN_COLUMNS
    }

    row.update(
        {
            "Campaign ID":
                "REACTIVA-2026-09",
            "Campaign Month":
                "2026-09",
            "Customer ID":
                "CUST-001",
            "Customer Full Name":
                "Cliente Prueba",
            "Customer Email":
                customer_email,
            "Recommendation 1":
                "Shirt",
            "Recommendation 2":
                "Sneakers",
            "Recommendation 3":
                "Backpack",
            "Discount Percent":
                10,
            "Coupon Code":
                "ABC123",
            "Scheduled Day":
                scheduled_day,
            "Status":
                status,
            "Retry Count":
                retry_count,
            "Last Attempt At":
                last_attempt_at,
            "Sent At":
                None,
            "Reactivated At":
                None,
            "Coupon Status":
                "ACTIVE",
            "Coupon Redeemed At":
                None,
            "Coupon Transaction ID":
                None,
            "Last Error":
                None,
        }
    )

    return pd.DataFrame(
        [row],
        columns=CAMPAIGN_COLUMNS,
    )


def build_transactions_dataframe(
    purchase_date="2025-01-01",
):
    """
    Creates the minimal operational transaction view
    required by the send process.
    """
    return pd.DataFrame(
        [
            {
                "Customer ID":
                    "CUST-001",
                "Purchase Date":
                    purchase_date,
            }
        ]
    )


# ============================================================
# FAKE SES CLIENTS
# ============================================================


class SuccessfulSESClient:

    def __init__(self):
        self.calls = []

    def send_email(
        self,
        **kwargs,
    ):
        self.calls.append(
            kwargs
        )

        return {
            "MessageId":
                "fake-message-id-001"
        }


class FailingSESClient:

    def __init__(self):
        self.calls = 0

    def send_email(
        self,
        **kwargs,
    ):
        self.calls += 1

        raise ClientError(
            {
                "Error": {
                    "Code":
                        "ServiceUnavailable",
                    "Message":
                        "Temporary SES failure",
                }
            },
            "SendEmail",
        )


# ============================================================
# IN-MEMORY S3
# ============================================================


class InMemoryS3:

    def __init__(
        self,
        active_campaign,
    ):
        self.files = {
            CAMPAIGN_ACTIVE_KEY:
                active_campaign.copy()
        }

        self.writes = []

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
                if column not in dataframe.columns
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
# REPORT KEY
# ============================================================


class TestSendReportKey(
    unittest.TestCase
):

    def test_report_key_contains_campaign_and_execution_time(self):
        key = build_send_report_key(
            campaign_id=
                "REACTIVA-2026-09",
            execution_time=
                "2026-09-01 09:00:00",
        )

        self.assertEqual(
            key,
            (
                "campaigns/reports/send_events/"
                "REACTIVA-2026-09_"
                "2026-09-01T090000.csv"
            ),
        )


# ============================================================
# SEND SERVICE
# ============================================================


class TestCampaignSendService(
    unittest.TestCase
):

    def _run_service(
        self,
        active_campaign,
        transactions_df,
        execution_time,
        ses_client,
    ):
        """
        Runs the production send service with in-memory
        persistence and fake SES.
        """
        storage = InMemoryS3(
            active_campaign
        )

        with (
            patch(
                "reactiva.campaigns.send_service."
                "read_csv_from_s3",
                side_effect=
                    storage.read_csv_from_s3,
            ),
            patch(
                "reactiva.campaigns.send_service."
                "write_csv_to_s3",
                side_effect=
                    storage.write_csv_to_s3,
            ),
            patch(
                "reactiva.campaigns.send_service."
                "load_operational_transactions",
                return_value=
                    transactions_df,
            ),
        ):
            result = (
                process_campaign_send_run(
                    sender_email=
                        "reactiva@example.com",
                    execution_time=
                        execution_time,
                    bucket=
                        "fake-bucket",
                    dataset_uri=
                        "fake-dataset.csv",
                    ses_client=
                        ses_client,
                )
            )

        return (
            result,
            storage,
        )

    # --------------------------------------------------------
    # SUCCESSFUL SEND
    # --------------------------------------------------------

    def test_due_inactive_customer_is_sent_and_persisted(self):
        active_campaign = (
            build_campaign_dataframe(
                scheduled_day=1
            )
        )

        transactions = (
            build_transactions_dataframe(
                purchase_date=
                    "2025-01-01"
            )
        )

        ses_client = (
            SuccessfulSESClient()
        )

        result, storage = (
            self._run_service(
                active_campaign=
                    active_campaign,
                transactions_df=
                    transactions,
                execution_time=
                    "2026-09-01 09:00:00",
                ses_client=
                    ses_client,
            )
        )

        self.assertEqual(
            result["processed"],
            1,
        )

        self.assertEqual(
            result["sent"],
            1,
        )

        self.assertEqual(
            result["failed"],
            0,
        )

        self.assertEqual(
            result[
                "cancelled_reactivated"
            ],
            0,
        )

        self.assertEqual(
            len(
                ses_client.calls
            ),
            1,
        )

        persisted_campaign = (
            storage.files[
                CAMPAIGN_ACTIVE_KEY
            ]
        )

        self.assertEqual(
            persisted_campaign.iloc[0][
                "Status"
            ],
            STATUS_SENT,
        )

        self.assertIsNotNone(
            persisted_campaign.iloc[0][
                "Sent At"
            ]
        )

        self.assertIsNotNone(
            result["report_key"]
        )

        self.assertIn(
            result["report_key"],
            storage.files,
        )

    # --------------------------------------------------------
    # NO CUSTOMER DUE
    # --------------------------------------------------------

    def test_no_due_customer_does_not_rewrite_campaign(self):
        active_campaign = (
            build_campaign_dataframe(
                scheduled_day=3
            )
        )

        transactions = (
            build_transactions_dataframe()
        )

        ses_client = (
            SuccessfulSESClient()
        )

        result, storage = (
            self._run_service(
                active_campaign=
                    active_campaign,
                transactions_df=
                    transactions,
                execution_time=
                    "2026-09-01 09:00:00",
                ses_client=
                    ses_client,
            )
        )

        self.assertEqual(
            result["processed"],
            0,
        )

        self.assertEqual(
            result["sent"],
            0,
        )

        self.assertEqual(
            len(
                ses_client.calls
            ),
            0,
        )

        self.assertEqual(
            storage.writes,
            [],
        )

        self.assertIsNone(
            result["report_key"]
        )

    # --------------------------------------------------------
    # PRE-SEND REACTIVATION CHECK
    # --------------------------------------------------------

    def test_recent_purchase_cancels_send_and_is_persisted(self):
        active_campaign = (
            build_campaign_dataframe(
                scheduled_day=1
            )
        )

        transactions = (
            build_transactions_dataframe(
                purchase_date=
                    "2026-08-30"
            )
        )

        ses_client = (
            SuccessfulSESClient()
        )

        result, storage = (
            self._run_service(
                active_campaign=
                    active_campaign,
                transactions_df=
                    transactions,
                execution_time=
                    "2026-09-01 09:00:00",
                ses_client=
                    ses_client,
            )
        )

        self.assertEqual(
            result["processed"],
            1,
        )

        self.assertEqual(
            result[
                "cancelled_reactivated"
            ],
            1,
        )

        self.assertEqual(
            result["sent"],
            0,
        )

        self.assertEqual(
            len(
                ses_client.calls
            ),
            0,
        )

        persisted_campaign = (
            storage.files[
                CAMPAIGN_ACTIVE_KEY
            ]
        )

        self.assertEqual(
            persisted_campaign.iloc[0][
                "Status"
            ],
            STATUS_CANCELLED_REACTIVATED,
        )

        self.assertIsNotNone(
            persisted_campaign.iloc[0][
                "Reactivated At"
            ]
        )

    # --------------------------------------------------------
    # TEMPORARY SES FAILURE
    # --------------------------------------------------------

    def test_temporary_ses_failure_is_persisted_as_retry(self):
        active_campaign = (
            build_campaign_dataframe(
                scheduled_day=1
            )
        )

        transactions = (
            build_transactions_dataframe()
        )

        ses_client = (
            FailingSESClient()
        )

        result, storage = (
            self._run_service(
                active_campaign=
                    active_campaign,
                transactions_df=
                    transactions,
                execution_time=
                    "2026-09-01 09:00:00",
                ses_client=
                    ses_client,
            )
        )

        self.assertEqual(
            result["processed"],
            1,
        )

        self.assertEqual(
            result[
                "retry_scheduled"
            ],
            1,
        )

        self.assertEqual(
            result["failed"],
            0,
        )

        persisted_campaign = (
            storage.files[
                CAMPAIGN_ACTIVE_KEY
            ]
        )

        self.assertEqual(
            persisted_campaign.iloc[0][
                "Status"
            ],
            STATUS_PENDING,
        )

        self.assertEqual(
            int(
                persisted_campaign.iloc[0][
                    "Retry Count"
                ]
            ),
            1,
        )

        self.assertIsNotNone(
            persisted_campaign.iloc[0][
                "Last Attempt At"
            ]
        )

    # --------------------------------------------------------
    # INVALID EMAIL
    # --------------------------------------------------------

    def test_invalid_email_is_persisted_as_failed(self):
        active_campaign = (
            build_campaign_dataframe(
                scheduled_day=1,
                customer_email=
                    "correo-invalido",
            )
        )

        transactions = (
            build_transactions_dataframe()
        )

        ses_client = (
            SuccessfulSESClient()
        )

        result, storage = (
            self._run_service(
                active_campaign=
                    active_campaign,
                transactions_df=
                    transactions,
                execution_time=
                    "2026-09-01 09:00:00",
                ses_client=
                    ses_client,
            )
        )

        self.assertEqual(
            result["processed"],
            1,
        )

        self.assertEqual(
            result["failed"],
            1,
        )

        self.assertEqual(
            result[
                "retry_scheduled"
            ],
            0,
        )

        self.assertEqual(
            len(
                ses_client.calls
            ),
            0,
        )

        persisted_campaign = (
            storage.files[
                CAMPAIGN_ACTIVE_KEY
            ]
        )

        self.assertEqual(
            persisted_campaign.iloc[0][
                "Status"
            ],
            STATUS_FAILED,
        )

        self.assertEqual(
            int(
                persisted_campaign.iloc[0][
                    "Retry Count"
                ]
            ),
            0,
        )

    # --------------------------------------------------------
    # OLD CAMPAIGN PROTECTION
    # --------------------------------------------------------

    def test_previous_month_active_campaign_is_rejected(self):
        active_campaign = (
            build_campaign_dataframe()
        )

        active_campaign.loc[
            :,
            "Campaign ID",
        ] = "REACTIVA-2026-08"

        active_campaign.loc[
            :,
            "Campaign Month",
        ] = "2026-08"

        storage = InMemoryS3(
            active_campaign
        )

        with (
            patch(
                "reactiva.campaigns.send_service."
                "read_csv_from_s3",
                side_effect=
                    storage.read_csv_from_s3,
            ),
            patch(
                "reactiva.campaigns.send_service."
                "write_csv_to_s3",
                side_effect=
                    storage.write_csv_to_s3,
            ),
            patch(
                "reactiva.campaigns.send_service."
                "load_operational_transactions",
                return_value=
                    build_transactions_dataframe(),
            ),
        ):
            with self.assertRaises(
                RuntimeError
            ):
                process_campaign_send_run(
                    sender_email=
                        "reactiva@example.com",
                    execution_time=
                        "2026-09-01 09:00:00",
                    bucket=
                        "fake-bucket",
                    dataset_uri=
                        "fake-dataset.csv",
                    ses_client=
                        SuccessfulSESClient(),
                )

        self.assertEqual(
            storage.writes,
            [],
        )


if __name__ == "__main__":
    unittest.main()