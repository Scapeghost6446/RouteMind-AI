from flask import Flask, render_template, request, redirect, url_for, flash

import pandas as pd
import requests
import os
import time
import re

from datetime import datetime, date

from pymongo import MongoClient
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
# CONEXIÓN A MONGODB
# =====================================================

MONGO_URI = os.getenv("MONGO_URI")

cliente_mongo = MongoClient(MONGO_URI)

db = cliente_mongo["routemind_db"]

coleccion_pedidos = db["pedidos"]

coleccion_historial = db["historial_estados"]


# =====================================================
# PROBAR CONEXIÓN
# =====================================================

try:

    cliente_mongo.admin.command("ping")

    print("===================================")
    print("CONEXIÓN EXITOSA A MONGODB")
    print("===================================")

except Exception as error:

    print("ERROR DE CONEXIÓN A MONGODB:")
    print(error)


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
# NORMALIZAR DIRECCIÓN
# =====================================================

def normalizar_direccion(direccion):

    direccion = direccion.upper().strip()

    reemplazos = {

        "AND ": "ANDADOR ",
        "MZ ": "MANZANA ",
        "LT ": "LOTE ",
        "COL ": "COLONIA ",
        "GRO": "GUERRERO ",
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

    codigo_postal = re.search(

        r"\b\d{5}\b",

        direccion_mayusculas

    )

    if codigo_postal:

        datos["codigo_postal"] = (

            codigo_postal.group()

        )

    colonia = re.search(

        r"(?:COL|COLONIA)\s+([^,]+)",

        direccion_mayusculas

    )

    if colonia:

        datos["colonia"] = (

            colonia.group(1).strip()

        )

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

    return ", ".join(partes)


# =====================================================
# OBTENER COORDENADAS
# =====================================================

def obtener_coordenadas(direccion):

    try:

        geolocator = Nominatim(

            user_agent="RouteMindAI"

        )

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

        print(error)

        return (

            None,

            None,

            "No encontrada"

        )


# =====================================================
# BUSCAR UBICACIÓN
# =====================================================

@app.route("/buscar-ubicacion")
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

            "Se encontró una ubicación aproximada. "

            "Verifica el punto en el mapa."

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

    total_pedidos = (

        coleccion_pedidos.count_documents({})

    )

    pendientes = (

        coleccion_pedidos.count_documents({

            "estado": "Pendiente"

        })

    )

    en_ruta = (

        coleccion_pedidos.count_documents({

            "estado": "En ruta"

        })

    )

    entregados = (

        coleccion_pedidos.count_documents({

            "estado": "Entregado"

        })

    )

    sin_ubicacion = (

        coleccion_pedidos.count_documents({

            "origen_ubicacion": "No encontrada"

        })

    )

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

    pedidos = list(

        coleccion_pedidos.find(

            {}

        ).sort(

            "id",

            -1

        )

    )

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

    ultimo_pedido = (

        coleccion_pedidos.find_one(

            sort=[

                ("id", -1)

            ]

        )

    )

    if ultimo_pedido:

        nuevo_id = (

            ultimo_pedido.get(

                "id",

                0

            )

            + 1

        )

    else:

        nuevo_id = 1

    pedido = {

        "id": nuevo_id,

        "cliente": cliente,

        "direccion": direccion,

        "producto": producto,

        "fecha_entrega": fecha_entrega,

        "prioridad": prioridad or "Media",

        "estado": "Pendiente",

        "latitud": latitud,

        "longitud": longitud,

        "origen_ubicacion": origen_ubicacion,

        "fecha_registro": datetime.now()

    }

    try:

        coleccion_pedidos.insert_one(

            pedido

        )

        flash(

            "Pedido registrado correctamente.",

            "success"

        )

    except Exception as error:

        print(

            "Error al registrar el pedido:",

            error

        )

        flash(

            f"Error al registrar el pedido: {error}",

            "danger"

        )

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

        ultimo_pedido = (

            coleccion_pedidos.find_one(

                sort=[

                    ("id", -1)

                ]

            )

        )

        siguiente_id = (

            ultimo_pedido.get(

                "id",

                0

            )

            + 1

            if ultimo_pedido

            else 1

        )

        pedidos_insertar = []

        for _, fila in df.iterrows():

            latitud, longitud, origen = (

                obtener_coordenadas(

                    str(

                        fila["direccion"]

                    )

                )

            )

            pedido = {

                "id": siguiente_id,

                "cliente": str(

                    fila["cliente"]

                ),

                "direccion": str(

                    fila["direccion"]

                ),

                "producto": str(

                    fila["producto"]

                ),

                "fecha_entrega": str(

                    fila["fecha_entrega"]

                ),

                "prioridad": str(

                    fila["prioridad"]

                ),

                "estado": "Pendiente",

                "latitud": latitud,

                "longitud": longitud,

                "origen_ubicacion": origen,

                "fecha_registro": datetime.now()

            }

            pedidos_insertar.append(

                pedido

            )

            siguiente_id += 1

        if pedidos_insertar:

            coleccion_pedidos.insert_many(

                pedidos_insertar

            )

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

        ultimo_pedido = (

            coleccion_pedidos.find_one(

                sort=[

                    ("id", -1)

                ]

            )

        )

        siguiente_id = (

            ultimo_pedido.get(

                "id",

                0

            )

            + 1

            if ultimo_pedido

            else 1

        )

        pedidos_insertar = []

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

            pedido = {

                "id": siguiente_id,

                "cliente": usuario["name"],

                "direccion": direccion,

                "producto": "Paquete de prueba",

                "fecha_entrega": date.today().isoformat(),

                "prioridad": "Media",

                "estado": "Pendiente",

                "latitud": latitud,

                "longitud": longitud,

                "origen_ubicacion": origen,

                "fecha_registro": datetime.now()

            }

            pedidos_insertar.append(

                pedido

            )

            siguiente_id += 1

        coleccion_pedidos.insert_many(

            pedidos_insertar

        )

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

    pedido = coleccion_pedidos.find_one(

        {

            "id": pedido_id

        }

    )

    if not pedido:

        flash(

            "Pedido no encontrado."

        )

        return redirect(

            "/pedidos"

        )

    estado_anterior = pedido.get(

        "estado"

    )

    if nuevo_estado not in transiciones.get(

        estado_anterior,

        []

    ):

        flash(

            "Transición de estado no permitida."

        )

        return redirect(

            "/pedidos"

        )

    coleccion_pedidos.update_one(

        {

            "id": pedido_id

        },

        {

            "$set": {

                "estado": nuevo_estado

            }

        }

    )

    historial = {

        "pedido_id": pedido_id,

        "estado_anterior": estado_anterior,

        "estado_nuevo": nuevo_estado,

        "fecha_cambio": datetime.now()

    }

    coleccion_historial.insert_one(

        historial

    )

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

    ubicaciones = []

    sin_ubicacion = []


    # ==========================================
    # PEDIDOS CON UBICACIÓN
    # ==========================================

    pedidos_con_ubicacion = coleccion_pedidos.find({

        "estado": {

            "$ne": "Entregado"

        },

        "latitud": {

            "$ne": None

        },

        "longitud": {

            "$ne": None

        }

    })


    for pedido in pedidos_con_ubicacion:

        pedido["id"] = str(

            pedido["_id"]

        )


        del pedido["_id"]


        ubicaciones.append(

            pedido

        )


    # ==========================================
    # PEDIDOS SIN UBICACIÓN
    # ==========================================

    pedidos_sin_ubicacion = coleccion_pedidos.find({

        "$or": [

            {

                "latitud": None

            },

            {

                "longitud": None

            },

            {

                "origen_ubicacion":

                "No encontrada"

            }

        ]

    })


    for pedido in pedidos_sin_ubicacion:

        pedido["id"] = str(

            pedido["_id"]

        )


        del pedido["_id"]


        sin_ubicacion.append(

            pedido

        )


    return render_template(

        "rutas.html",

        ubicaciones=ubicaciones,

        sin_ubicacion=sin_ubicacion

    )


# =====================================================
# IA LOGÍSTICA
# =====================================================

@app.route(

    "/ia/logistica",

    methods=["GET", "POST"]

)
def ia_logistica():

    pedidos = list(

        coleccion_pedidos.find({

            "estado": {

                "$ne": "Entregado"

            }

        })

    )

    pedidos.sort(

        key=lambda pedido:

        str(

            pedido.get(

                "fecha_entrega",

                ""

            )

        )

    )

    analisis = analizar_pedidos(

        pedidos

    )

    return render_template(

        "analisis_ia.html",

        analisis=analisis

    )


# =====================================================
# REPORTES
# =====================================================

@app.route("/reportes")
def reportes():

    datos = list(

        coleccion_pedidos.aggregate([

            {

                "$group": {

                    "_id": "$estado",

                    "cantidad": {

                        "$sum": 1

                    }

                }

            },

            {

                "$project": {

                    "_id": 0,

                    "estado": "$_id",

                    "cantidad": 1

                }

            }

        ])

    )

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