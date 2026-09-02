import os
import joblib
import pandas as pd
import boto3
from datetime import datetime
from pathlib import Path

from reactiva.config import (
    S3_BUCKET,
    S3_PREDICTIONS_KEY,
    S3_PREDICTIONSLOG,
    LAMBDA_LOG,
    DATASET_URI,
)
from reactiva.data.load_data import (
    cargar_datos,
    descargar_datos_des3,
    cargar_datos_as3,
    cargar_log_as3,
)
from reactiva.features.build_features import (
    build_customer_features,
    season_from_month,
)
from reactiva.data.save_results import generate_run_id
from reactiva.data.validate_data import clean_and_save_dataset
from reactiva.utils.logger import log_event, setup_logger

logger = setup_logger('model_predict_log', LAMBDA_LOG)

# ============================================================
# MODEL LOADING (from S3, matching recommender.py's persistence)
# ============================================================

MODEL_DIR = os.getenv("MODEL_DIR", ".")
MODEL_FILENAME = "recommender_model.pkl"
FEATURES_FILENAME = "recommender_features.pkl"
MODEL_PATH = os.path.join(MODEL_DIR, MODEL_FILENAME)
FEATURES_PATH = os.path.join(MODEL_DIR, FEATURES_FILENAME)

MODEL_S3_KEY = f"models/{MODEL_FILENAME}"
FEATURES_S3_KEY = f"models/{FEATURES_FILENAME}"


def _load_model_and_features():
    """
    Downloads the trained model and its training-time feature column
    list from S3. Both must have been produced together by the same
    training run in recommender.py.
    """
    os.makedirs(MODEL_DIR, exist_ok=True)
    s3 = boto3.client("s3")

    s3.download_file(S3_BUCKET, MODEL_S3_KEY, MODEL_PATH)
    s3.download_file(S3_BUCKET, FEATURES_S3_KEY, FEATURES_PATH)

    clf = joblib.load(MODEL_PATH)
    expected_columns = joblib.load(FEATURES_PATH)

    return clf, expected_columns


# ============================================================
# GENERATE RECOMMENDATIONS FOR INACTIVE CUSTOMERS
# ============================================================


def recommend_user_based_inactive_customers(
    df=DATASET_URI,
    k=5,
    inactivity_days=270,
    top_n=5,
):
    """

    Generate recommendations for inactive customers using a previously
    trained GBoost model (see recommender.py / train_gboost_model).

    This function does not train anything -- it loads the model and
    its training-time feature columns from S3, predicts, and persists
    recommendations using the exact same flow as before:

        historical purchases before the inactivity window
            -> customer features
            -> load trained GBoost + expected feature columns
            -> predict a category for inactive customers
            -> recommend the top-k most popular recent items in that category
            -> persist to S3 predictions + log

    top_n is retained for backward compatibility with existing callers but is
    not used by the classifier.

    Same parameters, same signature, same persistence flow as the
    original recommend_user_based_inactive_customers -- only the
    training step has moved out to recommender.py.
    """
    df = cargar_datos(DATASET_URI)

    raw = df.copy()

    data = clean_and_save_dataset(raw)

    data["Purchase Date"] = pd.to_datetime(data["Purchase Date"])

    cutoff_date = (
        data["Purchase Date"].max()
        - pd.Timedelta(days=inactivity_days)
    )

    # Historical information available before the recent window.
    df_train = data[
        data["Purchase Date"] <= cutoff_date
    ].copy()

    # Recent window used to identify active customers and determine
    # what is currently popular inside each category.
    df_recent = data[
        data["Purchase Date"] > cutoff_date
    ].copy()

    # Possible churn customers: they have historical behavior but did not
    # purchase during the recent inactivity window.
    train_customers = set(df_train["Customer ID"].unique())
    recent_customers = set(df_recent["Customer ID"].unique())
    inactive_customers = sorted(train_customers - recent_customers)

    if df_train.empty or df_recent.empty or not inactive_customers:
        logger.info(
            "GBoost predict skipped: insufficient train/recent data or no inactive customers"
        )
        return pd.DataFrame()

    features_train = build_customer_features(df_train)

    clf, expected_columns = _load_model_and_features()

    # ------------------------------------------------------------
    # Enforce that df_train produces exactly the columns the model
    # was trained on. New categories must never appear without a
    # retrain (and proper notification) -- so a mismatch here fails
    # loudly instead of silently reindexing.
    # ------------------------------------------------------------
    actual_columns = set(features_train.columns)
    expected_columns_set = set(expected_columns)

    missing_at_predict = expected_columns_set - actual_columns
    unexpected_new = actual_columns - expected_columns_set

    if missing_at_predict or unexpected_new:
        raise ValueError(
            "Feature mismatch between training and prediction data. "
            "This should not happen unless a category was introduced "
            "without retraining. "
            f"Missing: {missing_at_predict}, Unexpected: {unexpected_new}"
        )

    # Same column order the model was trained on.
    features_train = features_train[expected_columns]

    churn_features = features_train.loc[
        features_train.index.isin(inactive_customers)
    ]

    pred_category_churn = pd.Series(dtype=object)

    if not churn_features.empty:
        pred_category_churn = pd.Series(
            clf.predict(churn_features),
            index=churn_features.index,
        )
    else:
        logger.warning("GBoost predict: no matching inactive customers with features")

    # Current candidate pool: most popular recent items within each category.
    item_pop_by_cat_recent = (
        df_recent
        .groupby(["Category", "Item Purchased"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    customer_info = (
        data
        .sort_values("Purchase Date")
        .groupby("Customer ID")
        .last()
    )

    results = []

    for customer_id in inactive_customers:
        predicted_category = pred_category_churn.get(customer_id, None)

        if predicted_category is not None:
            recommendation = (
                item_pop_by_cat_recent[
                    item_pop_by_cat_recent["Category"] == predicted_category
                ]["Item Purchased"]
                .head(k)
                .tolist()
            )
        else:
            recommendation = []

        customer = customer_info.loc[customer_id]

        results.append(
            {
                "Customer Name": customer.get("Customer Full Name", None),
                "Customer Email": customer.get("Customer Email", None),
                "Customer ID": customer_id,
                "Location": customer.get("Location", None),
                "Current Season": season_from_month(pd.Timestamp.now().month),
                "Recommendations": recommendation,
                "Date": pd.Timestamp.now(),
            }
        )

    # Keep the existing prediction persistence and logging flow unchanged.
    new_df = pd.DataFrame(results)
    existing_df = descargar_datos_des3(S3_PREDICTIONS_KEY, S3_BUCKET)
    df_final = pd.concat([existing_df, new_df], ignore_index=True)
    # enviando el log de predicciones a s3
    cargar_datos_as3(df_final, S3_PREDICTIONS_KEY, S3_BUCKET)

    log_event(
        logger,
        f"GBoost recommender completed predictions: {len(results)} customers, "
        f"{sum(len(r['Recommendations']) for r in results)} recommendations",
        run_id=generate_run_id()
    )
    # enviar el log de metadata a s3
    log_file = (
        Path(LAMBDA_LOG)
        / f"reactiva_{datetime.now().strftime('%Y-%m-%d')}.log"
    )

    if log_file.exists():
        with open(log_file, "rb") as f:
            log_data = f.read()
        cargar_log_as3(
            log_data,
            S3_PREDICTIONSLOG,
            S3_BUCKET
        )
    else:
        logger.info("Log file does not exist in this environment")

    return pd.DataFrame(results)


if __name__ == "__main__":
    output = recommend_user_based_inactive_customers()
    print(f"Rows generated: {len(output)}")