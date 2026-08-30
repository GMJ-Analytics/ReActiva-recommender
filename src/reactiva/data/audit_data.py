from pathlib import Path
import pandas as pd
from reactiva.config import DATASET_URI
from reactiva.data.load_data import cargar_datos

# ============================================================
# 1. CONFIGURACION Y DESCRIPCIONES
# ============================================================

DESCRIPCIONES_COLUMNAS = {
    "Transaction ID": "Identificador unico de la transaccion.",
    "Customer ID": "Identificador del cliente.",
    "Customer Full Name": ("Nombre y apellido asociados al cliente para su identificacion."
    ),
    "Customer Email": ("Correo electronico asociado al cliente para acciones de reactivacion."
    ),
    "Purchase Date": "Fecha en la que se realizo la compra.",
    "Age": "Edad del cliente.",
    "Gender": "Genero informado del cliente.",
    "Location": "Ubicacion geografica asociada al cliente o compra.",
    "Online/Offline": "Canal en el que se realizo la compra.",
    "Online Store": (
        "Tienda online utilizada. Para compras offline se registra "
        "In-Store Purchase."
    ),
    "Category": "Categoria general del producto comprado.",
    "Item Purchased": "Producto adquirido por el cliente.",
    "Brand": "Marca del producto comprado.",
    "Color": "Color del producto.",
    "Size": "Talle o tamaño del producto.",
    "Quantity": "Cantidad de unidades compradas en la transaccion.",
    "Purchase Amount (₹)": "Importe total de la compra expresado en rupias.",
    "Discount (%)": "Porcentaje de descuento aplicado a la compra.",
    "Festival/Sale": (
        "Evento comercial o tipo de promocion asociado a la compra."
    ),
    "Shipping Charge (₹)": "Costo de envio expresado en rupias.",
    "Delivery Speed": (
        "Modalidad o velocidad de entrega. Para compras offline se utiliza "
        "N/A (Offline)."
    ),
    "Delivery Time (Days)": "Cantidad de dias requeridos para la entrega.",
    "Subscription Status": (
        "Indica si el cliente posee una suscripcion activa."
    ),
    "Payment Method": "Metodo utilizado para realizar el pago.",
    "Review Rating": "Calificacion de la compra o producto.",
    "Return Status": "Indica si la compra fue devuelta.",
    "Previous Purchases": "Cantidad de compras anteriores registradas.",
}

# ============================================================
# 2. AUDITORIA GENERAL DEL DATASET
# ============================================================

def auditar_dimensiones(df):
    """Obtiene la cantidad de filas y columnas del dataset."""

    return {
        "filas": int(df.shape[0]),
        "columnas": int(df.shape[1]),
    }


def auditar_duplicados(df):
    """Cuantifica filas completamente duplicadas."""

    filas = len(df)
    duplicados = int(df.duplicated().sum())

    porcentaje = float(
        round((duplicados / filas) * 100, 2)
    )

    return {
        "duplicados": duplicados,
        "porcentaje_duplicados": porcentaje,
    }


def auditar_nulos(df):
    """Cuantifica valores nulos reales por columna."""

    filas = len(df)
    nulos_por_columna = {}

    for columna in df.columns:
        cantidad_nulos = int(df[columna].isna().sum())

        porcentaje_nulos = float(
            round((cantidad_nulos / filas) * 100, 2)
        )

        if cantidad_nulos > 0:
            nulos_por_columna[columna] = {
                "cantidad": cantidad_nulos,
                "porcentaje": porcentaje_nulos,
            }

    return nulos_por_columna

# ============================================================
# 3. ESTRUCTURA Y TIPOS DE DATOS
# ============================================================

def auditar_tipos(df):
    """Registra el tipo detectado para cada columna."""

    return {
        columna: str(df[columna].dtype)
        for columna in df.columns
    }


def auditar_cardinalidad(df):
    """Calcula la cantidad de valores unicos por columna."""

    return {
        columna: int(df[columna].nunique(dropna=False))
        for columna in df.columns
    }


def auditar_rangos_numericos(df):
    """Obtiene estadisticas basicas de las variables numericas."""

    columnas_numericas = df.select_dtypes(
        include="number"
    ).columns

    rangos = {}

    for columna in columnas_numericas:
        rangos[columna] = {
            "minimo": float(df[columna].min()),
            "maximo": float(df[columna].max()),
            "media": float(
                round(df[columna].mean(), 2)
            ),
            "mediana": float(df[columna].median()),
        }

    return rangos

# ============================================================
# 4. AUDITORIA TEMPORAL
# ============================================================

def auditar_fechas(df):
    """
    Evalua Purchase Date sin modificar el dataset original.

    Comprueba si los valores pueden convertirse a datetime y
    determina el rango temporal disponible.
    """

    fechas_convertidas = pd.to_datetime(
        df["Purchase Date"],
        errors="coerce",
    )

    fechas_invalidas = int(
        fechas_convertidas.isna().sum()
    )

    filas = len(df)

    return {
        "tipo_original": str(
            df["Purchase Date"].dtype
        ),
        "fechas_invalidas": fechas_invalidas,
        "fecha_minima": (
            fechas_convertidas.min().strftime("%Y-%m-%d")
            if fechas_invalidas < filas
            else None
        ),
        "fecha_maxima": (
            fechas_convertidas.max().strftime("%Y-%m-%d")
            if fechas_invalidas < filas
            else None
        ),
    }

# ============================================================
# 5. VALORES ESTRUCTURALES Y CONSISTENCIA DEL CANAL
# ============================================================

def auditar_valores_estructurales(df):
    """
    Cuantifica valores esperados por la logica Online / Offline.

    Estos valores no se consideran datos faltantes.
    """

    filas = len(df)

    cantidad_in_store = int(
        (
            df["Online Store"]
            == "In-Store Purchase"
        ).sum()
    )

    cantidad_delivery_offline = int(
        (
            df["Delivery Speed"]
            == "N/A (Offline)"
        ).sum()
    )

    return {
        "Online Store": {
            "valor": "In-Store Purchase",
            "cantidad": cantidad_in_store,
            "porcentaje": float(
                round(
                    (cantidad_in_store / filas) * 100,
                    2,
                )
            ),
        },
        "Delivery Speed": {
            "valor": "N/A (Offline)",
            "cantidad": cantidad_delivery_offline,
            "porcentaje": float(
                round(
                    (
                        cantidad_delivery_offline
                        / filas
                    )
                    * 100,
                    2,
                )
            ),
        },
    }


def auditar_consistencia_canal(df):
    """
    Comprueba coherencia entre el canal de compra y variables
    relacionadas con tienda, envio y entrega.
    """

    offline = df[
        df["Online/Offline"] == "Offline"
    ]

    online = df[
        df["Online/Offline"] == "Online"
    ]

    return {
        "cantidad_offline": int(len(offline)),
        "cantidad_online": int(len(online)),
        "offline_online_store_incorrecto": int(
            (
                offline["Online Store"]
                != "In-Store Purchase"
            ).sum()
        ),
        "offline_delivery_speed_incorrecto": int(
            (
                offline["Delivery Speed"]
                != "N/A (Offline)"
            ).sum()
        ),
        "offline_shipping_charge_incorrecto": int(
            (
                offline["Shipping Charge (₹)"]
                != 0
            ).sum()
        ),
        "offline_delivery_time_incorrecto": int(
            (
                offline["Delivery Time (Days)"]
                != 0
            ).sum()
        ),
        "online_in_store_incorrecto": int(
            (
                online["Online Store"]
                == "In-Store Purchase"
            ).sum()
        ),
        "online_delivery_offline_incorrecto": int(
            (
                online["Delivery Speed"]
                == "N/A (Offline)"
            ).sum()
        ),
    }

# ============================================================
# 6. AUDITORIA DE MONTOS
# ============================================================

def auditar_montos(df):
    """
    Identifica valores extremos de Purchase Amount mediante IQR.

    Los valores detectados se consideran extremos estadisticos
    y no errores automaticamente.
    """

    monto = df["Purchase Amount (₹)"]

    q1 = float(monto.quantile(0.25))
    q3 = float(monto.quantile(0.75))
    iqr = q3 - q1

    limite_inferior = q1 - (1.5 * iqr)
    limite_superior = q3 + (1.5 * iqr)

    mascara_extremos = (
        (monto < limite_inferior)
        | (monto > limite_superior)
    )

    cantidad_extremos = int(
        mascara_extremos.sum()
    )

    filas = len(df)

    return {
        "q1": round(q1, 2),
        "q3": round(q3, 2),
        "iqr": round(iqr, 2),
        "limite_inferior_iqr": round(
            limite_inferior,
            2,
        ),
        "limite_superior_iqr": round(
            limite_superior,
            2,
        ),
        "cantidad_valores_extremos": cantidad_extremos,
        "porcentaje_valores_extremos": float(
            round(
                (cantidad_extremos / filas) * 100,
                2,
            )
        ),
        "percentil_95": float(
            round(monto.quantile(0.95), 2)
        ),
        "percentil_99": float(
            round(monto.quantile(0.99), 2)
        ),
        "maximo": float(monto.max()),
    }

# ============================================================
# 7. CONCENTRACION DE CATEGORIAS Y PRODUCTOS
# ============================================================

def auditar_concentracion_recomendador(df):
    """
    Cuantifica la concentracion de categorias y productos.

    Permite medir objetivamente posibles desbalances relevantes
    para el futuro sistema recomendador.
    """

    distribucion_categorias = (
        df["Category"]
        .value_counts(normalize=True)
        .mul(100)
        .round(2)
    )

    distribucion_productos = (
        df["Item Purchased"]
        .value_counts(normalize=True)
        .mul(100)
        .round(2)
    )

    return {
        "categorias": {
            categoria: float(porcentaje)
            for categoria, porcentaje
            in distribucion_categorias.items()
        },
        "producto_mas_frecuente": str(
            distribucion_productos.index[0]
        ),
        "porcentaje_producto_mas_frecuente": float(
            distribucion_productos.iloc[0]
        ),
        "porcentaje_top_5_productos": float(
            round(
                distribucion_productos.head(5).sum(),
                2,
            )
        ),
        "distribucion_productos": {
            producto: float(porcentaje)
            for producto, porcentaje
            in distribucion_productos.items()
        },
    }

# ============================================================
# 8. ESTRUCTURA DE TRANSACCIONES Y CLIENTES
# ============================================================

def auditar_estructura_clientes(df):
    """
    Analiza identificadores y cantidad de transacciones por cliente.

    Tener mas de una transaccion no implica por si solo recompra
    dentro de una ventana temporal determinada.
    """

    compras_por_cliente = (
        df.groupby("Customer ID").size()
    )

    return {
        "transaction_id_duplicados": int(
            df["Transaction ID"]
            .duplicated()
            .sum()
        ),
        "clientes_unicos": int(
            df["Customer ID"].nunique()
        ),
        "min_compras_por_cliente": int(
            compras_por_cliente.min()
        ),
        "max_compras_por_cliente": int(
            compras_por_cliente.max()
        ),
        "media_compras_por_cliente": float(
            round(
                compras_por_cliente.mean(),
                2,
            )
        ),
        "mediana_compras_por_cliente": float(
            compras_por_cliente.median()
        ),
        "clientes_una_compra": int(
            (
                compras_por_cliente == 1
            ).sum()
        ),
        "clientes_mas_de_una_compra": int(
            (
                compras_por_cliente > 1
            ).sum()
        ),
    }

# ============================================================
# 9. DICCIONARIO DE DATOS
# ============================================================

def crear_diccionario_datos(df):
    """
    Construye un diccionario tecnico a partir del dataset cargado.

    Incluye tipo detectado, nulos, cardinalidad, ejemplo y
    descripcion funcional de cada variable.
    """

    registros = []

    for columna in df.columns:
        serie = df[columna]
        valores_no_nulos = serie.dropna()

        ejemplo = (
            str(valores_no_nulos.iloc[0])
            if not valores_no_nulos.empty
            else ""
        )

        registros.append(
            {
                "variable": columna,
                "tipo_detectado": str(
                    serie.dtype
                ),
                "nulos": int(
                    serie.isna().sum()
                ),
                "porcentaje_nulos": float(
                    round(
                        serie.isna().mean() * 100,
                        2,
                    )
                ),
                "valores_unicos": int(
                    serie.nunique(
                        dropna=False
                    )
                ),
                "ejemplo": ejemplo,
                "descripcion": (
                    DESCRIPCIONES_COLUMNAS.get(
                        columna,
                        "Descripcion pendiente.",
                    )
                ),
            }
        )

    return pd.DataFrame(registros)


def guardar_diccionario_datos(diccionario):
    """Guarda el diccionario tecnico dentro de docs."""

    raiz_proyecto = (
        Path(__file__)
        .resolve()
        .parents[3]
    )

    ruta_salida = (
        raiz_proyecto
        / "docs"
        / "data_dictionary.csv"
    )

    diccionario.to_csv(
        ruta_salida,
        index=False,
        encoding="utf-8-sig",
    )

    return ruta_salida

# ============================================================
# 10. ORQUESTADOR PRINCIPAL
# ============================================================

def auditar_dataset(path_file):
    """
    Ejecuta todos los controles de auditoria sobre el dataset.

    Esta funcion centraliza los resultados sin modificar los datos
    originales utilizados por el resto del pipeline.
    """

    df = cargar_datos(path_file)

    dimensiones = auditar_dimensiones(df)
    duplicados = auditar_duplicados(df)

    resultado = {
        "filas": dimensiones["filas"],
        "columnas": dimensiones["columnas"],
        "duplicados": duplicados["duplicados"],
        "porcentaje_duplicados": (
            duplicados["porcentaje_duplicados"]
        ),
        "nulos_por_columna": auditar_nulos(df),
        "valores_estructurales": (
            auditar_valores_estructurales(df)
        ),
        "tipos_de_datos": auditar_tipos(df),
        "cardinalidad": auditar_cardinalidad(df),
        "rangos_numericos": (
            auditar_rangos_numericos(df)
        ),
        "auditoria_fechas": auditar_fechas(df),
        "auditoria_montos": auditar_montos(df),
        "consistencia_canal": (
            auditar_consistencia_canal(df)
        ),
        "concentracion_recomendador": (
            auditar_concentracion_recomendador(df)
        ),
        "estructura_clientes": (
            auditar_estructura_clientes(df)
        ),
        "diccionario_datos": (
            crear_diccionario_datos(df)
        ),
    }

    return resultado

# ============================================================
# 11. SALIDA DE CONSOLA
# ============================================================

def imprimir_resultados(resultado):
    """Presenta los principales resultados de la auditoria."""

    print("\n=== DIMENSIONES ===")
    print("Filas:", resultado["filas"])
    print("Columnas:", resultado["columnas"])

    print("\n=== DUPLICADOS ===")
    print(
        "Cantidad:",
        resultado["duplicados"],
    )
    print(
        "Porcentaje:",
        resultado["porcentaje_duplicados"],
        "%",
    )

    print("\n=== NULOS REALES ===")
    print(
        resultado["nulos_por_columna"]
    )

    print("\n=== VALORES ESTRUCTURALES ===")
    for columna, datos in (
        resultado["valores_estructurales"].items()
    ):
        print(
            columna,
            "->",
            datos,
        )

    print("\n=== TIPOS DE DATOS ===")
    for columna, tipo in (
        resultado["tipos_de_datos"].items()
    ):
        print(
            f"{columna}: {tipo}"
        )

    print("\n=== CARDINALIDAD ===")
    for columna, cantidad in (
        resultado["cardinalidad"].items()
    ):
        print(
            f"{columna}: {cantidad}"
        )

    print("\n=== RANGOS NUMERICOS ===")
    for columna, datos in (
        resultado["rangos_numericos"].items()
    ):
        print(
            f"{columna}: {datos}"
        )

    print("\n=== AUDITORIA DE FECHAS ===")
    for clave, valor in (
        resultado["auditoria_fechas"].items()
    ):
        print(
            f"{clave}: {valor}"
        )

    print("\n=== AUDITORIA DE MONTOS ===")
    for clave, valor in (
        resultado["auditoria_montos"].items()
    ):
        print(
            f"{clave}: {valor}"
        )

    print("\n=== CONSISTENCIA DE CANAL ===")
    for clave, valor in (
        resultado["consistencia_canal"].items()
    ):
        print(
            f"{clave}: {valor}"
        )

    print(
        "\n=== CONCENTRACION DEL RECOMENDADOR ==="
    )

    print("Categorias:")

    for categoria, porcentaje in (
        resultado[
            "concentracion_recomendador"
        ]["categorias"].items()
    ):
        print(
            f"{categoria}: {porcentaje} %"
        )

    print(
        "Producto mas frecuente:",
        resultado[
            "concentracion_recomendador"
        ]["producto_mas_frecuente"],
    )

    print(
        "Porcentaje producto mas frecuente:",
        resultado[
            "concentracion_recomendador"
        ][
            "porcentaje_producto_mas_frecuente"
        ],
        "%",
    )

    print(
        "Porcentaje Top 5 productos:",
        resultado[
            "concentracion_recomendador"
        ]["porcentaje_top_5_productos"],
        "%",
    )

    print("\n=== ESTRUCTURA DE CLIENTES ===")

    for clave, valor in (
        resultado["estructura_clientes"].items()
    ):
        print(
            f"{clave}: {valor}"
        )

    print("\n=== DICCIONARIO DE DATOS ===")

    print(
        resultado["diccionario_datos"]
        .to_string(index=False)
    )

# ============================================================
# 12. EJECUCION DIRECTA
# ============================================================

if __name__ == "__main__":
    resultado = auditar_dataset(DATASET_URI)

    ruta_diccionario = guardar_diccionario_datos(
        resultado["diccionario_datos"]
    )

    imprimir_resultados(resultado)

    print("\nDiccionario guardado en:")
    print(ruta_diccionario)