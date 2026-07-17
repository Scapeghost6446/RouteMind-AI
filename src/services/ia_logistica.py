from math import radians, sin, cos, sqrt, atan2


def calcular_distancia(lat1, lon1, lat2, lon2):

    radio_tierra = 6371


    lat1 = radians(lat1)

    lon1 = radians(lon1)

    lat2 = radians(lat2)

    lon2 = radians(lon2)


    diferencia_latitud = lat2 - lat1

    diferencia_longitud = lon2 - lon1


    a = (

        sin(diferencia_latitud / 2) ** 2

        +

        cos(lat1)

        *

        cos(lat2)

        *

        sin(diferencia_longitud / 2) ** 2

    )


    c = 2 * atan2(

        sqrt(a),

        sqrt(1 - a)

    )


    return radio_tierra * c


def calcular_distancia(lat1, lon1, lat2, lon2):

    radio_tierra = 6371

    lat1 = radians(lat1)
    lon1 = radians(lon1)

    lat2 = radians(lat2)
    lon2 = radians(lon2)

    diferencia_latitud = lat2 - lat1
    diferencia_longitud = lon2 - lon1

    a = (

        sin(diferencia_latitud / 2) ** 2

        +

        cos(lat1)

        *

        cos(lat2)

        *

        sin(diferencia_longitud / 2) ** 2

    )

    c = 2 * atan2(

        sqrt(a),

        sqrt(1 - a)

    )

    return radio_tierra * c


def analizar_pedidos(pedidos):


    if not pedidos:


        return {

            "resumen":

            "No hay pedidos pendientes para analizar.",


            "alertas": [],


            "recomendaciones": [],


            "grupos": [],


            "distancias": [],


            "ruta": [],


            "ruta_real": [],


            "distancia_ruta": 0,


            "duracion_ruta": 0

        }


    # ==========================================

    # PEDIDOS CON COORDENADAS

    # ==========================================


    pedidos_validos = []


    for pedido in pedidos:


        latitud = pedido.get(

            "latitud"

        )


        longitud = pedido.get(

            "longitud"

        )


        if (

            latitud is not None

            and

            longitud is not None

        ):


            pedidos_validos.append(

                pedido

            )


    # ==========================================

    # CREAR RUTA BASE

    # ==========================================


    ruta = []


    for pedido in pedidos_validos:


        ruta.append({

            "id": pedido["id"],


            "cliente": pedido.get(

                "cliente",

                "Cliente no especificado"

            ),


            "direccion": pedido.get(

                "direccion",

                "Dirección no especificada"

            ),


            "estado": pedido.get(

                "estado",

                "Pendiente"

            ),


            "latitud": float(

                pedido["latitud"]

            ),


            "longitud": float(

                pedido["longitud"]

            )

        })


    # ==========================================

    # OPTIMIZAR RUTA

    # ==========================================


    resultado_ruta = obtener_ruta_osrm(

        ruta

    )


    ruta_real = resultado_ruta["ruta"]


    orden_optimizado = resultado_ruta["orden"]


    distancia_ruta = resultado_ruta["distancia"]


    duracion_ruta = resultado_ruta["duracion"]


    # ==========================================

    # REORDENAR PEDIDOS

    # ==========================================


    ruta_optimizada = []


    for indice in orden_optimizado:


        if indice < len(ruta):


            ruta_optimizada.append(

                ruta[indice]

            )


    # Si OSRM no devolvió orden

    if not ruta_optimizada:


        ruta_optimizada = ruta


    # ==========================================

    # ANÁLISIS DE PEDIDOS CERCANOS

    # ==========================================


    alertas = []


    recomendaciones = []


    grupos = []


    distancias = []


    for i in range(

        len(pedidos_validos)

    ):


        pedido_actual = pedidos_validos[i]


        grupo_actual = [

            pedido_actual

        ]


        for j in range(

            i + 1,

            len(pedidos_validos)

        ):


            pedido_comparado = pedidos_validos[j]


            distancia = calcular_distancia(


                float(

                    pedido_actual["latitud"]

                ),


                float(

                    pedido_actual["longitud"]

                ),


                float(

                    pedido_comparado["latitud"]

                ),


                float(

                    pedido_comparado["longitud"]

                )

            )


            distancias.append({

                "pedido_1":

                pedido_actual["id"],


                "pedido_2":

                pedido_comparado["id"],


                "distancia":

                round(

                    distancia,

                    2

                )

            })


            if distancia <= 1:


                grupo_actual.append(

                    pedido_comparado

                )


        if len(

            grupo_actual

        ) > 1:


            grupos.append(

                grupo_actual

            )


    # ==========================================

    # ALERTAS

    # ==========================================


    if grupos:


        alertas.append({

            "tipo": "warning",


            "titulo":

            "Pedidos cercanos detectados",


            "mensaje":

            f"Se detectaron {len(grupos)} grupo(s) de pedidos cercanos."

        })


        recomendaciones.append(

            "Agrupar pedidos cercanos para reducir desplazamientos."

        )


    else:


        recomendaciones.append(

            "No se detectaron agrupaciones cercanas importantes."

        )


    # ==========================================

    # PEDIDOS SIN UBICACIÓN

    # ==========================================


    pedidos_sin_ubicacion = (

        len(pedidos)

        -

        len(pedidos_validos)

    )


    if pedidos_sin_ubicacion > 0:


        alertas.append({

            "tipo": "danger",


            "titulo":

            "Pedidos sin ubicación",


            "mensaje":


            f"{pedidos_sin_ubicacion} pedido(s) no tienen coordenadas."

        })


        recomendaciones.append(

            "Completar las coordenadas de los pedidos."

        )


    # ==========================================

    # RECOMENDACIÓN DE RUTA

    # ==========================================


    if ruta_optimizada:


        orden_texto = " → ".join(

            f"Pedido #{pedido['id']}"

            for pedido in ruta_optimizada

        )


        recomendaciones.append(

            f"Ruta optimizada sugerida: {orden_texto}."

        )


    # ==========================================

    # RESUMEN

    # ==========================================


    resumen = (

        f"Se analizaron {len(pedidos)} pedido(s). "

        f"{len(pedidos_validos)} cuentan con ubicación. "

        f"La ruta optimizada tiene "

        f"{distancia_ruta} km "

        f"y una duración aproximada de "

        f"{duracion_ruta} minutos."

    )


    return {


        "resumen":

        resumen,


        "alertas":

        alertas,


        "recomendaciones":

        recomendaciones,


        "grupos":

        grupos,


        "distancias":

        distancias,


        "ruta":

        ruta_optimizada,


        "ruta_real":

        ruta_real,


        "distancia_ruta":

        distancia_ruta,


        "duracion_ruta":

        duracion_ruta


    }

def obtener_ruta_osrm(pedidos):


    if len(pedidos) < 2:

        return {

            "ruta": [],

            "orden": [],

            "distancia": 0,

            "duracion": 0

        }


    # ==========================================

    # CREAR COORDENADAS

    # ==========================================


    coordenadas = ";".join(

        f"{pedido['longitud']},{pedido['latitud']}"

        for pedido in pedidos

    )


    # ==========================================

    # API TRIP DE OSRM

    # ==========================================


    url = (

        "https://router.project-osrm.org/trip/v1/driving/"

        + coordenadas

    )


    parametros = {


        "source": "first",


        "roundtrip": "false",


        "overview": "full",


        "geometries": "geojson"


    }


    try:


        respuesta = requests.get(

            url,

            params=parametros,

            timeout=30

        )


        if respuesta.status_code != 200:


            print(

                "Error HTTP OSRM:",

                respuesta.status_code

            )


            return {

                "ruta": [],

                "orden": [],

                "distancia": 0,

                "duracion": 0

            }


        datos = respuesta.json()


        if datos.get("code") != "Ok":


            print(

                "Error OSRM:",

                datos

            )


            return {

                "ruta": [],

                "orden": [],

                "distancia": 0,

                "duracion": 0

            }


        # ==========================================

        # ORDEN OPTIMIZADO

        # ==========================================


        waypoints = datos.get(

            "waypoints",

            []

        )


        orden = [

            waypoint["waypoint_index"]

            for waypoint in waypoints

        ]


        # ==========================================

        # RUTA CALCULADA

        # ==========================================


        ruta = datos["trips"][0]


        coordenadas_ruta = ruta["geometry"]["coordinates"]


        ruta_leaflet = [

            [

                coordenada[1],

                coordenada[0]

            ]

            for coordenada in coordenadas_ruta

        ]


        distancia_km = round(

            ruta["distance"] / 1000,

            2

        )


        duracion_minutos = round(

            ruta["duration"] / 60

        )


        return {


            "ruta": ruta_leaflet,


            "orden": orden,


            "distancia": distancia_km,


            "duracion": duracion_minutos


        }


    except Exception as e:


        print(

            "Error obteniendo ruta optimizada:",

            e

        )


        return {


            "ruta": [],


            "orden": [],


            "distancia": 0,


            "duracion": 0

        }
