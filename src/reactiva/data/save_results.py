import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import boto3
from botocore.exceptions import BotoCoreError, ClientError

# importaciones de la configuracion del proyecto y del sistema de logger
from reactiva.config import AWS_REGION, S3_BUCKET
from reactiva.utils.logger import log_event, setup_logger

logger = setup_logger(name="reactiva.data.save_results")

# se obtiene la raiz del proyecto: ReActiva-recommender/
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# guarda por defecto en ReActiva-recommender/artifacts/metrics/
LOCAL_ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "metrics"

# configuracion de S3 (produccion) ---
S3_RESULTS_PREFIX = "results/predictions"


# generacion de nombres y versionado
def generate_run_id() -> str:
    """
    Genera un ID único para la corrida basado en fecha/hora y un hash corto.
    Evita sobrescrituras accidentales en local y S3.
    """
    timestamp = datetime.now().strftime("%Y/%m/%d_%H:%M:%S")
    short_hash = uuid.uuid4().hex[:6]
    return f"run_{timestamp}_{short_hash}"


# funciones de guardado:

def save_to_local(data, file_path: Path, is_dataframe: bool = False) -> None:
    """Guarda un DataFrame (CSV) o un Diccionario/JSON en el sistema de archivos local."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    if is_dataframe and isinstance(data, pd.DataFrame):
        data.to_csv(file_path, index=False)
    else:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
    log_event(
        logger, 
        "Archivo guardado en almacenamiento local", 
        path=str(file_path),
        is_dataframe=is_dataframe
    )


def upload_to_s3(local_path: Path, s3_key: str, bucket_name: str = S3_BUCKET) -> None:
    """Sube un archivo desde el almacenamiento local hacia Amazon S3."""
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    try:
        s3_client.upload_file(str(local_path), bucket_name, s3_key)
        log_event(
            logger,
            "Archivo subido exitosamente a Amazon S3",
            bucket=bucket_name,
            s3_key=s3_key,
            local_path=str(local_path)
        )
    except (BotoCoreError, ClientError) as e:
        log_event(
            logger,
            "Error al intentar subir archivo a Amazon S3",
            level=30,
            bucket=bucket_name,
            s3_key=s3_key,
            error=str(e)
        )
        raise e



# funcion principal exportable

def save_experiment_results(
    predictions_df: pd.DataFrame,
    metrics_dict: dict,
    metadata_dict: dict = None,
    env: str = None
) -> str:
    """
    Orquesta el guardado de predicciones, métricas y metadatos.
    
    - Siempre guarda copia local dentro de 'artifacts/metrics/<run_id>/'.
    - Si env == 'prod' (o si APP_ENV es 'prod'), sube los resultados a Amazon S3.
    """
    current_env = (env or os.getenv("APP_ENV", "dev")).lower()
    run_id = generate_run_id()
    
    log_event(logger, "Iniciando proceso de guardado de resultados", run_id=run_id, environment=current_env)
    
    # configuracion de rutas locales
    run_local_dir = LOCAL_ARTIFACTS_DIR / run_id
    
    pred_local_path = run_local_dir / "predictions.csv"
    metrics_local_path = run_local_dir / "metrics.json"
    metadata_local_path = run_local_dir / "metadata.json"

    # estructura de metadata
    full_metadata = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "environment": current_env,
        **(metadata_dict or {})
    }

    # guardado local (env = 'dev')
    save_to_local(predictions_df, pred_local_path, is_dataframe=True)
    save_to_local(metrics_dict, metrics_local_path)
    save_to_local(full_metadata, metadata_local_path)

    # subida a s3 (env = 'prod')
    if current_env == "prod":
        s3_run_prefix = f"{S3_RESULTS_PREFIX}/{run_id}"
        
        upload_to_s3(pred_local_path, f"{s3_run_prefix}/predictions.csv")
        upload_to_s3(metrics_local_path, f"{s3_run_prefix}/metrics.json")
        upload_to_s3(metadata_local_path, f"{s3_run_prefix}/metadata.json")

    log_event(logger, "Proceso de guardado completado con éxito", run_id=run_id)
    return run_id
