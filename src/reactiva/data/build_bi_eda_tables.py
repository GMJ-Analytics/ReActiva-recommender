"""
Generación de tablas procesadas para la página inicial de EDA y calidad
del dashboard de Power BI de ReActiva.

Este módulo NO reproduce lógica crítica de modelos o recomendadores.
Consume la fuente oficial de ReActiva y reutiliza componentes canónicos
del proyecto para generar tablas simples orientadas a visualización.

Salidas:
    dashboard/data/bi_transactions.csv
    dashboard/data/bi_customers.csv
    dashboard/data/bi_products.csv
    dashboard/data/bi_calendar.csv
    dashboard/data/bi_quality_summary.csv
    dashboard/data/bi_quality_columns.csv
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from reactiva.data.load_data import cargar_datos
from reactiva.data.validate_data import DataValidator
from reactiva.features.build_features import (
    build_features,
    season_from_month,
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = REPO_ROOT / "dashboard" / "data"

INACTIVITY_DAYS = 270

EXPECTED_COLUMNS = [
    "Transaction ID",
    "Customer ID",
    "Customer Full Name",
    "Customer Email",
    "Purchase Date",
    "Age",
    "Gender",
    "Location",
    "Online/Offline",
    "Online Store",
    "Category",
    "Item Purchased",
    "Brand",
    "Color",
    "Size",
    "Quantity",
    "Purchase Amount (₹)",
    "Discount (%)",
    "Festival/Sale",
    "Shipping Charge (₹)",
    "Delivery Speed",
    "Delivery Time (Days)",
    "Subscription Status",
    "Payment Method",
    "Review Rating",
    "Return Status",
    "Previous Purchases",
]

# Para la página de EDA no se exportan nombre y email.
# Customer ID es suficiente para realizar agregaciones y relaciones.
BI_TRANSACTION_COLUMNS = [
    "Transaction ID",
    "Customer ID",
    "Purchase Date",
    "Age",
    "Gender",
    "Location",
    "Online/Offline",
    "Online Store",
    "Category",
    "Item Purchased",
    "Brand",
    "Color",
    "Size",
    "Quantity",
    "Purchase Amount (₹)",
    "Discount (%)",
    "Festival/Sale",
    "Shipping Charge (₹)",
    "Delivery Speed",
    "Delivery Time (Days)",
    "Subscription Status",
    "Payment Method",
    "Review Rating",
    "Return Status",
    "Previous Purchases",
    "season",
    "age_group",
]


# ============================================================
# HELPERS
# ============================================================

def _validate_schema(df: pd.DataFrame) -> None:
    """
    Verifica que el dataset posea el esquema esperado para construir
    las tablas de BI.
    """

    missing_columns = [
        column
        for column in EXPECTED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "No se pueden generar las tablas de Power BI. "
            f"Faltan columnas requeridas: {missing_columns}"
        )


def _mode_or_na(series: pd.Series):
    """
    Devuelve el valor modal de una serie.
    Si no existen valores válidos devuelve pd.NA.
    """

    valid = series.dropna()

    if valid.empty:
        return pd.NA

    modes = valid.mode()

    if modes.empty:
        return valid.iloc[0]

    return modes.iloc[0]


def _percentage(numerator, denominator) -> float:
    """
    Calcula un porcentaje evitando divisiones por cero.
    """

    if denominator == 0:
        return 0.0

    return round(float(numerator) / float(denominator) * 100, 2)


# ============================================================
# PREPARACIÓN BASE
# ============================================================

def prepare_base_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara una copia del dataset para BI.

    - valida el esquema;
    - convierte Purchase Date a datetime;
    - reutiliza las features canónicas season y age_group.
    """

    _validate_schema(df)

    result = df.copy()

    parsed_dates = pd.to_datetime(
        result["Purchase Date"],
        errors="coerce",
    )

    invalid_dates = parsed_dates.isna()

    if invalid_dates.any():
        raise ValueError(
            "No se pueden generar las tablas de BI porque existen "
            f"{int(invalid_dates.sum())} valores inválidos en "
            "'Purchase Date'."
        )

    result["Purchase Date"] = parsed_dates

    # Reutiliza la definición canónica del proyecto.
    result = build_features(
        result,
        include_age_group=True,
    )

    return result


# ============================================================
# TABLA DE TRANSACCIONES
# ============================================================

def build_transactions_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Una fila por transacción.

    Contiene las variables necesarias para la página EDA sin exportar
    Customer Full Name ni Customer Email.
    """

    transactions = df[BI_TRANSACTION_COLUMNS].copy()

    transactions = transactions.sort_values(
        by=["Purchase Date", "Transaction ID"],
        ascending=[True, True],
    ).reset_index(drop=True)

    return transactions


# ============================================================
# TABLA DE CLIENTES
# ============================================================

def build_customers_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Una fila por Customer ID con métricas descriptivas del historial.

    No contiene nombre ni email porque la página inicial de EDA no
    requiere información identificatoria adicional.
    """

    max_date = df["Purchase Date"].max()

    customer_metrics = (
        df.groupby("Customer ID", as_index=False)
        .agg(
            transactions=("Transaction ID", "nunique"),
            total_units=("Quantity", "sum"),
            total_spend=("Purchase Amount (₹)", "sum"),
            average_ticket=("Purchase Amount (₹)", "mean"),
            average_discount=("Discount (%)", "mean"),
            average_rating=("Review Rating", "mean"),
            first_purchase=("Purchase Date", "min"),
            last_purchase=("Purchase Date", "max"),
        )
    )

    returned = (
        df.assign(
            _returned=df["Return Status"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("returned")
        )
        .groupby("Customer ID")["_returned"]
        .sum()
        .rename("returned_transactions")
        .reset_index()
    )

    online = (
        df.assign(
            _online=df["Online/Offline"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("online")
        )
        .groupby("Customer ID")["_online"]
        .sum()
        .rename("online_transactions")
        .reset_index()
    )

    preferred_category = (
        df.groupby("Customer ID")["Category"]
        .agg(_mode_or_na)
        .rename("preferred_category")
        .reset_index()
    )

    preferred_product = (
        df.groupby("Customer ID")["Item Purchased"]
        .agg(_mode_or_na)
        .rename("preferred_product")
        .reset_index()
    )

    preferred_brand = (
        df.groupby("Customer ID")["Brand"]
        .agg(_mode_or_na)
        .rename("preferred_brand")
        .reset_index()
    )

    # Para atributos de perfil se utiliza el registro más reciente.
    latest_profile = (
        df.sort_values(
            by=[
                "Customer ID",
                "Purchase Date",
                "Transaction ID",
            ]
        )
        .groupby("Customer ID", as_index=False)
        .tail(1)
        [
            [
                "Customer ID",
                "Age",
                "age_group",
                "Gender",
                "Location",
                "Subscription Status",
            ]
        ]
        .rename(
            columns={
                "Age": "age",
                "Gender": "gender",
                "Location": "location",
                "Subscription Status": "subscription_status",
            }
        )
    )

    customers = customer_metrics.merge(
        latest_profile,
        on="Customer ID",
        how="left",
    )

    customers = customers.merge(
        returned,
        on="Customer ID",
        how="left",
    )

    customers = customers.merge(
        online,
        on="Customer ID",
        how="left",
    )

    customers = customers.merge(
        preferred_category,
        on="Customer ID",
        how="left",
    )

    customers = customers.merge(
        preferred_product,
        on="Customer ID",
        how="left",
    )

    customers = customers.merge(
        preferred_brand,
        on="Customer ID",
        how="left",
    )

    customers["days_since_last_purchase"] = (
        max_date - customers["last_purchase"]
    ).dt.days

    customers["inactive_270"] = (
        customers["days_since_last_purchase"] >= INACTIVITY_DAYS
    )

    customers["activity_status"] = customers["inactive_270"].map(
        {
            True: "Inactive 270+ days",
            False: "Active",
        }
    )

    customers["return_rate_pct"] = customers.apply(
        lambda row: _percentage(
            row["returned_transactions"],
            row["transactions"],
        ),
        axis=1,
    )

    customers["online_share_pct"] = customers.apply(
        lambda row: _percentage(
            row["online_transactions"],
            row["transactions"],
        ),
        axis=1,
    )

    customers["offline_share_pct"] = (
        100 - customers["online_share_pct"]
    ).round(2)

    round_columns = [
        "total_spend",
        "average_ticket",
        "average_discount",
        "average_rating",
        "return_rate_pct",
        "online_share_pct",
        "offline_share_pct",
    ]

    customers[round_columns] = customers[round_columns].round(2)

    customers = customers.sort_values(
        "Customer ID"
    ).reset_index(drop=True)

    return customers


# ============================================================
# TABLA DE PRODUCTOS
# ============================================================

def build_products_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Una fila por producto con métricas descriptivas de desempeño.
    """

    products = (
        df.groupby("Item Purchased", as_index=False)
        .agg(
            category=("Category", _mode_or_na),
            primary_brand=("Brand", _mode_or_na),
            transactions=("Transaction ID", "nunique"),
            unique_customers=("Customer ID", "nunique"),
            units_sold=("Quantity", "sum"),
            total_revenue=("Purchase Amount (₹)", "sum"),
            average_ticket=("Purchase Amount (₹)", "mean"),
            average_discount=("Discount (%)", "mean"),
            average_rating=("Review Rating", "mean"),
        )
    )

    returns = (
        df.assign(
            _returned=df["Return Status"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("returned")
        )
        .groupby("Item Purchased")["_returned"]
        .sum()
        .rename("returned_transactions")
        .reset_index()
    )

    products = products.merge(
        returns,
        on="Item Purchased",
        how="left",
    )

    products["transaction_share_pct"] = products[
        "transactions"
    ].apply(
        lambda value: _percentage(
            value,
            len(df),
        )
    )

    products["return_rate_pct"] = products.apply(
        lambda row: _percentage(
            row["returned_transactions"],
            row["transactions"],
        ),
        axis=1,
    )

    products["popularity_rank"] = (
        products["transactions"]
        .rank(
            method="dense",
            ascending=False,
        )
        .astype(int)
    )

    round_columns = [
        "total_revenue",
        "average_ticket",
        "average_discount",
        "average_rating",
        "transaction_share_pct",
        "return_rate_pct",
    ]

    products[round_columns] = products[round_columns].round(2)

    products = products.sort_values(
        by=["popularity_rank", "Item Purchased"]
    ).reset_index(drop=True)

    return products


# ============================================================
# TABLA CALENDARIO
# ============================================================

def build_calendar_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tabla calendario entre la primera y última fecha del dataset.

    Permite que Power BI maneje dimensiones temporales sin reconstruir
    lógica de temporada.
    """

    min_date = df["Purchase Date"].min().normalize()
    max_date = df["Purchase Date"].max().normalize()

    dates = pd.date_range(
        start=min_date,
        end=max_date,
        freq="D",
    )

    calendar = pd.DataFrame(
        {
            "date": dates,
        }
    )

    month_names_es = {
        1: "Enero",
        2: "Febrero",
        3: "Marzo",
        4: "Abril",
        5: "Mayo",
        6: "Junio",
        7: "Julio",
        8: "Agosto",
        9: "Septiembre",
        10: "Octubre",
        11: "Noviembre",
        12: "Diciembre",
    }

    day_names_es = {
        0: "Lunes",
        1: "Martes",
        2: "Miércoles",
        3: "Jueves",
        4: "Viernes",
        5: "Sábado",
        6: "Domingo",
    }

    calendar["year"] = calendar["date"].dt.year
    calendar["quarter"] = (
        "Q" + calendar["date"].dt.quarter.astype(str)
    )
    calendar["month_number"] = calendar["date"].dt.month
    calendar["month_name"] = (
        calendar["month_number"].map(month_names_es)
    )
    calendar["year_month"] = (
        calendar["date"].dt.strftime("%Y-%m")
    )
    calendar["day"] = calendar["date"].dt.day
    calendar["day_of_week_number"] = (
        calendar["date"].dt.dayofweek + 1
    )
    calendar["day_name"] = (
        calendar["date"].dt.dayofweek.map(day_names_es)
    )

    calendar["season"] = (
        calendar["date"]
        .dt.month
        .map(season_from_month)
    )

    return calendar


# ============================================================
# TABLAS DE CALIDAD
# ============================================================

def build_quality_tables(
    raw_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Genera dos tablas de calidad:

    - summary: métricas globales del dataset;
    - columns: calidad y cardinalidad por columna.

    Se reutiliza DataValidator para no crear reglas paralelas.
    """

    validator = DataValidator(raw_df)

    report = validator.run_checks()

    date_issues = report.get("date_issues") or {}

    quality_summary = pd.DataFrame(
        [
            {
                "total_rows": len(raw_df),
                "total_columns": len(raw_df.columns),
                "unique_transactions": (
                    raw_df["Transaction ID"].nunique()
                    if "Transaction ID" in raw_df.columns
                    else pd.NA
                ),
                "unique_customers": (
                    raw_df["Customer ID"].nunique()
                    if "Customer ID" in raw_df.columns
                    else pd.NA
                ),
                "unique_products": (
                    raw_df["Item Purchased"].nunique()
                    if "Item Purchased" in raw_df.columns
                    else pd.NA
                ),
                "unique_categories": (
                    raw_df["Category"].nunique()
                    if "Category" in raw_df.columns
                    else pd.NA
                ),
                "unique_locations": (
                    raw_df["Location"].nunique()
                    if "Location" in raw_df.columns
                    else pd.NA
                ),
                "total_null_values": int(
                    raw_df.isna().sum().sum()
                ),
                "duplicate_rows": report.get(
                    "duplicate_rows",
                    0,
                ),
                "duplicate_key_rows": report.get(
                    "duplicate_key_rows",
                    0,
                ),
                "unparseable_dates": date_issues.get(
                    "unparseable_count",
                    0,
                ),
                "future_dates": date_issues.get(
                    "future_dates",
                    0,
                ),
                "missing_required_columns": len(
                    report.get(
                        "missing_columns",
                        [],
                    )
                ),
                "customers_with_one_purchase": report.get(
                    "orphan_customers",
                    0,
                ),
                "dataset_min_date": pd.to_datetime(
                    raw_df["Purchase Date"],
                    errors="coerce",
                ).min(),
                "dataset_max_date": pd.to_datetime(
                    raw_df["Purchase Date"],
                    errors="coerce",
                ).max(),
            }
        ]
    )

    quality_rows = []

    total_rows = len(raw_df)

    for column in raw_df.columns:
        null_count = int(
            raw_df[column].isna().sum()
        )

        null_pct = _percentage(
            null_count,
            total_rows,
        )

        quality_rows.append(
            {
                "column": column,
                "dtype": str(raw_df[column].dtype),
                "null_count": null_count,
                "null_pct": null_pct,
                "unique_values": int(
                    raw_df[column].nunique(
                        dropna=True
                    )
                ),
            }
        )

    quality_columns = pd.DataFrame(
        quality_rows
    ).sort_values(
        by=["null_pct", "column"],
        ascending=[False, True],
    ).reset_index(drop=True)

    return quality_summary, quality_columns


# ============================================================
# EXPORTACIÓN
# ============================================================

def save_table(
    df: pd.DataFrame,
    filename: str,
) -> Path:
    """
    Guarda una tabla en CSV UTF-8 con BOM para facilitar su lectura
    desde Power BI y herramientas de escritorio.
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = OUTPUT_DIR / filename

    df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    return output_path


# ============================================================
# PIPELINE BI - ISSUE #61
# ============================================================

def build_bi_eda_tables() -> dict[str, Path]:
    """
    Ejecuta la generación completa de tablas para la página inicial
    de EDA y calidad de Power BI.
    """

    raw_df = cargar_datos()

    if raw_df is None:
        raise RuntimeError(
            "No fue posible cargar el dataset oficial de ReActiva."
        )

    _validate_schema(raw_df)

    prepared_df = prepare_base_dataframe(
        raw_df
    )

    transactions = build_transactions_table(
        prepared_df
    )

    customers = build_customers_table(
        prepared_df
    )

    products = build_products_table(
        prepared_df
    )

    calendar = build_calendar_table(
        prepared_df
    )

    quality_summary, quality_columns = (
        build_quality_tables(
            raw_df
        )
    )

    outputs = {
        "transactions": save_table(
            transactions,
            "bi_transactions.csv",
        ),
        "customers": save_table(
            customers,
            "bi_customers.csv",
        ),
        "products": save_table(
            products,
            "bi_products.csv",
        ),
        "calendar": save_table(
            calendar,
            "bi_calendar.csv",
        ),
        "quality_summary": save_table(
            quality_summary,
            "bi_quality_summary.csv",
        ),
        "quality_columns": save_table(
            quality_columns,
            "bi_quality_columns.csv",
        ),
    }

    print("=" * 70)
    print("POWER BI - TABLAS EDA / CALIDAD GENERADAS")
    print("=" * 70)

    for name, path in outputs.items():
        print(
            f"{name:<20} -> {path}"
        )

    print("-" * 70)
    print(
        f"Transacciones: {len(transactions):,}"
    )
    print(
        f"Clientes:      {len(customers):,}"
    )
    print(
        f"Productos:     {len(products):,}"
    )
    print(
        f"Fechas:        {len(calendar):,}"
    )
    print(
        f"Columnas QA:   {len(quality_columns):,}"
    )
    print("=" * 70)

    return outputs


if __name__ == "__main__":
    build_bi_eda_tables()