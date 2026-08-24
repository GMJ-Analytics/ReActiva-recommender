"""
Construcción estandarizada de features derivadas para ReActiva.

Este módulo centraliza la creación de variables utilizadas por
distintos componentes del proyecto para evitar duplicar reglas en
notebooks, recomendadores y otros módulos.
"""

from __future__ import annotations

import pandas as pd


# ============================================================
# CONSTANTES
# ============================================================

SEASON_COLUMN = "season"
AGE_GROUP_COLUMN = "age_group"

VALID_SEASONS = (
    "winter",
    "summer",
    "monsoon",
    "post-monsoon",
)


# ============================================================
# TEMPORADA
# ============================================================

def season_from_month(month: int) -> str:
    """
    Convierte un número de mes en la temporada utilizada
    de forma estándar por ReActiva.
    """

    if month in (12, 1, 2):
        return "winter"

    if month in (3, 4, 5):
        return "summer"

    if month in (6, 7, 8, 9):
        return "monsoon"

    if month in (10, 11):
        return "post-monsoon"

    raise ValueError(
        f"Mes inválido: {month}. Debe estar entre 1 y 12."
    )


def season_from_date(date_value) -> str:
    """
    Obtiene la temporada estándar de ReActiva a partir
    de una fecha concreta.
    """

    parsed_date = pd.to_datetime(
        date_value,
        errors="raise",
    )

    return season_from_month(parsed_date.month)


def add_season(
    df: pd.DataFrame,
    date_col: str = "Purchase Date",
    season_col: str = SEASON_COLUMN,
) -> pd.DataFrame:
    """
    Agrega la feature season de forma reproducible.

    La función devuelve una copia y no modifica el DataFrame
    original recibido.
    """

    if date_col not in df.columns:
        raise KeyError(
            f"No existe la columna requerida: {date_col}"
        )

    result = df.copy()

    parsed_dates = pd.to_datetime(
        result[date_col],
        errors="coerce",
    )

    invalid_dates = parsed_dates.isna()

    if invalid_dates.any():
        raise ValueError(
            f"Se encontraron {invalid_dates.sum()} fechas inválidas "
            f"en la columna '{date_col}'."
        )

    result[date_col] = parsed_dates

    result[season_col] = (
        result[date_col]
        .dt.month
        .map(season_from_month)
    )

    return result


# ============================================================
# GRUPO ETARIO
# ============================================================

def age_group_from_age(age) -> str:
    """
    Convierte una edad en el grupo etario utilizado por
    los modelos actuales de ReActiva.

    Reglas:
    - <= 25: Young Adult
    - 26 a 64: Adult
    - >= 65: Old
    """

    try:
        numeric_age = float(age)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Edad inválida: {age}"
        ) from exc

    if pd.isna(numeric_age) or numeric_age < 0:
        raise ValueError(
            f"Edad inválida: {age}"
        )

    if numeric_age <= 25:
        return "Young Adult"

    if numeric_age >= 65:
        return "Old"

    return "Adult"


def add_age_group(
    df: pd.DataFrame,
    age_col: str = "Age",
    age_group_col: str = AGE_GROUP_COLUMN,
) -> pd.DataFrame:
    """
    Agrega la feature age_group utilizando una única
    definición para todo el proyecto.

    La función devuelve una copia y no modifica el DataFrame
    original recibido.
    """

    if age_col not in df.columns:
        raise KeyError(
            f"No existe la columna requerida: {age_col}"
        )

    result = df.copy()

    result[age_group_col] = (
        result[age_col]
        .map(age_group_from_age)
    )

    return result


# ============================================================
# PIPELINE DE FEATURES
# ============================================================

def build_features(
    df: pd.DataFrame,
    include_age_group: bool = True,
) -> pd.DataFrame:
    """
    Construye las features derivadas estándar de ReActiva.

    Actualmente:
    - season
    - age_group, cuando include_age_group=True
    """

    result = add_season(df)

    if include_age_group:
        result = add_age_group(result)

    return result