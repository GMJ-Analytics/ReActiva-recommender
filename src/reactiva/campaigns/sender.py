from __future__ import annotations

import hashlib
import hmac
import html
import logging
from datetime import timedelta
from urllib.parse import urlencode

import boto3
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError

from reactiva.campaigns.campaign import (
    CAMPAIGN_COLUMNS,
    STATUS_CANCELLED_REACTIVATED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SENT,
)


logger = logging.getLogger(__name__)


# ============================================================
# SEND CONSTANTS
# ============================================================

MAX_EMAIL_RETRIES = 3
RETRY_DELAY_HOURS = 24

EMAIL_SUBJECT = "Increíbles Ofertas"


# ============================================================
# HELPERS
# ============================================================

def _get_ses_client(
    ses_client=None,
    region_name: str | None = None,
):
    """
    Returns the provided SES client or creates a default boto3 client.
    """
    return ses_client or boto3.client(
        "ses",
        region_name=region_name,
    )


def _normalize_timestamp(value):
    """
    Converts a value to pandas Timestamp or returns None.
    """
    if value is None or pd.isna(value):
        return None

    parsed = pd.to_datetime(
        value,
        errors="coerce",
    )

    if pd.isna(parsed):
        return None

    return pd.Timestamp(parsed)


def _normalize_email(value) -> str | None:
    """
    Returns a clean email or None.
    """
    if value is None or pd.isna(value):
        return None

    email = str(value).strip()

    if (
        not email
        or "@" not in email
        or "." not in email.split("@")[-1]
    ):
        return None

    return email


def _recommendations_from_row(
    row: pd.Series,
) -> list[str]:
    """
    Reads Recommendation 1-3 preserving ranking.
    """
    recommendations = []

    for column in (
        "Recommendation 1",
        "Recommendation 2",
        "Recommendation 3",
    ):
        value = row.get(column)

        if value is None or pd.isna(value):
            continue

        item = str(value).strip()

        if item:
            recommendations.append(item)

    return recommendations


# ============================================================
# UNSUBSCRIBE LINK
# ============================================================

def build_unsubscribe_token(
    customer_id: str,
    campaign_id: str,
    secret: str,
) -> str:
    """
    Creates the HMAC token used by the unsubscribe Function URL.

    This algorithm must remain identical to the validation
    performed by the unsubscribe Lambda.
    """
    customer_id = str(
        customer_id
    ).strip()

    campaign_id = str(
        campaign_id
    ).strip()

    secret = str(
        secret
    ).strip()

    if not customer_id:
        raise ValueError(
            "customer_id is required"
        )

    if not campaign_id:
        raise ValueError(
            "campaign_id is required"
        )

    if not secret:
        raise ValueError(
            "unsubscribe secret is required"
        )

    message = (
        f"{campaign_id}:{customer_id}"
    ).encode(
        "utf-8"
    )

    return hmac.new(
        secret.encode(
            "utf-8"
        ),
        message,
        hashlib.sha256,
    ).hexdigest()


def build_unsubscribe_url(
    row: pd.Series,
    base_url: str,
    secret: str,
) -> str:
    """
    Builds the signed unsubscribe URL for one campaign customer.

    Example:

        https://<function-url>/
        ?customer_id=CUST000001
        &campaign_id=REACTIVA-2026-09
        &token=<HMAC>
    """
    base_url = str(
        base_url
    ).strip()

    if not base_url:
        raise ValueError(
            "unsubscribe base URL is required"
        )

    customer_id = str(
        row.get(
            "Customer ID",
            ""
        )
    ).strip()

    campaign_id = str(
        row.get(
            "Campaign ID",
            ""
        )
    ).strip()

    token = build_unsubscribe_token(
        customer_id=customer_id,
        campaign_id=campaign_id,
        secret=secret,
    )

    query_string = urlencode(
        {
            "customer_id":
                customer_id,
            "campaign_id":
                campaign_id,
            "token":
                token,
        }
    )

    separator = (
        "&"
        if "?" in base_url
        else "?"
    )

    return (
        f"{base_url}"
        f"{separator}"
        f"{query_string}"
    )


def build_unsubscribe_url_builder(
    base_url: str,
    secret: str,
):
    """
    Returns the callback expected by process_due_campaign_emails().

    The sender Lambda can create this callback once per execution
    and reuse it for every customer processed in the run.
    """
    base_url = str(
        base_url
    ).strip()

    secret = str(
        secret
    ).strip()

    if not base_url:
        raise ValueError(
            "unsubscribe base URL is required"
        )

    if not secret:
        raise ValueError(
            "unsubscribe secret is required"
        )

    def _builder(
        row: pd.Series,
    ) -> str:
        return build_unsubscribe_url(
            row=row,
            base_url=base_url,
            secret=secret,
        )

    return _builder


# ============================================================
# EMAIL CONTENT
# ============================================================

def build_email_html(
    row: pd.Series,
    store_name: str = "ReActiva",
    unsubscribe_url: str | None = None,
) -> str:
    """
    Builds the campaign email.

    The campaign keeps recommendation ranking and includes:
    - customer name;
    - 1 to 3 products;
    - 10 percent discount;
    - coupon;
    - end-of-month validity;
    - optional unsubscribe link.
    """
    customer_name = row.get(
        "Customer Full Name"
    )

    if customer_name is None or pd.isna(customer_name):
        customer_name = "cliente"

    customer_name = html.escape(
        str(customer_name).strip()
    )

    recommendations = _recommendations_from_row(
        row
    )

    recommendation_items = "".join(
        f"<li>{html.escape(item)}</li>"
        for item in recommendations
    )

    discount_percent = int(
        float(
            row.get(
                "Discount Percent",
                10,
            )
        )
    )

    coupon_code = html.escape(
        str(
            row.get(
                "Coupon Code",
                ""
            )
        ).strip()
    )

    campaign_month = str(
        row.get(
            "Campaign Month",
            ""
        )
    ).strip()

    try:
        month_start = pd.Timestamp(
            f"{campaign_month}-01"
        )

        month_end = (
            month_start
            + pd.offsets.MonthEnd(0)
        )

        valid_until = (
            month_end.strftime(
                "%d/%m/%Y"
            )
        )

    except Exception:
        valid_until = (
            "el último día del mes"
        )

    unsubscribe_html = ""

    if unsubscribe_url:
        safe_url = html.escape(
            unsubscribe_url,
            quote=True,
        )

        unsubscribe_html = (
            "<p style='margin-top:24px;font-size:12px;'>"
            f"<a href='{safe_url}'>"
            "No quiero recibir más ofertas"
            "</a>"
            "</p>"
        )

    return f"""
    <html>
      <body>
        <p>
          Hola {customer_name}, ¡te extrañamos!<br>
          Hace un tiempo que no te vemos y queremos acercarte
          una oferta pensada especialmente para vos:
        </p>

        <ul>
          {recommendation_items}
        </ul>

        <p>
          Tenés un <strong>{discount_percent}% OFF</strong>
          en estos productos.
        </p>

        <p>
          Tu código de descuento es:
          <strong>{coupon_code}</strong>
        </p>

        <p>
          El cupón es de un solo uso y es válido hasta el {valid_until}.
        </p>

        <p>
          ¡Te esperamos en {html.escape(store_name)}!
        </p>

        {unsubscribe_html}
      </body>
    </html>
    """


def build_email_text(
    row: pd.Series,
    store_name: str = "ReActiva",
    unsubscribe_url: str | None = None,
) -> str:
    """
    Plain-text fallback for the campaign email.
    """
    customer_name = row.get(
        "Customer Full Name"
    )

    if customer_name is None or pd.isna(customer_name):
        customer_name = "cliente"

    recommendations = _recommendations_from_row(
        row
    )

    recommendation_text = "\n".join(
        f"- {item}"
        for item in recommendations
    )

    discount_percent = int(
        float(
            row.get(
                "Discount Percent",
                10,
            )
        )
    )

    coupon_code = str(
        row.get(
            "Coupon Code",
            ""
        )
    ).strip()

    campaign_month = str(
        row.get(
            "Campaign Month",
            ""
        )
    ).strip()

    try:
        month_start = pd.Timestamp(
            f"{campaign_month}-01"
        )

        month_end = (
            month_start
            + pd.offsets.MonthEnd(0)
        )

        valid_until = (
            month_end.strftime(
                "%d/%m/%Y"
            )
        )

    except Exception:
        valid_until = (
            "el último día del mes"
        )

    unsubscribe_text = ""

    if unsubscribe_url:
        unsubscribe_text = (
            "\n\nSi no querés recibir más ofertas, "
            "podés darte de baja desde este enlace:\n"
            f"{unsubscribe_url}"
        )

    return (
        f"Hola {customer_name}, ¡te extrañamos!\n"
        "Hace un tiempo que no te vemos y queremos acercarte "
        "una oferta pensada especialmente para vos:\n\n"
        f"{recommendation_text}\n\n"
        f"Tenés un {discount_percent}% OFF en estos productos.\n"
        f"Tu código de descuento es: {coupon_code}\n"
        f"El cupón es de un solo uso y es válido hasta el {valid_until}.\n\n"
        f"¡Te esperamos en {store_name}!"
        f"{unsubscribe_text}"
    )


# ============================================================
# INACTIVITY CHECK
# ============================================================

def build_last_purchase_lookup(
    transactions_df: pd.DataFrame,
) -> dict[str, pd.Timestamp]:
    """
    Builds Customer ID -> latest Purchase Date.

    The DataFrame should contain the complete operational view
    required for the inactivity check.
    """
    if transactions_df is None or transactions_df.empty:
        return {}

    required_columns = {
        "Customer ID",
        "Purchase Date",
    }

    missing_columns = (
        required_columns
        - set(transactions_df.columns)
    )

    if missing_columns:
        raise ValueError(
            "Transactions DataFrame is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    data = transactions_df[
        [
            "Customer ID",
            "Purchase Date",
        ]
    ].copy()

    data["Purchase Date"] = pd.to_datetime(
        data["Purchase Date"],
        errors="coerce",
    )

    data = data.dropna(
        subset=[
            "Customer ID",
            "Purchase Date",
        ]
    )

    latest = (
        data
        .groupby("Customer ID")[
            "Purchase Date"
        ]
        .max()
    )

    return {
        str(customer_id).strip(): pd.Timestamp(
            purchase_date
        )
        for customer_id, purchase_date
        in latest.items()
    }


def customer_still_inactive(
    customer_id: str,
    last_purchase_lookup: dict[str, pd.Timestamp],
    reference_date,
    inactivity_days: int = 270,
) -> bool:
    """
    Returns True only when the customer still has at least
    inactivity_days without purchases.
    """
    last_purchase = last_purchase_lookup.get(
        str(customer_id).strip()
    )

    if last_purchase is None:
        return False

    reference_date = pd.Timestamp(
        reference_date
    ).normalize()

    cutoff = (
        reference_date
        - pd.Timedelta(
            days=inactivity_days
        )
    )

    return (
        last_purchase.normalize()
        <= cutoff
    )


# ============================================================
# RETRY SCHEDULING
# ============================================================

def row_is_due(
    row: pd.Series,
    execution_time,
) -> bool:
    """
    Determines whether a PENDING campaign row must be attempted now.

    Initial send:
        Scheduled Day equals current day of month.

    Retry:
        previous attempt failed and at least 24 hours elapsed.

    Retry Count represents failed retries already enabled:
        0 -> initial attempt not yet failed
        1 -> first retry due after 24h
        2 -> second retry
        3 -> third and final retry
    """
    if str(
        row.get("Status", "")
    ).strip().upper() != STATUS_PENDING:
        return False

    execution_time = pd.Timestamp(
        execution_time
    )

    retry_count = int(
        float(
            row.get(
                "Retry Count",
                0,
            )
            or 0
        )
    )

    last_attempt = _normalize_timestamp(
        row.get(
            "Last Attempt At"
        )
    )

    if last_attempt is None:
        scheduled_day = int(
            float(
                row.get(
                    "Scheduled Day"
                )
            )
        )

        return (
            execution_time.day
            == scheduled_day
        )

    if retry_count < 1 or retry_count > MAX_EMAIL_RETRIES:
        return False

    next_attempt_at = (
        last_attempt
        + timedelta(
            hours=RETRY_DELAY_HOURS
        )
    )

    return execution_time >= next_attempt_at


# ============================================================
# SES SEND
# ============================================================

def send_campaign_email(
    row: pd.Series,
    sender_email: str,
    store_name: str = "ReActiva",
    unsubscribe_url: str | None = None,
    ses_client=None,
    region_name: str | None = None,
) -> dict:
    """
    Sends one campaign email through Amazon SES.
    """
    recipient = _normalize_email(
        row.get(
            "Customer Email"
        )
    )

    if recipient is None:
        raise ValueError(
            "Customer email is invalid"
        )

    if not sender_email:
        raise ValueError(
            "sender_email is required"
        )

    client = _get_ses_client(
        ses_client=ses_client,
        region_name=region_name,
    )

    html_body = build_email_html(
        row=row,
        store_name=store_name,
        unsubscribe_url=unsubscribe_url,
    )

    text_body = build_email_text(
        row=row,
        store_name=store_name,
        unsubscribe_url=unsubscribe_url,
    )

    response = client.send_email(
        Source=sender_email,
        Destination={
            "ToAddresses": [
                recipient
            ]
        },
        Message={
            "Subject": {
                "Data": EMAIL_SUBJECT,
                "Charset": "UTF-8",
            },
            "Body": {
                "Html": {
                    "Data": html_body,
                    "Charset": "UTF-8",
                },
                "Text": {
                    "Data": text_body,
                    "Charset": "UTF-8",
                },
            },
        },
    )

    return response


# ============================================================
# DAILY SEND RUNNER
# ============================================================

def process_due_campaign_emails(
    campaign_df: pd.DataFrame,
    transactions_df: pd.DataFrame,
    sender_email: str,
    execution_time=None,
    inactivity_days: int = 270,
    store_name: str = "ReActiva",
    unsubscribe_url_builder=None,
    ses_client=None,
    region_name: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Processes emails due at the current execution time.

    Rules:
    - only PENDING rows can be attempted;
    - initial attempt happens on Scheduled Day;
    - before every attempt inactivity is checked again;
    - reactivated customers become CANCELLED_REACTIVATED;
    - successful SES send becomes SENT;
    - failed initial send may retry up to 3 times;
    - retries occur at least 24 hours apart;
    - after the final failed retry the status becomes FAILED;
    - invalid campaign/customer data fails immediately without retry.

    Returns:
        updated_campaign_df
        events_df
    """
    if campaign_df is None:
        raise ValueError(
            "campaign_df cannot be None"
        )

    if campaign_df.empty:
        return (
            campaign_df.copy(),
            pd.DataFrame(),
        )

    missing_columns = [
        column
        for column in CAMPAIGN_COLUMNS
        if column not in campaign_df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Campaign DataFrame is missing required columns: "
            f"{missing_columns}"
        )

    if execution_time is None:
        execution_time = pd.Timestamp.now()

    execution_time = pd.Timestamp(
        execution_time
    )

    updated = campaign_df.copy()

    last_purchase_lookup = (
        build_last_purchase_lookup(
            transactions_df
        )
    )

    events = []

    for index, row in updated.iterrows():

        if not row_is_due(
            row=row,
            execution_time=execution_time,
        ):
            continue

        customer_id = str(
            row["Customer ID"]
        ).strip()

        # ----------------------------------------------------
        # PRE-SEND REACTIVATION CHECK
        # ----------------------------------------------------

        if not customer_still_inactive(
            customer_id=customer_id,
            last_purchase_lookup=last_purchase_lookup,
            reference_date=execution_time,
            inactivity_days=inactivity_days,
        ):
            updated.at[
                index,
                "Status",
            ] = STATUS_CANCELLED_REACTIVATED

            updated.at[
                index,
                "Reactivated At",
            ] = execution_time.isoformat()

            updated.at[
                index,
                "Last Error",
            ] = None

            events.append(
                {
                    "Campaign ID":
                        row["Campaign ID"],
                    "Customer ID":
                        customer_id,
                    "Event":
                        STATUS_CANCELLED_REACTIVATED,
                    "At":
                        execution_time.isoformat(),
                    "Detail":
                        "Customer purchased before campaign send",
                }
            )

            continue

        # ----------------------------------------------------
        # UNSUBSCRIBE URL
        # ----------------------------------------------------

        unsubscribe_url = None

        if unsubscribe_url_builder is not None:
            unsubscribe_url = (
                unsubscribe_url_builder(
                    row
                )
            )

        # ----------------------------------------------------
        # SEND
        # ----------------------------------------------------

        try:
            response = send_campaign_email(
                row=row,
                sender_email=sender_email,
                store_name=store_name,
                unsubscribe_url=unsubscribe_url,
                ses_client=ses_client,
                region_name=region_name,
            )

            updated.at[
                index,
                "Status",
            ] = STATUS_SENT

            updated.at[
                index,
                "Last Attempt At",
            ] = execution_time.isoformat()

            updated.at[
                index,
                "Sent At",
            ] = execution_time.isoformat()

            updated.at[
                index,
                "Last Error",
            ] = None

            events.append(
                {
                    "Campaign ID":
                        row["Campaign ID"],
                    "Customer ID":
                        customer_id,
                    "Event":
                        STATUS_SENT,
                    "At":
                        execution_time.isoformat(),
                    "Detail":
                        response.get(
                            "MessageId"
                        ),
                }
            )

        except ValueError as error:

            # Invalid campaign/customer data is a definitive error.
            # Retrying after 24 hours would not solve it.
            updated.at[
                index,
                "Last Attempt At",
            ] = execution_time.isoformat()

            updated.at[
                index,
                "Last Error",
            ] = str(error)

            updated.at[
                index,
                "Status",
            ] = STATUS_FAILED

            events.append(
                {
                    "Campaign ID":
                        row["Campaign ID"],
                    "Customer ID":
                        customer_id,
                    "Event":
                        STATUS_FAILED,
                    "At":
                        execution_time.isoformat(),
                    "Detail":
                        str(error),
                }
            )

            logger.warning(
                "Campaign email definitive failure "
                "campaign=%s customer=%s error=%s",
                row["Campaign ID"],
                customer_id,
                error,
            )

        except (
            ClientError,
            BotoCoreError,
        ) as error:

            current_retry_count = int(
                float(
                    row.get(
                        "Retry Count",
                        0,
                    )
                    or 0
                )
            )

            updated.at[
                index,
                "Last Attempt At",
            ] = execution_time.isoformat()

            updated.at[
                index,
                "Last Error",
            ] = str(error)

            if current_retry_count < MAX_EMAIL_RETRIES:

                new_retry_count = (
                    current_retry_count + 1
                )

                updated.at[
                    index,
                    "Retry Count",
                ] = new_retry_count

                updated.at[
                    index,
                    "Status",
                ] = STATUS_PENDING

                event_name = (
                    "RETRY_SCHEDULED"
                )

            else:

                updated.at[
                    index,
                    "Status",
                ] = STATUS_FAILED

                event_name = (
                    STATUS_FAILED
                )

            events.append(
                {
                    "Campaign ID":
                        row["Campaign ID"],
                    "Customer ID":
                        customer_id,
                    "Event":
                        event_name,
                    "At":
                        execution_time.isoformat(),
                    "Detail":
                        str(error),
                }
            )

            logger.warning(
                "Campaign email failed "
                "campaign=%s customer=%s retry=%s error=%s",
                row["Campaign ID"],
                customer_id,
                current_retry_count,
                error,
            )

    events_df = pd.DataFrame(
        events
    )

    return (
        updated,
        events_df,
    )