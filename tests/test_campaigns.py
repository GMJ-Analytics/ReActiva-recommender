import unittest

import pandas as pd
from botocore.exceptions import ClientError

from reactiva.campaigns.campaign import (
    CAMPAIGN_COLUMNS,
    STATUS_CANCELLED_REACTIVATED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SENT,
)
from reactiva.campaigns.sender import (
    build_email_text,
    build_last_purchase_lookup,
    customer_still_inactive,
    process_due_campaign_emails,
    row_is_due,
)


# ============================================================
# TEST HELPERS
# ============================================================


def build_campaign_row(**overrides):
    """
    Creates a complete campaign row using the official schema.
    """
    row = {
        column: None
        for column in CAMPAIGN_COLUMNS
    }

    row.update(
        {
            "Campaign ID": "REACTIVA-2026-09",
            "Campaign Month": "2026-09",
            "Customer ID": "CUST-001",
            "Customer Full Name": "Cliente Prueba",
            "Customer Email": "cliente@example.com",
            "Recommendation 1": "Shirt",
            "Recommendation 2": "Sneakers",
            "Recommendation 3": "Backpack",
            "Discount Percent": 10,
            "Coupon Code": "ABC123",
            "Scheduled Day": 1,
            "Status": STATUS_PENDING,
            "Retry Count": 0,
            "Last Attempt At": None,
            "Sent At": None,
            "Reactivated At": None,
            "Coupon Status": "ACTIVE",
            "Coupon Redeemed At": None,
            "Coupon Transaction ID": None,
            "Last Error": None,
        }
    )

    row.update(overrides)

    return row


def build_campaign_dataframe(**overrides):
    """
    Creates a one-row campaign DataFrame.
    """
    return pd.DataFrame(
        [
            build_campaign_row(
                **overrides
            )
        ],
        columns=CAMPAIGN_COLUMNS,
    )


class SuccessfulSESClient:
    """
    Fake SES client that records send_email calls.
    """

    def __init__(self):
        self.calls = []

    def send_email(self, **kwargs):
        self.calls.append(kwargs)

        return {
            "MessageId": "fake-message-id-001"
        }


class FailingSESClient:
    """
    Fake SES client that always raises a ClientError.
    """

    def __init__(self):
        self.calls = 0

    def send_email(self, **kwargs):
        self.calls += 1

        raise ClientError(
            {
                "Error": {
                    "Code": "ServiceUnavailable",
                    "Message": "Temporary SES failure",
                }
            },
            "SendEmail",
        )


# ============================================================
# LAST PURCHASE / INACTIVITY TESTS
# ============================================================


class TestInactivityLogic(unittest.TestCase):

    def test_build_last_purchase_lookup_keeps_latest_purchase(self):
        transactions = pd.DataFrame(
            {
                "Customer ID": [
                    "CUST-001",
                    "CUST-001",
                    "CUST-002",
                ],
                "Purchase Date": [
                    "2025-01-01",
                    "2025-05-01",
                    "2026-08-01",
                ],
            }
        )

        lookup = build_last_purchase_lookup(
            transactions
        )

        self.assertEqual(
            lookup["CUST-001"],
            pd.Timestamp("2025-05-01"),
        )

        self.assertEqual(
            lookup["CUST-002"],
            pd.Timestamp("2026-08-01"),
        )

    def test_customer_is_inactive_at_exact_270_day_boundary(self):
        reference_date = pd.Timestamp(
            "2026-09-01"
        )

        cutoff = (
            reference_date
            - pd.Timedelta(days=270)
        )

        lookup = {
            "CUST-001": cutoff
        }

        result = customer_still_inactive(
            customer_id="CUST-001",
            last_purchase_lookup=lookup,
            reference_date=reference_date,
            inactivity_days=270,
        )

        self.assertTrue(result)

    def test_customer_is_not_inactive_if_purchase_is_more_recent(self):
        lookup = {
            "CUST-001": pd.Timestamp(
                "2026-08-30"
            )
        }

        result = customer_still_inactive(
            customer_id="CUST-001",
            last_purchase_lookup=lookup,
            reference_date="2026-09-01",
            inactivity_days=270,
        )

        self.assertFalse(result)


# ============================================================
# SCHEDULING / RETRY TESTS
# ============================================================


class TestSendScheduling(unittest.TestCase):

    def test_initial_email_is_due_on_scheduled_day(self):
        row = pd.Series(
            build_campaign_row(
                **{
                    "Scheduled Day": 3,
                    "Status": STATUS_PENDING,
                    "Retry Count": 0,
                    "Last Attempt At": None,
                }
            )
        )

        self.assertTrue(
            row_is_due(
                row=row,
                execution_time="2026-09-03 09:00:00",
            )
        )

    def test_initial_email_is_not_due_before_scheduled_day(self):
        row = pd.Series(
            build_campaign_row(
                **{
                    "Scheduled Day": 3,
                    "Status": STATUS_PENDING,
                    "Retry Count": 0,
                    "Last Attempt At": None,
                }
            )
        )

        self.assertFalse(
            row_is_due(
                row=row,
                execution_time="2026-09-02 09:00:00",
            )
        )

    def test_retry_is_not_due_before_24_hours(self):
        row = pd.Series(
            build_campaign_row(
                **{
                    "Status": STATUS_PENDING,
                    "Retry Count": 1,
                    "Last Attempt At":
                        "2026-09-01T09:00:00",
                }
            )
        )

        self.assertFalse(
            row_is_due(
                row=row,
                execution_time="2026-09-02 08:59:00",
            )
        )

    def test_retry_is_due_after_24_hours(self):
        row = pd.Series(
            build_campaign_row(
                **{
                    "Status": STATUS_PENDING,
                    "Retry Count": 1,
                    "Last Attempt At":
                        "2026-09-01T09:00:00",
                }
            )
        )

        self.assertTrue(
            row_is_due(
                row=row,
                execution_time="2026-09-02 09:00:00",
            )
        )


# ============================================================
# EMAIL CONTENT TESTS
# ============================================================


class TestEmailContent(unittest.TestCase):

    def test_email_contains_customer_coupon_and_ranked_products(self):
        row = pd.Series(
            build_campaign_row()
        )

        text = build_email_text(
            row=row,
            store_name="ReActiva",
        )

        self.assertIn(
            "Cliente Prueba",
            text,
        )

        self.assertIn(
            "Shirt",
            text,
        )

        self.assertIn(
            "Sneakers",
            text,
        )

        self.assertIn(
            "Backpack",
            text,
        )

        self.assertIn(
            "ABC123",
            text,
        )

        self.assertIn(
            "10% OFF",
            text,
        )


# ============================================================
# DAILY CAMPAIGN RUNNER TESTS
# ============================================================


class TestCampaignSendRunner(unittest.TestCase):

    def test_inactive_customer_is_sent_successfully(self):
        campaign_df = (
            build_campaign_dataframe()
        )

        transactions_df = pd.DataFrame(
            {
                "Customer ID": [
                    "CUST-001"
                ],
                "Purchase Date": [
                    "2025-01-01"
                ],
            }
        )

        ses_client = SuccessfulSESClient()

        updated, events = (
            process_due_campaign_emails(
                campaign_df=campaign_df,
                transactions_df=transactions_df,
                sender_email="reactiva@example.com",
                execution_time="2026-09-01 09:00:00",
                inactivity_days=270,
                ses_client=ses_client,
            )
        )

        self.assertEqual(
            updated.iloc[0]["Status"],
            STATUS_SENT,
        )

        self.assertEqual(
            len(ses_client.calls),
            1,
        )

        self.assertEqual(
            len(events),
            1,
        )

        self.assertEqual(
            events.iloc[0]["Event"],
            STATUS_SENT,
        )

        self.assertEqual(
            updated.iloc[0]["Retry Count"],
            0,
        )

        self.assertIsNotNone(
            updated.iloc[0]["Sent At"]
        )

    def test_reactivated_customer_is_cancelled_before_send(self):
        campaign_df = (
            build_campaign_dataframe()
        )

        transactions_df = pd.DataFrame(
            {
                "Customer ID": [
                    "CUST-001"
                ],
                "Purchase Date": [
                    "2026-08-30"
                ],
            }
        )

        ses_client = SuccessfulSESClient()

        updated, events = (
            process_due_campaign_emails(
                campaign_df=campaign_df,
                transactions_df=transactions_df,
                sender_email="reactiva@example.com",
                execution_time="2026-09-01 09:00:00",
                inactivity_days=270,
                ses_client=ses_client,
            )
        )

        self.assertEqual(
            updated.iloc[0]["Status"],
            STATUS_CANCELLED_REACTIVATED,
        )

        self.assertEqual(
            len(ses_client.calls),
            0,
        )

        self.assertEqual(
            events.iloc[0]["Event"],
            STATUS_CANCELLED_REACTIVATED,
        )

        self.assertIsNotNone(
            updated.iloc[0]["Reactivated At"]
        )

    def test_temporary_ses_failure_schedules_retry(self):
        campaign_df = (
            build_campaign_dataframe()
        )

        transactions_df = pd.DataFrame(
            {
                "Customer ID": [
                    "CUST-001"
                ],
                "Purchase Date": [
                    "2025-01-01"
                ],
            }
        )

        ses_client = FailingSESClient()

        updated, events = (
            process_due_campaign_emails(
                campaign_df=campaign_df,
                transactions_df=transactions_df,
                sender_email="reactiva@example.com",
                execution_time="2026-09-01 09:00:00",
                inactivity_days=270,
                ses_client=ses_client,
            )
        )

        self.assertEqual(
            updated.iloc[0]["Status"],
            STATUS_PENDING,
        )

        self.assertEqual(
            int(updated.iloc[0]["Retry Count"]),
            1,
        )

        self.assertEqual(
            events.iloc[0]["Event"],
            "RETRY_SCHEDULED",
        )

        self.assertEqual(
            ses_client.calls,
            1,
        )

    def test_fourth_failure_finishes_as_failed(self):
        campaign_df = (
            build_campaign_dataframe(
                **{
                    "Retry Count": 3,
                    "Last Attempt At":
                        "2026-09-03T09:00:00",
                }
            )
        )

        transactions_df = pd.DataFrame(
            {
                "Customer ID": [
                    "CUST-001"
                ],
                "Purchase Date": [
                    "2025-01-01"
                ],
            }
        )

        ses_client = FailingSESClient()

        updated, events = (
            process_due_campaign_emails(
                campaign_df=campaign_df,
                transactions_df=transactions_df,
                sender_email="reactiva@example.com",
                execution_time="2026-09-04 09:00:00",
                inactivity_days=270,
                ses_client=ses_client,
            )
        )

        self.assertEqual(
            updated.iloc[0]["Status"],
            STATUS_FAILED,
        )

        self.assertEqual(
            int(updated.iloc[0]["Retry Count"]),
            3,
        )

        self.assertEqual(
            events.iloc[0]["Event"],
            STATUS_FAILED,
        )

    def test_customer_reactivated_before_retry_is_cancelled(self):
        campaign_df = (
            build_campaign_dataframe(
                **{
                    "Retry Count": 1,
                    "Last Attempt At":
                        "2026-09-01T09:00:00",
                }
            )
        )

        transactions_df = pd.DataFrame(
            {
                "Customer ID": [
                    "CUST-001"
                ],
                "Purchase Date": [
                    "2026-09-01 15:00:00"
                ],
            }
        )

        ses_client = SuccessfulSESClient()

        updated, events = (
            process_due_campaign_emails(
                campaign_df=campaign_df,
                transactions_df=transactions_df,
                sender_email="reactiva@example.com",
                execution_time="2026-09-02 09:00:00",
                inactivity_days=270,
                ses_client=ses_client,
            )
        )

        self.assertEqual(
            updated.iloc[0]["Status"],
            STATUS_CANCELLED_REACTIVATED,
        )

        self.assertEqual(
            len(ses_client.calls),
            0,
        )

        self.assertEqual(
            events.iloc[0]["Event"],
            STATUS_CANCELLED_REACTIVATED,
        )

    def test_invalid_email_must_fail_without_retry(self):
        """
        Business rule:
        an invalid customer email is a definitive error.

        It must be reported as FAILED immediately rather than consuming
        three 24-hour SES retries.
        """
        campaign_df = (
            build_campaign_dataframe(
                **{
                    "Customer Email":
                        "correo-invalido"
                }
            )
        )

        transactions_df = pd.DataFrame(
            {
                "Customer ID": [
                    "CUST-001"
                ],
                "Purchase Date": [
                    "2025-01-01"
                ],
            }
        )

        ses_client = SuccessfulSESClient()

        updated, events = (
            process_due_campaign_emails(
                campaign_df=campaign_df,
                transactions_df=transactions_df,
                sender_email="reactiva@example.com",
                execution_time="2026-09-01 09:00:00",
                inactivity_days=270,
                ses_client=ses_client,
            )
        )

        self.assertEqual(
            updated.iloc[0]["Status"],
            STATUS_FAILED,
        )

        self.assertEqual(
            int(updated.iloc[0]["Retry Count"]),
            0,
        )

        self.assertEqual(
            len(ses_client.calls),
            0,
        )

        self.assertEqual(
            events.iloc[0]["Event"],
            STATUS_FAILED,
        )


if __name__ == "__main__":
    unittest.main()