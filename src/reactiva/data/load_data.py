import boto3
from reactiva.config import S3_BUCKET
from io import StringIO
import pandas as pd
from botocore.exceptions import ClientError


def cargar_datos():
    from reactiva.config import DATASET_URI
    path_file =DATASET_URI
    

    import pandas as pd 

    try: 
        if path_file.endswith('.xlsx'):
            df = pd.read_excel(path_file)
        else:
            df = pd.read_csv(path_file)
        return df
    except FileNotFoundError:
        print(f'please verify the path file, {path_file} does not exist')

def  cargar_datos_as3(df,Key_s3,bucket):
    buffer = StringIO()
    s3= boto3.client('s3')

    df.to_csv(buffer, index =False)
    s3.put_object(
        Bucket = bucket,
        Key= Key_s3,
        Body = buffer.getvalue()

    )

def descargar_datos_des3(Key_s3,bucket):
    s3 = boto3.client('s3')
    try:
       response= s3.get_object(
            Bucket= bucket,
            Key= Key_s3
        )
       df = pd.DataFrame(response['Body'])
    except ClientError:
        df = pd.DataFrame()
    return df
        
    