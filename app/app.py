import hashlib
import io
import json
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import boto3
import numpy as np
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from botocore.exceptions import ClientError

from reactiva.config import AWS_REGION, DATASET_URI, S3_BUCKET, USUARIO_ADMIN, PASSWORD_ADMIN
from reactiva.utils.logger import log_event, setup_logger
from reactiva.recommender.recommender import (
    get_recommendations_items,
)
from reactiva.data.validate_data import FULL_DEFAULT_STRATEGY, DataValidator
from reactiva.features.build_features import add_season, season_from_date

load_dotenv()
logger = setup_logger(name='reactiva.app.streamlit')


# constantes:

#campos que van al modelo
CAMPOS_MODELO = [
    'Age',
    'Gender',
    'Location',
    'Brand',
    'Category',
    'Online/Offline',
    'Item Purchased',
]

#campos que se registran como detalles de la compra
CAMPOS_OPERATIVOS = [
    'Color',
    'Size',
    'Quantity',
    'Purchase Amount (₹)',
    'Discount (%)',
    'Festival/Sale',
    'Shipping Charge (₹)',
    'Delivery Speed',
    'Delivery Time (Days)',
    'Subscription Status',
    'Payment Method',
    'Review Rating',
    'Return Status',
    'Online Store',
]

#campos que solo tienen sentido en una venta online
CAMPOS_SOLO_ONLINE = [
    'Online Store',
    'Shipping Charge (₹)',
    'Delivery Speed',
    'Delivery Time (Days)',
]

#valores con los que se completan esos campos cuando la venta es offline
DEFAULTS_OFFLINE = {
    'Online Store': 'In-Store Purchase',
    'Shipping Charge (₹)': 0,
    'Delivery Speed': 'N/A (Offline)',
    'Delivery Time (Days)': 0,
}


CAMPOS_NUMERICOS = {
    'Age': (15, 100, 28),
    'Quantity': (1, 50, 1),
    'Purchase Amount (₹)': (0, 100000, 1850),
    'Discount (%)': (0, 100, 10),
    'Shipping Charge (₹)': (0, 5000, 50),
    'Delivery Time (Days)': (0, 60, 3),
    'Review Rating': (1, 5, 4),
    'Previous Purchases': (0, 200, 5),
}

#umbral para decidir selector vs campo libre
MAX_OPCIONES_SELECTOR = 30

#campos que se deben de rellenar si o si para el recomendador
ESTRATEGIA_INDIVIDUAL = {
    'Customer ID': 'drop_row',
    'Item Purchased': 'drop_row',
    'Purchase Date': 'drop_row',
    'Category': 'skip',
}

#cantidad de dias sin actividad a partir de la cual el cliente se considera inactivo
DIAS_INACTIVIDAD = 270

#cantidad de recomendaciones que se muestran al vendedor en cada lista
TOP_RECOMENDACIONES = 3

CANAL_ONLINE = 'Online'
CANAL_OFFLINE = 'Offline'
MAX_LOG_PREVIEW_MB = 5
MAX_LOG_PREVIEW_BYTES = MAX_LOG_PREVIEW_MB * 1024 * 1024
MAX_LOG_DOWNLOAD_MB = 20
MAX_LOG_DOWNLOAD_BYTES = MAX_LOG_DOWNLOAD_MB * 1024 * 1024


#funciones para la estructura de la pagina:


@st.cache_data(ttl=3600, show_spinner='Leyendo dataset historico...')
def cargar_dataset() -> pd.DataFrame:
    """Lee el dataset y normaliza la fecha."""
    try:
        df = pd.read_csv(DATASET_URI)
    except Exception:
        print('No se pudo cargar el dataset historico desde la fuente configurada.')
        raise

    df['Purchase Date'] = pd.to_datetime(
        df['Purchase Date'],
        errors='coerce'
    )

    return df

def pantalla_login() -> None:
    """
    Formulario de acceso. Guarda el usuario en session_state y corta la
    ejecucion del resto de la pagina mientras no haya sesion iniciada.
    """
    st.title('🛍️ ReActiva')
    st.caption('Ingrese sus credenciales para continuar.')

    _, centro, _ = st.columns([1, 2, 1])

    with centro:
        with st.form('login'):
            usuario = st.text_input('Usuario')
            password = st.text_input('Contraseña', type='password')
            entrar = st.form_submit_button('Ingresar', type='primary')

        if entrar:
            if not usuario.strip():
                st.error('Ingrese un nombre de usuario.')
                return

            st.session_state['usuario'] = usuario.strip()
            st.session_state['es_admin'] = (
                usuario.strip() == USUARIO_ADMIN and password == PASSWORD_ADMIN
            )

            log_event(
                logger,
                'Inicio de sesion',
                usuario=usuario.strip(),
                rol='admin' if st.session_state['es_admin'] else 'operador',
            )
            st.rerun()


def campo_categorico(
    df: pd.DataFrame,
    columna: str,
    etiqueta: str = None
):
    """
    muestra un selector si la columna tiene pocas categorias en el historico,
    o un campo de texto libre si la cantidad de opciones es alta.

    Las opciones salen del dataset, no de listas hardcodeadas: si mañana
    aparece una marca nueva, el formulario la ofrece solo.
    """
    etiqueta = etiqueta or columna

    if df is None or columna not in df.columns:
        return st.text_input(etiqueta)

    opciones = sorted(
        df[columna]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    if len(opciones) <= MAX_OPCIONES_SELECTOR:
        return st.selectbox(
            etiqueta,
            options=opciones
        )

    return st.text_input(
        etiqueta,
        help=(
            f'{len(opciones)} valores distintos en el historico, '
            'se carga a mano.'
        ),
    )


def campo_numerico(
    columna: str,
    etiqueta: str = None
):
    """
    Number input con los rangos definidos en CAMPOS_NUMERICOS.
    """
    etiqueta = etiqueta or columna

    minimo, maximo, defecto = CAMPOS_NUMERICOS.get(
        columna,
        (0, 1000000, 0)
    )

    return st.number_input(
        etiqueta,
        min_value=minimo,
        max_value=maximo,
        value=defecto
    )


def obtener_recomendacion_item(
    item_purchased,
    top_n=TOP_RECOMENDACIONES
):
    """
    Genera recomendaciones item-based a partir del producto
    que el cliente está comprando actualmente.
    """
    try:
        recomendacion = get_recommendations_items(
            item_purchased,
            top_n=top_n
        )

    except Exception as error:
        return None, f'El recomendador falló: {error}'

    if not recomendacion:
        return None, (
            'Sin items similares suficientes para este producto.'
        )

    return recomendacion, None


def contextlib_redirect(buffer):
    """
    Alias local de redirect_stdout, para no ensuciar el bloque de imports.
    """
    from contextlib import redirect_stdout

    return redirect_stdout(buffer)


def recomendar_por_perfil(
    df: pd.DataFrame,
    perfil: dict,
    top_n: int = 5
) -> pd.Series:
    """
    Recomendacion de arranque en frio para perfiles sin historial.

    Esta funcion se conserva porque formaba parte de la aplicacion,
    aunque la recomendacion utilizada actualmente para un cliente nuevo
    es item-to-item a partir del producto que esta comprando.
    """
    temporada = season_from_date(
        datetime.now()
    )

    edad = perfil.get(
        'Age',
        30
    )

    df = add_season(df)

    filtro = (
        (df['season'] == temporada)
        & (df['Location'] == perfil.get('Location'))
        & (df['Gender'] == perfil.get('Gender'))
        & (
            df['Age'].between(
                edad - 7,
                edad + 7
            )
        )
    )

    similares = df[filtro]

    #si el filtro queda vacio se afloja a solo temporada + ciudad
    if len(similares) < 10:

        similares = df[
            (df['season'] == temporada)
            & (
                df['Location']
                == perfil.get('Location')
            )
        ]

    if similares.empty:
        return pd.Series(dtype=int)

    comprado = perfil.get(
        'Item Purchased'
    )

    similares = similares[
        similares['Item Purchased']
        != comprado
    ]

    return (
        similares['Item Purchased']
        .value_counts()
        .head(top_n)
    )


def upload_df_to_s3(
    df: pd.DataFrame,
    bucket_name: str,
    prefijo: str = 'uploads',
    idempotency_key: str = None
):
    """
    Sube un DataFrame a S3 con una key deterministica.

    Si idempotency_key esta presente se usa para una transaccion individual.
    Para batch se calcula un hash estable del contenido limpio. La escritura
    condicional evita duplicados ante doble clic o reintentos.

    Devuelve (s3_key, creado).
    """
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_content = csv_buffer.getvalue()

    if idempotency_key:
        identificador = (
            str(idempotency_key)
            .strip()
            .replace('/', '_')
            .replace('\\', '_')
        )
        hash_content = csv_content
    else:
        #hash canonico: mismo lote = misma key aunque cambie el orden
        hash_df = df.copy().reindex(sorted(df.columns), axis=1)
        for columna in hash_df.columns:
            hash_df[columna] = hash_df[columna].map(
                lambda valor: '' if pd.isna(valor) else str(valor).strip()
            )
        if len(hash_df.columns) > 0:
            hash_df = hash_df.sort_values(
                by=list(hash_df.columns),
                kind='mergesort',
                na_position='first'
            )
        hash_content = hash_df.to_csv(index=False, lineterminator='\n')
        identificador = hashlib.sha256(
            hash_content.encode('utf-8')
        ).hexdigest()

    content_hash = hashlib.sha256(
        hash_content.encode('utf-8')
    ).hexdigest()

    s3_key = (
        f'{prefijo}/'
        f'transactions_clean_'
        f'{identificador}.csv'
    )

    try:
        s3_client = boto3.client(
            's3',
            region_name=AWS_REGION
        )

        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=csv_content,
            IfNoneMatch='*'
        )

        log_event(
            logger,
            'Archivo subido a S3',
            bucket=bucket_name,
            key=s3_key,
            filas=len(df),
            content_hash=content_hash
        )

        return s3_key, True

    except ClientError as error:
        status_code = (
            error.response
            .get('ResponseMetadata', {})
            .get('HTTPStatusCode')
        )
        error_code = (
            error.response
            .get('Error', {})
            .get('Code')
        )

        if (
            status_code in (409, 412)
            or error_code in ('PreconditionFailed', 'ConditionalRequestConflict')
        ):
            log_event(
                logger,
                'Carga duplicada evitada',
                level=30,
                bucket=bucket_name,
                key=s3_key,
                content_hash=content_hash
            )
            return s3_key, False

        log_event(
            logger,
            'Error al subir archivo a S3',
            level=40,
            error=str(error),
            key=s3_key
        )
        return None, False

    except Exception as error:
        log_event(
            logger,
            'Error al subir archivo a S3',
            level=40,
            error=str(error),
            key=s3_key
        )
        return None, False


def metricas_cliente(
    df: pd.DataFrame,
    customer_id
) -> dict:
    """
    Arma la ficha 360 de un cliente a partir del historico real.
    """
    historial = df[
        df['Customer ID'].astype(str) == str(customer_id)
    ].copy()

    if historial.empty:
        return {}

    fechas_validas = historial['Purchase Date'].dropna()
    fecha_referencia = df['Purchase Date'].dropna().max()

    if fechas_validas.empty or pd.isna(fecha_referencia):
        ultima = None
        dias_inactivo = None
        actividad = 'Sin dato'
    else:
        ultima = fechas_validas.max()
        dias_inactivo = int((fecha_referencia - ultima).days)
        actividad = (
            'Bajo'
            if dias_inactivo >= DIAS_INACTIVIDAD
            else 'Alto'
        )

    def moda_segura(columna: str, valor_default: str = 'Sin dato'):
        if columna not in historial.columns:
            return valor_default
        valores = historial[columna].dropna()
        if valores.empty:
            return valor_default
        moda = valores.mode()
        if moda.empty:
            return valor_default
        return moda.to_list()[0]

    montos = pd.to_numeric(
        historial['Purchase Amount (₹)'],
        errors='coerce'
    )

    return {
        'compras': len(historial),
        'gasto_total': montos.sum(),
        'ticket': montos.mean(),
        'categoria': moda_segura('Category'),
        'marca': moda_segura('Brand'),
        'ciudad': moda_segura('Location'),
        'ultima': ultima,
        'dias_inactivo': dias_inactivo,
        'actividad': actividad,
        'historial': historial.sort_values(
            'Purchase Date',
            ascending=False
        ),
    }


def email_valido(email: str) -> bool:
    """Valida un formato basico de correo electronico."""
    if not email:
        return False
    patron = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
    return bool(re.fullmatch(patron, email.strip()))


def phone_valido(phone: str) -> bool:
    """Valida que el telefono tenga entre 8 y 15 digitos (formato E.164 laxo)."""
    if not phone:
        return False
    patron = r'^\+?[0-9]{8,15}$'
    return bool(re.fullmatch(patron, phone.strip()))


def normalizar_item_existente(df: pd.DataFrame, item: str):
    """Devuelve el nombre canonico del item si existe en el historico."""
    if (
        df is None
        or df.empty
        or 'Item Purchased' not in df.columns
        or not item
    ):
        return None

    item_normalizado = item.strip().casefold()
    items = (
        df['Item Purchased']
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )

    for item_historico in items:
        if item_historico.casefold() == item_normalizado:
            return item_historico
    return None


def detectar_transaction_ids_duplicados(df: pd.DataFrame) -> list:
    """Devuelve los Transaction ID repetidos dentro del DataFrame."""
    if df is None or df.empty or 'Transaction ID' not in df.columns:
        return []
    ids = df['Transaction ID'].dropna().astype(str).str.strip()
    ids = ids[ids != '']
    return sorted(ids[ids.duplicated(keep=False)].unique().tolist())


def contar_transaction_ids_vacios(df: pd.DataFrame) -> int:
    """Cuenta Transaction ID nulos o vacios."""
    if df is None or df.empty or 'Transaction ID' not in df.columns:
        return 0
    ids = df['Transaction ID'].fillna('').astype(str).str.strip()
    return int((ids == '').sum())


def detectar_transaction_ids_existentes(
    df_nuevo: pd.DataFrame,
    df_historico: pd.DataFrame
) -> list:
    """Detecta Transaction ID del lote que ya existen en el canonico."""
    if (
        df_nuevo is None
        or df_nuevo.empty
        or df_historico is None
        or df_historico.empty
        or 'Transaction ID' not in df_nuevo.columns
        or 'Transaction ID' not in df_historico.columns
    ):
        return []

    ids_nuevos = {
        valor for valor in (
            df_nuevo['Transaction ID']
            .dropna().astype(str).str.strip().tolist()
        ) if valor
    }
    ids_historicos = {
        valor for valor in (
            df_historico['Transaction ID']
            .dropna().astype(str).str.strip().tolist()
        ) if valor
    }
    return sorted(ids_nuevos.intersection(ids_historicos))


def obtener_valor_perfil(historial: pd.DataFrame, columna: str):
    """Devuelve el valor no nulo mas reciente y si hubo inconsistencias."""
    if historial is None or historial.empty or columna not in historial.columns:
        return None, False
    valores = historial[columna].dropna()
    if valores.empty:
        return None, False
    valor_actual = valores.to_list()[0]
    inconsistente = valores.astype(str).nunique() > 1
    return valor_actual, inconsistente


def leer_ultimas_lineas_log(
    ruta: Path,
    max_bytes: int = MAX_LOG_PREVIEW_BYTES
):
    """Lee como maximo los ultimos max_bytes de un archivo de log."""
    tamanio = ruta.stat().st_size
    with open(ruta, 'rb') as archivo:
        if tamanio > max_bytes:
            archivo.seek(-max_bytes, 2)
            bloque = archivo.read()
            primera_nueva_linea = bloque.find(b'\n')
            if primera_nueva_linea >= 0:
                bloque = bloque[primera_nueva_linea + 1:]
            truncado = True
        else:
            bloque = archivo.read()
            truncado = False

    contenido = bloque.decode('utf-8', errors='replace')
    return contenido.splitlines(), truncado


def generate_pending_customer_id() -> str:
    """
    Genera un identificador temporal para clientes nuevos.

    El ID definitivo CUSTXXXXXX debe asignarse durante el proceso de
    consolidacion de staging para evitar duplicados entre sucursales.
    """
    return f'PENDING-{uuid4()}'


#armado de la pagina:
st.set_page_config(page_title='ReActiva Recommender', layout='wide', page_icon='🛍️')

if 'usuario' not in st.session_state:
    pantalla_login()
    st.stop()

es_admin = st.session_state.get('es_admin', False)

encabezado, sesion = st.columns([4, 1])

with encabezado:
    st.title('🛍️ ReActiva Recommender')
    st.caption(
        'Carga de transacciones, validacion de datos e interaccion 360 con clientes.'
    )

with sesion:
    rol = 'admin' if es_admin else 'operador'
    st.markdown(
        f'<div style="text-align: right;">👤 <b>{st.session_state["usuario"]}</b>'
        f'<br><small>{rol}</small></div>',
        unsafe_allow_html=True,
    )
    if st.button('Cerrar sesion'):
        log_event(logger, 'Cierre de sesion', usuario=st.session_state['usuario'])
        st.session_state.clear()
        st.rerun()

try:
    df_historico = cargar_dataset()
except Exception as error:
    df_historico = None
    st.error(f'No se pudo leer el dataset historico: {error}')
    log_event(logger, 'Fallo la lectura del dataset', level=40, error=str(error))

nombres_tabs = [
    '📥 1. Indexacion individual',
    '📂 2. Carga masiva',
    '💡 3. Explorador 360 y CRM',
]

if es_admin:
    nombres_tabs.append('📜 4. Auditoria y logs')

tabs = st.tabs(nombres_tabs)


#TAB 1 - indexacion individual

with tabs[0]:

    st.header(
        'Consulta individual al recomendador'
    )

    st.write(
        'Ingrese los datos de la compra realizada'
    )

    modo = st.radio(
        'Tipo de consulta',

        [
            'Cliente existente',
            'Perfil nuevo (sin historial)'
        ],

        horizontal=True,

        help=(
            'Indique si el cliente es nuevo '
            'o ha comprado anteriormente.'
        ),
    )

    col1, col2, col3 = st.columns(3)


    with col1:

        st.subheader(
            '👤 Perfil'
        )

        if modo == 'Cliente existente':

            if df_historico is None or df_historico.empty:
                st.error(
                    'No se puede consultar un cliente existente '
                    'porque el dataset historico no esta disponible.'
                )
                st.stop()

            clientes = sorted(
                df_historico[
                    'Customer Full Name'
                ]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            if not clientes:
                st.error('No hay clientes disponibles en el dataset historico.')
                st.stop()

            customer_name = st.selectbox(
                'Nombre Completo',
                options=clientes
            )

            datos_cliente = (
                df_historico[
                    df_historico['Customer Full Name'].astype(str)
                    == str(customer_name)
                ]
                .sort_values('Purchase Date', ascending=False)
            )

            customer_ids = (
                datos_cliente['Customer ID']
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            if not customer_ids:
                st.error('No se encontro un Customer ID valido para este cliente.')
                st.stop()

            if len(customer_ids) > 1:
                st.warning(
                    'Hay mas de un Customer ID asociado a este nombre. '
                    'Seleccione el cliente correcto.'
                )
                customer_id = st.selectbox(
                    'Customer ID',
                    options=customer_ids
                )
                datos_cliente = (
                    datos_cliente[
                        datos_cliente['Customer ID'].astype(str)
                        == str(customer_id)
                    ]
                    .sort_values('Purchase Date', ascending=False)
                )
            else:
                customer_id = customer_ids[0]

            age, age_inconsistente = obtener_valor_perfil(datos_cliente, 'Age')
            gender, gender_inconsistente = obtener_valor_perfil(datos_cliente, 'Gender')
            location, location_inconsistente = obtener_valor_perfil(datos_cliente, 'Location')
            email, email_inconsistente = obtener_valor_perfil(
                datos_cliente,
                'Customer Email'
            )
            phone, phone_inconsistente = obtener_valor_perfil(
                datos_cliente,
                'Customer Phone'
            )

            st.text_input(
                label='Edad',
                value='' if age is None else str(age),
                disabled=True
            )
            st.text_input(
                label='Genero',
                value='' if gender is None else str(gender),
                disabled=True
            )
            st.text_input(
                label='Ciudad',
                value='' if location is None else str(location),
                disabled=True
            )
            st.text_input(
                label='Email registrado',
                value='' if email is None else str(email),
                disabled=True
            )
            st.text_input(
                label='Telefono registrado',
                value='' if phone is None else str(phone),
                disabled=True
            )

            email_confirmacion = st.text_input(
                'Confirmar email del cliente',
                placeholder='Repita el email informado por el cliente',
                key=f'confirmar_email_{customer_id}'
            )

            campos_inconsistentes = [
                nombre
                for nombre, inconsistente in [
                    ('Edad', age_inconsistente),
                    ('Genero', gender_inconsistente),
                    ('Ciudad', location_inconsistente),
                    ('Email', email_inconsistente),
                    ('Telefono', phone_inconsistente),
                ]
                if inconsistente
            ]

            if campos_inconsistentes:
                st.warning(
                    'El historial contiene valores diferentes en: '
                    + ', '.join(campos_inconsistentes)
                    + '. Se muestra el valor mas reciente.'
                )

            #Previous Purchases representa
            #las compras anteriores a la actual
            previous_purchases = int(
                len(
                    df_historico[
                        df_historico['Customer ID'].astype(str)
                        == str(customer_id)
                    ]
                )
            )

            st.caption(
                'Confirme el correo con el cliente. '
                'Si no coincide, seleccione '
                '"Perfil nuevo (sin historial)".'
            )

        else:

            customer_name = st.text_input(
                label='Nombre completo',
                placeholder='Nombre Cliente'
            )

            #el cliente nuevo entra a staging con un ID temporal estable
            #durante toda la operacion. El definitivo se asignara al consolidar.
            if 'current_pending_customer_id' not in st.session_state:
                st.session_state['current_pending_customer_id'] = (
                    generate_pending_customer_id()
                )
            customer_id = st.session_state['current_pending_customer_id']

            age = campo_numerico(
                'Age',
                'Edad'
            )

            gender = campo_categorico(
                df_historico,
                'Gender',
                'Genero'
            )

            location = campo_categorico(
                df_historico,
                'Location',
                'Ciudad'
            )

            email = st.text_input(
                label='Email',
                placeholder='client@example.com'
            )

            phone = st.text_input(
                label='Telefono',
                placeholder='+91XXXXXXXXXX'
            )

            email_confirmacion = None
            previous_purchases = 0


    with col2:

        st.subheader(
            '🛒 Compra'
        )

        purchase_date = st.date_input(
            'Fecha de compra',
            value=datetime.today()
        )

        category = campo_categorico(
            df_historico,
            'Category',
            'Categoria'
        )

        brand = campo_categorico(
            df_historico,
            'Brand',
            'Marca'
        )

        item_purchased = campo_categorico(
            df_historico,
            'Item Purchased',
            'Item comprado'
        )


    with col3:

        st.subheader(
            '🏬 Canal'
        )

        online_offline = st.selectbox(
            'Canal de venta',
            options=[CANAL_OFFLINE, CANAL_ONLINE]
        )

        temporada = season_from_date(
            purchase_date
        )

        st.metric(
            'Temporada actual',
            temporada
        )


    if online_offline == CANAL_ONLINE:

        campos_visibles = CAMPOS_OPERATIVOS

    else:

        campos_visibles = [
            c
            for c in CAMPOS_OPERATIVOS
            if c not in CAMPOS_SOLO_ONLINE
        ]


    with st.expander(
        'Detalles del producto: '
    ):

        operativos = {}

        cols_op = st.columns(4)

        for i, columna in enumerate(
            campos_visibles
        ):

            with cols_op[i % 4]:

                if columna in CAMPOS_NUMERICOS:

                    operativos[columna] = (
                        campo_numerico(
                            columna
                        )
                    )

                else:

                    operativos[columna] = (
                        campo_categorico(
                            df_historico,
                            columna
                        )
                    )


        #se rellenan los campos que no se muestran
        #en una venta offline para conservar
        #las 27 columnas del dataset
        if online_offline == CANAL_OFFLINE:

            operativos.update(
                DEFAULTS_OFFLINE
            )


        #el ID de transaccion se conserva durante toda la operacion
        if 'current_transaction_id' not in st.session_state:
            st.session_state['current_transaction_id'] = (
                f'TXN-'
                f'{datetime.now().strftime("%Y%m%d")}-'
                f'{uuid4().hex.upper()}'
            )

        transaction_id = st.session_state['current_transaction_id']
        st.session_state.setdefault('transaction_registered', False)


    if st.session_state['transaction_registered']:
        if st.button('🆕 Nueva operacion'):
            st.session_state.pop('current_transaction_id', None)
            st.session_state.pop('current_pending_customer_id', None)
            st.session_state['transaction_registered'] = False
            st.rerun()

    if st.button(
        '🚀 Registrar y consultar recomendador',
        type='primary',
        disabled=st.session_state['transaction_registered']
    ):

        #validaciones de identidad
        if modo == 'Perfil nuevo (sin historial)':
            customer_name = str(customer_name).strip()
            email = str(email).strip()
            phone = str(phone).strip()

            if not customer_name:
                st.error('❌ Ingrese el nombre completo del cliente.')
                st.stop()

            if not email_valido(email):
                st.error('❌ Ingrese un email valido antes de registrar la venta.')
                st.stop()

            if not phone_valido(phone):
                st.error(
                    '❌ Ingrese un telefono valido (8 a 15 digitos, '
                    'puede incluir codigo de pais) antes de registrar la venta.'
                )
                st.stop()

        else:
            email_registrado = '' if email is None else str(email).strip()
            email_confirmado = (
                '' if email_confirmacion is None
                else str(email_confirmacion).strip()
            )

            if not email_valido(email_registrado):
                st.error(
                    '❌ El cliente existente no tiene un email valido. '
                    'Registre la compra como Perfil nuevo (sin historial).'
                )
                st.stop()

            if email_confirmado.casefold() != email_registrado.casefold():
                st.error(
                    '❌ El email informado no coincide con el registrado. '
                    'Si corresponde a otra persona use Perfil nuevo (sin historial).'
                )
                st.stop()

            email = email_registrado

        #en ventas presenciales el item debe existir para Item-to-Item
        if online_offline == CANAL_OFFLINE:
            item_canonico = normalizar_item_existente(
                df_historico,
                item_purchased
            )
            if item_canonico is None:
                st.error('❌ El item ingresado no existe en el catalogo conocido.')
                st.stop()
            item_purchased = item_canonico
        else:
            if item_purchased is None or not str(item_purchased).strip():
                st.error('❌ Ingrese un item valido antes de registrar la venta.')
                st.stop()
            item_purchased = str(item_purchased).strip()

        record = {
            'Transaction ID':
                transaction_id,

            'Customer ID':
                customer_id,

            'Customer Full Name':
                customer_name,

            'Customer Email':
                email,

            'Customer Phone':
                phone,

            'Purchase Date':
                str(purchase_date),

            'Age':
                age,

            'Gender':
                gender,

            'Location':
                location,

            'Online/Offline':
                online_offline,

            'Category':
                category,

            'Item Purchased':
                item_purchased,

            'Brand':
                brand,

            'Previous Purchases':
                previous_purchases,
        }


        #se agregan todos los detalles cargados por el vendedor
        #y los defaults correspondientes al canal
        #para no perder columnas
        record.update(
            operativos
        )


        single_df = pd.DataFrame(
            [record]
        )


        single_df[
            'Purchase Date'
        ] = pd.to_datetime(
            single_df[
                'Purchase Date'
            ],
            errors='coerce',
        )


        log_event(
            logger,
            'Indexacion individual recibida',
            customer_id=str(customer_id),
            transaction_id=transaction_id,
            modo=modo,
        )


        #validacion

        validator = DataValidator(
            single_df
        )

        reporte = validator.run_checks()


        buffer = io.StringIO()

        with contextlib_redirect(
            buffer
        ):

            single_clean = validator.clean(
                strategy=ESTRATEGIA_INDIVIDUAL
            )


        if reporte[
            'missing_columns'
        ]:

            st.error(
                'Faltan columnas obligatorias: '
                f'{reporte["missing_columns"]}'
            )

            log_event(
                logger,
                'Indexacion rechazada',
                level=40,
                columnas=reporte[
                    'missing_columns'
                ]
            )

            st.stop()


        if single_clean.empty:

            st.error(
                'Registro descartado: falta '
                'Customer ID, Item Purchased o fecha.'
            )

            log_event(
                logger,
                'Indexacion descartada en validacion',
                level=40
            )

            st.stop()


        st.success(
            f'✅ Transaccion '
            f'{transaction_id} validada.'
        )


        with st.expander(
            'Log de validacion'
        ):

            st.code(
                '\n'.join(
                    validator.get_log()
                )
                or
                'Sin observaciones.'
            )


        #cada venta individual usa una key derivada del Transaction ID
        #para impedir duplicados ante reintentos o doble clic
        s3_key, creado = upload_df_to_s3(
            single_clean,
            S3_BUCKET,
            prefijo='staging/individual',
            idempotency_key=transaction_id
        )


        if creado:

            st.info('Registro enviado a la base de datos')
            st.session_state['transaction_registered'] = True

        elif s3_key:

            st.warning(
                'Esta transaccion ya habia sido registrada. '
                'No se genero un duplicado.'
            )
            st.session_state['transaction_registered'] = True

        else:

            st.warning(
                'El registro se valido pero no se pudo '
                'subir a la Base de Datos. '
                'Reintentar o comunicarse con el soporte.'
            )


        st.markdown(
            '---'
        )

        st.subheader(
            '🔮 Recomendaciones'
        )


        #las compras online se registran completas
        #pero no generan recomendacion
        if online_offline == CANAL_ONLINE:

            st.info(
                'La compra online fue registrada. '
                'Las recomendaciones comerciales '
                'se muestran por ahora solo para '
                'ventas realizadas en el local.'
            )

        else:

            #clientes existentes y nuevos usan Item-to-Item
            #a partir del producto de la compra actual
            recomendacion, aviso = (
                obtener_recomendacion_item(
                    item_purchased,
                    top_n=TOP_RECOMENDACIONES,
                )
            )

            if recomendacion:

                st.success(
                    'Top 3 por similitud con **'
                    + item_purchased
                    + '**: '
                    + ', '.join(recomendacion)
                )

                log_event(
                    logger,
                    'Recomendacion generada',
                    item=item_purchased,
                    fuente='item_based',
                    customer_id=str(customer_id),
                )

            else:

                st.warning(aviso)

                log_event(
                    logger,
                    'Recomendacion no disponible para este usuario.',
                    level=30,
                    item=item_purchased,
                    motivo=aviso,
                    customer_id=str(customer_id),
                )

#TAB 2 - carga masiva

with tabs[1]:

    st.header(
        'Carga masiva de ventas online'
    )

    st.write(
        'Esta seccion incorpora manualmente ventas del canal online '
        'mientras ReActiva no tenga integracion directa con el e-commerce. '
        'El archivo se valida antes de enviarse a staging/batch.'
    )

    MAX_UPLOAD_SIZE_MB = 20
    MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

    uploaded_file = st.file_uploader(
        'Archivo de ventas online',
        type=['csv']
    )

    if uploaded_file is not None:

        if uploaded_file.size == 0:
            st.error('❌ El archivo esta vacio.')
            st.stop()

        if uploaded_file.size > MAX_UPLOAD_SIZE_BYTES:
            st.error(
                f'❌ El archivo supera el limite permitido '
                f'de {MAX_UPLOAD_SIZE_MB} MB.'
            )
            st.stop()

        try:
            archivo_bytes = uploaded_file.getvalue()
            archivo_hash = hashlib.sha256(archivo_bytes).hexdigest()

            #si cambia el archivo no se reutiliza una limpieza anterior
            if st.session_state.get('batch_source_hash') != archivo_hash:
                st.session_state.pop('df_clean', None)
                st.session_state.pop('clean_log', None)
                st.session_state['batch_source_hash'] = archivo_hash

            uploaded_file.seek(0)
            df_upload = pd.read_csv(uploaded_file)

            log_event(
                logger,
                'Archivo cargado por el usuario',
                filename=uploaded_file.name,
                rows=len(df_upload),
                content_hash=archivo_hash
            )

            st.write(
                f'📁 **{uploaded_file.name}** — '
                f'{len(df_upload)} filas, '
                f'{len(df_upload.columns)} columnas'
            )

            # ========================================================
            # FASE 1 - VALIDACION
            # ========================================================
            st.subheader('🔍 Fase 1: reporte de validacion')

            validator = DataValidator(df_upload)
            report = validator.run_checks()

            ids_duplicados_archivo = detectar_transaction_ids_duplicados(
                df_upload
            )
            ids_vacios_archivo = contar_transaction_ids_vacios(df_upload)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric('Total filas', report['shape'][0])
            m2.metric('Columnas faltantes', len(report['missing_columns']))
            m3.metric('Duplicados exactos', report['duplicate_rows'])
            m4.metric('Transaction ID repetidos', len(ids_duplicados_archivo))

            if report['missing_columns']:
                st.error(
                    '❌ Faltan columnas requeridas: '
                    f'{report["missing_columns"]}'
                )
                st.stop()

            if ids_vacios_archivo > 0:
                st.error(
                    f'❌ Se detectaron {ids_vacios_archivo} fila(s) '
                    'sin Transaction ID. La carga queda bloqueada.'
                )
                st.stop()

            if ids_duplicados_archivo:
                st.error(
                    f'❌ El archivo contiene {len(ids_duplicados_archivo)} '
                    'Transaction ID repetido(s).'
                )
                with st.expander('Ver Transaction ID repetidos'):
                    st.code('\n'.join(ids_duplicados_archivo[:50]))
                st.stop()

            #el batch representa exclusivamente ventas online
            if 'Online/Offline' in df_upload.columns:
                canales = (
                    df_upload['Online/Offline']
                    .fillna('')
                    .astype(str)
                    .str.strip()
                    .str.casefold()
                )
                filas_invalidas = canales != CANAL_ONLINE.casefold()
                if filas_invalidas.any():
                    st.error(
                        '❌ La carga masiva corresponde exclusivamente '
                        'a ventas online. Hay registros vacios o distintos de Online.'
                    )
                    st.stop()

            st.success('✅ Estructura de columnas valida.')

            nulos = pd.DataFrame({
                'nulos': report['null_counts'],
                'porcentaje': report['null_pct'],
            })
            nulos = nulos[nulos['nulos'] > 0]

            if nulos.empty:
                st.success('Sin nulos en el archivo.')
            else:
                st.dataframe(nulos, width='stretch')

            # ========================================================
            # FASE 2 - LIMPIEZA
            # ========================================================
            st.subheader('🧹 Fase 2: limpieza e imputacion')

            forzar = st.checkbox(
                'Imputar aunque la columna supere el 15% de nulos'
            )

            if st.button('Ejecutar limpieza', type='secondary'):
                buffer = io.StringIO()
                with contextlib_redirect(buffer):
                    df_clean = validator.clean(
                        strategy=FULL_DEFAULT_STRATEGY,
                        force_impute_above_threshold=forzar,
                    )

                st.session_state['df_clean'] = df_clean
                st.session_state['clean_log'] = validator.get_log()

                log_event(
                    logger,
                    'Limpieza ejecutada',
                    rows_before=len(df_upload),
                    rows_after=len(df_clean),
                    forzado=forzar
                )

            if 'df_clean' in st.session_state:
                df_clean = st.session_state['df_clean']
                clean_log = st.session_state['clean_log']

                if df_clean.empty:
                    st.error('❌ La limpieza no dejo filas validas para staging.')
                    st.stop()

                ids_duplicados_limpios = detectar_transaction_ids_duplicados(
                    df_clean
                )
                ids_vacios_limpios = contar_transaction_ids_vacios(df_clean)

                if ids_vacios_limpios > 0 or ids_duplicados_limpios:
                    st.error(
                        '❌ El dataset limpio no conserva Transaction ID '
                        'validos y unicos. La subida queda bloqueada.'
                    )
                    st.stop()

                c1, c2 = st.columns(2)
                c1.metric('Filas antes', len(df_upload))
                c2.metric(
                    'Filas despues',
                    len(df_clean),
                    delta=len(df_clean) - len(df_upload)
                )

                bloqueadas = [
                    linea for linea in clean_log
                    if 'BLOCKED' in linea
                ]
                if bloqueadas:
                    st.warning(
                        f'{len(bloqueadas)} columna(s) superaron el umbral '
                        'de nulos y quedaron sin imputar.'
                    )

                st.dataframe(df_clean.head(10), width='stretch')

                with st.expander('Log de cambios e imputaciones'):
                    for linea in clean_log:
                        st.text(f'• {linea}')

                st.markdown('---')

                # ====================================================
                # FASE 3 - CONSISTENCIA CONTRA CANONICO
                # ====================================================
                st.subheader('🔗 Fase 3: control de consistencia')

                consistencia_bloqueada = False

                if df_historico is None or df_historico.empty:
                    consistencia_bloqueada = True
                    st.error(
                        '❌ No se pudo consultar el dataset canonico. '
                        'La carga queda bloqueada para evitar duplicados.'
                    )
                else:
                    ids_existentes = detectar_transaction_ids_existentes(
                        df_clean,
                        df_historico
                    )

                    if ids_existentes:
                        consistencia_bloqueada = True
                        st.error(
                            f'❌ La carga contiene {len(ids_existentes)} '
                            'Transaction ID que ya existen en el dataset canonico.'
                        )
                        with st.expander('Ver Transaction ID existentes'):
                            st.code('\n'.join(ids_existentes[:50]))
                    else:
                        st.success(
                            '✅ No se encontraron Transaction ID '
                            'ya presentes en el dataset canonico.'
                        )

                st.caption(
                    'El control global entre objetos de staging corresponde '
                    'al proceso de consolidacion nocturna y queda fuera de este PR.'
                )

                # ====================================================
                # FASE 4 - SUBIDA A STAGING
                # ====================================================
                st.subheader('☁️ Fase 4: subida a staging')

                if st.button(
                    '📤 Subir dataset limpio',
                    type='primary',
                    disabled=consistencia_bloqueada
                ):
                    with st.spinner('Guardando en Base de Datos...'):
                        s3_key, creado = upload_df_to_s3(
                            df_clean,
                            S3_BUCKET,
                            prefijo='staging/batch'
                        )

                    if creado:
                        st.success('🎉 Archivo enviado a staging/batch.')
                    elif s3_key:
                        st.warning(
                            '⚠️ Este mismo contenido ya habia sido cargado. '
                            'No se genero una copia duplicada.'
                        )
                    else:
                        st.error(
                            '⚠️ Fallo la subida. Reintente o comuniquese '
                            'con el soporte.'
                        )

        except Exception as error:
            st.error(f'Error al procesar el archivo: {error}')
            log_event(
                logger,
                'Error en carga masiva',
                level=40,
                error=str(error)
            )

#TAB 3 - explorador 360

with tabs[2]:

    st.header(
        '💡 Exploracion e interaccion con clientes'
    )


    if df_historico is None or df_historico.empty:

        st.warning(
            'Sin dataset cargado '
            'no se puede construir la ficha.'
        )

    else:

        clientes = sorted(
            df_historico[
                'Customer Full Name'
            ]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        cliente = st.selectbox(
            'Cliente',
            options=clientes,
            key='cliente_360'
        )

        historial_nombre = (
            df_historico[
                df_historico['Customer Full Name'].astype(str)
                == str(cliente)
            ]
            .sort_values('Purchase Date', ascending=False)
        )

        cliente_ids = (
            historial_nombre['Customer ID']
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        if not cliente_ids:
            st.warning('No se encontro un Customer ID valido para este cliente.')
            st.stop()

        if len(cliente_ids) > 1:
            st.warning(
                'Hay mas de un Customer ID asociado a este nombre. '
                'Seleccione el cliente correcto.'
            )
            cliente_id = st.selectbox(
                'Customer ID',
                options=cliente_ids,
                key='cliente_id_360'
            )
        else:
            cliente_id = cliente_ids[0]

        datos = metricas_cliente(
            df_historico,
            cliente_id
        )


        if not datos:

            st.warning(
                'Sin historial para este cliente.'
            )


        else:

            st.markdown(
                f'### 🪪 Ficha 360 — {cliente} ({cliente_id})'
            )


            f1, f2, f3, f4, f5 = st.columns(5)


            f1.metric(
                'Ciudad',
                datos['ciudad']
            )


            f2.metric(
                'Gasto total (₹)',
                f'{datos["gasto_total"]:,.0f}'
            )


            f3.metric(
                'Ordenes',
                datos['compras']
            )


            f4.metric(
                'Categoria preferida',
                datos['categoria']
            )


            delta_actividad = (
                'Sin fecha de compra valida'
                if datos['dias_inactivo'] is None
                else f'{datos["dias_inactivo"]} dias sin comprar'
            )

            f5.metric(
                'Actividad',
                datos['actividad'],
                delta=delta_actividad,
                delta_color=(
                    'inverse'
                    if datos['actividad'] == 'Bajo'
                    else 'normal'
                ),
            )


            (
                t_hist,
                t_camp,
                t_notas
            ) = st.tabs(
                [
                    'Historial',
                    'Campañas',
                    'Notas CRM'
                ]
            )


            with t_hist:

                st.dataframe(
                    datos[
                        'historial'
                    ][[
                        'Purchase Date',
                        'Item Purchased',
                        'Category',
                        'Brand',
                        'Purchase Amount (₹)',
                        'Return Status',
                    ]],
                    width='stretch',
                )


            with t_camp:

                st.caption(
                    'Arma el mensaje a enviar.'
                )


                canal = st.radio(
                    'Canal',
                    [
                        'WhatsApp',
                        'SMS',
                        'Email'
                    ],
                    horizontal=True
                )


                descuento = st.slider(
                    'Descuento (%)',
                    5,
                    40,
                    15,
                    step=5
                )


                motivo = st.selectbox(
                    'Motivo',
                    [
                        'Diwali',
                        'Holi',
                        'Fin de temporada',
                        'Reactivacion'
                    ],
                )


                mensaje = (
                    f'Hola! Tenemos '
                    f'{descuento}% off en '
                    f'{datos["marca"]} '
                    f'({datos["categoria"]}) '
                    f'por {motivo}. '
                    f'Te esperamos en nuestra '
                    f'tienda de '
                    f'{datos["ciudad"]}.'
                )


                st.text_area(
                    'Vista previa',
                    value=mensaje,
                    height=100
                )


                if st.button(
                    '📲 Registrar envio simulado'
                ):

                    log_event(
                        logger,
                        'Campaña simulada',
                        customer_id=str(cliente_id),
                        canal=canal,
                        descuento=descuento,
                        motivo=motivo
                    )

                    st.success(
                        f'Envio por {canal} '
                        'registrado en el log.'
                    )


            with t_notas:

                #PENDIENTE:
                #las notas viven en memoria de sesion
                #es solo codigo de muestra
                #a futuro se puede agregar la logica
                #para guardar las notas en Json
                #para cada cliente
                notas = st.session_state.setdefault(
                    'notas_crm',
                    {}
                )


                clave_notas = str(cliente_id)

                previas = notas.get(
                    clave_notas,
                    []
                )


                nueva = st.text_area(
                    'Nueva nota'
                )


                if (
                    st.button(
                        '💾 Guardar nota'
                    )
                    and nueva.strip()
                ):

                    previas.append({
                        'fecha':
                            datetime.now().strftime(
                                '%Y-%m-%d %H:%M'
                            ),

                        'nota':
                            nueva.strip(),
                    })


                    notas[
                        clave_notas
                    ] = previas


                    log_event(
                        logger,
                        'Nota CRM agregada',
                        customer_id=str(cliente_id)
                    )


                    st.success(
                        'Nota guardada.'
                    )


                if previas:

                    st.table(
                        pd.DataFrame(
                            previas
                        )
                    )


#TAB 4 - auditoria y logs
if es_admin:

    with tabs[3]:

        st.header(
            '📜 Auditoria de logs'
        )

        log_dir = Path(
            'artifacts/logs'
        )

        if not log_dir.exists():

            st.info(
                'Todavia no se genero '
                'ningun archivo de log.'
            )

        else:

            archivos = sorted(
                log_dir.glob('*.log'),
                reverse=True
            )

            if not archivos:

                st.info(
                    'El directorio de logs '
                    'esta vacio.'
                )

            else:

                seleccionado = st.selectbox(
                    'Archivo de registro',
                    [f.name for f in archivos]
                )

                ruta_log = log_dir / seleccionado
                tamanio_log = ruta_log.stat().st_size
                lineas, truncado = leer_ultimas_lineas_log(ruta_log)

                if truncado:
                    st.info(
                        'ℹ️ Para proteger la memoria se muestran solo los ultimos '
                        f'{MAX_LOG_PREVIEW_MB} MB del archivo.'
                    )

                registros = []

                for linea in lineas:
                    try:
                        registros.append(json.loads(linea.strip()))
                    except (json.JSONDecodeError, TypeError):
                        continue

                if not registros:

                    st.warning(
                        'La porcion leida del archivo no tiene '
                        'lineas JSON validas.'
                    )

                else:

                    df_logs = pd.DataFrame(registros)

                    if 'level' not in df_logs.columns:
                        df_logs['level'] = 'UNKNOWN'
                    else:
                        df_logs['level'] = (
                            df_logs['level']
                            .fillna('UNKNOWN')
                            .astype(str)
                        )

                    niveles_disponibles = sorted(
                        df_logs['level'].unique().tolist()
                    )

                    niveles = st.multiselect(
                        'Filtrar por nivel',
                        options=niveles_disponibles,
                        default=niveles_disponibles,
                    )

                    df_filtrado = df_logs[
                        df_logs['level'].isin(niveles)
                    ]

                    st.dataframe(
                        df_filtrado,
                        width='stretch'
                    )

                if tamanio_log <= MAX_LOG_DOWNLOAD_BYTES:
                    st.download_button(
                        'Descargar log',
                        data=ruta_log.read_bytes(),
                        file_name=seleccionado,
                        mime='text/plain',
                    )
                else:
                    st.info(
                        'ℹ️ La descarga desde Streamlit esta limitada a '
                        f'{MAX_LOG_DOWNLOAD_MB} MB para evitar cargar '
                        'archivos grandes completos en memoria.'
                    )
