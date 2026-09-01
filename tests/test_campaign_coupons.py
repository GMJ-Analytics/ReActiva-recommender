import unittest

import pandas as pd

from reactiva.campaigns.coupons import (
    redeem_coupon,
    validate_coupon,
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
            {
                "Campaign ID": "REACTIVA-2026-09",
                "Campaign Month": "2026-09",
                "Customer ID": "CUST000003",
                "Recommendation 1": "Shoes",
                "Recommendation 2": "Hat",
                "Recommendation 3": "Belt",
                "Discount Percent": 10,
                "Coupon Code": "USED01",
                "Coupon Status": "REDEEMED",
                "Coupon Redeemed At": "2026-09-02 10:00:00",
                "Coupon Transaction ID": "TXN-USED-001",
            },
        ]
    )


class TestCouponValidation(unittest.TestCase):

    def test_valid_coupon_is_accepted(self):
        campaign_df = build_campaign_dataframe()

        result = validate_coupon(
            campaign_df=campaign_df,
            coupon_code="ABC123",
            customer_id="CUST000001",
            item_purchased="Socks",
            reference_date="2026-09-10",
        )

        self.assertTrue(
            result["valid"]
        )

        self.assertEqual(
            result["campaign_id"],
            "REACTIVA-2026-09",
        )

        self.assertEqual(
            result["coupon_code"],
            "ABC123",
        )

        self.assertEqual(
            result["discount_percent"],
            10,
        )

    def test_coupon_code_is_case_insensitive(self):
        campaign_df = build_campaign_dataframe()

        result = validate_coupon(
            campaign_df=campaign_df,
            coupon_code="abc123",
            customer_id="CUST000001",
            item_purchased="Socks",
            reference_date="2026-09-10",
        )

        self.assertTrue(
            result["valid"]
        )

        self.assertEqual(
            result["coupon_code"],
            "ABC123",
        )

    def test_customer_id_must_match_coupon_owner(self):
        campaign_df = build_campaign_dataframe()

        result = validate_coupon(
            campaign_df=campaign_df,
            coupon_code="ABC123",
            customer_id="CUST000002",
            item_purchased="Socks",
            reference_date="2026-09-10",
        )

        self.assertFalse(
            result["valid"]
        )

        self.assertEqual(
            result["reason"],
            "CUSTOMER_MISMATCH",
        )

    def test_unknown_coupon_is_rejected(self):
        campaign_df = build_campaign_dataframe()

        result = validate_coupon(
            campaign_df=campaign_df,
            coupon_code="NOEXISTE",
            customer_id="CUST000001",
            item_purchased="Socks",
            reference_date="2026-09-10",
        )

        self.assertFalse(
            result["valid"]
        )

        self.assertEqual(
            result["reason"],
            "COUPON_NOT_FOUND",
        )

    def test_empty_coupon_is_rejected(self):
        campaign_df = build_campaign_dataframe()

        result = validate_coupon(
            campaign_df=campaign_df,
            coupon_code="   ",
            customer_id="CUST000001",
            item_purchased="Socks",
            reference_date="2026-09-10",
        )

        self.assertFalse(
            result["valid"]
        )

        self.assertEqual(
            result["reason"],
            "EMPTY_COUPON",
        )

    def test_redeemed_coupon_cannot_be_used_again(self):
        campaign_df = build_campaign_dataframe()

        result = validate_coupon(
            campaign_df=campaign_df,
            coupon_code="USED01",
            customer_id="CUST000003",
            item_purchased="Shoes",
            reference_date="2026-09-10",
        )

        self.assertFalse(
            result["valid"]
        )

        self.assertEqual(
            result["reason"],
            "COUPON_NOT_ACTIVE",
        )

    def test_coupon_is_valid_only_during_campaign_month(self):
        campaign_df = build_campaign_dataframe()

        result = validate_coupon(
            campaign_df=campaign_df,
            coupon_code="ABC123",
            customer_id="CUST000001",
            item_purchased="Socks",
            reference_date="2026-10-01",
        )

        self.assertFalse(
            result["valid"]
        )

        self.assertEqual(
            result["reason"],
            "WRONG_CAMPAIGN_MONTH",
        )

    def test_coupon_is_valid_on_last_day_of_campaign_month(self):
        campaign_df = build_campaign_dataframe()

        result = validate_coupon(
            campaign_df=campaign_df,
            coupon_code="ABC123",
            customer_id="CUST000001",
            item_purchased="Socks",
            reference_date="2026-09-30",
        )

        self.assertTrue(
            result["valid"]
        )

    def test_product_must_be_in_campaign_recommendations(self):
        campaign_df = build_campaign_dataframe()

        result = validate_coupon(
            campaign_df=campaign_df,
            coupon_code="ABC123",
            customer_id="CUST000001",
            item_purchased="Watch",
            reference_date="2026-09-10",
        )

        self.assertFalse(
            result["valid"]
        )

        self.assertEqual(
            result["reason"],
            "PRODUCT_NOT_ELIGIBLE",
        )

    def test_product_comparison_is_case_insensitive(self):
        campaign_df = build_campaign_dataframe()

        result = validate_coupon(
            campaign_df=campaign_df,
            coupon_code="ABC123",
            customer_id="CUST000001",
            item_purchased="sOcKs",
            reference_date="2026-09-10",
        )

        self.assertTrue(
            result["valid"]
        )

    def test_coupon_validation_does_not_depend_on_quantity(self):
        campaign_df = build_campaign_dataframe()

        campaign_df["Quantity"] = [
            50,
            1,
            10,
        ]

        result = validate_coupon(
            campaign_df=campaign_df,
            coupon_code="ABC123",
            customer_id="CUST000001",
            item_purchased="Socks",
            reference_date="2026-09-10",
        )

        self.assertTrue(
            result["valid"]
        )

        self.assertEqual(
            result["discount_percent"],
            10,
        )


class TestCouponRedemption(unittest.TestCase):

    def test_active_coupon_is_marked_redeemed(self):
        campaign_df = build_campaign_dataframe()

        updated_df = redeem_coupon(
            campaign_df=campaign_df,
            coupon_code="ABC123",
            customer_id="CUST000001",
            transaction_id="TXN-20260910-001",
            redeemed_at="2026-09-10 10:30:00",
        )

        row = updated_df[
            updated_df["Coupon Code"] == "ABC123"
        ].iloc[0]

        self.assertEqual(
            row["Coupon Status"],
            "REDEEMED",
        )

        self.assertEqual(
            row["Coupon Transaction ID"],
            "TXN-20260910-001",
        )

        self.assertEqual(
            str(row["Coupon Redeemed At"]),
            "2026-09-10 10:30:00",
        )

    def test_redeeming_coupon_does_not_modify_other_customers(self):
        campaign_df = build_campaign_dataframe()

        updated_df = redeem_coupon(
            campaign_df=campaign_df,
            coupon_code="ABC123",
            customer_id="CUST000001",
            transaction_id="TXN-20260910-001",
            redeemed_at="2026-09-10 10:30:00",
        )

        other_customer = updated_df[
            updated_df["Customer ID"] == "CUST000002"
        ].iloc[0]

        self.assertEqual(
            other_customer["Coupon Status"],
            "ACTIVE",
        )

        self.assertTrue(
            pd.isna(
                other_customer["Coupon Transaction ID"]
            )
        )

    def test_coupon_cannot_be_redeemed_twice(self):
        campaign_df = build_campaign_dataframe()

        first_redemption = redeem_coupon(
            campaign_df=campaign_df,
            coupon_code="ABC123",
            customer_id="CUST000001",
            transaction_id="TXN-20260910-001",
            redeemed_at="2026-09-10 10:30:00",
        )

        with self.assertRaises(
            ValueError
        ):
            redeem_coupon(
                campaign_df=first_redemption,
                coupon_code="ABC123",
                customer_id="CUST000001",
                transaction_id="TXN-20260910-002",
                redeemed_at="2026-09-10 11:00:00",
            )

    def test_coupon_cannot_be_redeemed_by_different_customer(self):
        campaign_df = build_campaign_dataframe()

        with self.assertRaises(
            ValueError
        ):
            redeem_coupon(
                campaign_df=campaign_df,
                coupon_code="ABC123",
                customer_id="CUST000002",
                transaction_id="TXN-20260910-001",
                redeemed_at="2026-09-10 10:30:00",
            )

    def test_original_dataframe_is_not_modified_in_place(self):
        campaign_df = build_campaign_dataframe()

        redeem_coupon(
            campaign_df=campaign_df,
            coupon_code="ABC123",
            customer_id="CUST000001",
            transaction_id="TXN-20260910-001",
            redeemed_at="2026-09-10 10:30:00",
        )

        original_row = campaign_df[
            campaign_df["Coupon Code"] == "ABC123"
        ].iloc[0]

        self.assertEqual(
            original_row["Coupon Status"],
            "ACTIVE",
        )

        self.assertTrue(
            pd.isna(
                original_row["Coupon Transaction ID"]
            )
        )


if __name__ == "__main__":
    unittest.main()