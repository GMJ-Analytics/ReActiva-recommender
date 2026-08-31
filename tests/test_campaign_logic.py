import unittest

import pandas as pd

from reactiva.campaigns.campaign import (
    CAMPAIGN_COLUMNS,
    COUPON_ACTIVE,
    STATUS_CANCELLED_REACTIVATED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SENT,
    assign_balanced_days,
    build_campaign_id,
    build_monthly_campaign,
    generate_unique_coupon,
    normalize_recommendations,
)
from reactiva.campaigns.status import (
    apply_campaign_outcomes,
    consume_campaign_pause,
    ensure_customer_status_rows,
    reset_customer_after_purchase,
    set_customer_opt_out,
)


# ============================================================
# TEST HELPERS
# ============================================================


def build_recommendations_dataframe(
    count=1,
):
    """
    Creates a valid recommendation matrix for campaign tests.
    """
    rows = []

    for index in range(
        1,
        count + 1,
    ):
        rows.append(
            {
                "Customer ID":
                    f"CUST-{index:03d}",
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


def build_customer_status_row(
    customer_id="CUST-001",
    opt_out=False,
    campaigns_in_cycle=0,
    skip_next=False,
    last_reactivation=None,
    last_campaign_month=None,
):
    """
    Creates one customer status row using the canonical fields.
    """
    return {
        "Customer ID":
            customer_id,
        "Opt Out":
            opt_out,
        "Opt Out Date":
            (
                "2026-08-01T10:00:00"
                if opt_out
                else None
            ),
        "Campaigns In Current Cycle":
            campaigns_in_cycle,
        "Skip Next Campaign":
            skip_next,
        "Last Reactivation Date":
            last_reactivation,
        "Last Campaign Month":
            last_campaign_month,
    }


def build_campaign_outcome(
    customer_id,
    campaign_month,
    status,
    reactivated_at=None,
):
    """
    Creates the minimum campaign outcome required by status.py.
    """
    return {
        "Customer ID":
            customer_id,
        "Campaign Month":
            campaign_month,
        "Status":
            status,
        "Reactivated At":
            reactivated_at,
    }


# ============================================================
# RECOMMENDATION NORMALIZATION
# ============================================================


class TestRecommendationNormalization(
    unittest.TestCase
):

    def test_rank_is_preserved_and_duplicates_removed(self):
        result = normalize_recommendations(
            [
                "Shirt",
                "Sneakers",
                "shirt",
                "Backpack",
                "Hat",
            ],
            max_items=3,
        )

        self.assertEqual(
            result,
            [
                "Shirt",
                "Sneakers",
                "Backpack",
            ],
        )

    def test_string_representation_of_list_is_supported(self):
        result = normalize_recommendations(
            "['Shirt', 'Sneakers', 'Backpack']"
        )

        self.assertEqual(
            result,
            [
                "Shirt",
                "Sneakers",
                "Backpack",
            ],
        )

    def test_empty_recommendation_returns_empty_list(self):
        self.assertEqual(
            normalize_recommendations(""),
            [],
        )


# ============================================================
# CAMPAIGN ID
# ============================================================


class TestCampaignID(
    unittest.TestCase
):

    def test_campaign_id_is_monthly_and_deterministic(self):
        campaign_id = build_campaign_id(
            "2026-09-15"
        )

        self.assertEqual(
            campaign_id,
            "REACTIVA-2026-09",
        )


# ============================================================
# COUPON TESTS
# ============================================================


class TestCoupons(
    unittest.TestCase
):

    def test_coupon_has_six_uppercase_alphanumeric_characters(self):
        used_codes = set()

        coupon = generate_unique_coupon(
            campaign_id="REACTIVA-2026-09",
            customer_id="CUST-001",
            used_codes=used_codes,
        )

        self.assertEqual(
            len(coupon),
            6,
        )

        self.assertTrue(
            coupon.isalnum()
        )

        self.assertEqual(
            coupon,
            coupon.upper(),
        )

    def test_coupon_is_deterministic_for_same_campaign_and_customer(self):
        first = generate_unique_coupon(
            campaign_id="REACTIVA-2026-09",
            customer_id="CUST-001",
            used_codes=set(),
        )

        second = generate_unique_coupon(
            campaign_id="REACTIVA-2026-09",
            customer_id="CUST-001",
            used_codes=set(),
        )

        self.assertEqual(
            first,
            second,
        )

    def test_coupons_are_unique_inside_campaign(self):
        used_codes = set()

        coupons = [
            generate_unique_coupon(
                campaign_id="REACTIVA-2026-09",
                customer_id=f"CUST-{index:03d}",
                used_codes=used_codes,
            )
            for index in range(
                1,
                101,
            )
        ]

        self.assertEqual(
            len(coupons),
            len(set(coupons)),
        )


# ============================================================
# BALANCED DAY ASSIGNMENT
# ============================================================


class TestBalancedDays(
    unittest.TestCase
):

    def test_customers_are_distributed_only_between_days_1_and_5(self):
        customer_ids = [
            f"CUST-{index:03d}"
            for index in range(
                1,
                21,
            )
        ]

        assignments = assign_balanced_days(
            customer_ids=customer_ids,
            campaign_id="REACTIVA-2026-09",
        )

        self.assertEqual(
            set(assignments.values()),
            {
                1,
                2,
                3,
                4,
                5,
            },
        )

    def test_day_groups_are_balanced(self):
        customer_ids = [
            f"CUST-{index:03d}"
            for index in range(
                1,
                24,
            )
        ]

        assignments = assign_balanced_days(
            customer_ids=customer_ids,
            campaign_id="REACTIVA-2026-09",
        )

        counts = (
            pd.Series(
                list(
                    assignments.values()
                )
            )
            .value_counts()
        )

        self.assertLessEqual(
            int(
                counts.max()
                - counts.min()
            ),
            1,
        )

    def test_balanced_assignment_is_deterministic_for_campaign(self):
        customer_ids = [
            f"CUST-{index:03d}"
            for index in range(
                1,
                16,
            )
        ]

        first = assign_balanced_days(
            customer_ids=customer_ids,
            campaign_id="REACTIVA-2026-09",
        )

        second = assign_balanced_days(
            customer_ids=customer_ids,
            campaign_id="REACTIVA-2026-09",
        )

        self.assertEqual(
            first,
            second,
        )


# ============================================================
# MONTHLY CAMPAIGN BUILD
# ============================================================


class TestMonthlyCampaignBuild(
    unittest.TestCase
):

    def test_valid_customers_generate_pending_campaign(self):
        recommendations_df = (
            build_recommendations_dataframe(
                count=10
            )
        )

        campaign_df, exclusions_df = (
            build_monthly_campaign(
                recommendations_df=
                    recommendations_df,
                campaign_date=
                    "2026-09-01",
            )
        )

        self.assertEqual(
            len(campaign_df),
            10,
        )

        self.assertTrue(
            exclusions_df.empty
        )

        self.assertEqual(
            set(
                campaign_df[
                    "Campaign ID"
                ]
            ),
            {
                "REACTIVA-2026-09"
            },
        )

        self.assertEqual(
            set(
                campaign_df[
                    "Campaign Month"
                ]
            ),
            {
                "2026-09"
            },
        )

        self.assertEqual(
            set(
                campaign_df[
                    "Status"
                ]
            ),
            {
                STATUS_PENDING
            },
        )

        self.assertEqual(
            set(
                campaign_df[
                    "Coupon Status"
                ]
            ),
            {
                COUPON_ACTIVE
            },
        )

        self.assertEqual(
            set(
                campaign_df[
                    "Discount Percent"
                ]
            ),
            {
                10
            },
        )

    def test_campaign_contains_unique_coupons(self):
        recommendations_df = (
            build_recommendations_dataframe(
                count=50
            )
        )

        campaign_df, _ = (
            build_monthly_campaign(
                recommendations_df=
                    recommendations_df,
                campaign_date=
                    "2026-09-01",
            )
        )

        coupons = campaign_df[
            "Coupon Code"
        ].tolist()

        self.assertEqual(
            len(coupons),
            len(set(coupons)),
        )

        self.assertTrue(
            all(
                len(code) == 6
                for code in coupons
            )
        )

    def test_campaign_preserves_recommendation_ranking_and_maximum_three(self):
        recommendations_df = pd.DataFrame(
            [
                {
                    "Customer ID":
                        "CUST-001",
                    "Customer Name":
                        "Cliente Uno",
                    "Customer Email":
                        "uno@example.com",
                    "Recommendations": [
                        "Shirt",
                        "Sneakers",
                        "Backpack",
                        "Hat",
                    ],
                    "Date":
                        "2026-09-01",
                }
            ]
        )

        campaign_df, _ = (
            build_monthly_campaign(
                recommendations_df=
                    recommendations_df,
                campaign_date=
                    "2026-09-01",
            )
        )

        row = campaign_df.iloc[0]

        self.assertEqual(
            row["Recommendation 1"],
            "Shirt",
        )

        self.assertEqual(
            row["Recommendation 2"],
            "Sneakers",
        )

        self.assertEqual(
            row["Recommendation 3"],
            "Backpack",
        )

    def test_opt_out_customer_is_excluded(self):
        recommendations_df = (
            build_recommendations_dataframe()
        )

        status_df = pd.DataFrame(
            [
                build_customer_status_row(
                    customer_id="CUST-001",
                    opt_out=True,
                )
            ]
        )

        campaign_df, exclusions_df = (
            build_monthly_campaign(
                recommendations_df=
                    recommendations_df,
                customer_status_df=
                    status_df,
                campaign_date=
                    "2026-09-01",
            )
        )

        self.assertTrue(
            campaign_df.empty
        )

        self.assertEqual(
            exclusions_df.iloc[0][
                "Reason"
            ],
            "OPT_OUT",
        )

    def test_customer_paused_after_three_sent_is_excluded(self):
        recommendations_df = (
            build_recommendations_dataframe()
        )

        status_df = pd.DataFrame(
            [
                build_customer_status_row(
                    customer_id="CUST-001",
                    campaigns_in_cycle=3,
                    skip_next=True,
                    last_campaign_month=
                        "2026-08",
                )
            ]
        )

        campaign_df, exclusions_df = (
            build_monthly_campaign(
                recommendations_df=
                    recommendations_df,
                customer_status_df=
                    status_df,
                campaign_date=
                    "2026-09-01",
            )
        )

        self.assertTrue(
            campaign_df.empty
        )

        self.assertEqual(
            exclusions_df.iloc[0][
                "Reason"
            ],
            "PAUSED_AFTER_3_SENT",
        )

    def test_customer_without_recommendation_is_excluded(self):
        recommendations_df = pd.DataFrame(
            [
                {
                    "Customer ID":
                        "CUST-001",
                    "Customer Name":
                        "Cliente Uno",
                    "Customer Email":
                        "uno@example.com",
                    "Recommendations":
                        [],
                    "Date":
                        "2026-09-01",
                }
            ]
        )

        campaign_df, exclusions_df = (
            build_monthly_campaign(
                recommendations_df=
                    recommendations_df,
                campaign_date=
                    "2026-09-01",
            )
        )

        self.assertTrue(
            campaign_df.empty
        )

        self.assertEqual(
            exclusions_df.iloc[0][
                "Reason"
            ],
            "NO_VALID_RECOMMENDATION",
        )

    def test_invalid_customer_id_is_excluded(self):
        recommendations_df = pd.DataFrame(
            [
                {
                    "Customer ID":
                        None,
                    "Customer Name":
                        "Cliente Sin ID",
                    "Customer Email":
                        "cliente@example.com",
                    "Recommendations":
                        ["Shirt"],
                    "Date":
                        "2026-09-01",
                }
            ]
        )

        campaign_df, exclusions_df = (
            build_monthly_campaign(
                recommendations_df=
                    recommendations_df,
                campaign_date=
                    "2026-09-01",
            )
        )

        self.assertTrue(
            campaign_df.empty
        )

        self.assertEqual(
            exclusions_df.iloc[0][
                "Reason"
            ],
            "INVALID_CUSTOMER_ID",
        )

    def test_latest_recommendation_execution_is_used_for_duplicate_customer(self):
        recommendations_df = pd.DataFrame(
            [
                {
                    "Customer ID":
                        "CUST-001",
                    "Customer Name":
                        "Cliente Uno",
                    "Customer Email":
                        "uno@example.com",
                    "Recommendations":
                        ["Old Product"],
                    "Date":
                        "2026-09-01 00:01:00",
                },
                {
                    "Customer ID":
                        "CUST-001",
                    "Customer Name":
                        "Cliente Uno",
                    "Customer Email":
                        "uno@example.com",
                    "Recommendations":
                        ["New Product"],
                    "Date":
                        "2026-09-01 00:10:00",
                },
            ]
        )

        campaign_df, _ = (
            build_monthly_campaign(
                recommendations_df=
                    recommendations_df,
                campaign_date=
                    "2026-09-01",
            )
        )

        self.assertEqual(
            len(campaign_df),
            1,
        )

        self.assertEqual(
            campaign_df.iloc[0][
                "Recommendation 1"
            ],
            "New Product",
        )

    def test_same_month_existing_campaign_is_reused(self):
        recommendations_df = (
            build_recommendations_dataframe(
                count=5
            )
        )

        existing_campaign, _ = (
            build_monthly_campaign(
                recommendations_df=
                    recommendations_df,
                campaign_date=
                    "2026-09-01",
            )
        )

        different_recommendations = (
            build_recommendations_dataframe(
                count=2
            )
        )

        reused_campaign, exclusions = (
            build_monthly_campaign(
                recommendations_df=
                    different_recommendations,
                existing_active_df=
                    existing_campaign,
                campaign_date=
                    "2026-09-20",
            )
        )

        pd.testing.assert_frame_equal(
            reused_campaign,
            existing_campaign,
        )

        self.assertTrue(
            exclusions.empty
        )

    def test_previous_month_active_campaign_blocks_new_campaign(self):
        recommendations_df = (
            build_recommendations_dataframe()
        )

        previous_campaign, _ = (
            build_monthly_campaign(
                recommendations_df=
                    recommendations_df,
                campaign_date=
                    "2026-08-01",
            )
        )

        with self.assertRaises(
            RuntimeError
        ):
            build_monthly_campaign(
                recommendations_df=
                    recommendations_df,
                existing_active_df=
                    previous_campaign,
                campaign_date=
                    "2026-09-01",
            )


# ============================================================
# CUSTOMER STATUS / OPT OUT
# ============================================================


class TestCustomerStatus(
    unittest.TestCase
):

    def test_status_row_is_created_for_new_customer(self):
        status_df = (
            ensure_customer_status_rows(
                customer_status_df=None,
                customer_ids=[
                    "CUST-001"
                ],
            )
        )

        self.assertEqual(
            len(status_df),
            1,
        )

        row = status_df.iloc[0]

        self.assertEqual(
            row["Customer ID"],
            "CUST-001",
        )

        self.assertFalse(
            bool(row["Opt Out"])
        )

        self.assertEqual(
            int(
                row[
                    "Campaigns In Current Cycle"
                ]
            ),
            0,
        )

    def test_customer_can_be_marked_opt_out(self):
        status_df = (
            set_customer_opt_out(
                customer_status_df=None,
                customer_id="CUST-001",
                opt_out_date=
                    "2026-09-02 10:00:00",
            )
        )

        row = status_df.iloc[0]

        self.assertTrue(
            bool(row["Opt Out"])
        )

        self.assertEqual(
            row["Opt Out Date"],
            "2026-09-02T10:00:00",
        )

    def test_purchase_resets_opt_out_and_campaign_cycle(self):
        initial_status = pd.DataFrame(
            [
                build_customer_status_row(
                    customer_id="CUST-001",
                    opt_out=True,
                    campaigns_in_cycle=3,
                    skip_next=True,
                    last_campaign_month=
                        "2026-08",
                )
            ]
        )

        reset_status = (
            reset_customer_after_purchase(
                customer_status_df=
                    initial_status,
                customer_id=
                    "CUST-001",
                purchase_date=
                    "2026-09-15 14:30:00",
            )
        )

        row = reset_status.iloc[0]

        self.assertFalse(
            bool(row["Opt Out"])
        )

        self.assertFalse(
            bool(
                row[
                    "Skip Next Campaign"
                ]
            )
        )

        self.assertEqual(
            int(
                row[
                    "Campaigns In Current Cycle"
                ]
            ),
            0,
        )

        self.assertEqual(
            row[
                "Last Reactivation Date"
            ],
            "2026-09-15T14:30:00",
        )

        # Audit/idempotency field must be preserved.
        self.assertEqual(
            row["Last Campaign Month"],
            "2026-08",
        )


# ============================================================
# CAMPAIGN OUTCOME STATE MACHINE
# ============================================================


class TestCampaignOutcomes(
    unittest.TestCase
):

    def test_only_sent_campaign_increments_cycle(self):
        campaign_df = pd.DataFrame(
            [
                build_campaign_outcome(
                    customer_id=
                        "CUST-001",
                    campaign_month=
                        "2026-09",
                    status=
                        STATUS_SENT,
                ),
                build_campaign_outcome(
                    customer_id=
                        "CUST-002",
                    campaign_month=
                        "2026-09",
                    status=
                        STATUS_FAILED,
                ),
                build_campaign_outcome(
                    customer_id=
                        "CUST-003",
                    campaign_month=
                        "2026-09",
                    status=
                        STATUS_PENDING,
                ),
            ]
        )

        status_df = apply_campaign_outcomes(
            customer_status_df=None,
            campaign_df=campaign_df,
        )

        lookup = (
            status_df
            .set_index(
                "Customer ID"
            )
        )

        self.assertEqual(
            int(
                lookup.loc[
                    "CUST-001",
                    "Campaigns In Current Cycle",
                ]
            ),
            1,
        )

        self.assertEqual(
            int(
                lookup.loc[
                    "CUST-002",
                    "Campaigns In Current Cycle",
                ]
            ),
            0,
        )

        self.assertEqual(
            int(
                lookup.loc[
                    "CUST-003",
                    "Campaigns In Current Cycle",
                ]
            ),
            0,
        )

    def test_same_campaign_month_is_not_counted_twice(self):
        campaign_df = pd.DataFrame(
            [
                build_campaign_outcome(
                    customer_id=
                        "CUST-001",
                    campaign_month=
                        "2026-09",
                    status=
                        STATUS_SENT,
                )
            ]
        )

        first_status = (
            apply_campaign_outcomes(
                customer_status_df=None,
                campaign_df=campaign_df,
            )
        )

        second_status = (
            apply_campaign_outcomes(
                customer_status_df=
                    first_status,
                campaign_df=
                    campaign_df,
            )
        )

        row = second_status.iloc[0]

        self.assertEqual(
            int(
                row[
                    "Campaigns In Current Cycle"
                ]
            ),
            1,
        )

        self.assertEqual(
            row["Last Campaign Month"],
            "2026-09",
        )

    def test_three_sent_campaigns_activate_next_month_pause(self):
        campaign_df = pd.DataFrame(
            [
                build_campaign_outcome(
                    customer_id=
                        "CUST-001",
                    campaign_month=
                        "2026-06",
                    status=
                        STATUS_SENT,
                ),
                build_campaign_outcome(
                    customer_id=
                        "CUST-001",
                    campaign_month=
                        "2026-07",
                    status=
                        STATUS_SENT,
                ),
                build_campaign_outcome(
                    customer_id=
                        "CUST-001",
                    campaign_month=
                        "2026-08",
                    status=
                        STATUS_SENT,
                ),
            ]
        )

        status_df = apply_campaign_outcomes(
            customer_status_df=None,
            campaign_df=campaign_df,
        )

        row = status_df.iloc[0]

        self.assertEqual(
            int(
                row[
                    "Campaigns In Current Cycle"
                ]
            ),
            3,
        )

        self.assertTrue(
            bool(
                row[
                    "Skip Next Campaign"
                ]
            )
        )

        self.assertEqual(
            row[
                "Last Campaign Month"
            ],
            "2026-08",
        )

    def test_cancelled_reactivated_resets_campaign_cycle(self):
        initial_status = pd.DataFrame(
            [
                build_customer_status_row(
                    customer_id=
                        "CUST-001",
                    opt_out=True,
                    campaigns_in_cycle=2,
                    skip_next=False,
                    last_campaign_month=
                        "2026-08",
                )
            ]
        )

        campaign_df = pd.DataFrame(
            [
                build_campaign_outcome(
                    customer_id=
                        "CUST-001",
                    campaign_month=
                        "2026-09",
                    status=
                        STATUS_CANCELLED_REACTIVATED,
                    reactivated_at=
                        "2026-09-03 12:00:00",
                )
            ]
        )

        status_df = apply_campaign_outcomes(
            customer_status_df=
                initial_status,
            campaign_df=
                campaign_df,
        )

        row = status_df.iloc[0]

        self.assertEqual(
            int(
                row[
                    "Campaigns In Current Cycle"
                ]
            ),
            0,
        )

        self.assertFalse(
            bool(row["Opt Out"])
        )

        self.assertFalse(
            bool(
                row[
                    "Skip Next Campaign"
                ]
            )
        )

        self.assertEqual(
            row[
                "Last Reactivation Date"
            ],
            "2026-09-03T12:00:00",
        )

        self.assertEqual(
            row[
                "Last Campaign Month"
            ],
            "2026-08",
        )


# ============================================================
# MANDATORY PAUSE
# ============================================================


class TestCampaignPause(
    unittest.TestCase
):

    def test_pause_is_consumed_after_customer_skips_one_campaign(self):
        initial_status = pd.DataFrame(
            [
                build_customer_status_row(
                    customer_id=
                        "CUST-001",
                    campaigns_in_cycle=3,
                    skip_next=True,
                    last_campaign_month=
                        "2026-08",
                )
            ]
        )

        consumed = consume_campaign_pause(
            customer_status_df=
                initial_status,
            paused_customer_ids=[
                "CUST-001"
            ],
        )

        row = consumed.iloc[0]

        self.assertEqual(
            int(
                row[
                    "Campaigns In Current Cycle"
                ]
            ),
            0,
        )

        self.assertFalse(
            bool(
                row[
                    "Skip Next Campaign"
                ]
            )
        )

        self.assertEqual(
            row[
                "Last Campaign Month"
            ],
            "2026-08",
        )


if __name__ == "__main__":
    unittest.main()