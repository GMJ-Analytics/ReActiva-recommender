import os
import joblib
import pandas as pd
import boto3

from reactiva.data.validate_data import clean_and_save_dataset
from reactiva.utils.logger import setup_logger
from sklearn.ensemble import GradientBoostingClassifier

from botocore.exceptions import ClientError
from io import StringIO
from reactiva.config import S3_BUCKET,API_KEY,S3_PREDICTIONS_KEY,MATRIX_UIR,LAMBDA_LOG,S3_PREDICTIONSLOG,DATASET_URI
from reactiva.data.load_data import cargar_datos_as3,descargar_datos_des3,cargar_log_as3,cargar_datos
from reactiva.features.build_features import build_customer_features
from reactiva.data.save_results import generate_run_id
from datetime import datetime
from reactiva.utils.logger import log_event,setup_logger
from reactiva.features.build_features import (add_season, season_from_month)
from reactiva.features.context import (recommend_contextual_popularity)
from pathlib import Path



# ============================================================
# ITEM-SIMILARITY MATRIX CACHE
# ============================================================

_similarity_matrix = None

logger = setup_logger('model_train_log', LAMBDA_LOG)

# ============================================================
# MODEL PERSISTENCE
# ============================================================
# MODEL_DIR defaults to the current directory (local runs). When this
# runs inside Lambda, lambda_function.py sets MODEL_DIR=/tmp before
# importing this module, since Lambda's filesystem is read-only
# outside of /tmp.

MODEL_DIR = os.getenv("MODEL_DIR", ".")
MODEL_FILENAME = "recommender_model.pkl"
FEATURES_FILENAME = "recommender_features.pkl"
MODEL_PATH = os.path.join(MODEL_DIR, MODEL_FILENAME)
FEATURES_PATH = os.path.join(MODEL_DIR, FEATURES_FILENAME)

MODEL_S3_KEY = f"models/{MODEL_FILENAME}"
FEATURES_S3_KEY = f"models/{FEATURES_FILENAME}"


# ============================================================
# TRAIN GBOOST MODEL FOR INACTIVE-CUSTOMER RECOMMENDATIONS
# ============================================================


def train_gboost_model(
    df=DATASET_URI,
    inactivity_days=270,
):
    """
    Train the GBoost classifier used to predict which category an
    inactive customer is likely to return to.

    This function only trains and persists the model -- it does not
    predict, does not build recommendations, and does not return a
    DataFrame. Use predict.py to load the resulting model and
    generate recommendations without retraining every time.

    Saves two artifacts, both locally (respecting MODEL_DIR) and to
    S3:
      - the fitted classifier (recommender_model.pkl)
      - the exact training-time feature columns (recommender_features.pkl)

    New categories must never appear at prediction time without a
    retrain -- predict.py enforces this by failing loudly on any
    column mismatch, rather than silently reindexing.
    """
    if isinstance(df, pd.DataFrame):
        raw = df.copy()
    else:
        raw = cargar_datos(df).copy()

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

    # Recent window used to identify active customers and create labels.
    df_recent = data[
        data["Purchase Date"] > cutoff_date
    ].copy()

    if df_train.empty or df_recent.empty:
        logger.info(
            "GBoost training skipped: insufficient train/recent data"
        )
        return None

    features_train = build_customer_features(df_train)

    # Active customers are the supervised training examples. Their label
    # is their most frequent category during the recent window.
    labels_recent = (
        df_recent[
            df_recent["Customer ID"].isin(features_train.index)
        ]
        .groupby("Customer ID")["Category"]
        .agg(lambda x: x.mode().iloc[0])
    )

    X = features_train.loc[
        features_train.index.isin(labels_recent.index)
    ]
    y = labels_recent.loc[X.index]

    if len(X) == 0 or y.nunique() <= 1:
        logger.warning(
            "GBoost training aborted: fewer than two target categories"
        )
        return None

    class_counts = y.value_counts()
    n_classes = len(class_counts)
    n_samples = len(y)

    class_weights = {
        category: n_samples / (n_classes * count)
        for category, count in class_counts.items()
    }
    sample_weight = y.map(class_weights)

    clf = GradientBoostingClassifier(random_state=42)
    clf.fit(X, y, sample_weight=sample_weight)

    # ------------------------------------------------------------
    # Persist the trained model + the exact feature columns it was
    # trained on. Serialized once in memory, then written locally
    # (useful if training and prediction ever run on the same box)
    # and sent directly to S3 from that same buffer -- S3 is the
    # source of truth predict.py always pulls from, regardless of
    # where training ran.
    # ------------------------------------------------------------
    from io import BytesIO

    model_buffer = BytesIO()
    joblib.dump(clf, model_buffer)
    model_buffer.seek(0)

    features_buffer = BytesIO()
    joblib.dump(list(clf.feature_names_in_), features_buffer)
    features_buffer.seek(0)

    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        f.write(model_buffer.getvalue())
    with open(FEATURES_PATH, "wb") as f:
        f.write(features_buffer.getvalue())
    logger.info(f"Model saved locally to {MODEL_PATH}")
    logger.info(f"Feature columns saved locally to {FEATURES_PATH}")

    s3 = boto3.client("s3")
    s3.put_object(Bucket=S3_BUCKET, Key=MODEL_S3_KEY, Body=model_buffer.getvalue())
    s3.put_object(Bucket=S3_BUCKET, Key=FEATURES_S3_KEY, Body=features_buffer.getvalue())
    logger.info(f"Model sent directly to s3://{S3_BUCKET}/{MODEL_S3_KEY}")
    logger.info(f"Feature columns sent directly to s3://{S3_BUCKET}/{FEATURES_S3_KEY}")

    return clf


if __name__ == "__main__":
    model = train_gboost_model()
    if model is not None:
        print(f"Model trained and saved to {MODEL_PATH}")
    else:
        print("Training skipped or aborted -- see logs.")

def _load_similarity_matrix():
    """
    Load the item-similarity matrix only when it is required.

    The matrix is cached after the first load so importing this
    module does not trigger unnecessary I/O.
    """

    global _similarity_matrix

    if _similarity_matrix is None:
        _similarity_matrix = pd.read_csv(MATRIX_UIR)

    return _similarity_matrix

# ============================================================
# ITEM-BASED RECOMMENDATIONS
# ============================================================

def get_recommendations_items(
    trigger_item,
    top_n=5,
):
    """
    Return the most similar products for a trigger item.

    The item-similarity matrix is loaded lazily on first use
    instead of during module import.
    """

    similarity = _load_similarity_matrix()

    # Check whether the trigger exists in the Items column

    if trigger_item not in similarity["Items"].values:
        return []

    # Get the row corresponding to the trigger item

    scores = similarity.loc[
        similarity["Items"] == trigger_item
    ].iloc[0]

    # Remove the Items label

    scores = scores.drop("Items")

    # Remove zero similarities

    scores = scores[
        scores > 0
    ]

    # Highest similarity first

    scores_filter = scores.sort_values(
        ascending=False
    )

    return (
        scores_filter
        .head(top_n)
        .index
        .tolist()
    )
