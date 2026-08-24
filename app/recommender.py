import numpy as np
import pandas as pd
from reactiva.config import DATASET_URI,MATRIX_UIR,S3_BUCKET

from collections import defaultdict
import s3fs
from matplotlib import pyplot as plt
import seaborn as sns
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

df = pd.read_csv(DATASET_URI)
similarity = pd.read_csv(MATRIX_UIR)


def build_customer_profile(df):
    customer_item_matrix = (
        df
        .groupby(['Customer ID', 'Item Purchased'])
        .size()
        .unstack(fill_value=0)
    )
    return customer_item_matrix


def build_customer_similarity(df):
    customer_item_matrix = build_customer_profile(df)
    similarity = cosine_similarity(customer_item_matrix)
    similarity_df = pd.DataFrame(
        similarity,
        index=customer_item_matrix.index,
        columns=customer_item_matrix.index
    )
    return similarity_df


def recommend_user_based_inactive_customers(
    df,
    k=5,
    inactivity_days=270,
    top_n=5
):

    df = df.copy()

    df['Purchase Date'] = pd.to_datetime(
        df['Purchase Date']
    )

    # --------------------------------------------------------
    # Create season from purchase date
    # --------------------------------------------------------

    df['season'] = df['Purchase Date'].dt.month.apply(
        lambda x:
            'winter' if x in (12, 1, 2)
            else 'summer' if x in (3, 4, 5)
            else 'monsoon' if x in (6, 7, 8, 9)
            else 'post-monsoon'
    )

    # --------------------------------------------------------
    # Current season
    # --------------------------------------------------------

    current_month = pd.Timestamp.now().month

    current_season = (
        'winter' if current_month in (12, 1, 2)
        else 'summer' if current_month in (3, 4, 5)
        else 'monsoon' if current_month in (6, 7, 8, 9)
        else 'post-monsoon'
    )

    # --------------------------------------------------------
    # Find last purchase of every customer
    # --------------------------------------------------------

    last_purchase = (
        df.groupby('Customer ID')['Purchase Date']
        .max()
    )

    cutoff_date = (
        df['Purchase Date'].max()
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
        df.sort_values('Purchase Date')
        .groupby('Customer ID')['Location']
        .last()
    )

    # --------------------------------------------------------
    # Customer-item profile + similarity matrix
    # (built on full purchase history, all seasons, so
    # inactive customers with no current-season purchases
    # still get a similarity score)
    # --------------------------------------------------------

    similarity_df = build_customer_similarity(df)

    # --------------------------------------------------------
    # Purchases from the current season only, used as the
    # pool neighbors' recommendations are drawn from
    # --------------------------------------------------------

    current_season_data = df[df['season'] == current_season]

    # --------------------------------------------------------
    # Location + season popularity, used only as a fallback
    # when a customer has no usable neighbors
    # --------------------------------------------------------

    def location_season_popularity(location, k):
        location_season_data = current_season_data[
            current_season_data['Location'] == location
        ]

        if location_season_data.empty:
            return []

        return (
            location_season_data['Item Purchased']
            .value_counts()
            .head(k)
            .index
            .tolist()
        )

    results = []

    # --------------------------------------------------------
    # Recommend for each inactive customer
    # --------------------------------------------------------

    for customer_id in inactive_customers:

        location = customer_location.loc[
            customer_id
        ]

        # ----------------------------------------------------
        # User-based CF: find the customer's nearest
        # neighbors by purchase-profile similarity, then
        # recommend the neighbors' most frequent items
        # purchased in the current season
        # ----------------------------------------------------

        recommendation = []

        if customer_id in similarity_df.index:
            neighbors = (
                similarity_df[customer_id]
                .drop(customer_id)
                .sort_values(ascending=False)
                .head(top_n)
            )
            neighbors = neighbors[neighbors > 0]

            if not neighbors.empty:
                neighbor_purchases = current_season_data[
                    current_season_data['Customer ID'].isin(
                        neighbors.index
                    )
                ]

                if not neighbor_purchases.empty:
                    recommendation = (
                        neighbor_purchases['Item Purchased']
                        .value_counts()
                        .head(k)
                        .index
                        .tolist()
                    )

        # ----------------------------------------------------
        # Fallback: no neighbors, or no neighbor activity in
        # the current season -> location + season popularity
        # ----------------------------------------------------

        if not recommendation:
            recommendation = location_season_popularity(location, k)

        results.append({
            'Customer ID': customer_id,
            'Location': location,
            'Current Season': current_season,
            'Recommendations': recommendation
        })

    return pd.DataFrame(results)

recommendations = recommend_user_based_inactive_customers(
    df,
    k=5,
    inactivity_days=270,
    top_n=5
)

print(recommendations)

#_______________#

def get_recommendations_items(trigger_item, top_n=5):

    # Check whether the trigger exists in the Items column
    if trigger_item not in similarity['Items'].values:
        return []

    # Get the row corresponding to the trigger item
    scores = similarity.loc[
        similarity['Items'] == trigger_item
    ].iloc[0]
    # Remove the Items label
    scores = scores.drop('Items')
    # Remove zero similarities
    scores = scores[scores > 0]
    # Highest similarity first
    scores_filter = scores.sort_values(ascending=False)

    return scores_filter.head(top_n).index.tolist()
