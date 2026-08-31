import os

from dotenv import load_dotenv

# Carga las variables definidas en el archivo .env local. Este archivo contiene configuraciones privadas y no se sube a GitHub.

load_dotenv()

# Configuración de la fuente de datos en Amazon S3.
DATASET_URI = os.getenv("DATASET_URI")
S3_BUCKET = os.getenv("S3_BUCKET")

# ACCESO files
MATRIX_UIR = os.getenv('MATRIX_URI')
S3_PREDICTIONS_KEY = os.getenv('S3_PREDICTIOSKEY')

# Configuraciones que podrán utilizarse más adelante.
AWS_REGION = os.getenv("AWS_REGION")
API_KEY = os.getenv("API_KEY")

#CREDNETIALS
USUARIO_ADMIN = os.getenv('USUARIO_ADMIN')
PASSWORD_ADMIN = os.getenv('PASSWORD_ADMIN')

#LOGS

S3_PREDICTIONSLOG= os.getenv('S3_PREDICTIONSLOG')
if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    LAMBDA_LOG = "/tmp"
else:
    LAMBDA_LOG = "predictions_log"


# Validamos las variables obligatorias para trabajar con el dataset.
if not DATASET_URI:
    raise ValueError(
        "Falta configurar DATASET_URI en el archivo .env"
    )

if not S3_BUCKET:
    raise ValueError(
        "Falta configurar S3_BUCKET en el archivo .env"
    )