import numpy as np
import pandas as pd
from reactiva.config import DATASET_URI,MATRIX_UIR,S3_BUCKET
from reactiva.features.build_features import add_season, season_from_month

from collections import defaultdict
import s3fs
from matplotlib import pyplot as plt
import seaborn as sns
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

df = pd.read_csv(DATASET_URI)
similarity = pd.read_csv(MATRIX_UIR)


def recommend_popularity_inactive_customers(
    df,
    k=5,
    inactivity_days=270
):

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

    results = []

    # --------------------------------------------------------
    # Recommend for each inactive customer
    # --------------------------------------------------------

    for customer_id in inactive_customers:

        location = customer_location.loc[
            customer_id
        ]

        # ----------------------------------------------------
        # Popularity for customer's location
        # and current season
        # ----------------------------------------------------

        location_season_data = df[
            (df['Location'] == location) &
            (df['season'] == current_season)
        ]

        if location_season_data.empty:
            recommendation = []
        else:
            recommendation = (
                location_season_data[
                    'Item Purchased'
                ]
                .value_counts()
                .head(k)
                .index
                .tolist()
            )

        results.append({
            'Customer ID': customer_id,
            'Location': location,
            'Current Season': current_season,
            'Recommendations': recommendation
        })

    return pd.DataFrame(results)

recommendations = recommend_popularity_inactive_customers(
    df,
    k=5,
    inactivity_days=270
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