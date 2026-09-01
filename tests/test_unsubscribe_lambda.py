import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


# ============================================================
# LOAD LAMBDA MODULE
# ============================================================


LAMBDA_PATH = (
    Path(__file__).resolve().parents[1]
    / "artifacts"
    / "AwsLambda"
    / "unsubscribe"
    / "lambda.py"
)


spec = importlib.util.spec_from_file_location(
    "reactiva_unsubscribe_lambda",
    LAMBDA_PATH,
)

unsubscribe_lambda = (
    importlib.util.module_from_spec(
        spec
    )
)

spec.loader.exec_module(
    unsubscribe_lambda
)


# ============================================================
# TEST HELPERS
# ============================================================


def build_status_dataframe(
    customer_id="CUST000001",
    opt_out=False,
):
    return pd.DataFrame(
        [
            {
                "Customer ID":
                    customer_id,
                "Opt Out":
                    opt_out,
                "Opt Out Date":
                    None,
                "Campaigns In Current Cycle":
                    2,
                "Skip Next Campaign":
                    False,
                "Last Reactivation Date":
                    None,
                "Last Campaign Month":
                    "2026-09",
            }
        ]
    )


class InMemoryStatusStorage:

    def __init__(
        self,
        dataframe,
    ):
        self.dataframe = (
            dataframe.copy()
        )

        self.write_count = 0

    def read(
        self,
        bucket,
        key,
        expected_columns=None,
        s3_client=None,
    ):
        return self.dataframe.copy()

    def write(
        self,
        df,
        bucket,
        key,
        s3_client=None,
    ):
        self.write_count += 1

        self.dataframe = (
            df.copy()
        )


# ============================================================
# HMAC TOKEN
# ============================================================


class TestUnsubscribeToken(
    unittest.TestCase
):

    def test_same_customer_and_campaign_generate_same_token(self):
        token_1 = (
            unsubscribe_lambda
            .build_unsubscribe_token(
                customer_id=
                    "CUST000001",
                campaign_id=
                    "REACTIVA-2026-09",
                secret=
                    "test-secret",
            )
        )

        token_2 = (
            unsubscribe_lambda
            .build_unsubscribe_token(
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

    def test_valid_token_is_accepted(self):
        token = (
            unsubscribe_lambda
            .build_unsubscribe_token(
                customer_id=
                    "CUST000001",
                campaign_id=
                    "REACTIVA-2026-09",
                secret=
                    "test-secret",
            )
        )

        result = (
            unsubscribe_lambda
            .validate_unsubscribe_token(
                customer_id=
                    "CUST000001",
                campaign_id=
                    "REACTIVA-2026-09",
                token=
                    token,
                secret=
                    "test-secret",
            )
        )

        self.assertTrue(
            result
        )

    def test_token_is_rejected_if_customer_changes(self):
        token = (
            unsubscribe_lambda
            .build_unsubscribe_token(
                customer_id=
                    "CUST000001",
                campaign_id=
                    "REACTIVA-2026-09",
                secret=
                    "test-secret",
            )
        )

        result = (
            unsubscribe_lambda
            .validate_unsubscribe_token(
                customer_id=
                    "CUST999999",
                campaign_id=
                    "REACTIVA-2026-09",
                token=
                    token,
                secret=
                    "test-secret",
            )
        )

        self.assertFalse(
            result
        )

    def test_token_is_rejected_if_campaign_changes(self):
        token = (
            unsubscribe_lambda
            .build_unsubscribe_token(
                customer_id=
                    "CUST000001",
                campaign_id=
                    "REACTIVA-2026-09",
                secret=
                    "test-secret",
            )
        )

        result = (
            unsubscribe_lambda
            .validate_unsubscribe_token(
                customer_id=
                    "CUST000001",
                campaign_id=
                    "REACTIVA-2026-10",
                token=
                    token,
                secret=
                    "test-secret",
            )
        )

        self.assertFalse(
            result
        )


# ============================================================
# QUERY PARAMETERS
# ============================================================


class TestUnsubscribeParameters(
    unittest.TestCase
):

    def test_valid_query_parameters_are_read(self):
        event = {
            "queryStringParameters": {
                "customer_id":
                    "CUST000001",
                "campaign_id":
                    "REACTIVA-2026-09",
                "token":
                    "abc123",
            }
        }

        result = (
            unsubscribe_lambda
            ._get_query_parameters(
                event
            )
        )

        self.assertEqual(
            result,
            (
                "CUST000001",
                "REACTIVA-2026-09",
                "abc123",
            ),
        )

    def test_missing_parameter_is_rejected(self):
        event = {
            "queryStringParameters": {
                "customer_id":
                    "CUST000001",
                "campaign_id":
                    "REACTIVA-2026-09",
            }
        }

        with self.assertRaises(
            ValueError
        ):
            unsubscribe_lambda._get_query_parameters(
                event
            )


# ============================================================
# PERSISTENCE
# ============================================================


class TestUnsubscribePersistence(
    unittest.TestCase
):

    def test_valid_unsubscribe_sets_opt_out_true(self):
        storage = (
            InMemoryStatusStorage(
                build_status_dataframe()
            )
        )

        with (
            patch.object(
                unsubscribe_lambda,
                "read_csv_from_s3",
                side_effect=
                    storage.read,
            ),
            patch.object(
                unsubscribe_lambda,
                "write_csv_to_s3",
                side_effect=
                    storage.write,
            ),
        ):
            result = (
                unsubscribe_lambda
                ._persist_opt_out(
                    customer_id=
                        "CUST000001",
                    bucket=
                        "fake-bucket",
                )
            )

        customer = (
            result[
                result[
                    "Customer ID"
                ]
                == "CUST000001"
            ]
            .iloc[0]
        )

        self.assertTrue(
            bool(
                customer[
                    "Opt Out"
                ]
            )
        )

        self.assertFalse(
            pd.isna(
                customer[
                    "Opt Out Date"
                ]
            )
        )

        self.assertEqual(
            storage.write_count,
            1,
        )

    def test_unsubscribe_is_idempotent(self):
        storage = (
            InMemoryStatusStorage(
                build_status_dataframe(
                    opt_out=True
                )
            )
        )

        with (
            patch.object(
                unsubscribe_lambda,
                "read_csv_from_s3",
                side_effect=
                    storage.read,
            ),
            patch.object(
                unsubscribe_lambda,
                "write_csv_to_s3",
                side_effect=
                    storage.write,
            ),
        ):
            first_result = (
                unsubscribe_lambda
                ._persist_opt_out(
                    customer_id=
                        "CUST000001",
                    bucket=
                        "fake-bucket",
                )
            )

            second_result = (
                unsubscribe_lambda
                ._persist_opt_out(
                    customer_id=
                        "CUST000001",
                    bucket=
                        "fake-bucket",
                )
            )

        self.assertTrue(
            bool(
                first_result.iloc[0][
                    "Opt Out"
                ]
            )
        )

        self.assertTrue(
            bool(
                second_result.iloc[0][
                    "Opt Out"
                ]
            )
        )

        self.assertEqual(
            storage.write_count,
            2,
        )


# ============================================================
# LAMBDA HANDLER
# ============================================================


class TestUnsubscribeHandler(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.secret = (
            "test-secret"
        )

        self.customer_id = (
            "CUST000001"
        )

        self.campaign_id = (
            "REACTIVA-2026-09"
        )

        self.token = (
            unsubscribe_lambda
            .build_unsubscribe_token(
                customer_id=
                    self.customer_id,
                campaign_id=
                    self.campaign_id,
                secret=
                    self.secret,
            )
        )

    def build_event(
        self,
        token=None,
    ):
        return {
            "queryStringParameters": {
                "customer_id":
                    self.customer_id,
                "campaign_id":
                    self.campaign_id,
                "token":
                    (
                        self.token
                        if token is None
                        else token
                    ),
            }
        }

    def test_missing_parameters_return_400(self):
        response = (
            unsubscribe_lambda
            .lambda_handler(
                {
                    "queryStringParameters":
                        {}
                },
                None,
            )
        )

        self.assertEqual(
            response[
                "statusCode"
            ],
            400,
        )

    def test_invalid_token_returns_403_and_does_not_persist(self):
        with (
            patch.dict(
                os.environ,
                {
                    "UNSUBSCRIBE_SECRET":
                        self.secret,
                },
                clear=False,
            ),
            patch.object(
                unsubscribe_lambda,
                "_persist_opt_out",
            ) as persist_mock,
        ):
            response = (
                unsubscribe_lambda
                .lambda_handler(
                    self.build_event(
                        token=
                            "invalid-token"
                    ),
                    None,
                )
            )

        self.assertEqual(
            response[
                "statusCode"
            ],
            403,
        )

        persist_mock.assert_not_called()

    def test_valid_token_returns_200_and_persists_opt_out(self):
        with (
            patch.dict(
                os.environ,
                {
                    "UNSUBSCRIBE_SECRET":
                        self.secret,
                },
                clear=False,
            ),
            patch.object(
                unsubscribe_lambda,
                "_persist_opt_out",
                return_value=
                    build_status_dataframe(
                        opt_out=True
                    ),
            ) as persist_mock,
        ):
            response = (
                unsubscribe_lambda
                .lambda_handler(
                    self.build_event(),
                    None,
                )
            )

        self.assertEqual(
            response[
                "statusCode"
            ],
            200,
        )

        persist_mock.assert_called_once_with(
            customer_id=
                self.customer_id,
        )

        self.assertIn(
            "Baja confirmada",
            response[
                "body"
            ],
        )

    def test_internal_error_returns_500(self):
        with (
            patch.dict(
                os.environ,
                {
                    "UNSUBSCRIBE_SECRET":
                        self.secret,
                },
                clear=False,
            ),
            patch.object(
                unsubscribe_lambda,
                "_persist_opt_out",
                side_effect=
                    RuntimeError(
                        "simulated error"
                    ),
            ),
        ):
            response = (
                unsubscribe_lambda
                .lambda_handler(
                    self.build_event(),
                    None,
                )
            )

        self.assertEqual(
            response[
                "statusCode"
            ],
            500,
        )


if __name__ == "__main__":
    unittest.main()