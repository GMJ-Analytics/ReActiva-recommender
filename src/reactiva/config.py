import os

from dotenv import load_dotenv

# Carga las variables definidas en el archivo .env local. Este archivo contiene configuraciones privadas y no se sube a GitHub.

load_dotenv()

# Configuración de la fuente de datos en Amazon S3.
DATASET_URI = os.getenv("DATASET_URI")
S3_BUCKET = os.getenv("S3_BUCKET")

# Configuraciones que podrán utilizarse más adelante.
AWS_REGION = os.getenv("AWS_REGION")
API_KEY = os.getenv("API_KEY")


# Validamos las variables obligatorias para trabajar con el dataset.
if not DATASET_URI:
    raise ValueError(
        "Falta configurar DATASET_URI en el archivo .env"
    )

if not S3_BUCKET:
    raise ValueError(
        "Falta configurar S3_BUCKET en el archivo .env"
    )