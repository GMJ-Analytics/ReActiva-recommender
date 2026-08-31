from __future__ import annotations

import logging

import pandas as pd

from reactiva.campaigns.campaign import (
    CUSTOMER_STATUS_COLUMNS,
    STATUS_CANCELLED_REACTIVATED,
    STATUS_SENT,
)


logger = logging.getLogger(__name__)


# ============================================================
# HELPERS
# ============================================================

def _as_bool(value) -> bool:
    """
    Normalizes boolean values that may come from CSV files.
    """
    if isinstance(value, bool):
        return value

    if value is None or pd.isna(value):
        return False

    return str(value).strip().casefold() in {
        "true",
        "1",
        "yes",
        "y",
        "si",
        "sí",
    }


def _as_int(value, default: int = 0) -> int:
    """
    Converts CSV numeric values safely to int.
    """
    if value is None or pd.isna(value):
        return default

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _normalize_customer_id(value) -> str | None:
    """
    Returns a clean Customer ID or None when missing.
    """
    if value is None or pd.isna(value):
        return None

    customer_id = str(value).strip()

    return customer_id or None


def _normalize_timestamp(value):
    """
    Converts a value to an ISO-like timestamp string.

    None/NaN values remain None.
    """
    if value is None or pd.isna(value):
        return None

    parsed = pd.to_datetime(
        value,
        errors="coerce",
    )

    if pd.isna(parsed):
        return None

    return parsed.isoformat()


# ============================================================
# STATUS TABLE
# ============================================================

def empty_customer_status() -> pd.DataFrame:
    """
    Returns an empty customer campaign status table
    with the canonical schema.
    """
    return pd.DataFrame(
        columns=CUSTOMER_STATUS_COLUMNS
    )


def normalize_customer_status(
    customer_status_df: pd.DataFrame | None,
) -> pd.DataFrame:
    """
    Normalizes the persistent customer status table.

    Missing columns are added with safe defaults so older or
    first-run files can be upgraded without breaking the campaign.
    """
    if (
        customer_status_df is None
        or customer_status_df.empty
    ):
        return empty_customer_status()

    status_df = customer_status_df.copy()

    defaults = {
        "Customer ID": None,
        "Opt Out": False,
        "Opt Out Date": None,
        "Campaigns In Current Cycle": 0,
        "Skip Next Campaign": False,
        "Last Reactivation Date": None,
        "Last Campaign Month": None,
    }

    for column in CUSTOMER_STATUS_COLUMNS:
        if column not in status_df.columns:
            status_df[column] = defaults[column]

    status_df = status_df[
        CUSTOMER_STATUS_COLUMNS
    ].copy()

    status_df["Customer ID"] = (
        status_df["Customer ID"]
        .map(_normalize_customer_id)
    )

    status_df = status_df[
        status_df["Customer ID"].notna()
    ]

    status_df["Opt Out"] = (
        status_df["Opt Out"]
        .map(_as_bool)
    )

    status_df["Skip Next Campaign"] = (
        status_df["Skip Next Campaign"]
        .map(_as_bool)
    )

    status_df["Campaigns In Current Cycle"] = (
        status_df["Campaigns In Current Cycle"]
        .map(_as_int)
    )

    status_df = (
        status_df
        .drop_duplicates(
            subset=["Customer ID"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    return status_df


def ensure_customer_status_rows(
    customer_status_df: pd.DataFrame | None,
    customer_ids,
) -> pd.DataFrame:
    """
    Ensures that every supplied customer has a row in the
    persistent status table.
    """
    status_df = normalize_customer_status(
        customer_status_df
    )

    existing_ids = set(
        status_df["Customer ID"]
        .dropna()
        .astype(str)
    )

    new_rows = []

    for value in customer_ids:
        customer_id = _normalize_customer_id(
            value
        )

        if (
            customer_id is None
            or customer_id in existing_ids
        ):
            continue

        new_rows.append(
            {
                "Customer ID": customer_id,
                "Opt Out": False,
                "Opt Out Date": None,
                "Campaigns In Current Cycle": 0,
                "Skip Next Campaign": False,
                "Last Reactivation Date": None,
                "Last Campaign Month": None,
            }
        )

        existing_ids.add(
            customer_id
        )

    if new_rows:
        status_df = pd.concat(
            [
                status_df,
                pd.DataFrame(new_rows),
            ],
            ignore_index=True,
        )

    return status_df[
        CUSTOMER_STATUS_COLUMNS
    ]


# ============================================================
# OPT OUT
# ============================================================

def set_customer_opt_out(
    customer_status_df: pd.DataFrame | None,
    customer_id: str,
    opt_out_date=None,
) -> pd.DataFrame:
    """
    Marks a customer as OPT_OUT.

    A later purchase may reset this state according to the
    ReActiva campaign rules.
    """
    normalized_id = _normalize_customer_id(
        customer_id
    )

    if normalized_id is None:
        raise ValueError(
            "customer_id is required"
        )

    status_df = ensure_customer_status_rows(
        customer_status_df,
        [normalized_id],
    )

    if opt_out_date is None:
        opt_out_date = pd.Timestamp.now()

    mask = (
        status_df["Customer ID"]
        == normalized_id
    )

    status_df.loc[
        mask,
        "Opt Out",
    ] = True

    status_df.loc[
        mask,
        "Opt Out Date",
    ] = _normalize_timestamp(
        opt_out_date
    )

    logger.info(
        "Customer %s marked OPT_OUT",
        normalized_id,
    )

    return status_df


# ============================================================
# NEW PURCHASE / REACTIVATION RESET
# ============================================================

def reset_customer_after_purchase(
    customer_status_df: pd.DataFrame | None,
    customer_id: str,
    purchase_date=None,
) -> pd.DataFrame:
    """
    Resets the campaign cycle after a new purchase.

    Business rule:
    - Campaigns In Current Cycle -> 0
    - Skip Next Campaign -> False
    - OPT_OUT -> False
    - Opt Out Date -> cleared
    - Last Reactivation Date -> purchase date

    Last Campaign Month is intentionally preserved for
    idempotency/audit purposes.
    """
    normalized_id = _normalize_customer_id(
        customer_id
    )

    if normalized_id is None:
        raise ValueError(
            "customer_id is required"
        )

    status_df = ensure_customer_status_rows(
        customer_status_df,
        [normalized_id],
    )

    if purchase_date is None:
        purchase_date = pd.Timestamp.now()

    mask = (
        status_df["Customer ID"]
        == normalized_id
    )

    status_df.loc[
        mask,
        "Opt Out",
    ] = False

    status_df.loc[
        mask,
        "Opt Out Date",
    ] = None

    status_df.loc[
        mask,
        "Campaigns In Current Cycle",
    ] = 0

    status_df.loc[
        mask,
        "Skip Next Campaign",
    ] = False

    status_df.loc[
        mask,
        "Last Reactivation Date",
    ] = _normalize_timestamp(
        purchase_date
    )

    logger.info(
        "Campaign state reset after purchase customer=%s",
        normalized_id,
    )

    return status_df


def reset_customers_after_purchases(
    customer_status_df: pd.DataFrame | None,
    purchases_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Resets campaign state for customers contained in a DataFrame
    of NEW purchases.

    Required columns:
        Customer ID
        Purchase Date

    The caller is responsible for supplying only purchases that are
    considered new for campaign-state processing.
    """
    if purchases_df is None or purchases_df.empty:
        return normalize_customer_status(
            customer_status_df
        )

    required_columns = {
        "Customer ID",
        "Purchase Date",
    }

    missing_columns = (
        required_columns
        - set(purchases_df.columns)
    )

    if missing_columns:
        raise ValueError(
            "Purchases DataFrame is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    purchases = purchases_df.copy()

    purchases["Purchase Date"] = pd.to_datetime(
        purchases["Purchase Date"],
        errors="coerce",
    )

    purchases = (
        purchases
        .dropna(
            subset=[
                "Customer ID",
                "Purchase Date",
            ]
        )
        .sort_values(
            "Purchase Date"
        )
        .drop_duplicates(
            subset=["Customer ID"],
            keep="last",
        )
    )

    status_df = normalize_customer_status(
        customer_status_df
    )

    for _, row in purchases.iterrows():
        status_df = reset_customer_after_purchase(
            customer_status_df=status_df,
            customer_id=row["Customer ID"],
            purchase_date=row["Purchase Date"],
        )

    return status_df


# ============================================================
# CAMPAIGN OUTCOMES
# ============================================================

def apply_campaign_outcomes(
    customer_status_df: pd.DataFrame | None,
    campaign_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Applies final campaign outcomes to customer state.

    Rules:
    - only SENT increments the campaign cycle;
    - FAILED and PENDING do not increment it;
    - CANCELLED_REACTIVATED resets the cycle;
    - after the third SENT campaign, Skip Next Campaign becomes True;
    - the same campaign month cannot be counted twice.

    campaign_df must contain:
        Customer ID
        Campaign Month
        Status
    """
    if campaign_df is None or campaign_df.empty:
        return normalize_customer_status(
            customer_status_df
        )

    required_columns = {
        "Customer ID",
        "Campaign Month",
        "Status",
    }

    missing_columns = (
        required_columns
        - set(campaign_df.columns)
    )

    if missing_columns:
        raise ValueError(
            "Campaign DataFrame is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    status_df = ensure_customer_status_rows(
        customer_status_df,
        campaign_df["Customer ID"].tolist(),
    )

    campaign_data = (
        campaign_df
        .drop_duplicates(
            subset=[
                "Campaign Month",
                "Customer ID",
            ],
            keep="last",
        )
        .copy()
    )

    for _, campaign_row in campaign_data.iterrows():

        customer_id = _normalize_customer_id(
            campaign_row.get(
                "Customer ID"
            )
        )

        if customer_id is None:
            continue

        campaign_month = str(
            campaign_row.get(
                "Campaign Month"
            )
        ).strip()

        campaign_status = str(
            campaign_row.get(
                "Status"
            )
        ).strip().upper()

        mask = (
            status_df["Customer ID"]
            == customer_id
        )

        if campaign_status == STATUS_CANCELLED_REACTIVATED:

            reactivated_at = (
                campaign_row.get(
                    "Reactivated At"
                )
                if "Reactivated At"
                in campaign_row.index
                else None
            )

            status_df = reset_customer_after_purchase(
                customer_status_df=status_df,
                customer_id=customer_id,
                purchase_date=(
                    reactivated_at
                    if reactivated_at is not None
                    and not pd.isna(reactivated_at)
                    else pd.Timestamp.now()
                ),
            )

            continue

        if campaign_status != STATUS_SENT:
            continue

        last_campaign_month = (
            status_df.loc[
                mask,
                "Last Campaign Month",
            ]
            .iloc[0]
        )

        # Idempotency:
        # do not count the same monthly campaign twice.
        if (
            last_campaign_month is not None
            and not pd.isna(last_campaign_month)
            and str(last_campaign_month).strip()
            == campaign_month
        ):
            continue

        current_count = _as_int(
            status_df.loc[
                mask,
                "Campaigns In Current Cycle",
            ].iloc[0]
        )

        new_count = current_count + 1

        status_df.loc[
            mask,
            "Campaigns In Current Cycle",
        ] = new_count

        status_df.loc[
            mask,
            "Last Campaign Month",
        ] = campaign_month

        if new_count >= 3:
            status_df.loc[
                mask,
                "Skip Next Campaign",
            ] = True

            logger.info(
                "Customer %s reached 3 SENT campaigns "
                "and must skip the next campaign",
                customer_id,
            )

    return status_df


# ============================================================
# CONSUME MANDATORY PAUSE
# ============================================================

def consume_campaign_pause(
    customer_status_df: pd.DataFrame | None,
    paused_customer_ids,
) -> pd.DataFrame:
    """
    Consumes the mandatory one-campaign pause.

    This function must be called only AFTER the new monthly campaign
    has been persisted successfully.

    Customers excluded because of PAUSED_AFTER_3_SENT become eligible
    again for the following month:
        Campaigns In Current Cycle -> 0
        Skip Next Campaign -> False
    """
    status_df = normalize_customer_status(
        customer_status_df
    )

    if status_df.empty:
        return status_df

    paused_ids = {
        customer_id
        for customer_id in (
            _normalize_customer_id(value)
            for value in paused_customer_ids
        )
        if customer_id is not None
    }

    if not paused_ids:
        return status_df

    mask = (
        status_df["Customer ID"]
        .isin(paused_ids)
    )

    status_df.loc[
        mask,
        "Campaigns In Current Cycle",
    ] = 0

    status_df.loc[
        mask,
        "Skip Next Campaign",
    ] = False

    logger.info(
        "Mandatory campaign pause consumed customers=%s",
        int(mask.sum()),
    )

    return status_df