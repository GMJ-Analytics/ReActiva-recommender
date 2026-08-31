from __future__ import annotations

import logging

import pandas as pd

from reactiva.config import (
    DATASET_URI,
    S3_BUCKET,
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
    write_csv_to_s3,
)
from reactiva.recommender.recommender import (
    recommend_user_based_inactive_customers,
)


logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

CONSOLIDATED_TRANSACTIONS_KEY = (
    "csv_transactions_consolidated/"
    "consolidated_transactions.csv"
)

MONTHLY_RECOMMENDATION_PREFIX = (
    "recommender/monthly"
)

INACTIVITY_DAYS = 270
TOP_RECOMMENDATIONS = 3


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


def build_monthly_recommendation_key(
    reference_date=None,
) -> str:
    """
    Builds the S3 key for the monthly recommendation output.

    Example:
        recommender/monthly/recommendations_2026-09.csv
    """
    reference_date = normalize_reference_date(
        reference_date
    )

    campaign_month = (
        reference_date.strftime(
            "%Y-%m"
        )
    )

    return (
        f"{MONTHLY_RECOMMENDATION_PREFIX}/"
        f"recommendations_{campaign_month}.csv"
    )


# ============================================================
# DATA SOURCES
# ============================================================

def load_historical_transactions(
    dataset_uri: str = DATASET_URI,
) -> pd.DataFrame:
    """
    Loads the historical dataset configured for ReActiva.
    """
    if not dataset_uri:
        raise ValueError(
            "dataset_uri is required"
        )

    historical_df = pd.read_csv(
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
        - set(historical_df.columns)
    )

    if missing_columns:
        raise ValueError(
            "Historical dataset is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    historical_df["Purchase Date"] = (
        pd.to_datetime(
            historical_df["Purchase Date"],
            errors="coerce",
        )
    )

    if historical_df[
        "Purchase Date"
    ].isna().any():
        raise ValueError(
            "Historical dataset contains invalid Purchase Date values"
        )

    return historical_df


def load_consolidated_transactions(
    bucket: str,
    s3_client=None,
) -> pd.DataFrame:
    """
    Loads the transactions produced by the consolidation Lambda.

    The consolidated file may legitimately be empty during a first run.
    """
    return read_csv_from_s3(
        bucket=bucket,
        key=CONSOLIDATED_TRANSACTIONS_KEY,
        s3_client=s3_client,
    )


def build_operational_transactions_view(
    historical_df: pd.DataFrame,
    consolidated_df: pd.DataFrame | None,
) -> pd.DataFrame:
    """
    Combines historical and newly consolidated transactions.

    The historical dataset remains untouched in S3. This function creates
    only an in-memory operational view for recommendation/campaign logic.

    Transaction ID is used to prevent the same purchase from appearing
    twice if it is present in both sources.
    """
    if historical_df is None or historical_df.empty:
        raise ValueError(
            "Historical dataset cannot be empty"
        )

    historical = historical_df.copy()

    historical["Purchase Date"] = (
        pd.to_datetime(
            historical["Purchase Date"],
            errors="coerce",
        )
    )

    if (
        consolidated_df is None
        or consolidated_df.empty
    ):
        combined = historical.copy()

    else:
        consolidated = consolidated_df.copy()

        historical_columns = list(
            historical.columns
        )

        missing_in_consolidated = [
            column
            for column in historical_columns
            if column not in consolidated.columns
        ]

        extra_in_consolidated = [
            column
            for column in consolidated.columns
            if column not in historical.columns
        ]

        if (
            missing_in_consolidated
            or extra_in_consolidated
        ):
            raise ValueError(
                "Historical and consolidated schemas do not match. "
                f"Missing in consolidated: {missing_in_consolidated}. "
                f"Extra in consolidated: {extra_in_consolidated}."
            )

        consolidated = consolidated[
            historical_columns
        ].copy()

        consolidated["Purchase Date"] = (
            pd.to_datetime(
                consolidated["Purchase Date"],
                errors="coerce",
            )
        )

        if consolidated[
            "Purchase Date"
        ].isna().any():
            raise ValueError(
                "Consolidated transactions contain invalid "
                "Purchase Date values"
            )

        combined = pd.concat(
            [
                historical,
                consolidated,
            ],
            ignore_index=True,
        )

    if "Transaction ID" in combined.columns:
        combined = (
            combined
            .drop_duplicates(
                subset=["Transaction ID"],
                keep="last",
            )
        )

    combined = (
        combined
        .sort_values(
            "Purchase Date"
        )
        .reset_index(drop=True)
    )

    return combined


def load_operational_transactions(
    bucket: str = S3_BUCKET,
    dataset_uri: str = DATASET_URI,
    s3_client=None,
) -> pd.DataFrame:
    """
    Convenience wrapper that loads both sources and builds
    the complete operational transaction view.
    """
    historical_df = (
        load_historical_transactions(
            dataset_uri=dataset_uri
        )
    )

    consolidated_df = (
        load_consolidated_transactions(
            bucket=bucket,
            s3_client=s3_client,
        )
    )

    return build_operational_transactions_view(
        historical_df=historical_df,
        consolidated_df=consolidated_df,
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
# MONTHLY GBOOST JOB
# ============================================================

def generate_monthly_recommendations(
    reference_date=None,
    bucket: str = S3_BUCKET,
    dataset_uri: str = DATASET_URI,
    s3_client=None,
) -> dict:
    """
    Executes the monthly GBoost recommender and persists the
    recommendation output for the current month.

    One GBoost execution trains once and predicts recommendations
    for all inactive customers in the same run.
    """
    reference_date = (
        normalize_reference_date(
            reference_date
        )
    )

    campaign_month = (
        reference_date.strftime(
            "%Y-%m"
        )
    )

    transactions_df = (
        load_operational_transactions(
            bucket=bucket,
            dataset_uri=dataset_uri,
            s3_client=s3_client,
        )
    )

    recommendations_df = (
        recommend_user_based_inactive_customers(
            transactions_df,
            k=TOP_RECOMMENDATIONS,
            inactivity_days=INACTIVITY_DAYS,
            persist_predictions=False,
            reference_date=reference_date,
        )
    )

    if (
        recommendations_df is None
        or recommendations_df.empty
    ):
        raise RuntimeError(
            "GBoost did not generate valid monthly recommendations"
        )

    recommendations_df = (
        recommendations_df.copy()
    )

    recommendations_df[
        "Campaign Month"
    ] = campaign_month

    recommendations_df[
        "Reference Date"
    ] = reference_date.strftime(
        "%Y-%m-%d"
    )

    validate_monthly_recommendations(
        recommendations_df=recommendations_df,
        reference_date=reference_date,
    )

    recommendations_key = (
        build_monthly_recommendation_key(
            reference_date
        )
    )

    # Critical S3 write:
    # storage.py performs up to five attempts.
    write_csv_to_s3(
        df=recommendations_df,
        bucket=bucket,
        key=recommendations_key,
        s3_client=s3_client,
    )

    # Read-after-write verification.
    verified_df = read_csv_from_s3(
        bucket=bucket,
        key=recommendations_key,
        expected_columns=MONTHLY_RECOMMENDATION_REQUIRED_COLUMNS,
        s3_client=s3_client,
    )

    if len(
        verified_df
    ) != len(
        recommendations_df
    ):
        raise RuntimeError(
            "Monthly recommendation verification "
            "failed after S3 write"
        )

    validate_monthly_recommendations(
        recommendations_df=verified_df,
        reference_date=reference_date,
    )

    logger.info(
        "Monthly recommendations generated "
        "month=%s customers=%s key=%s",
        campaign_month,
        len(verified_df),
        recommendations_key,
    )

    return {
        "campaign_month": campaign_month,
        "reference_date": reference_date,
        "recommendations_key": recommendations_key,
        "recommendations": verified_df,
        "transactions": transactions_df,
    }


# ============================================================
# LOAD CURRENT MONTH RECOMMENDATIONS
# ============================================================

def load_monthly_recommendations(
    reference_date=None,
    bucket: str = S3_BUCKET,
    s3_client=None,
) -> pd.DataFrame:
    """
    Loads ONLY the recommendation output corresponding to the
    requested month.

    A missing or invalid output aborts campaign generation.
    Previous-month recommendations are never reused.
    """
    reference_date = (
        normalize_reference_date(
            reference_date
        )
    )

    recommendations_key = (
        build_monthly_recommendation_key(
            reference_date
        )
    )

    recommendations_df = read_csv_from_s3(
        bucket=bucket,
        key=recommendations_key,
        expected_columns=MONTHLY_RECOMMENDATION_REQUIRED_COLUMNS,
        s3_client=s3_client,
    )

    if recommendations_df.empty:
        raise RuntimeError(
            "Recommendations for the current month "
            f"do not exist: {recommendations_key}"
        )

    validate_monthly_recommendations(
        recommendations_df=recommendations_df,
        reference_date=reference_date,
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
    Creates the monthly campaign using ONLY the recommendation
    output generated for the requested month.

    Previous-month recommendation outputs are never reused.

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