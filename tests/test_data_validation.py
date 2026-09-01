import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from reactiva.data.validate_data import DataValidator, FULL_DEFAULT_STRATEGY


def test_current_schema_strategy():
    """La estrategia debe contemplar el esquema actual del dataset."""
    assert FULL_DEFAULT_STRATEGY["Customer Full Name"] == "skip"
    assert FULL_DEFAULT_STRATEGY["Customer Email"] == "skip"
    assert FULL_DEFAULT_STRATEGY["Customer Phone"] == "skip"
    assert "Frequency of Purchases" not in FULL_DEFAULT_STRATEGY


def test_different_transaction_ids_are_not_duplicates():
    """
    Dos compras del mismo cliente, producto y fecha son transacciones
    distintas si tienen diferente Transaction ID.
    """
    df = pd.DataFrame(
        [
            {
                "Transaction ID": "TXN001",
                "Customer ID": "CUST001",
                "Customer Full Name": "Ana Perez",
                "Customer Email": "ana.perez@example.com",
                "Item Purchased": "Kurta",
                "Category": "Clothing",
                "Purchase Date": "2024-01-10",
            },
            {
                "Transaction ID": "TXN002",
                "Customer ID": "CUST001",
                "Customer Full Name": "Ana Perez",
                "Customer Email": "ana.perez@example.com",
                "Item Purchased": "Kurta",
                "Category": "Clothing",
                "Purchase Date": "2024-01-10",
            },
        ]
    )

    validator = DataValidator(df)

    report = validator.run_checks()
    clean_df = validator.clean(strategy=FULL_DEFAULT_STRATEGY)

    assert report["duplicate_key_rows"] == 0
    assert len(clean_df) == 2


def test_same_complete_transaction_key_is_duplicate():
    """
    Si dos filas conservan el mismo Transaction ID, el reporte debe
    identificar el duplicado y la limpieza debe rechazar el conflicto.
    """
    df = pd.DataFrame(
        [
            {
                "Transaction ID": "TXN001",
                "Customer ID": "CUST001",
                "Customer Full Name": "Ana Perez",
                "Customer Email": "ana.perez@example.com",
                "Item Purchased": "Kurta",
                "Category": "Clothing",
                "Purchase Date": "2024-01-10",
            },
            {
                "Transaction ID": "TXN001",
                "Customer ID": "CUST001",
                "Customer Full Name": "Ana Perez",
                "Customer Email": "ana.perez@example.com",
                "Item Purchased": "Kurta",
                "Category": "Accessories",
                "Purchase Date": "2024-01-10",
            },
        ]
    )

    validator = DataValidator(df)

    report = validator.run_checks()

    assert report["duplicate_key_rows"] == 1

    with pytest.raises(
        ValueError,
        match="Duplicate Transaction ID values remain",
    ):
        validator.clean(strategy=FULL_DEFAULT_STRATEGY)


def test_missing_transaction_id_does_not_use_old_dedupe_rule():
    """
    Sin Transaction ID no debe deduplicarse usando solamente
    Customer ID + Item Purchased + Purchase Date.
    """
    df = pd.DataFrame(
        [
            {
                "Customer ID": "CUST001",
                "Customer Full Name": "Ana Perez",
                "Customer Email": "ana.perez@example.com",
                "Item Purchased": "Kurta",
                "Category": "Clothing",
                "Purchase Date": "2024-01-10",
            },
            {
                "Customer ID": "CUST001",
                "Customer Full Name": "Ana Perez",
                "Customer Email": "ana.perez@example.com",
                "Item Purchased": "Kurta",
                "Category": "Accessories",
                "Purchase Date": "2024-01-10",
            },
        ]
    )

    validator = DataValidator(df)
    clean_df = validator.clean(strategy=FULL_DEFAULT_STRATEGY)

    assert len(clean_df) == 2


def test_cleaning_is_reproducible():
    """El mismo input debe producir exactamente el mismo resultado."""
    df = pd.DataFrame(
        [
            {
                "Transaction ID": "TXN001",
                "Customer ID": "CUST001",
                "Customer Full Name": "Ana Perez",
                "Customer Email": "ana.perez@example.com",
                "Item Purchased": "Kurta",
                "Category": "Clothing",
                "Purchase Date": "2024-01-10",
            },
            {
                "Transaction ID": "TXN002",
                "Customer ID": "CUST001",
                "Customer Full Name": "Ana Perez",
                "Customer Email": "ana.perez@example.com",
                "Item Purchased": "Kurta",
                "Category": "Clothing",
                "Purchase Date": "2024-01-10",
            },
        ]
    )

    clean_1 = DataValidator(df).clean(strategy=FULL_DEFAULT_STRATEGY)
    clean_2 = DataValidator(df).clean(strategy=FULL_DEFAULT_STRATEGY)

    assert_frame_equal(clean_1, clean_2)


def test_text_normalization_strips_surrounding_whitespace():
    """
    La limpieza debe eliminar espacios sobrantes al inicio y al final
    de las columnas de texto sin alterar su contenido.
    """
    df = pd.DataFrame(
        [
            {
                "Transaction ID": " TXN001 ",
                "Customer ID": " CUST001 ",
                "Customer Full Name": " Ana Perez ",
                "Customer Email": " ana.perez@example.com ",
                "Item Purchased": " Kurta ",
                "Category": " Clothing ",
                "Purchase Date": "2024-01-10",
            }
        ]
    )

    clean_df = DataValidator(df).clean(
        strategy=FULL_DEFAULT_STRATEGY,
        normalize_text=True,
    )

    assert clean_df.iloc[0]["Transaction ID"] == "TXN001"
    assert clean_df.iloc[0]["Customer ID"] == "CUST001"
    assert clean_df.iloc[0]["Customer Full Name"] == "Ana Perez"
    assert clean_df.iloc[0]["Customer Email"] == "ana.perez@example.com"
    assert clean_df.iloc[0]["Item Purchased"] == "Kurta"
    assert clean_df.iloc[0]["Category"] == "Clothing"


def test_channel_consistency_detects_invalid_offline_values():
    """
    Una compra offline con valores propios del canal online debe ser
    detectada como inconsistente sin modificar los datos originales.
    """
    df = pd.DataFrame(
        [
            {
                "Transaction ID": "TXN001",
                "Customer ID": "CUST001",
                "Item Purchased": "Kurta",
                "Category": "Clothing",
                "Purchase Date": "2024-01-10",
                "Online/Offline": "Offline",
                "Online Store": "Myntra",
                "Delivery Speed": "Express",
                "Shipping Charge (₹)": 40,
                "Delivery Time (Days)": 3,
            }
        ]
    )

    validator = DataValidator(df)
    report = validator.run_checks()

    consistency = report["channel_consistency"]

    assert consistency["cantidad_offline"] == 1
    assert consistency["cantidad_online"] == 0
    assert consistency["offline_online_store_incorrecto"] == 1
    assert consistency["offline_delivery_speed_incorrecto"] == 1
    assert consistency["offline_shipping_charge_incorrecto"] == 1
    assert consistency["offline_delivery_time_incorrecto"] == 1

    assert_frame_equal(validator.df, df)


def test_numeric_range_validation_detects_invalid_values():
    """
    Los valores fuera de los rangos de validez deben ser detectados
    sin eliminar, recortar ni modificar las filas originales.
    """
    df = pd.DataFrame(
        [
            {
                "Transaction ID": "TXN001",
                "Customer ID": "CUST001",
                "Item Purchased": "Kurta",
                "Category": "Clothing",
                "Purchase Date": "2024-01-10",
                "Age": 14,
                "Quantity": 0,
                "Purchase Amount (₹)": -1,
                "Discount (%)": 101,
                "Shipping Charge (₹)": -10,
                "Delivery Time (Days)": -1,
                "Review Rating": 6,
                "Previous Purchases": -1,
            }
        ]
    )

    validator = DataValidator(df)
    report = validator.run_checks()

    range_issues = report["range_issues"]

    assert range_issues["Age"]["below_min"] == 1
    assert range_issues["Age"]["above_max"] == 0

    assert range_issues["Quantity"]["below_min"] == 1
    assert range_issues["Purchase Amount (₹)"]["below_min"] == 1

    assert range_issues["Discount (%)"]["below_min"] == 0
    assert range_issues["Discount (%)"]["above_max"] == 1

    assert range_issues["Shipping Charge (₹)"]["below_min"] == 1
    assert range_issues["Delivery Time (Days)"]["below_min"] == 1

    assert range_issues["Review Rating"]["below_min"] == 0
    assert range_issues["Review Rating"]["above_max"] == 1

    assert range_issues["Previous Purchases"]["below_min"] == 1

    assert_frame_equal(validator.df, df)


def test_clean_and_save_dataset_returns_reproducible_dataframe():
    """
    La preparación debe poder limpiar el dataset mediante una función
    reutilizable, produciendo la misma salida para el mismo input.
    """
    from reactiva.data.validate_data import clean_and_save_dataset

    df = pd.DataFrame(
        [
            {
                "Transaction ID": " TXN001 ",
                "Customer ID": " CUST001 ",
                "Customer Full Name": " Ana Perez ",
                "Customer Email": " ana.perez@example.com ",
                "Item Purchased": " Kurta ",
                "Category": " Clothing ",
                "Purchase Date": "2024-01-10",
            }
        ]
    )

    clean_1 = clean_and_save_dataset(df)
    clean_2 = clean_and_save_dataset(df)

    assert_frame_equal(clean_1, clean_2)

    assert len(clean_1) == 1
    assert clean_1.iloc[0]["Transaction ID"] == "TXN001"
    assert clean_1.iloc[0]["Customer ID"] == "CUST001"
    assert clean_1.iloc[0]["Customer Full Name"] == "Ana Perez"
    assert clean_1.iloc[0]["Customer Email"] == "ana.perez@example.com"
    assert clean_1.iloc[0]["Item Purchased"] == "Kurta"
    assert clean_1.iloc[0]["Category"] == "Clothing"