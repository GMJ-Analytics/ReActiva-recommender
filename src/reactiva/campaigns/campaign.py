from __future__ import annotations

import ast
import base64
import hashlib
import logging
import random
from datetime import date, datetime

import pandas as pd


logger = logging.getLogger(__name__)


# ============================================================
# CAMPAIGN CONSTANTS
# ============================================================

CAMPAIGN_ID_PREFIX = "REACTIVA"
DEFAULT_DISCOUNT_PERCENT = 10
SCHEDULE_DAYS = (1, 2, 3, 4, 5)

STATUS_PENDING = "PENDING"
STATUS_SENT = "SENT"
STATUS_FAILED = "FAILED"
STATUS_CANCELLED_REACTIVATED = "CANCELLED_REACTIVATED"

COUPON_ACTIVE = "ACTIVE"
COUPON_REDEEMED = "REDEEMED"
COUPON_EXPIRED = "EXPIRED"


CAMPAIGN_COLUMNS = [
    "Campaign ID",
    "Campaign Month",
    "Customer ID",
    "Customer Full Name",
    "Customer Email",
    "Recommendation 1",
    "Recommendation 2",
    "Recommendation 3",
    "Discount Percent",
    "Coupon Code",
    "Scheduled Day",
    "Status",
    "Retry Count",
    "Last Attempt At",
    "Sent At",
    "Reactivated At",
    "Coupon Status",
    "Coupon Redeemed At",
    "Coupon Transaction ID",
    "Last Error",
]


CUSTOMER_STATUS_COLUMNS = [
    "Customer ID",
    "Opt Out",
    "Opt Out Date",
    "Campaigns In Current Cycle",
    "Skip Next Campaign",
    "Last Reactivation Date",
    "Last Campaign Month",
]


EXCLUSION_COLUMNS = [
    "Campaign ID",
    "Campaign Month",
    "Customer ID",
    "Reason",
]


REQUIRED_RECOMMENDATION_COLUMNS = [
    "Customer ID",
    "Customer Name",
    "Customer Email",
    "Recommendations",
]


# ============================================================
# DATE / CAMPAIGN HELPERS
# ============================================================

def normalize_campaign_date(
    campaign_date=None,
) -> pd.Timestamp:
    """
    Converts the provided campaign date to a normalized pandas Timestamp.

    If no date is provided, the current local date is used.
    """
    if campaign_date is None:
        return pd.Timestamp.today().normalize()

    parsed = pd.Timestamp(campaign_date)

    if pd.isna(parsed):
        raise ValueError("campaign_date is invalid")

    return parsed.normalize()


def build_campaign_id(
    campaign_date=None,
) -> str:
    """
    Builds the monthly campaign identifier.

    Example:
        REACTIVA-2026-09
    """
    reference_date = normalize_campaign_date(
        campaign_date
    )

    return (
        f"{CAMPAIGN_ID_PREFIX}-"
        f"{reference_date.strftime('%Y-%m')}"
    )


# ============================================================
# VALUE NORMALIZATION
# ============================================================

def _as_bool(value) -> bool:
    """
    Normalizes common boolean representations used by CSV files.
    """
    if isinstance(value, bool):
        return value

    if value is None or pd.isna(value):
        return False

    normalized = str(value).strip().casefold()

    return normalized in {
        "true",
        "1",
        "yes",
        "y",
        "si",
        "sí",
    }


def _normalize_customer_id(value) -> str | None:
    """
    Returns a clean Customer ID or None when it is missing.
    """
    if value is None or pd.isna(value):
        return None

    customer_id = str(value).strip()

    if not customer_id:
        return None

    return customer_id


# ============================================================
# RECOMMENDATION NORMALIZATION
# ============================================================

def normalize_recommendations(
    value,
    max_items: int = 3,
) -> list[str]:
    """
    Converts the recommender output to a clean ranked list.

    Accepted examples:
        ["Shirt", "Shoes"]
        "['Shirt', 'Shoes']"
        "Shirt"

    Ranking is preserved and duplicates are removed.
    """
    if value is None:
        return []

    if isinstance(value, float) and pd.isna(value):
        return []

    parsed = value

    if isinstance(value, str):
        text = value.strip()

        if not text:
            return []

        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            parsed = [text]

    if isinstance(parsed, str):
        parsed = [parsed]

    if not isinstance(
        parsed,
        (list, tuple, set),
    ):
        parsed = [parsed]

    recommendations = []
    seen = set()

    for item in parsed:
        if item is None:
            continue

        if isinstance(item, float) and pd.isna(item):
            continue

        item_text = str(item).strip()

        if not item_text:
            continue

        normalized = item_text.casefold()

        if normalized in seen:
            continue

        seen.add(normalized)
        recommendations.append(item_text)

        if len(recommendations) >= max_items:
            break

    return recommendations


# ============================================================
# CUSTOMER STATUS
# ============================================================

def _build_status_lookup(
    customer_status_df: pd.DataFrame | None,
) -> dict[str, dict]:
    """
    Builds a Customer ID -> status dictionary.

    Missing status information means the customer has no previous
    campaign restriction.
    """
    if (
        customer_status_df is None
        or customer_status_df.empty
    ):
        return {}

    if "Customer ID" not in customer_status_df.columns:
        raise ValueError(
            "customer_campaign_status.csv is missing "
            "'Customer ID'"
        )

    status_df = customer_status_df.copy()

    status_df["Customer ID"] = (
        status_df["Customer ID"]
        .astype(str)
        .str.strip()
    )

    status_df = status_df[
        status_df["Customer ID"] != ""
    ].drop_duplicates(
        subset=["Customer ID"],
        keep="last",
    )

    return {
        row["Customer ID"]: row.to_dict()
        for _, row in status_df.iterrows()
    }


def customer_exclusion_reason(
    customer_id: str,
    status_lookup: dict[str, dict],
) -> str | None:
    """
    Returns the reason why a customer cannot enter the current campaign.

    Only campaign state restrictions are evaluated here.
    Recommendation availability is evaluated separately.
    """
    status = status_lookup.get(
        customer_id
    )

    if status is None:
        return None

    if _as_bool(
        status.get("Opt Out", False)
    ):
        return "OPT_OUT"

    if _as_bool(
        status.get("Skip Next Campaign", False)
    ):
        return "PAUSED_AFTER_3_SENT"

    return None


# ============================================================
# COUPONS
# ============================================================

def _coupon_candidate(
    campaign_id: str,
    customer_id: str,
    counter: int = 0,
) -> str:
    """
    Generates a deterministic six-character uppercase coupon candidate.

    Determinism helps preserve idempotency if campaign generation
    is retried.
    """
    source = (
        f"{campaign_id}|"
        f"{customer_id}|"
        f"{counter}"
    ).encode("utf-8")

    digest = hashlib.sha256(
        source
    ).digest()

    encoded = (
        base64.b32encode(digest)
        .decode("ascii")
        .rstrip("=")
    )

    return encoded[:6]


def generate_unique_coupon(
    campaign_id: str,
    customer_id: str,
    used_codes: set[str],
) -> str:
    """
    Generates a unique six-character alphanumeric coupon.

    In the unlikely event of a collision, another deterministic
    candidate is generated.
    """
    counter = 0

    while True:
        code = _coupon_candidate(
            campaign_id=campaign_id,
            customer_id=customer_id,
            counter=counter,
        )

        if code not in used_codes:
            used_codes.add(code)
            return code

        counter += 1


# ============================================================
# BALANCED DAY ASSIGNMENT
# ============================================================

def assign_balanced_days(
    customer_ids: list[str],
    campaign_id: str,
) -> dict[str, int]:
    """
    Randomly distributes customers across days 1 to 5 while keeping
    group sizes as balanced as possible.

    The random order is seeded with Campaign ID so a retry produces
    the same assignment.
    """
    shuffled = list(customer_ids)

    random_generator = random.Random(
        campaign_id
    )

    random_generator.shuffle(
        shuffled
    )

    assignments = {}

    for index, customer_id in enumerate(
        shuffled
    ):
        scheduled_day = SCHEDULE_DAYS[
            index % len(SCHEDULE_DAYS)
        ]

        assignments[
            customer_id
        ] = scheduled_day

    return assignments


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_recommendation_matrix(
    recommendations_df: pd.DataFrame,
) -> None:
    """
    Validates the minimum schema required to create a campaign.
    """
    if recommendations_df is None:
        raise ValueError(
            "recommendations_df cannot be None"
        )

    missing_columns = [
        column
        for column in REQUIRED_RECOMMENDATION_COLUMNS
        if column not in recommendations_df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Recommendation matrix is missing required columns: "
            f"{missing_columns}"
        )


# ============================================================
# IDEMPOTENCY
# ============================================================

def get_existing_campaign(
    existing_active_df: pd.DataFrame | None,
    campaign_id: str,
) -> pd.DataFrame | None:
    """
    Returns the already-created campaign when campaign_active.csv
    contains the same Campaign ID.

    If campaign_active.csv belongs to another month, generation is
    blocked. The previous active campaign must be archived before
    creating the new one.
    """
    if (
        existing_active_df is None
        or existing_active_df.empty
    ):
        return None

    if "Campaign ID" not in existing_active_df.columns:
        raise ValueError(
            "Existing campaign file is missing 'Campaign ID'"
        )

    campaign_ids = {
        str(value).strip()
        for value in existing_active_df[
            "Campaign ID"
        ].dropna()
        if str(value).strip()
    }

    if not campaign_ids:
        return None

    if campaign_ids == {campaign_id}:
        logger.info(
            "Campaign %s already exists. "
            "Existing active campaign will be reused.",
            campaign_id,
        )

        return existing_active_df.copy()

    raise RuntimeError(
        "campaign_active.csv contains a previous campaign. "
        "It must be archived successfully before creating "
        f"{campaign_id}."
    )


# ============================================================
# CAMPAIGN BUILD
# ============================================================

def build_monthly_campaign(
    recommendations_df: pd.DataFrame,
    customer_status_df: pd.DataFrame | None = None,
    existing_active_df: pd.DataFrame | None = None,
    campaign_date=None,
    discount_percent: int = DEFAULT_DISCOUNT_PERCENT,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Builds the monthly ReActiva campaign.

    Rules implemented:
    - one campaign per month;
    - idempotent Campaign ID;
    - OPT_OUT customers are excluded;
    - customers in their mandatory pause month are excluded;
    - customers without a valid recommendation are excluded;
    - recommendation ranking is preserved;
    - maximum three recommended products;
    - 10 percent discount by default;
    - one unique six-character coupon per customer;
    - customers are randomly but evenly distributed across days 1-5;
    - all newly-created rows start as PENDING.

    Returns:
        campaign_df
        exclusions_df
    """
    validate_recommendation_matrix(
        recommendations_df
    )

    reference_date = normalize_campaign_date(
        campaign_date
    )

    campaign_month = (
        reference_date.strftime("%Y-%m")
    )

    campaign_id = build_campaign_id(
        reference_date
    )

    existing_campaign = get_existing_campaign(
        existing_active_df=existing_active_df,
        campaign_id=campaign_id,
    )

    if existing_campaign is not None:
        return (
            existing_campaign,
            pd.DataFrame(
                columns=EXCLUSION_COLUMNS
            ),
        )

    if discount_percent <= 0 or discount_percent > 100:
        raise ValueError(
            "discount_percent must be between 1 and 100"
        )

    recommendation_data = (
        recommendations_df.copy()
    )

    # If the recommender has multiple executions for the same customer,
    # keep the most recent result.
    if "Date" in recommendation_data.columns:
        recommendation_data["Date"] = pd.to_datetime(
            recommendation_data["Date"],
            errors="coerce",
        )

        recommendation_data = (
            recommendation_data
            .sort_values(
                "Date",
                na_position="first",
            )
        )

    recommendation_data = (
        recommendation_data
        .drop_duplicates(
            subset=["Customer ID"],
            keep="last",
        )
    )

    status_lookup = _build_status_lookup(
        customer_status_df
    )

    candidates = []
    exclusions = []

    for _, row in recommendation_data.iterrows():

        customer_id = _normalize_customer_id(
            row.get("Customer ID")
        )

        if customer_id is None:
            exclusions.append(
                {
                    "Campaign ID": campaign_id,
                    "Campaign Month": campaign_month,
                    "Customer ID": None,
                    "Reason": "INVALID_CUSTOMER_ID",
                }
            )
            continue

        exclusion_reason = customer_exclusion_reason(
            customer_id=customer_id,
            status_lookup=status_lookup,
        )

        if exclusion_reason is not None:
            exclusions.append(
                {
                    "Campaign ID": campaign_id,
                    "Campaign Month": campaign_month,
                    "Customer ID": customer_id,
                    "Reason": exclusion_reason,
                }
            )
            continue

        recommendations = normalize_recommendations(
            row.get("Recommendations"),
            max_items=3,
        )

        if not recommendations:
            exclusions.append(
                {
                    "Campaign ID": campaign_id,
                    "Campaign Month": campaign_month,
                    "Customer ID": customer_id,
                    "Reason": "NO_VALID_RECOMMENDATION",
                }
            )
            continue

        candidates.append(
            {
                "Customer ID": customer_id,
                "Customer Full Name": row.get(
                    "Customer Name"
                ),
                "Customer Email": row.get(
                    "Customer Email"
                ),
                "Recommendations": recommendations,
            }
        )

    if not candidates:
        logger.warning(
            "Campaign %s has no eligible customers",
            campaign_id,
        )

        return (
            pd.DataFrame(
                columns=CAMPAIGN_COLUMNS
            ),
            pd.DataFrame(
                exclusions,
                columns=EXCLUSION_COLUMNS,
            ),
        )

    customer_ids = [
        candidate["Customer ID"]
        for candidate in candidates
    ]

    day_assignments = assign_balanced_days(
        customer_ids=customer_ids,
        campaign_id=campaign_id,
    )

    used_coupon_codes = set()
    campaign_rows = []

    for candidate in candidates:

        customer_id = candidate[
            "Customer ID"
        ]

        recommendations = candidate[
            "Recommendations"
        ]

        padded_recommendations = (
            recommendations + [None, None, None]
        )[:3]

        coupon_code = generate_unique_coupon(
            campaign_id=campaign_id,
            customer_id=customer_id,
            used_codes=used_coupon_codes,
        )

        campaign_rows.append(
            {
                "Campaign ID": campaign_id,
                "Campaign Month": campaign_month,
                "Customer ID": customer_id,
                "Customer Full Name": candidate[
                    "Customer Full Name"
                ],
                "Customer Email": candidate[
                    "Customer Email"
                ],
                "Recommendation 1":
                    padded_recommendations[0],
                "Recommendation 2":
                    padded_recommendations[1],
                "Recommendation 3":
                    padded_recommendations[2],
                "Discount Percent":
                    discount_percent,
                "Coupon Code":
                    coupon_code,
                "Scheduled Day":
                    day_assignments[customer_id],
                "Status":
                    STATUS_PENDING,
                "Retry Count":
                    0,
                "Last Attempt At":
                    None,
                "Sent At":
                    None,
                "Reactivated At":
                    None,
                "Coupon Status":
                    COUPON_ACTIVE,
                "Coupon Redeemed At":
                    None,
                "Coupon Transaction ID":
                    None,
                "Last Error":
                    None,
            }
        )

    campaign_df = pd.DataFrame(
        campaign_rows,
        columns=CAMPAIGN_COLUMNS,
    )

    # Operational ordering only. The balanced assignment itself was
    # generated before this sort.
    campaign_df = (
        campaign_df
        .sort_values(
            ["Scheduled Day", "Customer ID"]
        )
        .reset_index(drop=True)
    )

    exclusions_df = pd.DataFrame(
        exclusions,
        columns=EXCLUSION_COLUMNS,
    )

    logger.info(
        "Campaign %s built eligible=%s excluded=%s",
        campaign_id,
        len(campaign_df),
        len(exclusions_df),
    )

    return campaign_df, exclusions_df