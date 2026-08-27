import pandas as pd
import boto3
from botocore.exceptions import ClientError
from io import StringIO
from reactiva.config import S3_BUCKET,API_KEY,S3_PREDICTIONS_KEY
from reactiva.data.load_data import cargar_datos_as3,descargar_datos_des3

import logging
from sklearn.metrics.pairwise import cosine_similarity
from reactiva.config import MATRIX_UIR
from reactiva.features.build_features import (add_season, season_from_month)
from reactiva.features.context import (recommend_contextual_popularity)
from pathlib import Path



# ============================================================
# ITEM-SIMILARITY MATRIX CACHE
# ============================================================

_similarity_matrix = None

#se crea la carpeta de logs si no existe para evitar errores
#al importar el recomendador desde Streamlit, Docker o notebooks
LOG_DIR = Path('logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / 'app.logs',
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
# CUSTOMER PROFILE
# ============================================================

def build_customer_profile(df):
    """
    Build the customer-item interaction matrix used by the
    User-Based Collaborative Filtering recommender.
    """

    customer_item_matrix = (
        df
        .groupby(["Customer ID", "Item Purchased"])
        .size()
        .unstack(fill_value=0)
    )

    return customer_item_matrix


def build_customer_similarity(df):
    """
    Build the customer-to-customer cosine-similarity matrix.
    """

    customer_item_matrix = build_customer_profile(df)

    similarity = cosine_similarity(
        customer_item_matrix
    )

    similarity_df = pd.DataFrame(
        similarity,
        index=customer_item_matrix.index,
        columns=customer_item_matrix.index,
    )

    return similarity_df


# ============================================================
# USER-BASED RECOMMENDER FOR INACTIVE CUSTOMERS
# ============================================================

def recommend_user_based_inactive_customers(
    df,
    k=5,
    inactivity_days=270,
    top_n=5,
):
    """
    Generate recommendations for inactive customers using
    User-Based Collaborative Filtering.

    If the collaborative-filtering model cannot produce usable
    recommendations, the standardized contextual fallback is used:

    season + Location
        ->
    Location
        ->
    season
        ->
    Global
    """

    # --------------------------------------------------------
    # Add standardized season feature
    # --------------------------------------------------------

    df = add_season(df)

    # --------------------------------------------------------
    # Current season
    # --------------------------------------------------------

    current_month = pd.Timestamp.now().month

    current_season = season_from_month(
        current_month
    )

    # --------------------------------------------------------
    # Find last purchase of every customer
    # --------------------------------------------------------

    last_purchase = (
        df
        .groupby("Customer ID")["Purchase Date"]
        .max()
    )

    cutoff_date = (
        df["Purchase Date"].max()
        - pd.Timedelta(days=inactivity_days)
    )

    inactive_customers = (
        last_purchase[
            last_purchase <= cutoff_date
        ]
        .index
    )

    # --------------------------------------------------------
    # Most recent location of each inactive customer
    # --------------------------------------------------------

    customer_location = (
        df
        .sort_values("Purchase Date")
        .groupby("Customer ID")["Location"]
        .last()
    )

    # --------------------------------------------------------
    # Customer-item profile + similarity matrix
    #
    # Built on the full purchase history, across all seasons,
    # so inactive customers with no current-season purchases
    # still receive a similarity score.
    # --------------------------------------------------------

    similarity_df = build_customer_similarity(df)

    # --------------------------------------------------------
    # Purchases from the current season only.
    #
    # These purchases form the candidate pool from which
    # neighbors' recommendations are selected.
    # --------------------------------------------------------

    current_season_data = df[
        df["season"] == current_season
    ]

    results = []

    # --------------------------------------------------------
    # Recommend for each inactive customer
    # --------------------------------------------------------

    for customer_id in inactive_customers:

        location = customer_location.loc[
            customer_id
        ]
        c_name = df.loc[df['Customer ID']== customer_id,'Customer Full Name'].iloc[0]
        c_email =df.loc[df['Customer ID']== customer_id,'Customer Email'].iloc[0]

        # ----------------------------------------------------
        # User-Based Collaborative Filtering
        #
        # Find the customer's nearest neighbors by purchase
        # profile similarity and recommend their most frequent
        # products purchased during the current season.
        # ----------------------------------------------------

        recommendation = []

        if customer_id in similarity_df.index:

            neighbors = (
                similarity_df[customer_id]
                .drop(customer_id)
                .sort_values(ascending=False)
                .head(top_n)
            )

            neighbors = neighbors[
                neighbors > 0
            ]

            if not neighbors.empty:

                neighbor_purchases = (
                    current_season_data[
                        current_season_data[
                            "Customer ID"
                        ].isin(neighbors.index)
                    ]
                )

                if not neighbor_purchases.empty:

                    recommendation = (
                        neighbor_purchases[
                            "Item Purchased"
                        ]
                        .value_counts()
                        .head(k)
                        .index
                        .tolist()
                    )

        # ----------------------------------------------------
        # Standardized contextual fallback
        #
        # Used only when User-Based CF cannot produce usable
        # recommendations.
        # ----------------------------------------------------

        if not recommendation:

            contextual_result = (
                recommend_contextual_popularity(
                    df=df,
                    location=location,
                    season=current_season,
                    k=k,
                )
            )

            recommendation = contextual_result[
                "recommendations"
            ]

        results.append(
            {   "Customer Name":c_name,
                "Customer Email":c_email,
                "Customer ID": customer_id,
                "Location": location,
                "Current Season": current_season,
                "Recommendations": recommendation,
                "Date": pd.Timestamp.now()
            }
        )
    # updating the dataframe in s3#

    new_df = pd.DataFrame(results)
    existing_df = descargar_datos_des3(S3_PREDICTIONS_KEY,S3_BUCKET)
    
    df_final= pd.concat([existing_df, new_df],ignore_index = True)

    cargar_datos_as3(df_final,S3_PREDICTIONS_KEY,S3_BUCKET)

    logger.info('recommender completed predictions')
    
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
