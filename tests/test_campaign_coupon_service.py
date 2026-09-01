import unittest
from unittest.mock import patch

import pandas as pd

from reactiva.campaigns.coupon_service import (
    redeem_coupon_from_s3,
    validate_coupon_from_s3,
)
from reactiva.campaigns.storage import (
    CAMPAIGN_ACTIVE_KEY,
)


def build_campaign_dataframe():
    return pd.DataFrame(
        [
            {
                "Campaign ID": "REACTIVA-2026-09",
                "Campaign Month": "2026-09",
                "Customer ID": "CUST000001",
                "Recommendation 1": "Socks",
                "Recommendation 2": "Sneakers",
                "Recommendation 3": "Backpack",
                "Discount Percent": 10,
                "Coupon Code": "ABC123",
                "Coupon Status": "ACTIVE",
                "Coupon Redeemed At": None,
                "Coupon Transaction ID": None,
            },
            {
                "Campaign ID": "REACTIVA-2026-09",
                "Campaign Month": "2026-09",
                "Customer ID": "CUST000002",
                "Recommendation 1": "Shirt",
                "Recommendation 2": "Jeans",
                "Recommendation 3": "Jacket",
                "Discount Percent": 10,
                "Coupon Code": "XYZ789",
                "Coupon Status": "ACTIVE",
                "Coupon Redeemed At": None,
                "Coupon Transaction ID": None,
            },
        ]
    )


class TestCouponValidationFromS3(
    unittest.TestCase
):

    @patch(
        "reactiva.campaigns.coupon_service.read_csv_from_s3"
    )
    def test_valid_coupon_is_loaded_and_validated_from_active_campaign(
        self,
        mock_read,
    ):
        mock_read.return_value = (
            build_campaign_dataframe()
        )

        result = validate_coupon_from_s3(
            bucket="test-bucket",
            coupon_code="ABC123",
            customer_id="CUST000001",
            item_purchased="Socks",
            reference_date="2026-09-10",
            s3_client="fake-client",
        )

        self.assertTrue(
            result["valid"]
        )

        self.assertEqual(
            result["coupon_code"],
            "ABC123",
        )

        self.assertEqual(
            result["discount_percent"],
            10,
        )

        mock_read.assert_called_once()

        call_kwargs = (
            mock_read.call_args.kwargs
        )

        self.assertEqual(
            call_kwargs["bucket"],
            "test-bucket",
        )

        self.assertEqual(
            call_kwargs["key"],
            CAMPAIGN_ACTIVE_KEY,
        )

        self.assertEqual(
            call_kwargs["s3_client"],
            "fake-client",
        )

    @patch(
        "reactiva.campaigns.coupon_service.read_csv_from_s3"
    )
    def test_missing_active_campaign_returns_invalid_result(
        self,
        mock_read,
    ):
        mock_read.return_value = pd.DataFrame()

        result = validate_coupon_from_s3(
            bucket="test-bucket",
            coupon_code="ABC123",
            customer_id="CUST000001",
            item_purchased="Socks",
            reference_date="2026-09-10",
            s3_client="fake-client",
        )

        self.assertFalse(
            result["valid"]
        )

        self.assertEqual(
            result["reason"],
            "CAMPAIGN_NOT_AVAILABLE",
        )

    @patch(
        "reactiva.campaigns.coupon_service.read_csv_from_s3"
    )
    def test_invalid_product_is_rejected_without_modifying_campaign(
        self,
        mock_read,
    ):
        campaign_df = (
            build_campaign_dataframe()
        )

        mock_read.return_value = campaign_df

        result = validate_coupon_from_s3(
            bucket="test-bucket",
            coupon_code="ABC123",
            customer_id="CUST000001",
            item_purchased="Watch",
            reference_date="2026-09-10",
            s3_client="fake-client",
        )

        self.assertFalse(
            result["valid"]
        )

        self.assertEqual(
            result["reason"],
            "PRODUCT_NOT_ELIGIBLE",
        )

        self.assertEqual(
            campaign_df.iloc[0][
                "Coupon Status"
            ],
            "ACTIVE",
        )


class TestCouponRedemptionFromS3(
    unittest.TestCase
):

    @patch(
        "reactiva.campaigns.coupon_service.read_csv_from_s3"
    )
    @patch(
        "reactiva.campaigns.coupon_service.write_csv_to_s3"
    )
    def test_valid_coupon_is_redeemed_and_persisted(
        self,
        mock_write,
        mock_read,
    ):
        original_df = (
            build_campaign_dataframe()
        )

        verified_df = (
            original_df.copy(
                deep=True
            )
        )

        verified_df.loc[
            verified_df[
                "Coupon Code"
            ] == "ABC123",
            "Coupon Status",
        ] = "REDEEMED"

        verified_df.loc[
            verified_df[
                "Coupon Code"
            ] == "ABC123",
            "Coupon Redeemed At",
        ] = "2026-09-10 10:30:00"

        verified_df.loc[
            verified_df[
                "Coupon Code"
            ] == "ABC123",
            "Coupon Transaction ID",
        ] = "TXN-20260910-001"

        mock_read.side_effect = [
            original_df,
            verified_df,
        ]

        result = redeem_coupon_from_s3(
            bucket="test-bucket",
            coupon_code="ABC123",
            customer_id="CUST000001",
            item_purchased="Socks",
            reference_date="2026-09-10",
            transaction_id="TXN-20260910-001",
            redeemed_at="2026-09-10 10:30:00",
            s3_client="fake-client",
        )

        self.assertTrue(
            result["redeemed"]
        )

        self.assertEqual(
            result["coupon_code"],
            "ABC123",
        )

        self.assertEqual(
            result["transaction_id"],
            "TXN-20260910-001",
        )

        mock_write.assert_called_once()

        write_kwargs = (
            mock_write.call_args.kwargs
        )

        self.assertEqual(
            write_kwargs["bucket"],
            "test-bucket",
        )

        self.assertEqual(
            write_kwargs["key"],
            CAMPAIGN_ACTIVE_KEY,
        )

        self.assertEqual(
            write_kwargs["s3_client"],
            "fake-client",
        )

        written_df = (
            write_kwargs["df"]
        )

        written_row = written_df[
            written_df[
                "Coupon Code"
            ] == "ABC123"
        ].iloc[0]

        self.assertEqual(
            written_row[
                "Coupon Status"
            ],
            "REDEEMED",
        )

        self.assertEqual(
            written_row[
                "Coupon Transaction ID"
            ],
            "TXN-20260910-001",
        )

        self.assertEqual(
            mock_read.call_count,
            2,
        )

    @patch(
        "reactiva.campaigns.coupon_service.read_csv_from_s3"
    )
    @patch(
        "reactiva.campaigns.coupon_service.write_csv_to_s3"
    )
    def test_invalid_coupon_is_not_written_to_s3(
        self,
        mock_write,
        mock_read,
    ):
        mock_read.return_value = (
            build_campaign_dataframe()
        )

        result = redeem_coupon_from_s3(
            bucket="test-bucket",
            coupon_code="NOEXISTE",
            customer_id="CUST000001",
            item_purchased="Socks",
            reference_date="2026-09-10",
            transaction_id="TXN-20260910-001",
            redeemed_at="2026-09-10 10:30:00",
            s3_client="fake-client",
        )

        self.assertFalse(
            result["redeemed"]
        )

        self.assertEqual(
            result["reason"],
            "COUPON_NOT_FOUND",
        )

        mock_write.assert_not_called()

    @patch(
        "reactiva.campaigns.coupon_service.read_csv_from_s3"
    )
    @patch(
        "reactiva.campaigns.coupon_service.write_csv_to_s3"
    )
    def test_wrong_customer_is_not_written_to_s3(
        self,
        mock_write,
        mock_read,
    ):
        mock_read.return_value = (
            build_campaign_dataframe()
        )

        result = redeem_coupon_from_s3(
            bucket="test-bucket",
            coupon_code="ABC123",
            customer_id="CUST000002",
            item_purchased="Socks",
            reference_date="2026-09-10",
            transaction_id="TXN-20260910-001",
            redeemed_at="2026-09-10 10:30:00",
            s3_client="fake-client",
        )

        self.assertFalse(
            result["redeemed"]
        )

        self.assertEqual(
            result["reason"],
            "CUSTOMER_MISMATCH",
        )

        mock_write.assert_not_called()

    @patch(
        "reactiva.campaigns.coupon_service.read_csv_from_s3"
    )
    @patch(
        "reactiva.campaigns.coupon_service.write_csv_to_s3"
    )
    def test_invalid_product_is_not_written_to_s3(
        self,
        mock_write,
        mock_read,
    ):
        mock_read.return_value = (
            build_campaign_dataframe()
        )

        result = redeem_coupon_from_s3(
            bucket="test-bucket",
            coupon_code="ABC123",
            customer_id="CUST000001",
            item_purchased="Watch",
            reference_date="2026-09-10",
            transaction_id="TXN-20260910-001",
            redeemed_at="2026-09-10 10:30:00",
            s3_client="fake-client",
        )

        self.assertFalse(
            result["redeemed"]
        )

        self.assertEqual(
            result["reason"],
            "PRODUCT_NOT_ELIGIBLE",
        )

        mock_write.assert_not_called()

    @patch(
        "reactiva.campaigns.coupon_service.read_csv_from_s3"
    )
    @patch(
        "reactiva.campaigns.coupon_service.write_csv_to_s3"
    )
    def test_failed_persistence_verification_raises_runtime_error(
        self,
        mock_write,
        mock_read,
    ):
        campaign_df = (
            build_campaign_dataframe()
        )

        mock_read.side_effect = [
            campaign_df,
            campaign_df,
        ]

        with self.assertRaises(
            RuntimeError
        ):
            redeem_coupon_from_s3(
                bucket="test-bucket",
                coupon_code="ABC123",
                customer_id="CUST000001",
                item_purchased="Socks",
                reference_date="2026-09-10",
                transaction_id="TXN-20260910-001",
                redeemed_at="2026-09-10 10:30:00",
                s3_client="fake-client",
            )

        mock_write.assert_called_once()

    @patch(
        "reactiva.campaigns.coupon_service.read_csv_from_s3"
    )
    @patch(
        "reactiva.campaigns.coupon_service.write_csv_to_s3"
    )
    def test_same_transaction_redemption_is_idempotent(
        self,
        mock_write,
        mock_read,
    ):
        campaign_df = (
            build_campaign_dataframe()
        )

        redeemed_df = (
            campaign_df.copy(
                deep=True
            )
        )

        redeemed_df.loc[
            redeemed_df[
                "Coupon Code"
            ] == "ABC123",
            "Coupon Status",
        ] = "REDEEMED"

        redeemed_df.loc[
            redeemed_df[
                "Coupon Code"
            ] == "ABC123",
            "Coupon Redeemed At",
        ] = "2026-09-10 10:30:00"

        redeemed_df.loc[
            redeemed_df[
                "Coupon Code"
            ] == "ABC123",
            "Coupon Transaction ID",
        ] = "TXN-20260910-001"

        mock_read.return_value = (
            redeemed_df
        )

        result = redeem_coupon_from_s3(
            bucket="test-bucket",
            coupon_code="ABC123",
            customer_id="CUST000001",
            item_purchased="Socks",
            reference_date="2026-09-10",
            transaction_id="TXN-20260910-001",
            redeemed_at="2026-09-10 10:30:00",
            s3_client="fake-client",
        )

        self.assertTrue(
            result["redeemed"]
        )

        self.assertTrue(
            result["already_redeemed"]
        )

        self.assertEqual(
            result["transaction_id"],
            "TXN-20260910-001",
        )

        mock_write.assert_not_called()

    @patch(
        "reactiva.campaigns.coupon_service.read_csv_from_s3"
    )
    @patch(
        "reactiva.campaigns.coupon_service.write_csv_to_s3"
    )
    def test_redeemed_coupon_cannot_be_reused_by_another_transaction(
        self,
        mock_write,
        mock_read,
    ):
        campaign_df = (
            build_campaign_dataframe()
        )

        campaign_df.loc[
            campaign_df[
                "Coupon Code"
            ] == "ABC123",
            "Coupon Status",
        ] = "REDEEMED"

        campaign_df.loc[
            campaign_df[
                "Coupon Code"
            ] == "ABC123",
            "Coupon Transaction ID",
        ] = "TXN-OLD-001"

        mock_read.return_value = (
            campaign_df
        )

        result = redeem_coupon_from_s3(
            bucket="test-bucket",
            coupon_code="ABC123",
            customer_id="CUST000001",
            item_purchased="Socks",
            reference_date="2026-09-10",
            transaction_id="TXN-NEW-002",
            redeemed_at="2026-09-10 11:00:00",
            s3_client="fake-client",
        )

        self.assertFalse(
            result["redeemed"]
        )

        self.assertEqual(
            result["reason"],
            "COUPON_NOT_ACTIVE",
        )

        mock_write.assert_not_called()


if __name__ == "__main__":
    unittest.main()