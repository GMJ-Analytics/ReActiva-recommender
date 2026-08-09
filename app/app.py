import boto3
from botocore.exceptions import ClientError
import streamlit as st
from datetime import datetime


S3_BUCKET = 'rawdatafp'

s3 = boto3.client('s3')

# interface de streamlit
st.set_page_config(
    page_title='ReActiva - Carga de datos',
    page_icon='🛍️',
    layout='centered',
)
st.title('🛍️ ReActiva Recommender')
st.subheader('Carga de datos de la tienda')
st.write(
    'Seleccione el archivo CSV de datos de la tienda para cargarlo al sistema.'
)

uploaded_file = st.file_uploader('Seleccione un archivo CSV', type=['csv'])

# subir el archivo a S3
if uploaded_file is not None:

  st.success(f'Archivo seleccionado: {uploaded_file.name}')

  if st.button('📤 Subir datos a S3'):

    try:
      fecha_hoy = datetime.now().strftime('%d_%m_%Y')
      s3_key = f'client_data_{fecha_hoy}.csv'

      # Subir archivo directamente desde Streamlit a S3
      s3.upload_fileobj(uploaded_file, S3_BUCKET, s3_key)

      st.success('✅ Archivo subido correctamente.')

    except ClientError as e:

      st.error('❌ No se pudo subir el archivo.')

      st.exception(e)