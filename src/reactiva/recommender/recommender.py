import pandas as pd
import boto3
from botocore.exceptions import ClientError
from io import StringIO
from reactiva.config import S3_BUCKET,API_KEY,S3_PREDICTIONS_KEY
from reactiva.data.load_data import cargar_datos_as3,descargar_datos_des3
from reactiva.features.build_features import build_customer_features
import logging
from sklearn.ensemble import GradientBoostingClassifier
from reactiva.config import MATRIX_UIR
from reactiva.features.build_features import (add_season, season_from_month)
from reactiva.features.context import (recommend_contextual_popularity)



# ============================================================
# ITEM-SIMILARITY MATRIX CACHE
# ============================================================

_similarity_matrix = None

logging.basicConfig(
    filename= 'logs/app.logs',
    level=logging.INFO,
    format=' %(asctime)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)

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
# GRADIENT BOOSTING RECOMMENDER FOR INACTIVE CUSTOMERS
# ============================================================


def recommend_user_based_inactive_customers(
    df,
    k=5,
    inactivity_days=270,
    top_n=5,
):
    """
    Generate recommendations for inactive customers using Gradient Boosting.

    The function name is intentionally preserved for compatibility with the
    existing application. The recommendation logic is now GBoost-only:

        historical purchases before the inactivity window
            -> customer features
            -> train GBoost using active customers' most frequent recent category
            -> predict a category for inactive customers
            -> recommend the top-k most popular recent items in that category

    top_n is retained for backward compatibility with existing callers but is
    not used by the classifier.
    """

    data = df.copy()
    data["Purchase Date"] = pd.to_datetime(data["Purchase Date"])

    cutoff_date = (
        data["Purchase Date"].max()
        - pd.Timedelta(days=inactivity_days)
    )

    # Historical information available before the recent window.
    df_train = data[
        data["Purchase Date"] <= cutoff_date
    ].copy()

    # Recent window used to identify active customers, create labels, and
    # determine what is currently popular inside each category.
    df_recent = data[
        data["Purchase Date"] > cutoff_date
    ].copy()

    # Possible churn customers: they have historical behavior but did not
    # purchase during the recent inactivity window.
    train_customers = set(df_train["Customer ID"].unique())
    recent_customers = set(df_recent["Customer ID"].unique())
    inactive_customers = sorted(train_customers - recent_customers)

    if df_train.empty or df_recent.empty or not inactive_customers:
        logger.info("GBoost recommender skipped: insufficient train/recent data or no inactive customers")
        return pd.DataFrame()

    features_train = build_customer_features(df_train)

    # Active customers are the supervised training examples. Their label is
    # their most frequent category during the recent window.
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

    pred_category_churn = pd.Series(dtype=object)

    if len(X) > 0 and y.nunique() > 1:
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

        churn_features = features_train.loc[
            features_train.index.isin(inactive_customers)
        ]

        if not churn_features.empty:
            pred_category_churn = pd.Series(
                clf.predict(churn_features),
                index=churn_features.index,
            )
    else:
        logger.warning("GBoost recommender could not train: fewer than two target categories")

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
    cargar_datos_as3(df_final, S3_PREDICTIONS_KEY, S3_BUCKET)

    logger.info("GBoost recommender completed predictions")

    return pd.DataFrame(results)



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
