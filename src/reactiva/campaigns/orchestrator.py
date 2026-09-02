from __future__ import annotations

import logging

import pandas as pd

from reactiva.config import (
    DATASET_URI,
    S3_BUCKET,
    S3_PREDICTIONS_KEY,
)
from reactiva.campaigns.campaign import (
    CAMPAIGN_COLUMNS,
)
from reactiva.campaigns.service import (
    create_monthly_campaign,
)
from reactiva.campaigns.storage import (
    CAMPAIGN_ACTIVE_KEY,
    read_csv_from_s3,
)


logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

INACTIVITY_DAYS = 270


RECOMMENDER_OUTPUT_REQUIRED_COLUMNS = [
    "Customer Name",
    "Customer Email",
    "Customer ID",
    "Location",
    "Current Season",
    "Recommendations",
    "Date",
]


MONTHLY_RECOMMENDATION_REQUIRED_COLUMNS = [
    "Customer Name",
    "Customer Email",
    "Customer ID",
    "Location",
    "Current Season",
    "Recommendations",
    "Date",
    "Campaign Month",
    "Reference Date",
]


# ============================================================
# DATE HELPERS
# ============================================================

def normalize_reference_date(
    reference_date=None,
) -> pd.Timestamp:
    """
    Returns the business reference date used by the monthly process.
    """
    if reference_date is None:
        return pd.Timestamp.today().normalize()

    parsed = pd.Timestamp(
        reference_date
    )

    if pd.isna(parsed):
        raise ValueError(
            "reference_date is invalid"
        )

    return parsed.normalize()


# ============================================================
# DATA SOURCES
# ============================================================

def load_canonical_transactions(
    dataset_uri: str = DATASET_URI,
) -> pd.DataFrame:
    """
    Loads the accumulated canonical ReActiva transaction dataset.

    The consolidation Lambda already incorporates new transactions
    into this canonical source and resolves duplicate Transaction ID
    values before overwriting it.

    Campaign services therefore consume this single source of truth
    and must not concatenate a separate consolidated dataset.
    """
    if not dataset_uri:
        raise ValueError(
            "dataset_uri is required"
        )

    canonical_df = pd.read_csv(
        dataset_uri
    )

    required_columns = {
        "Transaction ID",
        "Customer ID",
        "Purchase Date",
        "Category",
        "Item Purchased",
    }

    missing_columns = (
        required_columns
        - set(canonical_df.columns)
    )

    if missing_columns:
        raise ValueError(
            "Canonical dataset is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    canonical_df["Purchase Date"] = (
        pd.to_datetime(
            canonical_df["Purchase Date"],
            errors="coerce",
        )
    )

    if canonical_df[
        "Purchase Date"
    ].isna().any():
        raise ValueError(
            "Canonical dataset contains invalid Purchase Date values"
        )

    return canonical_df


def load_operational_transactions(
    bucket: str = S3_BUCKET,
    dataset_uri: str = DATASET_URI,
    s3_client=None,
) -> pd.DataFrame:
    """
    Loads the complete operational transaction view from the
    accumulated canonical ReActiva dataset.

    `bucket` and `s3_client` remain in the public signature for
    compatibility with existing campaign callers and tests, but
    transaction history is now obtained exclusively from DATASET_URI.
    """
    return load_canonical_transactions(
        dataset_uri=dataset_uri
    )


# ============================================================
# REACTIVATION DETECTION
# ============================================================

def find_reactivated_previous_campaign_purchases(
    transactions_df: pd.DataFrame,
    previous_campaign_df: pd.DataFrame | None,
    reference_date=None,
    inactivity_days: int = INACTIVITY_DAYS,
) -> pd.DataFrame:
    """
    Finds confirmed purchases that reset campaign state.

    Business rule:
    a customer who participated in the previous active campaign
    and is no longer inactive for at least `inactivity_days`
    is considered reactivated.

    The result contains only:
        Customer ID
        Purchase Date

    These rows can safely be supplied to
    reset_customers_after_purchases() through create_monthly_campaign().

    Important:
    exactly `inactivity_days` without a purchase is still considered
    inactive, so reactivation requires:

        Last Purchase Date > reference_date - inactivity_days
    """
    empty_result = pd.DataFrame(
        columns=[
            "Customer ID",
            "Purchase Date",
        ]
    )

    if (
        previous_campaign_df is None
        or previous_campaign_df.empty
    ):
        return empty_result

    if (
        transactions_df is None
        or transactions_df.empty
    ):
        return empty_result

    required_transaction_columns = {
        "Customer ID",
        "Purchase Date",
    }

    missing_transaction_columns = (
        required_transaction_columns
        - set(transactions_df.columns)
    )

    if missing_transaction_columns:
        raise ValueError(
            "Transactions DataFrame is missing required columns: "
            f"{sorted(missing_transaction_columns)}"
        )

    if (
        "Customer ID"
        not in previous_campaign_df.columns
    ):
        raise ValueError(
            "Previous campaign is missing 'Customer ID'"
        )

    reference_date = (
        normalize_reference_date(
            reference_date
        )
    )

    cutoff_date = (
        reference_date
        - pd.Timedelta(
            days=inactivity_days
        )
    )

    previous_customer_ids = (
        previous_campaign_df[
            "Customer ID"
        ]
        .dropna()
        .astype(str)
        .str.strip()
    )

    previous_customer_ids = {
        customer_id
        for customer_id
        in previous_customer_ids
        if customer_id
    }

    if not previous_customer_ids:
        return empty_result

    transactions = (
        transactions_df[
            [
                "Customer ID",
                "Purchase Date",
            ]
        ]
        .copy()
    )

    transactions = transactions.dropna(
        subset=[
            "Customer ID",
            "Purchase Date",
        ]
    )

    transactions[
        "Customer ID"
    ] = (
        transactions[
            "Customer ID"
        ]
        .astype(str)
        .str.strip()
    )

    transactions[
        "Purchase Date"
    ] = pd.to_datetime(
        transactions[
            "Purchase Date"
        ],
        errors="coerce",
    )

    transactions = transactions.dropna(
        subset=[
            "Purchase Date",
        ]
    )

    # Future purchases must never influence a monthly execution.
    transactions = transactions[
        transactions[
            "Purchase Date"
        ]
        <= reference_date
    ].copy()

    transactions = transactions[
        transactions[
            "Customer ID"
        ].isin(
            previous_customer_ids
        )
    ].copy()

    if transactions.empty:
        return empty_result

    latest_purchases = (
        transactions
        .sort_values(
            "Purchase Date"
        )
        .drop_duplicates(
            subset=[
                "Customer ID",
            ],
            keep="last",
        )
    )

    reactivated_purchases = (
        latest_purchases[
            latest_purchases[
                "Purchase Date"
            ]
            > cutoff_date
        ]
        [
            [
                "Customer ID",
                "Purchase Date",
            ]
        ]
        .reset_index(
            drop=True
        )
    )

    logger.info(
        "Previous campaign reactivations detected "
        "customers=%s reference_date=%s cutoff=%s",
        len(
            reactivated_purchases
        ),
        reference_date.strftime(
            "%Y-%m-%d"
        ),
        cutoff_date.strftime(
            "%Y-%m-%d"
        ),
    )

    return reactivated_purchases


# ============================================================
# MONTHLY RECOMMENDATION VALIDATION
# ============================================================

def validate_monthly_recommendations(
    recommendations_df: pd.DataFrame,
    reference_date,
) -> None:
    """
    Validates that the recommendation output belongs to the requested
    month and contains the fields needed by the campaign process.
    """
    if (
        recommendations_df is None
        or recommendations_df.empty
    ):
        raise RuntimeError(
            "Monthly recommendations are empty"
        )

    missing_columns = [
        column
        for column in MONTHLY_RECOMMENDATION_REQUIRED_COLUMNS
        if column not in recommendations_df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Monthly recommendations are missing "
            f"required columns: {missing_columns}"
        )

    reference_date = (
        normalize_reference_date(
            reference_date
        )
    )

    expected_month = (
        reference_date.strftime(
            "%Y-%m"
        )
    )

    recommendation_months = {
        str(value).strip()
        for value in recommendations_df[
            "Campaign Month"
        ].dropna()
        if str(value).strip()
    }

    if recommendation_months != {
        expected_month
    }:
        raise RuntimeError(
            "Monthly recommendations do not belong "
            f"exclusively to {expected_month}. "
            f"Found: {sorted(recommendation_months)}"
        )

    valid_recommendations = (
        recommendations_df["Recommendations"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    if (
        valid_recommendations
        .isin(
            [
                "",
                "[]",
            ]
        )
        .all()
    ):
        raise RuntimeError(
            "Monthly recommendation output contains "
            "no valid recommendations"
        )


# ============================================================
# LOAD CURRENT MONTH RECOMMENDATIONS
# ============================================================

def load_monthly_recommendations(
    reference_date=None,
    bucket: str = S3_BUCKET,
    s3_client=None,
) -> pd.DataFrame:
    """
    Loads the existing recommender output from S3 and selects only
    recommendations that belong to the requested campaign month.

    Campaigns do not execute or retrain the recommender.

    If a customer appears more than once during the selected month,
    only the most recent recommendation available up to the
    reference date is retained.
    """
    reference_date = (
        normalize_reference_date(
            reference_date
        )
    )

    if not S3_PREDICTIONS_KEY:
        raise ValueError(
            "S3_PREDICTIONS_KEY is required"
        )

    recommendations_df = read_csv_from_s3(
        bucket=bucket,
        key=S3_PREDICTIONS_KEY,
        expected_columns=RECOMMENDER_OUTPUT_REQUIRED_COLUMNS,
        s3_client=s3_client,
    )

    if (
        recommendations_df is None
        or recommendations_df.empty
    ):
        raise RuntimeError(
            "Recommender output is empty or unavailable"
        )

    recommendations_df = (
        recommendations_df.copy()
    )

    recommendations_df[
        "Date"
    ] = pd.to_datetime(
        recommendations_df[
            "Date"
        ],
        errors="coerce",
    )

    recommendations_df = (
        recommendations_df.dropna(
            subset=[
                "Customer ID",
                "Date",
            ]
        )
    )

    recommendations_df[
        "Customer ID"
    ] = (
        recommendations_df[
            "Customer ID"
        ]
        .astype(str)
        .str.strip()
    )

    recommendations_df = (
        recommendations_df[
            recommendations_df[
                "Customer ID"
            ]
            != ""
        ]
        .copy()
    )

    expected_month = (
        reference_date.strftime(
            "%Y-%m"
        )
    )

    recommendation_months = (
        recommendations_df[
            "Date"
        ]
        .dt.strftime(
            "%Y-%m"
        )
    )

    recommendation_dates = (
        recommendations_df[
            "Date"
        ]
        .dt.normalize()
    )

    recommendations_df = (
        recommendations_df[
            (
                recommendation_months
                == expected_month
            )
            & (
                recommendation_dates
                <= reference_date
            )
        ]
        .copy()
    )

    if recommendations_df.empty:
        raise RuntimeError(
            "Recommendations for the current month "
            f"do not exist in {S3_PREDICTIONS_KEY}"
        )

    recommendations_df = (
        recommendations_df
        .sort_values(
            "Date"
        )
        .drop_duplicates(
            subset=[
                "Customer ID",
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )

    recommendations_df[
        "Campaign Month"
    ] = expected_month

    recommendations_df[
        "Reference Date"
    ] = reference_date.strftime(
        "%Y-%m-%d"
    )

    recommendations_df = (
        recommendations_df[
            MONTHLY_RECOMMENDATION_REQUIRED_COLUMNS
        ]
        .copy()
    )

    validate_monthly_recommendations(
        recommendations_df=recommendations_df,
        reference_date=reference_date,
    )

    logger.info(
        "Current recommender output loaded "
        "month=%s customers=%s key=%s",
        expected_month,
        len(
            recommendations_df
        ),
        S3_PREDICTIONS_KEY,
    )

    return recommendations_df


# ============================================================
# MONTHLY CAMPAIGN JOB
# ============================================================

def create_campaign_from_monthly_recommendations(
    reference_date=None,
    bucket: str = S3_BUCKET,
    dataset_uri: str = DATASET_URI,
    s3_client=None,
) -> dict:
    """
    Creates the monthly campaign using the existing recommender
    output stored in S3.

    Campaigns never execute or retrain the recommendation model.

    Customers who participated in the previous active campaign
    and are now confirmed to have purchased within the 270-day
    inactivity window are treated as reactivated and their
    campaign cycle is reset before the new campaign is built.
    """
    reference_date = (
        normalize_reference_date(
            reference_date
        )
    )

    recommendations_df = (
        load_monthly_recommendations(
            reference_date=reference_date,
            bucket=bucket,
            s3_client=s3_client,
        )
    )

    previous_campaign_df = (
        read_csv_from_s3(
            bucket=bucket,
            key=CAMPAIGN_ACTIVE_KEY,
            expected_columns=CAMPAIGN_COLUMNS,
            s3_client=s3_client,
        )
    )

    transactions_df = (
        load_operational_transactions(
            bucket=bucket,
            dataset_uri=dataset_uri,
            s3_client=s3_client,
        )
    )

    reactivated_purchases_df = (
        find_reactivated_previous_campaign_purchases(
            transactions_df=transactions_df,
            previous_campaign_df=previous_campaign_df,
            reference_date=reference_date,
            inactivity_days=INACTIVITY_DAYS,
        )
    )

    result = create_monthly_campaign(
        recommendations_df=recommendations_df,
        bucket=bucket,
        campaign_date=reference_date,
        new_purchases_df=reactivated_purchases_df,
        s3_client=s3_client,
    )

    logger.info(
        "Monthly campaign job completed "
        "campaign=%s created=%s reactivated=%s",
        result["campaign_id"],
        result["created"],
        len(
            reactivated_purchases_df
        ),
    )

    return result