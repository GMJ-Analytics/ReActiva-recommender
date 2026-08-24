"""
Lógica contextual reutilizable para ReActiva.

Este módulo centraliza:

- Rankings de popularidad globales y contextuales.
- Control de soporte mínimo.
- Fallback escalonado para grupos con pocos datos.
- Trazabilidad de la recomendación contextual.

La construcción de features derivadas, como ``season``, se encuentra
centralizada en ``reactiva.features.build_features``.

IMPORTANTE:
Location se utiliza únicamente como contexto geográfico.
No representa clima real ni sucursal.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from reactiva.features.build_features import (
    SEASON_COLUMN,
    VALID_SEASONS,
    add_season,
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

DEFAULT_MIN_SUPPORT = 20


# ============================================================
# NORMALIZACIÓN DE CONTEXTO
# ============================================================

def normalize_season(season: str) -> str:
    """
    Normaliza una temporada al formato estándar utilizado
    actualmente por ReActiva.
    """

    normalized = (
        str(season)
        .strip()
        .lower()
        .replace("_", "-")
        .replace(" ", "-")
    )

    if normalized == "postmonsoon":
        normalized = "post-monsoon"

    if normalized not in VALID_SEASONS:
        raise ValueError(
            f"Temporada inválida: {season}. "
            f"Valores esperados: {VALID_SEASONS}."
        )

    return normalized


# ============================================================
# VALIDACIONES INTERNAS
# ============================================================

def _require_columns(
    df: pd.DataFrame,
    columns: Iterable[str],
) -> None:
    """
    Verifica que existan las columnas necesarias.
    """

    missing = [
        column
        for column in columns
        if column not in df.columns
    ]

    if missing:
        raise KeyError(
            "Faltan columnas requeridas: "
            + ", ".join(missing)
        )


# ============================================================
# RANKINGS DE POPULARIDAD
# ============================================================

def _global_popularity_ranking(
    df: pd.DataFrame,
    item_col: str,
) -> pd.DataFrame:
    """
    Construye un ranking global determinista de productos.
    """

    data = df.dropna(
        subset=[item_col]
    )

    ranking = (
        data
        .groupby(item_col)
        .size()
        .reset_index(name="Purchase Count")
    )

    ranking = ranking.sort_values(
        by=["Purchase Count", item_col],
        ascending=[False, True],
        kind="mergesort",
    ).reset_index(drop=True)

    ranking["Rank"] = ranking.index + 1

    return ranking


def _grouped_popularity_ranking(
    df: pd.DataFrame,
    group_cols: list[str],
    item_col: str,
) -> pd.DataFrame:
    """
    Construye rankings de popularidad dentro de grupos
    contextuales.
    """

    data = df.dropna(
        subset=[*group_cols, item_col]
    )

    ranking = (
        data
        .groupby(
            [*group_cols, item_col],
            dropna=False,
        )
        .size()
        .reset_index(name="Purchase Count")
    )

    ranking = ranking.sort_values(
        by=[
            *group_cols,
            "Purchase Count",
            item_col,
        ],
        ascending=[
            *([True] * len(group_cols)),
            False,
            True,
        ],
        kind="mergesort",
    )

    ranking["Rank"] = (
        ranking
        .groupby(group_cols)
        .cumcount()
        + 1
    )

    return ranking.reset_index(drop=True)


def build_context_popularity_rankings(
    df: pd.DataFrame,
    date_col: str = "Purchase Date",
    item_col: str = "Item Purchased",
    location_col: str = "Location",
    season_col: str = SEASON_COLUMN,
) -> dict[str, pd.DataFrame]:
    """
    Genera los cuatro niveles de popularidad utilizados
    por el contexto de ReActiva:

    1. Global.
    2. Por season.
    3. Por Location.
    4. Por season + Location.
    """

    _require_columns(
        df,
        [
            date_col,
            item_col,
            location_col,
        ],
    )

    data = add_season(
        df,
        date_col=date_col,
        season_col=season_col,
    )

    return {
        "global": _global_popularity_ranking(
            data,
            item_col=item_col,
        ),
        "season": _grouped_popularity_ranking(
            data,
            group_cols=[season_col],
            item_col=item_col,
        ),
        "location": _grouped_popularity_ranking(
            data,
            group_cols=[location_col],
            item_col=item_col,
        ),
        "season_location": _grouped_popularity_ranking(
            data,
            group_cols=[
                season_col,
                location_col,
            ],
            item_col=item_col,
        ),
    }


# ============================================================
# FALLBACK CONTEXTUAL
# ============================================================

def recommend_contextual_popularity(
    df: pd.DataFrame,
    location: str,
    season: str,
    k: int = 5,
    min_support: int = DEFAULT_MIN_SUPPORT,
    date_col: str = "Purchase Date",
    item_col: str = "Item Purchased",
    location_col: str = "Location",
    season_col: str = SEASON_COLUMN,
) -> dict:
    """
    Genera recomendaciones de popularidad con fallback
    contextual escalonado.

    Orden:

    season + Location
        ↓
    Location
        ↓
    season
        ↓
    Global

    Los niveles contextuales solo se utilizan si alcanzan
    el soporte mínimo configurado.

    El nivel global funciona como respaldo final.
    """

    if k <= 0:
        raise ValueError(
            "k debe ser mayor que cero."
        )

    if min_support <= 0:
        raise ValueError(
            "min_support debe ser mayor que cero."
        )

    _require_columns(
        df,
        [
            date_col,
            item_col,
            location_col,
        ],
    )

    data = add_season(
        df,
        date_col=date_col,
        season_col=season_col,
    )

    season = normalize_season(season)

    recommendations: list[str] = []
    trace: list[dict] = []

    levels = [
        (
            "season + Location",
            data[
                (data[season_col] == season)
                & (data[location_col] == location)
            ],
            True,
        ),
        (
            "Location",
            data[
                data[location_col] == location
            ],
            True,
        ),
        (
            "season",
            data[
                data[season_col] == season
            ],
            True,
        ),
        (
            "Global",
            data,
            False,
        ),
    ]

    for (
        level_name,
        segment,
        requires_min_support,
    ) in levels:

        support = len(segment)

        if (
            requires_min_support
            and support < min_support
        ):
            trace.append(
                {
                    "level": level_name,
                    "support": support,
                    "used": False,
                    "reason": "insufficient_support",
                    "added_items": [],
                }
            )

            continue

        ranking = _global_popularity_ranking(
            segment,
            item_col=item_col,
        )

        added_items = []

        for item in ranking[item_col]:

            if item in recommendations:
                continue

            recommendations.append(item)
            added_items.append(item)

            if len(recommendations) >= k:
                break

        trace.append(
            {
                "level": level_name,
                "support": support,
                "used": bool(added_items),
                "reason": (
                    "used"
                    if added_items
                    else "no_candidates"
                ),
                "added_items": added_items,
            }
        )

        if len(recommendations) >= k:
            break

    return {
        "recommendations": recommendations,
        "location": location,
        "season": season,
        "k": k,
        "min_support": min_support,
        "trace": trace,
    }