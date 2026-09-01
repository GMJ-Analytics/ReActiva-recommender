import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pandas as pd

from reactiva.campaigns.campaign import (
    CAMPAIGN_COLUMNS,
)
from reactiva.campaigns.sender import (
    build_email_html,
    build_email_text,
    build_unsubscribe_token,
    build_unsubscribe_url,
    build_unsubscribe_url_builder,
    process_due_campaign_emails,
)


# ============================================================
# LOAD CAMPAIGN SENDER LAMBDA
# ============================================================

LAMBDA_PATH = (
    Path(__file__).resolve().parents[1]
    / "artifacts"
    / "AwsLambda"
    / "campaign_sender"
    / "lambda.py"
)

spec = importlib.util.spec_from_file_location(
    "reactiva_campaign_sender_lambda",
    LAMBDA_PATH,
)

campaign_sender_lambda = (
    importlib.util.module_from_spec(
        spec
    )
)

spec.loader.exec_module(
    campaign_sender_lambda
)


# ============================================================
# TEST HELPERS
# ============================================================

def build_campaign_row():
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
                "CUST000001",
            "Customer Full Name":
                "Cliente Prueba",
            "Customer Email":
                "cliente@example.com",
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
                1,
            "Status":
                "PENDING",
            "Retry Count":
                0,
            "Last Attempt At":
                None,
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

    return pd.Series(
        row
    )


def build_campaign_dataframe():
    return pd.DataFrame(
        [
            build_campaign_row()
            .to_dict()
        ],
        columns=CAMPAIGN_COLUMNS,
    )


def build_transactions_dataframe():
    return pd.DataFrame(
        [
            {
                "Customer ID":
                    "CUST000001",
                "Purchase Date":
                    "2025-01-01",
            }
        ]
    )


class FakeSESClient:

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
                "fake-message-001"
        }


# ============================================================
# TOKEN + URL
# ============================================================

class TestCampaignUnsubscribeURL(
    unittest.TestCase
):

    def test_token_is_deterministic(self):
        token_1 = (
            build_unsubscribe_token(
                customer_id=
                    "CUST000001",
                campaign_id=
                    "REACTIVA-2026-09",
                secret=
                    "test-secret",
            )
        )

        token_2 = (
            build_unsubscribe_token(
                customer_id=
                    "CUST000001",
                campaign_id=
                    "REACTIVA-2026-09",
                secret=
                    "test-secret",
            )
        )

        self.assertEqual(
            token_1,
            token_2,
        )

    def test_url_contains_customer_campaign_and_token(self):
        row = build_campaign_row()

        url = (
            build_unsubscribe_url(
                row=row,
                base_url=
                    "https://example.lambda-url.aws/",
                secret=
                    "test-secret",
            )
        )

        parsed = urlparse(
            url
        )

        query = parse_qs(
            parsed.query
        )

        self.assertEqual(
            query[
                "customer_id"
            ][0],
            "CUST000001",
        )

        self.assertEqual(
            query[
                "campaign_id"
            ][0],
            "REACTIVA-2026-09",
        )

        self.assertIn(
            "token",
            query,
        )

        expected_token = (
            build_unsubscribe_token(
                customer_id=
                    "CUST000001",
                campaign_id=
                    "REACTIVA-2026-09",
                secret=
                    "test-secret",
            )
        )

        self.assertEqual(
            query[
                "token"
            ][0],
            expected_token,
        )

    def test_builder_generates_customer_specific_url(self):
        builder = (
            build_unsubscribe_url_builder(
                base_url=
                    "https://example.lambda-url.aws/",
                secret=
                    "test-secret",
            )
        )

        url = builder(
            build_campaign_row()
        )

        self.assertIn(
            "customer_id=CUST000001",
            url,
        )

        self.assertIn(
            "campaign_id=REACTIVA-2026-09",
            url,
        )


# ============================================================
# EMAIL CONTENT
# ============================================================

class TestUnsubscribeEmailContent(
    unittest.TestCase
):

    def test_html_email_contains_unsubscribe_link(self):
        row = build_campaign_row()

        url = (
            "https://example.lambda-url.aws/"
            "?customer_id=CUST000001"
            "&campaign_id=REACTIVA-2026-09"
            "&token=abc123"
        )

        body = build_email_html(
            row=row,
            unsubscribe_url=url,
        )

        self.assertIn(
            "No quiero recibir más ofertas",
            body,
        )

        self.assertIn(
            "customer_id=CUST000001",
            body,
        )

        self.assertIn(
            "token=abc123",
            body,
        )

    def test_text_email_contains_unsubscribe_link(self):
        row = build_campaign_row()

        url = (
            "https://example.lambda-url.aws/"
            "?customer_id=CUST000001"
            "&campaign_id=REACTIVA-2026-09"
            "&token=abc123"
        )

        body = build_email_text(
            row=row,
            unsubscribe_url=url,
        )

        self.assertIn(
            "darte de baja",
            body,
        )

        self.assertIn(
            url,
            body,
        )


# ============================================================
# DAILY SEND INTEGRATION
# ============================================================

class TestSenderUnsubscribeIntegration(
    unittest.TestCase
):

    def test_due_email_receives_signed_unsubscribe_url(self):
        campaign_df = (
            build_campaign_dataframe()
        )

        transactions_df = (
            build_transactions_dataframe()
        )

        ses_client = (
            FakeSESClient()
        )

        builder = (
            build_unsubscribe_url_builder(
                base_url=
                    "https://example.lambda-url.aws/",
                secret=
                    "test-secret",
            )
        )

        updated_df, events_df = (
            process_due_campaign_emails(
                campaign_df=
                    campaign_df,
                transactions_df=
                    transactions_df,
                sender_email=
                    "reactiva@example.com",
                execution_time=
                    "2026-09-01 09:00:00",
                unsubscribe_url_builder=
                    builder,
                ses_client=
                    ses_client,
            )
        )

        self.assertEqual(
            len(
                ses_client.calls
            ),
            1,
        )

        ses_call = (
            ses_client.calls[0]
        )

        html_body = (
            ses_call[
                "Message"
            ][
                "Body"
            ][
                "Html"
            ][
                "Data"
            ]
        )

        text_body = (
            ses_call[
                "Message"
            ][
                "Body"
            ][
                "Text"
            ][
                "Data"
            ]
        )

        self.assertIn(
            "customer_id=CUST000001",
            html_body,
        )

        self.assertIn(
            "campaign_id=REACTIVA-2026-09",
            html_body,
        )

        self.assertIn(
            "token=",
            html_body,
        )

        self.assertIn(
            "customer_id=CUST000001",
            text_body,
        )

        self.assertEqual(
            updated_df.iloc[0][
                "Status"
            ],
            "SENT",
        )

        self.assertEqual(
            events_df.iloc[0][
                "Event"
            ],
            "SENT",
        )


# ============================================================
# CAMPAIGN SENDER LAMBDA
# ============================================================

class TestCampaignSenderLambdaUnsubscribe(
    unittest.TestCase
):

    def test_lambda_builds_unsubscribe_callback_from_environment(self):
        fake_result = {
            "campaign_id":
                "REACTIVA-2026-09",
            "campaign_month":
                "2026-09",
            "execution_time":
                pd.Timestamp(
                    "2026-09-01 09:00:00"
                ),
            "processed":
                1,
            "sent":
                1,
            "failed":
                0,
            "cancelled_reactivated":
                0,
            "retry_scheduled":
                0,
            "report_key":
                "campaigns/reports/send_events/test.csv",
        }

        captured = {}

        def fake_process(
            **kwargs,
        ):
            captured.update(
                kwargs
            )

            return fake_result

        with (
            patch.dict(
                os.environ,
                {
                    "SES_SENDER_EMAIL":
                        "reactiva@example.com",
                    "UNSUBSCRIBE_BASE_URL":
                        "https://example.lambda-url.aws/",
                    "UNSUBSCRIBE_SECRET":
                        "test-secret",
                    "AWS_REGION":
                        "ap-south-1",
                },
                clear=False,
            ),
            patch.object(
                campaign_sender_lambda,
                "process_campaign_send_run",
                side_effect=
                    fake_process,
            ),
        ):
            response = (
                campaign_sender_lambda
                .lambda_handler(
                    {
                        "execution_time":
                            "2026-09-01 09:00:00"
                    },
                    None,
                )
            )

        self.assertEqual(
            response[
                "status"
            ],
            "SUCCESS",
        )

        self.assertEqual(
            captured[
                "sender_email"
            ],
            "reactiva@example.com",
        )

        self.assertEqual(
            captured[
                "region_name"
            ],
            "ap-south-1",
        )

        builder = (
            captured[
                "unsubscribe_url_builder"
            ]
        )

        url = builder(
            build_campaign_row()
        )

        self.assertIn(
            "customer_id=CUST000001",
            url,
        )

        self.assertIn(
            "campaign_id=REACTIVA-2026-09",
            url,
        )

        self.assertIn(
            "token=",
            url,
        )

    def test_lambda_requires_unsubscribe_configuration(self):
        environment = {
            "SES_SENDER_EMAIL":
                "reactiva@example.com",
            "UNSUBSCRIBE_BASE_URL":
                "",
            "UNSUBSCRIBE_SECRET":
                "",
        }

        with patch.dict(
            os.environ,
            environment,
            clear=False,
        ):
            with self.assertRaises(
                RuntimeError
            ):
                campaign_sender_lambda.lambda_handler(
                    {
                        "execution_time":
                            "2026-09-01 09:00:00"
                    },
                    None,
                )


if __name__ == "__main__":
    unittest.main()