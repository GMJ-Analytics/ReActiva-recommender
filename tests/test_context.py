import pandas as pd
import pytest

from reactiva.features.context import (
    add_season_india,
    build_context_popularity_rankings,
    normalize_season_india,
    recommend_contextual_popularity,
    season_india_from_month,
)


def _sample_transactions():
    """
    Dataset controlado para probar contexto y fallbacks
    sin depender de AWS ni del dataset productivo.
    """
    return pd.DataFrame(
        [
            {
                "Purchase Date": "2024-01-10",
                "Location": "Delhi",
                "Item Purchased": "Kurta",
            },
            {
                "Purchase Date": "2024-02-10",
                "Location": "Delhi",
                "Item Purchased": "Kurta",
            },
            {
                "Purchase Date": "2024-03-10",
                "Location": "Delhi",
                "Item Purchased": "Sandal",
            },
            {
                "Purchase Date": "2024-04-10",
                "Location": "Delhi",
                "Item Purchased": "Jeans",
            },
            {
                "Purchase Date": "2024-01-15",
                "Location": "Mumbai",
                "Item Purchased": "Jacket",
            },
            {
                "Purchase Date": "2024-01-20",
                "Location": "Mumbai",
                "Item Purchased": "Jacket",
            },
            {
                "Purchase Date": "2024-02-20",
                "Location": "Mumbai",
                "Item Purchased": "Jacket",
            },
        ]
    )


def test_season_india_mapping():
    """Cada mes debe mapearse a la temporada esperada."""

    assert season_india_from_month(1) == "Winter"
    assert season_india_from_month(4) == "Summer"
    assert season_india_from_month(7) == "Monsoon"
    assert season_india_from_month(11) == "Post-Monsoon"


def test_invalid_month_raises_error():
    """Un mes fuera de 1-12 debe rechazarse."""

    with pytest.raises(ValueError):
        season_india_from_month(13)


def test_normalize_season_keeps_compatibility():
    """
    Los nombres utilizados previamente en minúscula
    deben normalizarse al formato canónico.
    """

    assert normalize_season_india("winter") == "Winter"
    assert normalize_season_india("SUMMER") == "Summer"
    assert normalize_season_india("post-monsoon") == "Post-Monsoon"
    assert normalize_season_india("Post Monsoon") == "Post-Monsoon"


def test_add_season_india_does_not_modify_original_dataframe():
    """
    La generación del contexto debe ser reproducible
    y no alterar el DataFrame recibido.
    """

    df = _sample_transactions()
    original_columns = df.columns.tolist()

    result = add_season_india(df)

    assert "Season_India" not in original_columns
    assert "Season_India" not in df.columns
    assert "Season_India" in result.columns

    assert result.loc[0, "Season_India"] == "Winter"
    assert result.loc[2, "Season_India"] == "Summer"


def test_build_context_popularity_rankings():
    """
    Deben existir rankings globales y para cada
    nivel contextual definido.
    """

    df = _sample_transactions()

    rankings = build_context_popularity_rankings(df)

    assert set(rankings) == {
        "global",
        "season",
        "location",
        "season_location",
    }

    global_ranking = rankings["global"]

    assert global_ranking.iloc[0]["Item Purchased"] == "Jacket"
    assert global_ranking.iloc[0]["Purchase Count"] == 3
    assert global_ranking.iloc[0]["Rank"] == 1


def test_fallback_from_season_location_to_location():
    """
    Si Season + Location no tiene soporte suficiente,
    debe utilizarse el siguiente nivel válido: Location.
    """

    df = _sample_transactions()

    result = recommend_contextual_popularity(
        df=df,
        location="Delhi",
        season="Winter",
        k=2,
        min_support=3,
    )

    assert result["recommendations"] == [
        "Kurta",
        "Jeans",
    ]

    assert result["trace"][0]["level"] == (
        "Season_India + Location"
    )
    assert result["trace"][0]["support"] == 2
    assert result["trace"][0]["used"] is False
    assert result["trace"][0]["reason"] == (
        "insufficient_support"
    )

    assert result["trace"][1]["level"] == "Location"
    assert result["trace"][1]["used"] is True


def test_global_is_final_fallback():
    """
    El ranking global debe funcionar como respaldo final
    cuando ningún contexto alcanza el soporte mínimo.
    """

    df = _sample_transactions()

    result = recommend_contextual_popularity(
        df=df,
        location="Unknown Location",
        season="Winter",
        k=3,
        min_support=100,
    )

    assert len(result["recommendations"]) == 3

    assert result["trace"][-1]["level"] == "Global"
    assert result["trace"][-1]["used"] is True


def test_recommendations_do_not_repeat_products():
    """
    El fallback puede completar recomendaciones usando
    varios niveles, pero nunca debe repetir productos.
    """

    df = _sample_transactions()

    result = recommend_contextual_popularity(
        df=df,
        location="Delhi",
        season="Winter",
        k=4,
        min_support=2,
    )

    recommendations = result["recommendations"]

    assert len(recommendations) == len(
        set(recommendations)
    )