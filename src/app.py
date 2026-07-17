from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
import pandas as pd
import requests
import os
import time
import re

from geopy.geocoders import Nominatim
from dotenv import load_dotenv
from openai import OpenAI
from services.ia_logistica import analizar_pedidos


# =====================================================
# CARGAR VARIABLES DE ENTORNO
# =====================================================

load_dotenv()


# =====================================================
# CONFIGURACIÓN DE FLASK
# =====================================================

app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "routemind-secret-key"
)


# =====================================================
# CONFIGURACIÓN DE OPENAI
# =====================================================

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY"
)


if OPENAI_API_KEY:

    cliente_ia = OpenAI(
        api_key=OPENAI_API_KEY
    )

else:

    cliente_ia = None


# =====================================================
# CONEXIÓN A MYSQL
# =====================================================

def obtener_conexion():

    return mysql.connector.connect(

        host=os.getenv(
            "ROUTEMIND_DB_HOST",
            "localhost"
        ),

        user=os.getenv(
            "ROUTEMIND_DB_USER",
            "root"
        ),

        password=os.getenv(
            "ROUTEMIND_DB_PASSWORD",
            "080905"
        ),

        database=os.getenv(
            "ROUTEMIND_DB_NAME",
            "routemind_db"
        )

    )


# =====================================================
# NORMALIZAR DIRECCIÓN
# =====================================================

def normalizar_direccion(direccion):

    direccion = direccion.upper().strip()


    reemplazos = {

        "AND ": "ANDADOR ",

        "MZ ": "MANZANA ",

        "LT ": "LOTE ",

        "COL ": "COLONIA ",

        "GRO": "GUERRERO",

        "CDMX": "CIUDAD DE MÉXICO"

    }


    for original, nuevo in reemplazos.items():

        direccion = direccion.replace(

            original,

            nuevo

        )


    if "MÉXICO" not in direccion:

        direccion += ", MÉXICO"


    return direccion


# =====================================================
# EXTRAER DATOS DE LA DIRECCIÓN
# =====================================================

def extraer_datos_direccion(direccion):

    direccion_mayusculas = direccion.upper()


    datos = {

        "colonia": None,

        "codigo_postal": None,

        "ciudad": None,

        "estado": None

    }


    # -----------------------------------------------
    # CÓDIGO POSTAL
    # -----------------------------------------------

    codigo_postal = re.search(

        r"\b\d{5}\b",

        direccion_mayusculas

    )


    if codigo_postal:

        datos["codigo_postal"] = (

            codigo_postal.group()

        )


    # -----------------------------------------------
    # COLONIA
    # -----------------------------------------------

    colonia = re.search(

        r"(?:COL|COLONIA)\s+([^,]+)",

        direccion_mayusculas

    )


    if colonia:

        datos["colonia"] = (

            colonia.group(1).strip()

        )


    # -----------------------------------------------
    # ESTADO
    # -----------------------------------------------

    estados = [

        "GUERRERO",

        "CIUDAD DE MÉXICO",

        "JALISCO",

        "MICHOACÁN",

        "PUEBLA",

        "OAXACA",

        "VERACRUZ",

        "MORELOS",

        "QUERÉTARO",

        "SONORA",

        "SINALOA",

        "NAYARIT"

    ]


    for estado in estados:

        if estado in direccion_mayusculas:

            datos["estado"] = estado

            break


    # -----------------------------------------------
    # CIUDAD
    # -----------------------------------------------

    if "ACAPULCO" in direccion_mayusculas:

        datos["ciudad"] = (

            "ACAPULCO DE JUÁREZ"

        )


    return datos


# =====================================================
# CONSTRUIR DIRECCIÓN DE RESPALDO
# =====================================================

def construir_direccion_respaldo(direccion):

    datos = extraer_datos_direccion(

        direccion

    )


    partes = []


    if datos["colonia"]:

        partes.append(

            datos["colonia"]

        )


    if datos["codigo_postal"]:

        partes.append(

            datos["codigo_postal"]

        )


    if datos["ciudad"]:

        partes.append(

            datos["ciudad"]

        )


    if datos["estado"]:

        partes.append(

            datos["estado"]

        )


    partes.append(

        "MÉXICO"

    )


    return ", ".join(

        partes

    )


# =====================================================
# OBTENER COORDENADAS
# =====================================================

def obtener_coordenadas(direccion):

    try:


        geolocator = Nominatim(

            user_agent="RouteMindAI"

        )


        # =================================================
        # PRIMERA BÚSQUEDA: DIRECCIÓN COMPLETA
        # =================================================


        direccion_normalizada = normalizar_direccion(

            direccion

        )


        print(

            "Buscando dirección exacta:"

        )


        print(

            direccion_normalizada

        )


        location = geolocator.geocode(

            direccion_normalizada,

            country_codes="mx",

            language="es",

            addressdetails=True,

            timeout=10

        )


        time.sleep(1)


        if location:


            print(

                "Ubicación exacta encontrada"

            )


            return (

                float(location.latitude),

                float(location.longitude),

                "Exacta"

            )


        # =================================================
        # SEGUNDA BÚSQUEDA: UBICACIÓN APROXIMADA
        # =================================================


        direccion_respaldo = (

            construir_direccion_respaldo(

                direccion

            )

        )


        print(

            "Buscando ubicación aproximada:"

        )


        print(

            direccion_respaldo

        )


        location = geolocator.geocode(

            direccion_respaldo,

            country_codes="mx",

            language="es",

            addressdetails=True,

            timeout=10

        )


        time.sleep(1)


        if location:


            print(

                "Ubicación aproximada encontrada"

            )


            return (

                float(location.latitude),

                float(location.longitude),

                "Aproximada"

            )


        # =================================================
        # NO ENCONTRADA
        # =================================================


        print(

            "No se encontró la ubicación"

        )


        return (

            None,

            None,

            "No encontrada"

        )


    except Exception as error:


        print(

            "Error al geolocalizar:"

        )


        print(

            error

        )


        return (

            None,

            None,

            "No encontrada"

        )

@app.route(

    "/buscar-ubicacion"

)

# =====================================================
# BUSCAR UBICACIÓN
# =====================================================

def buscar_ubicacion():


    direccion = request.args.get(

        "direccion"

    )


    if not direccion:


        return {

            "encontrada": False

        }


    latitud, longitud, tipo = (

        obtener_coordenadas(

            direccion

        )

    )


    if latitud is None:


        return {

            "encontrada": False,

            "tipo": "No encontrada"

        }


    if tipo == "Exacta":


        mensaje = (

            "Ubicación exacta encontrada."

        )


    else:


        mensaje = (

            "Se encontró una ubicación aproximada."

            " Verifica el punto en el mapa."

        )


    return {


        "encontrada": True,


        "latitud": latitud,


        "longitud": longitud,


        "tipo": tipo,


        "mensaje": mensaje


    }


# =====================================================
# DASHBOARD
# =====================================================

@app.route("/")
def index():

    conexion = obtener_conexion()

    cursor = conexion.cursor(

        dictionary=True

    )


    cursor.execute(

        """

        SELECT COUNT(*) AS total

        FROM pedidos

        """

    )


    total_pedidos = cursor.fetchone()["total"]


    cursor.execute(

        """

        SELECT COUNT(*) AS total

        FROM pedidos

        WHERE estado = 'Pendiente'

        """

    )


    pendientes = cursor.fetchone()["total"]


    cursor.execute(

        """

        SELECT COUNT(*) AS total

        FROM pedidos

        WHERE estado = 'En ruta'

        """

    )


    en_ruta = cursor.fetchone()["total"]


    cursor.execute(

        """

        SELECT COUNT(*) AS total

        FROM pedidos

        WHERE estado = 'Entregado'

        """

    )


    entregados = cursor.fetchone()["total"]


    cursor.execute(

        """

        SELECT COUNT(*) AS total

        FROM pedidos

        WHERE origen_ubicacion = 'No encontrada'

        """

    )


    sin_ubicacion = cursor.fetchone()["total"]


    cursor.close()

    conexion.close()


    return render_template(

        "index.html",

        total_pedidos=total_pedidos,

        pendientes=pendientes,

        en_ruta=en_ruta,

        entregados=entregados,

        sin_ubicacion=sin_ubicacion

    )


# =====================================================
# PEDIDOS
# =====================================================

@app.route("/pedidos")
def pedidos():

    conexion = obtener_conexion()

    cursor = conexion.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT *
            FROM pedidos
            ORDER BY id DESC
            """
        )

        pedidos = cursor.fetchall()

    finally:

        cursor.close()

        conexion.close()


    return render_template(

        "pedidos.html",

        pedidos=pedidos

    )


# =====================================================
# REGISTRAR PEDIDO
# =====================================================

@app.route(
    "/registrar-pedido",
    methods=["GET", "POST"]
)
def registrar_pedido():

    if request.method == "GET":

        return render_template(
            "RegistrarPedido.html"
        )


    cliente = request.form.get(
        "cliente"
    )


    direccion = request.form.get(
        "direccion"
    )


    producto = request.form.get(
        "producto"
    )


    fecha_entrega = request.form.get(
        "fecha_entrega"
    )


    prioridad = request.form.get(
        "prioridad"
    )


    latitud_manual = request.form.get(
        "latitud"
    )


    longitud_manual = request.form.get(
        "longitud"
    )


    if not cliente or not direccion or not producto:

        flash(
            "Todos los campos obligatorios deben completarse.",
            "danger"
        )


        return redirect(
            url_for(
                "registrar_pedido"
            )
        )


    try:

        if latitud_manual and longitud_manual:

            latitud = float(
                latitud_manual
            )


            longitud = float(
                longitud_manual
            )


            origen_ubicacion = "Exacta"


        else:

            latitud, longitud, origen_ubicacion = (

                obtener_coordenadas(
                    direccion
                )

            )


    except Exception as error:

        print(
            "Error obteniendo coordenadas:",
            error
        )


        latitud = None


        longitud = None


        origen_ubicacion = "No encontrada"


    conexion = obtener_conexion()


    cursor = conexion.cursor()


    try:

        consulta = """

            INSERT INTO pedidos (

                cliente,

                direccion,

                producto,

                fecha_entrega,

                prioridad,

                estado,

                latitud,

                longitud,

                origen_ubicacion

            )

            VALUES (

                %s,

                %s,

                %s,

                %s,

                %s,

                %s,

                %s,

                %s,

                %s

            )

        """


        valores = (

            cliente,

            direccion,

            producto,

            fecha_entrega,

            prioridad,

            "Pendiente",

            latitud,

            longitud,

            origen_ubicacion

        )


        cursor.execute(

            consulta,

            valores

        )


        conexion.commit()


        flash(

            "Pedido registrado correctamente.",

            "success"

        )


    except Exception as error:

        conexion.rollback()


        print(

            "Error al registrar el pedido:",

            error

        )


        flash(

            f"Error al registrar el pedido: {error}",

            "danger"

        )


    finally:

        cursor.close()


        conexion.close()


    return redirect(

        url_for(

            "pedidos"

        )

    )

# =====================================================
# IMPORTAR CSV
# =====================================================

@app.route(

    "/importar-csv",

    methods=["POST"]

)

def importar_csv():


    archivo = request.files.get(

        "archivo"

    )


    if not archivo:


        flash(

            "No se seleccionó ningún archivo."

        )


        return redirect(

            "/pedidos"

        )


    try:


        df = pd.read_csv(

            archivo

        )


        columnas_requeridas = [

            "cliente",

            "direccion",

            "producto",

            "fecha_entrega",

            "prioridad"

        ]


        for columna in columnas_requeridas:


            if columna not in df.columns:


                flash(

                    f"Falta la columna: {columna}"

                )


                return redirect(

                    "/pedidos"

                )


        conexion = obtener_conexion()

        cursor = conexion.cursor()


        for _, fila in df.iterrows():


            latitud, longitud, origen = (

                obtener_coordenadas(

                    fila["direccion"]

                )

            )


            cursor.execute(

                """

                INSERT INTO pedidos

                (

                    cliente,

                    direccion,

                    producto,

                    fecha_entrega,

                    prioridad,

                    estado,

                    latitud,

                    longitud,

                    origen_ubicacion

                )

                VALUES

                (

                    %s,

                    %s,

                    %s,

                    %s,

                    %s,

                    'Pendiente',

                    %s,

                    %s,

                    %s

                )

                """,

                (

                    fila["cliente"],

                    fila["direccion"],

                    fila["producto"],

                    fila["fecha_entrega"],

                    fila["prioridad"],

                    latitud,

                    longitud,

                    origen

                )

            )


        conexion.commit()


        cursor.close()

        conexion.close()


        flash(

            "Pedidos importados correctamente."

        )


    except Exception as error:


        flash(

            f"Error al importar CSV: {error}"

        )


    return redirect(

        "/pedidos"

    )


# =====================================================
# IMPORTAR API
# =====================================================

@app.route("/importar-api")
def importar_api():


    try:


        respuesta = requests.get(

            "https://jsonplaceholder.typicode.com/users",

            timeout=10

        )


        usuarios = respuesta.json()


        conexion = obtener_conexion()

        cursor = conexion.cursor()


        for usuario in usuarios[:5]:


            direccion = (

                f'{usuario["address"]["street"]}, '

                f'{usuario["address"]["city"]}, '

                'México'

            )


            latitud, longitud, origen = (

                obtener_coordenadas(

                    direccion

                )

            )


            cursor.execute(

                """

                INSERT INTO pedidos

                (

                    cliente,

                    direccion,

                    producto,

                    fecha_entrega,

                    prioridad,

                    estado,

                    latitud,

                    longitud,

                    origen_ubicacion

                )

                VALUES

                (

                    %s,

                    %s,

                    %s,

                    CURDATE(),

                    'Media',

                    'Pendiente',

                    %s,

                    %s,

                    %s

                )

                """,

                (

                    usuario["name"],

                    direccion,

                    "Paquete de prueba",

                    latitud,

                    longitud,

                    origen

                )

            )


        conexion.commit()


        cursor.close()

        conexion.close()


        flash(

            "Pedidos importados desde la API."

        )


    except Exception as error:


        flash(

            f"Error al importar desde API: {error}"

        )


    return redirect(

        "/pedidos"

    )


# =====================================================
# CAMBIAR ESTADO
# =====================================================

@app.route(

    "/cambiar-estado/<int:pedido_id>/<nuevo_estado>"

)

def cambiar_estado(

    pedido_id,

    nuevo_estado

):


    transiciones = {


        "Pendiente": [

            "En preparación"

        ],


        "En preparación": [

            "En ruta"

        ],


        "En ruta": [

            "Entregado"

        ],


        "Entregado": []

    }


    conexion = obtener_conexion()

    cursor = conexion.cursor(

        dictionary=True

    )


    cursor.execute(

        """

        SELECT estado

        FROM pedidos

        WHERE id = %s

        """,

        (

            pedido_id,

        )

    )


    pedido = cursor.fetchone()


    if not pedido:


        flash(

            "Pedido no encontrado."

        )


        cursor.close()

        conexion.close()


        return redirect(

            "/pedidos"

        )


    estado_anterior = pedido["estado"]


    if nuevo_estado not in transiciones.get(

        estado_anterior,

        []

    ):


        flash(

            "Transición de estado no permitida."

        )


        cursor.close()

        conexion.close()


        return redirect(

            "/pedidos"

        )


    cursor.execute(

        """

        UPDATE pedidos

        SET estado = %s

        WHERE id = %s

        """,

        (

            nuevo_estado,

            pedido_id

        )

    )


    cursor.execute(

        """

        INSERT INTO historial_estados

        (

            pedido_id,

            estado_anterior,

            estado_nuevo

        )

        VALUES

        (

            %s,

            %s,

            %s

        )

        """,

        (

            pedido_id,

            estado_anterior,

            nuevo_estado

        )

    )


    conexion.commit()


    cursor.close()

    conexion.close()


    flash(

        "Estado actualizado correctamente."

    )


    return redirect(

        "/pedidos"

    )


# =====================================================
# RUTAS
# =====================================================

@app.route("/rutas")
def rutas():


    conexion = obtener_conexion()

    cursor = conexion.cursor(

        dictionary=True

    )


    cursor.execute(

        """

        SELECT *

        FROM pedidos

        WHERE estado != 'Entregado'

        AND latitud IS NOT NULL

        AND longitud IS NOT NULL

        """

    )


    ubicaciones = cursor.fetchall()


    cursor.execute(

        """

        SELECT *

        FROM pedidos

        WHERE origen_ubicacion = 'No encontrada'

        """

    )


    sin_ubicacion = cursor.fetchall()


    cursor.close()

    conexion.close()


    return render_template(

        "rutas.html",

        ubicaciones=ubicaciones,

        sin_ubicacion=sin_ubicacion

    )


# =====================================================
# IA LOGÍSTICA
# =====================================================

@app.route("/ia/logistica", methods=["GET", "POST"])
def ia_logistica():

    conexion = obtener_conexion()

    cursor = conexion.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT *
            FROM pedidos
            WHERE estado != 'Entregado'
            ORDER BY fecha_entrega ASC
            """
        )

        pedidos = cursor.fetchall()

        analisis = analizar_pedidos(
            pedidos
        )

    finally:

        cursor.close()

        conexion.close()


    return render_template(

        "analisis_ia.html",

        analisis=analisis

    )


# =====================================================
# REPORTES
# =====================================================

@app.route("/reportes")
def reportes():


    conexion = obtener_conexion()

    cursor = conexion.cursor(

        dictionary=True

    )


    cursor.execute(

        """

        SELECT

            estado,

            COUNT(*) AS cantidad

        FROM pedidos

        GROUP BY estado

        """

    )


    datos = cursor.fetchall()


    cursor.close()

    conexion.close()


    return render_template(

        "reportes.html",

        datos=datos

    )


# =====================================================
# LOGOUT
# =====================================================

@app.route("/logout")
def logout():

    return redirect("/")


# =====================================================
# EJECUTAR APLICACIÓN
# =====================================================

if __name__ == "__main__":

    app.run(

        debug=True

    )
