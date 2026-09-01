from __future__ import annotations

import logging

import pandas as pd

from reactiva.campaigns.campaign import (
    CAMPAIGN_COLUMNS,
    EXCLUSION_COLUMNS,
    build_campaign_id,
    build_monthly_campaign,
)
from reactiva.campaigns.status import (
    apply_campaign_outcomes,
    consume_campaign_pause,
    ensure_customer_status_rows,
    normalize_customer_status,
    reset_customers_after_purchases,
)
from reactiva.campaigns.storage import (
    CAMPAIGN_ACTIVE_KEY,
    CAMPAIGN_HISTORY_KEY,
    CAMPAIGN_REPORTS_PREFIX,
    CUSTOMER_CAMPAIGN_STATUS_KEY,
    read_csv_from_s3,
    write_csv_to_s3,
)


logger = logging.getLogger(__name__)


# ============================================================
# HELPERS
# ============================================================

def _same_campaign(
    active_df: pd.DataFrame,
    campaign_id: str,
) -> bool:
    """
    Returns True when campaign_active.csv already belongs
    exclusively to the requested monthly campaign.
    """
    if active_df is None or active_df.empty:
        return False

    if "Campaign ID" not in active_df.columns:
        raise ValueError(
            "campaign_active.csv is missing 'Campaign ID'"
        )

    campaign_ids = {
        str(value).strip()
        for value in active_df["Campaign ID"].dropna()
        if str(value).strip()
    }

    return campaign_ids == {campaign_id}


def _append_campaign_history(
    history_df: pd.DataFrame,
    active_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Appends the previous active campaign to cumulative history.

    Duplicate Campaign ID + Customer ID combinations are removed
    so a retry cannot duplicate historical campaign rows.
    """
    if active_df is None or active_df.empty:
        return history_df.copy()

    if history_df is None or history_df.empty:
        combined = active_df.copy()
    else:
        combined = pd.concat(
            [
                history_df,
                active_df,
            ],
            ignore_index=True,
        )

    required_id_columns = {
        "Campaign ID",
        "Customer ID",
    }

    if required_id_columns.issubset(
        combined.columns
    ):
        combined = combined.drop_duplicates(
            subset=[
                "Campaign ID",
                "Customer ID",
            ],
            keep="last",
        )

    return combined.reset_index(
        drop=True
    )


def _write_and_verify_csv(
    df: pd.DataFrame,
    bucket: str,
    key: str,
    expected_columns: list[str] | None = None,
    s3_client=None,
) -> pd.DataFrame:
    """
    Performs a critical S3 write and then reads the object back.

    The write already includes the five-attempt retry policy from
    storage.py. Reading the file back prevents the campaign flow
    from continuing after an unverified critical persistence step.
    """
    write_csv_to_s3(
        df=df,
        bucket=bucket,
        key=key,
        s3_client=s3_client,
    )

    verified_df = read_csv_from_s3(
        bucket=bucket,
        key=key,
        expected_columns=expected_columns,
        s3_client=s3_client,
    )

    if len(verified_df) != len(df):
        raise RuntimeError(
            f"Verification failed for s3://{bucket}/{key}: "
            f"expected {len(df)} rows and found "
            f"{len(verified_df)}"
        )

    return verified_df


def _build_exclusion_report_key(
    campaign_id: str,
) -> str:
    """
    Returns the S3 key used for the monthly exclusion report.
    """
    return (
        f"{CAMPAIGN_REPORTS_PREFIX}/"
        f"{campaign_id}_exclusions.csv"
    )


# ============================================================
# MONTHLY CAMPAIGN SERVICE
# ============================================================

def create_monthly_campaign(
    recommendations_df: pd.DataFrame,
    bucket: str,
    campaign_date=None,
    new_purchases_df: pd.DataFrame | None = None,
    s3_client=None,
) -> dict:
    """
    Creates and persists the monthly ReActiva campaign.

    Main flow:

    1. Read active campaign, cumulative history and customer status.
    2. If the current monthly campaign already exists, reuse it.
    3. Apply outcomes from the previous active campaign to customer state.
    4. Apply new-purchase resets when supplied.
    5. Archive the previous active campaign into cumulative history.
    6. Verify history before replacing campaign_active.csv.
    7. Build the new monthly campaign.
    8. Persist and verify campaign_active.csv.
    9. Consume the mandatory pause only after the new campaign exists.
    10. Persist and verify customer_campaign_status.csv.
    11. Persist the monthly exclusions report.

    Returns a dictionary containing the resulting DataFrames and
    whether a new campaign was created.
    """
    campaign_id = build_campaign_id(
        campaign_date
    )

    active_df = read_csv_from_s3(
        bucket=bucket,
        key=CAMPAIGN_ACTIVE_KEY,
        expected_columns=CAMPAIGN_COLUMNS,
        s3_client=s3_client,
    )

    history_df = read_csv_from_s3(
        bucket=bucket,
        key=CAMPAIGN_HISTORY_KEY,
        expected_columns=CAMPAIGN_COLUMNS,
        s3_client=s3_client,
    )

    customer_status_df = read_csv_from_s3(
        bucket=bucket,
        key=CUSTOMER_CAMPAIGN_STATUS_KEY,
        s3_client=s3_client,
    )

    customer_status_df = normalize_customer_status(
        customer_status_df
    )

    # ========================================================
    # IDEMPOTENCY
    # ========================================================

    if _same_campaign(
        active_df=active_df,
        campaign_id=campaign_id,
    ):
        logger.info(
            "Campaign %s already exists. "
            "No new campaign will be generated.",
            campaign_id,
        )

        return {
            "created": False,
            "campaign_id": campaign_id,
            "campaign": active_df,
            "history": history_df,
            "customer_status": customer_status_df,
            "exclusions": pd.DataFrame(
                columns=EXCLUSION_COLUMNS
            ),
        }

    # ========================================================
    # PREVIOUS CAMPAIGN OUTCOMES
    # ========================================================

    if not active_df.empty:
        customer_status_df = apply_campaign_outcomes(
            customer_status_df=customer_status_df,
            campaign_df=active_df,
        )

    # ========================================================
    # NEW PURCHASES / REACTIVATIONS
    # ========================================================

    if (
        new_purchases_df is not None
        and not new_purchases_df.empty
    ):
        customer_status_df = reset_customers_after_purchases(
            customer_status_df=customer_status_df,
            purchases_df=new_purchases_df,
        )

    # ========================================================
    # ARCHIVE PREVIOUS ACTIVE CAMPAIGN
    # ========================================================

    if not active_df.empty:

        updated_history_df = _append_campaign_history(
            history_df=history_df,
            active_df=active_df,
        )

        # Critical rule:
        # history must be successfully saved and verified before
        # campaign_active.csv can be replaced.
        history_df = _write_and_verify_csv(
            df=updated_history_df,
            bucket=bucket,
            key=CAMPAIGN_HISTORY_KEY,
            expected_columns=CAMPAIGN_COLUMNS,
            s3_client=s3_client,
        )

        logger.info(
            "Previous campaign archived successfully "
            "before creating %s",
            campaign_id,
        )

    # ========================================================
    # BUILD NEW CAMPAIGN
    # ========================================================

    campaign_df, exclusions_df = build_monthly_campaign(
        recommendations_df=recommendations_df,
        customer_status_df=customer_status_df,
        existing_active_df=None,
        campaign_date=campaign_date,
    )

    if campaign_df.empty:
        raise RuntimeError(
            f"Campaign {campaign_id} has no eligible customers. "
            "campaign_active.csv was not replaced."
        )

    # Ensure every selected customer has persistent status.
    customer_status_df = ensure_customer_status_rows(
        customer_status_df=customer_status_df,
        customer_ids=campaign_df[
            "Customer ID"
        ].tolist(),
    )

    # ========================================================
    # WRITE NEW ACTIVE CAMPAIGN
    # ========================================================

    campaign_df = _write_and_verify_csv(
        df=campaign_df,
        bucket=bucket,
        key=CAMPAIGN_ACTIVE_KEY,
        expected_columns=CAMPAIGN_COLUMNS,
        s3_client=s3_client,
    )

    # ========================================================
    # CONSUME ONE-MONTH PAUSE
    # ========================================================

    paused_customer_ids = []

    if not exclusions_df.empty:
        paused_customer_ids = (
            exclusions_df.loc[
                exclusions_df["Reason"]
                == "PAUSED_AFTER_3_SENT",
                "Customer ID",
            ]
            .dropna()
            .astype(str)
            .tolist()
        )

    # Important:
    # the pause is consumed only now, after campaign_active.csv
    # has been written and verified successfully.
    customer_status_df = consume_campaign_pause(
        customer_status_df=customer_status_df,
        paused_customer_ids=paused_customer_ids,
    )

    # ========================================================
    # WRITE CUSTOMER STATUS
    # ========================================================

    customer_status_df = _write_and_verify_csv(
        df=customer_status_df,
        bucket=bucket,
        key=CUSTOMER_CAMPAIGN_STATUS_KEY,
        s3_client=s3_client,
    )

    # ========================================================
    # WRITE EXCLUSION REPORT
    # ========================================================

    if not exclusions_df.empty:

        exclusion_report_key = (
            _build_exclusion_report_key(
                campaign_id
            )
        )

        _write_and_verify_csv(
            df=exclusions_df,
            bucket=bucket,
            key=exclusion_report_key,
            expected_columns=EXCLUSION_COLUMNS,
            s3_client=s3_client,
        )

    logger.info(
        "Campaign %s persisted successfully "
        "customers=%s exclusions=%s",
        campaign_id,
        len(campaign_df),
        len(exclusions_df),
    )

    return {
        "created": True,
        "campaign_id": campaign_id,
        "campaign": campaign_df,
        "history": history_df,
        "customer_status": customer_status_df,
        "exclusions": exclusions_df,
    }