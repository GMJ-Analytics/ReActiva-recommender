import io
import json
from datetime import datetime
from pathlib import Path
import boto3
import numpy as np
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from src.reactiva.config import AWS_REGION, DATASET_URI, S3_BUCKET, USUARIO_ADMIN, PASSWORD_ADMIN
from src.reactiva.utils.logger import log_event, setup_logger
from src.reactiva.recommender.recommender import get_recommendations_items
from src.reactiva.data.validate_data import FULL_DEFAULT_STRATEGY, DataValidator

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
]

#campos que solo tienen sentido en una venta online
CAMPOS_SOLO_ONLINE = [
    'Online Store',
    'Shipping Charge (₹)',
    'Delivery Speed',
    'Delivery Time (Days)',
    'Review Rating',
]

#valores con los que se completan esos campos cuando la venta es offline
DEFAULTS_OFFLINE = {
    'Shipping Charge (₹)': 0,
    'Delivery Speed': 'N/A (Offline)',
    'Delivery Time (Days)': 0,
    'Review Rating': np.nan,
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

DIAS_CHURN = 270  # mismo corte que usa el recomendador


#funciones para la estructura de la pagina:


@st.cache_data(show_spinner='Leyendo dataset historico...')
def cargar_dataset() -> pd.DataFrame:
    """Lee el dataset y normaliza la fecha."""
    try:
        df = pd.read_csv(DATASET_URI)
    except Exception as e:
        print('No se pudo cargar el dataset en la nube, intentando conexion con el respaldo local.')
    df['Purchase Date'] = pd.to_datetime(df['Purchase Date'], errors='coerce')
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

def asignar_session(fecha) -> str:
    """Devuelve la temporada climatica que usa el recomendador."""
    mes = pd.Timestamp(fecha).month

    if mes in (12, 1, 2):
        return 'winter'
    if mes in (3, 4, 5):
        return 'summer'
    if mes in (6, 7, 8, 9):
        return 'monsoon'
    return 'post-monsoon'


def campo_categorico(df: pd.DataFrame, columna: str, etiqueta: str = None):
    """
    muestra un selector si la columna tiene pocas categorias en el historico,
    o un campo de texto libre si la cantidad de opciones es alta.

    Las opciones salen del dataset, no de listas hardcodeadas: si mañana
    aparece una marca nueva, el formulario la ofrece solo.
    """
    etiqueta = etiqueta or columna

    if df is None or columna not in df.columns:
        return st.text_input(etiqueta)

    opciones = sorted(df[columna].dropna().astype(str).unique().tolist())

    if len(opciones) <= MAX_OPCIONES_SELECTOR:
        return st.selectbox(etiqueta, options=opciones)

    return st.text_input(
        etiqueta,
        help=f'{len(opciones)} valores distintos en el historico, se carga a mano.',
    )


def campo_numerico(columna: str, etiqueta: str = None):
    """Number input con los rangos definidos en CAMPOS_NUMERICOS."""
    etiqueta = etiqueta or columna
    minimo, maximo, defecto = CAMPOS_NUMERICOS.get(columna, (0, 1000000, 0))
    return st.number_input(etiqueta, min_value=minimo, max_value=maximo, value=defecto)


def obtener_recomendacion_item(item_purchased):
    """
    Genera recomendaciones item-based a partir del producto
    que el cliente está comprando actualmente.
    """
    try:
        recomendacion = get_recommendations_items(
            item_purchased,
            top_n=5
        )

    except Exception as error:
        return None, f"El recomendador falló: {error}"

    if not recomendacion:
        return None, (
            "Sin items similares suficientes para este producto."
        )

    return recomendacion, None


def contextlib_redirect(buffer):
    """Alias local de redirect_stdout, para no ensuciar el bloque de imports."""
    from contextlib import redirect_stdout
    return redirect_stdout(buffer)


def recomendar_por_perfil(df: pd.DataFrame, perfil: dict, top_n: int = 5) -> pd.Series:
    """
    Recomendacion de arranque en frio para perfiles sin historial.

    El recomendador colaborativo necesita compras previas del cliente para
    construir la matriz de similitud, asi que para un cliente nuevo se usa
    una regla simple: que compraron en esta temporada los clientes del mismo
    genero, ciudad y franja etaria.
    """
    temporada = asignar_session(datetime.now())
    edad = perfil.get('Age', 30)

    df = df.copy()
    df['session'] = df['Purchase Date'].apply(asignar_session)

    filtro = (
        (df['session'] == temporada)
        & (df['Location'] == perfil.get('Location'))
        & (df['Gender'] == perfil.get('Gender'))
        & (df['Age'].between(edad - 7, edad + 7))
    )

    similares = df[filtro]

    # Si el filtro queda vacio se afloja a solo temporada + ciudad.
    if len(similares) < 10:
        similares = df[(df['session'] == temporada) & (df['Location'] == perfil.get('Location'))]

    if similares.empty:
        return pd.Series(dtype=int)

    comprado = perfil.get('Item Purchased')
    similares = similares[similares['Item Purchased'] != comprado]

    return similares['Item Purchased'].value_counts().head(top_n)


def upload_df_to_s3(df: pd.DataFrame, bucket_name: str, prefijo: str = 'uploads') -> str:
    """
    Sube un DataFrame a S3 con timestamp en el nombre.

    Devuelve la key si salio bien y None si fallo, para que el llamador
    decida que mostrar.
    """
    try:
        timestamp = datetime.now().strftime('%Y/%m/%d_%H:%M:%S')
        s3_key = f'{prefijo}/transactions_clean_{timestamp}.csv'

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)

        s3_client = boto3.client('s3', region_name=AWS_REGION)
        s3_client.put_object(Bucket=bucket_name, Key=s3_key, Body=csv_buffer.getvalue())

        log_event(logger, 'Archivo subido a S3', bucket=bucket_name, key=s3_key, filas=len(df))
        return s3_key

    except Exception as error:
        log_event(logger, 'Error al subir archivo a S3', level=40, error=str(error))
        return None


def metricas_cliente(df: pd.DataFrame, customer_id) -> dict:
    """Arma la ficha 360 de un cliente a partir del historico real."""
    historial = df[df['Customer ID'] == customer_id]

    if historial.empty:
        return {}

    ultima = historial['Purchase Date'].max()
    dias_inactivo = (df['Purchase Date'].max() - ultima).days

    return {
        'compras': len(historial),
        'gasto_total': historial['Purchase Amount (₹)'].sum(),
        'ticket': historial['Purchase Amount (₹)'].mean(),
        'categoria': historial['Category'].mode().iloc[0],
        'marca': historial['Brand'].mode().iloc[0],
        'ciudad': historial['Location'].mode().iloc[0],
        'ultima': ultima,
        'dias_inactivo': dias_inactivo,
        'actividad': 'Bajo' if dias_inactivo > DIAS_CHURN else 'Alto',
        'historial': historial.sort_values('Purchase Date', ascending=False),
    }

def generate_new_customer_id(df: pd.DataFrame, id_column: str = "Customer ID") -> str:
    """
    Busca el valor numérico más alto en las IDs con formato CUSTXXXXXX
    y retorna la siguiente ID consecutiva.
    """
    if df.empty or id_column not in df.columns:
        return "CUST000001"

    # Extrae solo los dígitos eliminando el prefijo 'CUST' y los convierte a enteros
    numeric_ids = (
        df[id_column]
        .astype(str)
        .str.extract(r"CUST(\d+)", expand=False)
        .dropna()
        .astype(int)
    )

    if numeric_ids.empty:
        next_number = 1
    else:
        # Encuentra el número máximo registrado
        next_number = numeric_ids.max() + 1

    # Formatea el número a 6 dígitos rellenados con ceros a la izquierda
    return f"CUST{next_number:06d}"


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
    st.header('Consulta individual al recomendador')
    st.write(
        'Ingrese los datos de la compra realizada ')

    modo = st.radio(
        'Tipo de consulta',
        ['Cliente existente', 'Perfil nuevo (sin historial)'],
        horizontal=True,
        help=(
            'Indique si el cliente es nuevo o ha comprado anteriormente.'),
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader('👤 Perfil')

        if modo == 'Cliente existente' and df_historico is not None:
            clientes = sorted(df_historico['Customer Full Name'].dropna().unique().tolist())
            customer_name = st.selectbox('Nombre Completo', options=clientes)
            customer_id = df_historico.loc[df_historico['Customer Full Name'] == customer_name, 'Customer ID'].iloc[0]
            age = df_historico.loc[df_historico['Customer Full Name'] == customer_name, 'Age'].iloc[0]
            st.text_input(label='Edad', value=age, disabled=True)
            gender = df_historico.loc[df_historico['Customer Full Name'] == customer_name, 'Gender'].iloc[0]
            st.text_input(label='Genero', value=gender, disabled=True)
            location = df_historico.loc[df_historico['Customer Full Name'] == customer_name, 'Location'].iloc[0]
            st.text_input(label='Ciudad', value=location, disabled=True)
            email = df_historico.loc[df_historico['Customer Full Name'] == customer_name, 'Customer Email'].iloc[0]
            st.text_input(label='Email', value=email, disabled=True)
            previous_purchases = int(df_historico.loc[df_historico['Customer Full Name'] == customer_name, 'Previous Purchases'].iloc[0])
            previous_purchases += 1

        else:
            customer_name = st.text_input(label='Nombre completo', placeholder='Nombre Cliente')
            customer_id = generate_new_customer_id(df_historico, id_column="Customer ID")
            age = campo_numerico('Age', 'Edad')
            gender = campo_categorico(df_historico, 'Gender', 'Genero')
            location = campo_categorico(df_historico, 'Location', 'Ciudad')
            email = st.text_input(label='Email', placeholder='client@example.com')
            previous_purchases = 1

        
    with col2:
        st.subheader('🛒 Compra')
        purchase_date = st.date_input('Fecha de compra', value=datetime.today())
        category = campo_categorico(df_historico, 'Category', 'Categoria')
        brand = campo_categorico(df_historico, 'Brand', 'Marca')
        item_purchased = campo_categorico(df_historico, 'Item Purchased', 'Item comprado')

    with col3:
        st.subheader('🏬 Canal')
        online_offline = campo_categorico(df_historico, 'Online/Offline', 'Canal de venta')

        temporada = asignar_session(purchase_date)
        st.metric('Temporada actual', temporada)


    if online_offline == 'Online':
        campos_visibles = CAMPOS_OPERATIVOS
    else:
        campos_visibles = [c for c in CAMPOS_OPERATIVOS if c not in CAMPOS_SOLO_ONLINE]

    with st.expander('Detalles del producto: '):
        operativos = {}
        cols_op = st.columns(4)

        for i, columna in enumerate(campos_visibles):
            with cols_op[i % 4]:
                if columna in CAMPOS_NUMERICOS:
                    operativos[columna] = campo_numerico(columna)
                else:
                    operativos[columna] = campo_categorico(df_historico, columna)

        #se rellenan los campos que no se mostraron para que el registro quede completo en el dataset
        if campos_visibles != CAMPOS_OPERATIVOS:
            operativos.update(DEFAULTS_OFFLINE)
            online_store = 'In-Store Purchase'
        else:
            online_store = operativos['Online Store']

        transaction_id = st.text_input(
            'Transaction ID', value=f'TXN-{np.random.randint(10000, 99999)}'
        )

    if st.button('🚀 Registrar y consultar recomendador', type='primary'):
        record = {
            'Transaction ID': transaction_id,
            'Customer ID': customer_id,
            'Customer Full Name': customer_name,
            'Customer Email': email,
            'Purchase Date': str(purchase_date),
            'Age': age,
            'Gender': gender,
            'Location': location,
            'Online/Offline': online_offline,
            'Online Store': online_store,
            'Category': category,
            'Item Purchased': item_purchased,
            'Brand': brand,
            'Color': operativos['Color'],
            'Size': operativos['Size'],
            'Quantity': operativos['Quantity'],
            'Purchase Amount (₹)': operativos['Purchase Amount (₹)'],
            'Discount (%)': operativos['Discount (%)'],
            'Festival/Sale': operativos['Festival/Sale'],
            'Shipping Charge (₹)': operativos['Shipping Charge (₹)'],
            'Delivery Speed': operativos['Delivery Speed'],
            'Delivery Time (Days)': operativos['Delivery Time (Days)'],
            'Subscription Status': operativos['Subscription Status'],
            'Payment Method': operativos['Payment Method'],
            'Review Rating': operativos['Review Rating'],
            'Return Status': operativos['Return Status'],
            'Previous Purchases': previous_purchases,
        }

        single_df = pd.DataFrame([record])

        log_event(
            logger,
            'Indexacion individual recibida',
            customer_id=str(customer_id),
            transaction_id=transaction_id,
            modo=modo,
        )

        #validacion
        validator = DataValidator(single_df)
        reporte = validator.run_checks()

        buffer = io.StringIO()
        with contextlib_redirect(buffer):
            single_clean = validator.clean(strategy=ESTRATEGIA_INDIVIDUAL)

        if reporte['missing_columns']:
            st.error(f'Faltan columnas obligatorias: {reporte["missing_columns"]}')
            log_event(logger, 'Indexacion rechazada', level=40,
                      columnas=reporte['missing_columns'])
            st.stop()

        if single_clean.empty:
            st.error('Registro descartado: falta Customer ID, Item Purchased o fecha.')
            log_event(logger, 'Indexacion descartada en validacion', level=40)
            st.stop()

        st.success(f'✅ Transaccion {transaction_id} validada.')

        with st.expander('Log de validacion'):
            st.code('\n'.join(validator.get_log()) or 'Sin observaciones.')

        s3_key = upload_df_to_s3(single_clean, S3_BUCKET, prefijo='staging/individual')

        if s3_key:
            st.info(f'Registro enviado a la base de datos')
        else:
            st.warning('El registro se valido pero no se pudo subir a la Base de Datos. Reintentar o comunicarse con el soporte.')

        #recomendacion — prediccion unica, item-based
        st.markdown('---')
        st.subheader('🔮 Recomendaciones')

        recomendacion, aviso = obtener_recomendacion_item(item_purchased)

        if recomendacion:
            st.success('Items similares a **' + item_purchased + '**: ' + ', '.join(recomendacion))
            log_event(logger, 'Recomendacion generada',
                      item=item_purchased, fuente='item_based')
        else:
            st.warning(aviso)
            log_event(logger, 'Recomendacion no disponible para este usuario.', level=30,
                      item=item_purchased, motivo=aviso)


#TAB 2 - carga masiva
with tabs[1]:
    st.header('Carga mensual de transacciones a la Base de Datos')
    st.write('El archivo se valida antes de guardarse.')

    uploaded_file = st.file_uploader('Archivo mensual de ventas', type=['csv'])

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_upload = pd.read_csv(uploaded_file)
            else:
                df_upload = pd.read_excel(uploaded_file)

            log_event(logger, 'Archivo cargado por el usuario',
                      filename=uploaded_file.name, rows=len(df_upload))

            st.write(
                f'📁 **{uploaded_file.name}** — {len(df_upload)} filas, '
                f'{len(df_upload.columns)} columnas'
            )

            st.subheader('🔍 Fase 1: reporte de validacion')
            validator = DataValidator(df_upload)
            report = validator.run_checks()

            m1, m2, m3, m4 = st.columns(4)
            m1.metric('Total filas', report['shape'][0])
            m2.metric('Columnas faltantes', len(report['missing_columns']))
            m3.metric('Duplicados exactos', report['duplicate_rows'])
            m4.metric('Clientes con 1 compra', report['orphan_customers'])

            if report['missing_columns']:
                st.error(f'❌ Faltan columnas requeridas: {report["missing_columns"]}')
                log_event(logger, 'Archivo rechazado', level=40,
                          columnas=report['missing_columns'])
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

            st.subheader('🧹 Fase 2: limpieza e imputacion')

            forzar = st.checkbox(
                'Imputar aunque la columna supere el 15% de nulos',)

            if st.button('Ejecutar limpieza', type='secondary'):
                buffer = io.StringIO()
                with contextlib_redirect(buffer):
                    df_clean = validator.clean(
                        strategy=FULL_DEFAULT_STRATEGY,
                        force_impute_above_threshold=forzar,
                    )

                st.session_state['df_clean'] = df_clean
                st.session_state['clean_log'] = validator.get_log()

                log_event(logger, 'Limpieza ejecutada',
                          rows_before=len(df_upload), rows_after=len(df_clean),
                          forzado=forzar)

            if 'df_clean' in st.session_state:
                df_clean = st.session_state['df_clean']
                clean_log = st.session_state['clean_log']

                c1, c2 = st.columns(2)
                c1.metric('Filas antes', len(df_upload))
                c2.metric('Filas despues', len(df_clean),
                          delta=len(df_clean) - len(df_upload))

                bloqueadas = [linea for linea in clean_log if 'BLOCKED' in linea]
                if bloqueadas:
                    st.warning(
                        f'{len(bloqueadas)} columna(s) superaron el umbral de nulos '
                        'y quedaron sin imputar.'
                    )

                st.dataframe(df_clean.head(10), width='stretch')

                with st.expander('Log de cambios e imputaciones'):
                    for linea in clean_log:
                        st.text(f'• {linea}')

                st.markdown('---')
                st.subheader('☁️ Fase 3: subida a la base de datos')

                if st.button('📤 Subir dataset limpio', type='primary'):
                    with st.spinner('Guardando en Base de Datos...'):
                        s3_key = upload_df_to_s3(df_clean, S3_BUCKET)

                    if s3_key:
                        st.success(f'🎉 Subido a la Base de Datos')
                    else:
                        st.error('⚠️ Fallo la subida. Reintente o comuniquese con el soporte.')

        except Exception as error:
            st.error(f'Error al procesar el archivo: {error}')
            log_event(logger, 'Error en carga masiva', level=40, error=str(error))


#TAB 3 - explorador 360
with tabs[2]:
    st.header('💡 Exploracion e interaccion con clientes')

    if df_historico is None:
        st.warning('Sin dataset cargado no se puede construir la ficha.')
    else:
        clientes = sorted(df_historico['Customer Full Name'].dropna().unique().tolist())
        cliente = st.selectbox('Cliente', options=clientes, key='cliente_360')
        cliente_id = df_historico.loc[df_historico['Customer Full Name'] == cliente, 'Customer ID'].iloc[0]

        datos = metricas_cliente(df_historico, cliente_id)

        if not datos:
            st.warning('Sin historial para este cliente.')
        else:
            st.markdown(f'### 🪪 Ficha 360 — Cliente {cliente}')

            f1, f2, f3, f4, f5 = st.columns(5)
            f1.metric('Ciudad', datos['ciudad'])
            f2.metric('Gasto total (₹)', f'{datos["gasto_total"]:,.0f}')
            f3.metric('Ordenes', datos['compras'])
            f4.metric('Categoria preferida', datos['categoria'])
            f5.metric(
                'Actividad',
                datos['actividad'],
                delta=f'{datos["dias_inactivo"]} dias sin comprar',
                delta_color='inverse' if datos['actividad'] == 'Bajo' else 'normal',
            )

            t_hist, t_camp, t_notas = st.tabs(
                ['Historial', 'Campañas', 'Notas CRM']
            )

            with t_hist:
                st.dataframe(
                    datos['historial'][[
                        'Purchase Date', 'Item Purchased', 'Category', 'Brand',
                        'Purchase Amount (₹)', 'Return Status',
                    ]],
                    width='stretch',
                )

            with t_camp:
                st.caption('Arma el mensaje a enviar.')

                canal = st.radio('Canal', ['WhatsApp', 'SMS', 'Email'], horizontal=True)
                descuento = st.slider('Descuento (%)', 5, 40, 15, step=5)
                motivo = st.selectbox(
                    'Motivo',
                    ['Diwali', 'Holi', 'Fin de temporada', 'Reactivacion'],
                )

                mensaje = (
                    f'Hola! Tenemos {descuento}% off en {datos["marca"]} '
                    f'({datos["categoria"]}) por {motivo}. '
                    f'Te esperamos en nuestra tienda de {datos["ciudad"]}.'
                )
                st.text_area('Vista previa', value=mensaje, height=100)

                if st.button('📲 Registrar envio simulado'):
                    log_event(logger, 'Campaña simulada', customer_id=cliente,
                              canal=canal, descuento=descuento, motivo=motivo)
                    st.success(f'Envio por {canal} registrado en el log.')

            with t_notas:
                #PENDIENTE: las notas viven en memoria de sesion, es solo codigo de muestra
                #a futuro se puede agregar la logica para guardar las notas en Json para cada cliente
                notas = st.session_state.setdefault('notas_crm', {})
                previas = notas.get(cliente, [])

                nueva = st.text_area('Nueva nota')

                if st.button('💾 Guardar nota') and nueva.strip():
                    previas.append({
                        'fecha': datetime.now().strftime('%Y-%m-%d %H:%M'),
                        'nota': nueva.strip(),
                    })
                    notas[cliente] = previas
                    log_event(logger, 'Nota CRM agregada', customer_id=cliente)
                    st.success('Nota guardada.')

                if previas:
                    st.table(pd.DataFrame(previas))


#TAB 4 - auditoria, solo para admin
if es_admin:
    with tabs[3]:
        st.header('📜 Auditoria de logs')

        log_dir = Path('artifacts/logs')

        if not log_dir.exists():
            st.info('Todavia no se genero ningun archivo de log.')
        else:
            archivos = sorted(log_dir.glob('*.log'), reverse=True)

            if not archivos:
                st.info('El directorio de logs esta vacio.')
            else:
                seleccionado = st.selectbox(
                    'Archivo de registro', [f.name for f in archivos]
                )

                with open(log_dir / seleccionado, 'r', encoding='utf-8') as f:
                    lineas = f.readlines()

                registros = []
                for linea in lineas:
                    try:
                        registros.append(json.loads(linea.strip()))
                    except json.JSONDecodeError:
                        continue

                if not registros:
                    st.warning('El archivo no tiene lineas JSON validas.')
                else:
                    df_logs = pd.DataFrame(registros)

                    niveles = st.multiselect(
                        'Filtrar por nivel',
                        options=sorted(df_logs['level'].unique()),
                        default=sorted(df_logs['level'].unique()),
                    )

                    df_filtrado = df_logs[df_logs['level'].isin(niveles)]
                    st.dataframe(df_filtrado, width='stretch')

                    st.download_button(
                        'Descargar log',
                        data='\n'.join(lineas),
                        file_name=seleccionado,
                        mime='text/plain',
                    )