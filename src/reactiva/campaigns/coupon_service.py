from __future__ import annotations

from typing import Any

import pandas as pd

from reactiva.campaigns.coupons import (
    REQUIRED_COUPON_COLUMNS,
    redeem_coupon,
    validate_coupon,
)
from reactiva.campaigns.storage import (
    CAMPAIGN_ACTIVE_KEY,
    read_csv_from_s3,
    write_csv_to_s3,
)


def _normalize_text(
    value: Any,
) -> str:
    """
    Normaliza valores escalares de texto.
    """
    if value is None:
        return ""

    if pd.isna(value):
        return ""

    return str(value).strip()


def _normalize_casefold(
    value: Any,
) -> str:
    """
    Normaliza texto ignorando mayusculas y minusculas.
    """
    return _normalize_text(
        value
    ).casefold()


def _find_coupon_customer_rows(
    campaign_df: pd.DataFrame,
    coupon_code: str,
    customer_id: str,
) -> pd.DataFrame:
    """
    Busca las filas correspondientes al cupon y al cliente.
    """
    if campaign_df.empty:
        return campaign_df.copy()

    normalized_coupon = (
        _normalize_casefold(
            coupon_code
        )
    )

    normalized_customer = (
        _normalize_casefold(
            customer_id
        )
    )

    coupon_matches = (
        campaign_df[
            "Coupon Code"
        ]
        .map(
            _normalize_casefold
        )
        == normalized_coupon
    )

    customer_matches = (
        campaign_df[
            "Customer ID"
        ]
        .map(
            _normalize_casefold
        )
        == normalized_customer
    )

    return campaign_df[
        coupon_matches
        & customer_matches
    ]


def validate_coupon_from_s3(
    bucket: str,
    coupon_code: str,
    customer_id: str,
    item_purchased: str,
    reference_date: Any,
    s3_client=None,
) -> dict[str, Any]:
    """
    Carga la campaña activa desde S3 y valida un cupon.

    Esta funcion es de solo lectura:
    no modifica ni persiste ningun dato.
    """
    campaign_df = read_csv_from_s3(
        bucket=bucket,
        key=CAMPAIGN_ACTIVE_KEY,
        expected_columns=REQUIRED_COUPON_COLUMNS,
        s3_client=s3_client,
    )

    if campaign_df.empty:
        return {
            "valid": False,
            "reason": "CAMPAIGN_NOT_AVAILABLE",
        }

    return validate_coupon(
        campaign_df=campaign_df,
        coupon_code=coupon_code,
        customer_id=customer_id,
        item_purchased=item_purchased,
        reference_date=reference_date,
    )


def redeem_coupon_from_s3(
    bucket: str,
    coupon_code: str,
    customer_id: str,
    item_purchased: str,
    reference_date: Any,
    transaction_id: str,
    redeemed_at: Any,
    s3_client=None,
) -> dict[str, Any]:
    """
    Valida, consume y persiste un cupon de la campaña activa.

    Flujo:
    1. lee campaign_active.csv;
    2. verifica idempotencia;
    3. valida nuevamente el cupon;
    4. lo marca REDEEMED;
    5. persiste la campaña;
    6. vuelve a leer S3;
    7. verifica que el consumo haya quedado guardado.

    Si el mismo Transaction ID ya habia consumido el cupon,
    la operacion se considera idempotente y no vuelve a escribir.

    Un cupon consumido por otra transaccion no puede reutilizarse.
    """
    normalized_transaction = (
        _normalize_text(
            transaction_id
        )
    )

    if not normalized_transaction:
        raise ValueError(
            "Transaction ID is required."
        )

    campaign_df = read_csv_from_s3(
        bucket=bucket,
        key=CAMPAIGN_ACTIVE_KEY,
        expected_columns=REQUIRED_COUPON_COLUMNS,
        s3_client=s3_client,
    )

    if campaign_df.empty:
        return {
            "redeemed": False,
            "reason": "CAMPAIGN_NOT_AVAILABLE",
        }

    matching_rows = (
        _find_coupon_customer_rows(
            campaign_df=campaign_df,
            coupon_code=coupon_code,
            customer_id=customer_id,
        )
    )

    if not matching_rows.empty:
        if len(
            matching_rows
        ) == 1:
            existing_row = (
                matching_rows.iloc[
                    0
                ]
            )

            existing_status = (
                _normalize_text(
                    existing_row[
                        "Coupon Status"
                    ]
                )
                .upper()
            )

            existing_transaction = (
                _normalize_text(
                    existing_row[
                        "Coupon Transaction ID"
                    ]
                )
            )

            if (
                existing_status
                == "REDEEMED"
                and existing_transaction
                == normalized_transaction
            ):
                return {
                    "redeemed": True,
                    "already_redeemed": True,
                    "campaign_id": _normalize_text(
                        existing_row[
                            "Campaign ID"
                        ]
                    ),
                    "coupon_code": _normalize_text(
                        existing_row[
                            "Coupon Code"
                        ]
                    ),
                    "transaction_id":
                        normalized_transaction,
                }

    validation = validate_coupon(
        campaign_df=campaign_df,
        coupon_code=coupon_code,
        customer_id=customer_id,
        item_purchased=item_purchased,
        reference_date=reference_date,
    )

    if not validation[
        "valid"
    ]:
        return {
            "redeemed": False,
            "reason": validation[
                "reason"
            ],
        }

    updated_df = redeem_coupon(
        campaign_df=campaign_df,
        coupon_code=coupon_code,
        customer_id=customer_id,
        transaction_id=normalized_transaction,
        redeemed_at=redeemed_at,
    )

    write_csv_to_s3(
        df=updated_df,
        bucket=bucket,
        key=CAMPAIGN_ACTIVE_KEY,
        s3_client=s3_client,
    )

    verified_df = read_csv_from_s3(
        bucket=bucket,
        key=CAMPAIGN_ACTIVE_KEY,
        expected_columns=REQUIRED_COUPON_COLUMNS,
        s3_client=s3_client,
    )

    verified_rows = (
        _find_coupon_customer_rows(
            campaign_df=verified_df,
            coupon_code=coupon_code,
            customer_id=customer_id,
        )
    )

    verified = False

    if len(
        verified_rows
    ) == 1:
        verified_row = (
            verified_rows.iloc[
                0
            ]
        )

        verified_status = (
            _normalize_text(
                verified_row[
                    "Coupon Status"
                ]
            )
            .upper()
        )

        verified_transaction = (
            _normalize_text(
                verified_row[
                    "Coupon Transaction ID"
                ]
            )
        )

        verified = (
            verified_status
            == "REDEEMED"
            and verified_transaction
            == normalized_transaction
        )

    if not verified:
        raise RuntimeError(
            "Coupon redemption could not be verified "
            "after persistence."
        )

    return {
        "redeemed": True,
        "already_redeemed": False,
        "campaign_id": validation[
            "campaign_id"
        ],
        "coupon_code": validation[
            "coupon_code"
        ],
        "transaction_id":
            normalized_transaction,
    }