import numpy as np
import pandas as pd
from config import DATASET_URI
from collections import defaultdict
import s3fs
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

df = pd.read_csv(DATASET_URI)


#preprocesamiento puede reemplazarse con el file feature_engineering#
df['Purchase Date'] = pd.to_datetime(df['Purchase Date'])
df['session'] = df['Purchase Date'].dt.month.apply(lambda x: 'winter' if x in(12,1,2) else 'summer' if  x in (3,4,5) else 'monsoon' if x in (6,7,8,9) else 'post-monsoon')
df_tovectorize = df[['Age','Gender','Location','session','Brand','Category','Online/Offline','Customer ID','Item Purchased']]


df_purchases_270morethandays = df[df['Purchase Date']<=(df['Purchase Date'].max() - pd.Timedelta(days=270))]
df_purchases_270lessthandays = df[df['Purchase Date']>(df['Purchase Date'].max() - pd.Timedelta(days=270))]
cx_didnot_270daysago =np.setdiff1d(df_purchases_270morethandays['Customer ID'].unique(), df_purchases_270lessthandays['Customer ID'].unique())

# trayendo la temporada actual# 
month = pd.Timestamp.now().month

session = (
    'winter' if month in (12, 1, 2)
    else 'summer' if month in (3, 4, 5)
    else 'monsoon' if month in (6, 7, 8, 9)
    else 'post-monsoon')

session_list = pd.Series(['winter','summer','monsoon','post-monsoon'])


def user_recomendation(user):
    # creamos el default dictionary que va a almacenar las usuarios que similares y que si compraron en la sessión que neustro cliente no compró#
    user_dict = defaultdict(dict)
    #excluimos la temporada climatica que queremos predecir#
    list_session = session_list[session_list!= session]

    df_sessio_to_predict = df_tovectorize[df_tovectorize['session'] == session]
    # iteramos todas las sessión que no son las predictoras#
    for i in list_session:
        
        df_tovector= df_tovectorize[df_tovectorize['session'] == i]
        user_item_matrix = pd.crosstab(df_tovector['Customer ID'],df_tovector['Item Purchased'])
        
        similarity= cosine_similarity(user_item_matrix)
        similarity_df = pd.DataFrame(similarity,index= user_item_matrix.index, columns=user_item_matrix.index)
        if user not in similarity_df.columns:
            continue
        top5 =(
        similarity_df[user]
        .drop(user)
        .sort_values(ascending=False).head(5))
        for user,l in top5.items():
            if user not in df_sessio_to_predict.values:
                continue
            else:
                user_dict[user] = df_sessio_to_predict[df_sessio_to_predict['Customer ID']== user]
    if len(user_dict) > 1:
        df_users = pd.concat(user_dict.values(), ignore_index=True)
        m =df_users['Category'].mode().iloc[0]
        df_recomend = df_users[df_users['Category'] == m]
        recomendation = df_recomend['Item Purchased'].values.tolist()
        print(f'Estos items podrian interesarte para la temporada {session} :', ', '.join(dict.fromkeys(recomendation)))
    else:
        print('no hay recomendaciones para este usuario')
    
        
    