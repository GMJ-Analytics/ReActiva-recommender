import unittest

import numpy as np
import pandas as pd

from reactiva.campaigns.coupons import (
    redeem_coupon,
)


def build_s3_like_campaign_dataframe():
    """
    Reproduce el tipo de datos que genera pandas.read_csv()
    cuando las columnas de consumo del cupon estan totalmente vacias.

    En el CSV real de S3:
    - Coupon Redeemed At       -> float64
    - Coupon Transaction ID    -> float64
    """
    return pd.DataFrame(
        [
            {
                "Campaign ID":
                    "REACTIVA-2026-09",
                "Campaign Month":
                    "2026-09",
                "Customer ID":
                    "CUST000013",
                "Recommendation 1":
                    "Saree",
                "Recommendation 2":
                    "Kurta",
                "Recommendation 3":
                    "Jacket",
                "Discount Percent":
                    10,
                "Coupon Code":
                    "NTOHAZ",
                "Coupon Status":
                    "ACTIVE",
                "Coupon Redeemed At":
                    np.nan,
                "Coupon Transaction ID":
                    np.nan,
            }
        ]
    )


class TestCouponDtypesFromS3(
    unittest.TestCase
):

    def test_empty_coupon_tracking_columns_are_float_like_s3(self):
        campaign_df = (
            build_s3_like_campaign_dataframe()
        )

        self.assertEqual(
            str(
                campaign_df[
                    "Coupon Redeemed At"
                ].dtype
            ),
            "float64",
        )

        self.assertEqual(
            str(
                campaign_df[
                    "Coupon Transaction ID"
                ].dtype
            ),
            "float64",
        )

    def test_redeem_coupon_accepts_string_values_after_s3_read(self):
        campaign_df = (
            build_s3_like_campaign_dataframe()
        )

        updated_df = redeem_coupon(
            campaign_df=campaign_df,
            coupon_code="NTOHAZ",
            customer_id="CUST000013",
            transaction_id=(
                "TXN-20260831-"
                "D87A79AB206247D0A4CD1361887EAD8E"
            ),
            redeemed_at=(
                "2026-08-31T08:50:51.746173+05:30"
            ),
        )

        row = updated_df.iloc[
            0
        ]

        self.assertEqual(
            row[
                "Coupon Status"
            ],
            "REDEEMED",
        )

        self.assertEqual(
            row[
                "Coupon Redeemed At"
            ],
            "2026-08-31T08:50:51.746173+05:30",
        )

        self.assertEqual(
            row[
                "Coupon Transaction ID"
            ],
            (
                "TXN-20260831-"
                "D87A79AB206247D0A4CD1361887EAD8E"
            ),
        )

    def test_original_dataframe_keeps_float_tracking_columns(self):
        campaign_df = (
            build_s3_like_campaign_dataframe()
        )

        redeem_coupon(
            campaign_df=campaign_df,
            coupon_code="NTOHAZ",
            customer_id="CUST000013",
            transaction_id="TXN-TEST-001",
            redeemed_at="2026-09-01T09:00:00+05:30",
        )

        self.assertEqual(
            str(
                campaign_df[
                    "Coupon Redeemed At"
                ].dtype
            ),
            "float64",
        )

        self.assertEqual(
            str(
                campaign_df[
                    "Coupon Transaction ID"
                ].dtype
            ),
            "float64",
        )

        self.assertTrue(
            pd.isna(
                campaign_df.iloc[
                    0
                ][
                    "Coupon Redeemed At"
                ]
            )
        )

        self.assertTrue(
            pd.isna(
                campaign_df.iloc[
                    0
                ][
                    "Coupon Transaction ID"
                ]
            )
        )


if __name__ == "__main__":
    unittest.main()