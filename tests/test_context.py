import pandas as pd
import pytest

from reactiva.features.build_features import (
    add_season,
    age_group_from_age,
    build_features,
    season_from_month,
)
from reactiva.features.context import (
    build_context_popularity_rankings,
    normalize_season,
    recommend_contextual_popularity,
)


def _sample_transactions():
    """
    Dataset controlado para probar features, contexto y fallbacks
    sin depender de AWS ni del dataset productivo.
    """
    return pd.DataFrame(
        [
            {
                "Purchase Date": "2024-01-10",
                "Age": 22,
                "Location": "Delhi",
                "Item Purchased": "Kurta",
            },
            {
                "Purchase Date": "2024-02-10",
                "Age": 30,
                "Location": "Delhi",
                "Item Purchased": "Kurta",
            },
            {
                "Purchase Date": "2024-03-10",
                "Age": 45,
                "Location": "Delhi",
                "Item Purchased": "Sandal",
            },
            {
                "Purchase Date": "2024-04-10",
                "Age": 65,
                "Location": "Delhi",
                "Item Purchased": "Jeans",
            },
            {
                "Purchase Date": "2024-01-15",
                "Age": 70,
                "Location": "Mumbai",
                "Item Purchased": "Jacket",
            },
            {
                "Purchase Date": "2024-01-20",
                "Age": 25,
                "Location": "Mumbai",
                "Item Purchased": "Jacket",
            },
            {
                "Purchase Date": "2024-02-20",
                "Age": 40,
                "Location": "Mumbai",
                "Item Purchased": "Jacket",
            },
        ]
    )


def test_season_mapping():
    """Cada mes debe mapearse a la temporada estándar."""

    assert season_from_month(1) == "winter"
    assert season_from_month(4) == "summer"
    assert season_from_month(7) == "monsoon"
    assert season_from_month(11) == "post-monsoon"


def test_invalid_month_raises_error():
    """Un mes fuera de 1-12 debe rechazarse."""

    with pytest.raises(ValueError):
        season_from_month(13)


def test_normalize_season_keeps_compatibility():
    """
    Distintas formas de escribir una temporada deben
    normalizarse al formato estándar del proyecto.
    """

    assert normalize_season("Winter") == "winter"
    assert normalize_season("SUMMER") == "summer"
    assert normalize_season("post-monsoon") == "post-monsoon"
    assert normalize_season("Post Monsoon") == "post-monsoon"


def test_add_season_does_not_modify_original_dataframe():
    """
    La generación de season debe ser reproducible
    y no alterar el DataFrame recibido.
    """

    df = _sample_transactions()
    original_columns = df.columns.tolist()

    result = add_season(df)

    assert "season" not in original_columns
    assert "season" not in df.columns
    assert "season" in result.columns

    assert result.loc[0, "season"] == "winter"
    assert result.loc[2, "season"] == "summer"


def test_age_group_mapping():
    """Los grupos etarios deben respetar la regla estándar."""

    assert age_group_from_age(25) == "Young Adult"
    assert age_group_from_age(26) == "Adult"
    assert age_group_from_age(64) == "Adult"
    assert age_group_from_age(65) == "Old"


def test_build_features_adds_standard_columns():
    """
    El pipeline común debe generar las features estándar
    utilizadas por los componentes del proyecto.
    """

    df = _sample_transactions()

    result = build_features(df)

    assert "season" in result.columns
    assert "age_group" in result.columns

    assert result.loc[0, "season"] == "winter"
    assert result.loc[0, "age_group"] == "Young Adult"
    assert result.loc[3, "age_group"] == "Old"


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
    Si season + Location no tiene soporte suficiente,
    debe utilizarse el siguiente nivel válido: Location.
    """

    df = _sample_transactions()

    result = recommend_contextual_popularity(
        df=df,
        location="Delhi",
        season="winter",
        k=2,
        min_support=3,
    )

    assert result["recommendations"] == [
        "Kurta",
        "Jeans",
    ]

    assert result["trace"][0]["level"] == (
        "season + Location"
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
        season="winter",
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
        season="winter",
        k=4,
        min_support=2,
    )

    recommendations = result["recommendations"]

    assert len(recommendations) == len(
        set(recommendations)
    )