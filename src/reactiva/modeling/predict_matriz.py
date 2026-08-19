from io import BytesIO,StringIO
import boto3
import numpy as np
import pandas as pd
from collections import defaultdict
from sklearn.metrics.pairwise import cosine_similarity
from reactiva.config import DATASET_URI,S3_BUCKET


df_train = pd.read_csv(DATASET_URI)

def build_item_item_similarity(df_train, bucket_name, s3_key):

    co_count = defaultdict(
        lambda: defaultdict(int)
    )

    # --------------------------------------------------------
    # Each customer contributes each item pair once
    # --------------------------------------------------------

    customer_items = (
        df_train
        .groupby('Customer ID')['Item Purchased']
        .apply(set)
    )

    # --------------------------------------------------------
    # Create item list and mapping
    # --------------------------------------------------------

    all_items = sorted(
        df_train['Item Purchased']
        .dropna()
        .unique()
    )

    id_map = {
        item: i
        for i, item in enumerate(all_items)
    }

    # --------------------------------------------------------
    # Build co-occurrence counts
    # --------------------------------------------------------

    for items in customer_items:

        item_list = list(items)

        for i in range(len(item_list)):

            item_a = item_list[i]

            for j in range(i + 1, len(item_list)):

                item_b = item_list[j]

                co_count[item_a][item_b] += 1
                co_count[item_b][item_a] += 1

    # --------------------------------------------------------
    # Build item × item co-occurrence matrix
    # --------------------------------------------------------

    matrix = np.zeros(
        (
            len(all_items),
            len(all_items)
        ),
        dtype=float
    )

    for item, neighbors in co_count.items():

        i = id_map[item]

        for neighbor, count in neighbors.items():

            j = id_map[neighbor]

            matrix[i, j] = count

    # --------------------------------------------------------
    # Calculate item-item similarity
    # --------------------------------------------------------

    similarity = cosine_similarity(
        matrix
    )

    np.fill_diagonal(
        similarity,
        0
    )

    similarity = pd.DataFrame(
        similarity,
        index=all_items,
        columns=all_items
    )

    # --------------------------------------------------------
    # Upload similarity matrix directly to S3
    # --------------------------------------------------------

   
    buffer = StringIO()

    similarity.to_csv(buffer,index_label='Items')
    

    buffer.seek(0)

    s3 = boto3.client('s3')

    s3.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=buffer.getvalue()
    )

    print(
        f'Similarity matrix uploaded to s3://{bucket_name}/{s3_key}'
    )

    return similarity

similarity = build_item_item_similarity(
    df_train,
    bucket_name=S3_BUCKET,
    s3_key='models1/item_item_similarity.csv'
)