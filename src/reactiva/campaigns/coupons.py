from __future__ import annotations

from typing import Any

import pandas as pd


REQUIRED_COUPON_COLUMNS = [
    "Campaign ID",
    "Campaign Month",
    "Customer ID",
    "Recommendation 1",
    "Recommendation 2",
    "Recommendation 3",
    "Discount Percent",
    "Coupon Code",
    "Coupon Status",
    "Coupon Redeemed At",
    "Coupon Transaction ID",
]


def _normalize_text(
    value: Any,
) -> str:
    """
    Normaliza valores de texto para comparaciones internas.
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


def _validate_campaign_schema(
    campaign_df: pd.DataFrame,
) -> None:
    """
    Verifica que el DataFrame de campaña tenga las columnas
    necesarias para validar y consumir cupones.
    """
    if not isinstance(
        campaign_df,
        pd.DataFrame,
    ):
        raise TypeError(
            "campaign_df must be a pandas DataFrame."
        )

    missing_columns = [
        column
        for column in REQUIRED_COUPON_COLUMNS
        if column not in campaign_df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing required campaign columns: "
            + ", ".join(
                missing_columns
            )
        )


def _normalize_reference_month(
    reference_date: Any,
) -> str:
    """
    Convierte una fecha de referencia al formato YYYY-MM.
    """
    timestamp = pd.to_datetime(
        reference_date,
        errors="coerce",
    )

    if pd.isna(
        timestamp
    ):
        raise ValueError(
            "Invalid reference_date."
        )

    return timestamp.strftime(
        "%Y-%m"
    )


def _find_coupon_rows(
    campaign_df: pd.DataFrame,
    coupon_code: str,
) -> pd.DataFrame:
    """
    Busca un cupon sin distinguir mayusculas/minusculas.
    """
    normalized_coupon = (
        _normalize_casefold(
            coupon_code
        )
    )

    coupon_series = (
        campaign_df[
            "Coupon Code"
        ]
        .map(
            _normalize_casefold
        )
    )

    return campaign_df[
        coupon_series
        == normalized_coupon
    ]


def _recommended_products(
    row: pd.Series,
) -> list[str]:
    """
    Obtiene los productos recomendados validos de una campaña.
    """
    recommendations = []

    for column in (
        "Recommendation 1",
        "Recommendation 2",
        "Recommendation 3",
    ):
        product = _normalize_text(
            row.get(
                column
            )
        )

        if product:
            recommendations.append(
                product
            )

    return recommendations


def validate_coupon(
    campaign_df: pd.DataFrame,
    coupon_code: str,
    customer_id: str,
    item_purchased: str,
    reference_date: Any,
) -> dict[str, Any]:
    """
    Valida un cupon contra la campaña activa.

    Reglas de la simulacion:
    - codigo de cupon case-insensitive;
    - el cupon debe pertenecer al Customer ID;
    - debe estar ACTIVE;
    - debe corresponder al mes de la compra;
    - el producto comprado debe estar dentro de Recommendation 1-3;
    - la cantidad comprada no afecta la validez del cupon.

    Esta funcion no modifica el DataFrame recibido.
    """
    _validate_campaign_schema(
        campaign_df
    )

    normalized_coupon = _normalize_text(
        coupon_code
    )

    if not normalized_coupon:
        return {
            "valid": False,
            "reason": "EMPTY_COUPON",
        }

    coupon_rows = _find_coupon_rows(
        campaign_df=campaign_df,
        coupon_code=normalized_coupon,
    )

    if coupon_rows.empty:
        return {
            "valid": False,
            "reason": "COUPON_NOT_FOUND",
        }

    normalized_customer = (
        _normalize_casefold(
            customer_id
        )
    )

    customer_matches = (
        coupon_rows[
            "Customer ID"
        ]
        .map(
            _normalize_casefold
        )
        == normalized_customer
    )

    matching_customer_rows = (
        coupon_rows[
            customer_matches
        ]
    )

    if matching_customer_rows.empty:
        return {
            "valid": False,
            "reason": "CUSTOMER_MISMATCH",
        }

    row = matching_customer_rows.iloc[
        0
    ]

    coupon_status = (
        _normalize_text(
            row[
                "Coupon Status"
            ]
        )
        .upper()
    )

    if coupon_status != "ACTIVE":
        return {
            "valid": False,
            "reason": "COUPON_NOT_ACTIVE",
        }

    reference_month = (
        _normalize_reference_month(
            reference_date
        )
    )

    campaign_month = (
        _normalize_text(
            row[
                "Campaign Month"
            ]
        )
    )

    if campaign_month != reference_month:
        return {
            "valid": False,
            "reason": "WRONG_CAMPAIGN_MONTH",
        }

    recommendations = (
        _recommended_products(
            row
        )
    )

    normalized_item = (
        _normalize_casefold(
            item_purchased
        )
    )

    eligible_products = {
        _normalize_casefold(
            product
        )
        for product in recommendations
    }

    if (
        not normalized_item
        or normalized_item
        not in eligible_products
    ):
        return {
            "valid": False,
            "reason": "PRODUCT_NOT_ELIGIBLE",
        }

    discount_percent = (
        row[
            "Discount Percent"
        ]
    )

    if pd.isna(
        discount_percent
    ):
        discount_percent = 0

    try:
        discount_percent = int(
            discount_percent
        )
    except (
        TypeError,
        ValueError,
    ):
        discount_percent = 0

    return {
        "valid": True,
        "reason": None,
        "campaign_id": _normalize_text(
            row[
                "Campaign ID"
            ]
        ),
        "campaign_month": campaign_month,
        "customer_id": _normalize_text(
            row[
                "Customer ID"
            ]
        ),
        "coupon_code": _normalize_text(
            row[
                "Coupon Code"
            ]
        ),
        "discount_percent": discount_percent,
        "eligible_products": recommendations,
    }


def redeem_coupon(
    campaign_df: pd.DataFrame,
    coupon_code: str,
    customer_id: str,
    transaction_id: str,
    redeemed_at: Any,
) -> pd.DataFrame:
    """
    Marca un cupon ACTIVE como REDEEMED.

    El consumo se registra solamente despues de que la transaccion
    haya sido confirmada por el flujo que invoque esta funcion.

    Retorna una copia del DataFrame y no modifica el original.
    """
    _validate_campaign_schema(
        campaign_df
    )

    normalized_coupon = _normalize_text(
        coupon_code
    )

    normalized_customer = (
        _normalize_casefold(
            customer_id
        )
    )

    normalized_transaction = (
        _normalize_text(
            transaction_id
        )
    )

    if not normalized_coupon:
        raise ValueError(
            "Coupon code is required."
        )

    if not normalized_customer:
        raise ValueError(
            "Customer ID is required."
        )

    if not normalized_transaction:
        raise ValueError(
            "Transaction ID is required."
        )

    coupon_rows = _find_coupon_rows(
        campaign_df=campaign_df,
        coupon_code=normalized_coupon,
    )

    if coupon_rows.empty:
        raise ValueError(
            "Coupon not found."
        )

    customer_matches = (
        coupon_rows[
            "Customer ID"
        ]
        .map(
            _normalize_casefold
        )
        == normalized_customer
    )

    matching_rows = (
        coupon_rows[
            customer_matches
        ]
    )

    if matching_rows.empty:
        raise ValueError(
            "Coupon does not belong to customer."
        )

    if len(
        matching_rows
    ) != 1:
        raise ValueError(
            "Coupon is ambiguous for customer."
        )

    row_index = (
        matching_rows.index[
            0
        ]
    )

    current_status = (
        _normalize_text(
            campaign_df.at[
                row_index,
                "Coupon Status",
            ]
        )
        .upper()
    )

    if current_status != "ACTIVE":
        raise ValueError(
            "Coupon is not active."
        )

    updated_df = (
        campaign_df.copy(
            deep=True
        )
    )

    # Al leer campaign_active.csv desde S3, pandas puede inferir estas
    # columnas completamente vacias como float64. Se convierten solo
    # en la copia antes de registrar texto, sin modificar el original.
    updated_df[
        "Coupon Redeemed At"
    ] = (
        updated_df[
            "Coupon Redeemed At"
        ].astype(
            "object"
        )
    )

    updated_df[
        "Coupon Transaction ID"
    ] = (
        updated_df[
            "Coupon Transaction ID"
        ].astype(
            "object"
        )
    )

    updated_df.at[
        row_index,
        "Coupon Status",
    ] = "REDEEMED"

    updated_df.at[
        row_index,
        "Coupon Redeemed At",
    ] = redeemed_at

    updated_df.at[
        row_index,
        "Coupon Transaction ID",
    ] = normalized_transaction

    return updated_df