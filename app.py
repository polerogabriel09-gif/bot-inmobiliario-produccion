from flask import Flask, request, Response, redirect, url_for, render_template_string, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import requests
import os
import base64
import tempfile
from threading import Thread, Lock
import time
import re
import json
from datetime import datetime
from zoneinfo import ZoneInfo

try:
    from pywebpush import webpush, WebPushException
except ImportError:
    webpush = None
    WebPushException = Exception

try:
    import psycopg2
except ImportError:
    psycopg2 = None

try:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
except Exception:
    ec = None
    serialization = None


# ============================================================
# CONFIGURACION
# ============================================================

load_dotenv()

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# PostgreSQL persistente para conservar las suscripciones Push
# aunque Render se duerma, reinicie o haga deploy.
DATABASE_URL = os.getenv("DATABASE_URL")

# ============================================================
# NTFY - NOTIFICACIONES NATIVAS EN ANDROID
# ============================================================
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "").strip()
NTFY_SERVER = os.getenv("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
CRM_PUBLIC_URL = os.getenv(
    "CRM_PUBLIC_URL",
    "https://bot-inmobiliario-produccion.onrender.com/crm"
).rstrip("/")

# Acceso al CRM. Config├║ralos en Render > Environment.
CRM_USER = os.getenv("CRM_USER", "gabriel")
CRM_PASSWORD = os.getenv("CRM_PASSWORD")

# Web Push para notificaciones reales en computadora y tel├®fono.
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.getenv("VAPID_SUBJECT", "mailto:gabriel@example.com")

client = OpenAI(api_key=OPENAI_API_KEY)


# ============================================================
# IMAGENES POR PROYECTO
# ============================================================

IMAGENES_PROYECTOS = {
    "palmeras": [
        "media/palmeras/palmeras_1.jpeg",
        "media/palmeras/palmeras_2.jpeg",
        "media/palmeras/palmeras_3.jpeg",
        "media/palmeras/palmeras_4.jpeg",
        "media/palmeras/palmeras_5.jpeg",
        "media/palmeras/palmeras_6.jpeg",
    ],
    "buenaventura": [
        "media/buenaventura/buenaventura_1.jpeg",
        "media/buenaventura/buenaventura_2.jpeg",
        "media/buenaventura/buenaventura_3.jpeg",
        "media/buenaventura/buenaventura_4.jpeg",
        "media/buenaventura/buenaventura_5.jpeg",
        "media/buenaventura/buenaventura_6.jpeg",
        "media/buenaventura/buenaventura_7.jpeg",
        "media/buenaventura/buenaventura_8.jpeg",
        "media/buenaventura/buenaventura_9.jpeg",
    ],
    # Vista Hermosa: no enviar fotos generales autom├íticamente.
    # A solicitud de fotos o videos se enviar├ín ├║nicamente sus videos,
    # porque las fotos anteriores ya no se quieren mostrar a clientes.
    "vista_hermosa": []
}


VIDEOS_PROYECTOS = {
    "palmeras": [
        "media/videos/palmeras/palmeras_video_1.mp4",
        "media/videos/palmeras/palmeras_video_2.mp4",
        "media/videos/palmeras/palmeras_video_3.mp4",
    ],
    "vista_hermosa": [
        "media/videos/vista_hermosa/vista_video_1.mp4",
        "media/videos/vista_hermosa/vista_video_2.mp4",
        "media/videos/vista_hermosa/vista_video_3.mp4",
    ],
    "buenaventura": [
        "media/videos/buenaventura/buenaventura_video_1.mp4",
        "media/videos/buenaventura/buenaventura_video_2.mp4",
        "media/videos/buenaventura/buenaventura_video_3.mp4",
        "media/videos/buenaventura/buenaventura_video_4.mp4",
    ],
}

VIDEOS_GENERALES = [
    "media/videos/general/amenidades_1.mp4",
    "media/videos/general/amenidades_2.mp4",
    "media/videos/general/amenidades_3.mp4",
    "media/videos/general/amenidades_4.mp4",
    "media/videos/general/amenidades_5.mp4",
]


# ============================================================
# COTIZACIONES EN IMAGEN POR PROYECTO
# ============================================================

COTIZACIONES_IMAGEN = {
    "palmeras": {
        "8x16": [
            "media/cotizaciones/palmeras/8x16_no_esquina.jpeg",
            "media/cotizaciones/palmeras/8x16_segunda_fase.jpeg",
        ],
        "8x18": [
            "media/cotizaciones/palmeras/8x18_primera_fase.jpeg",
            "media/cotizaciones/palmeras/8x18_segunda_fase.jpeg",
        ],
    },
    "vista_hermosa": {
        "8x16": [
            "media/cotizaciones/vista_hermosa/8x16_fase_f.jpeg",
            "media/cotizaciones/vista_hermosa/8x16_fase_g.jpeg",
        ],
    },
    "buenaventura": {
        "8x16": [
            "media/cotizaciones/buenaventura/8x16.jpeg",
        ],
        "8x18": [
            "media/cotizaciones/buenaventura/8x18.jpeg",
        ],
        "9x20": [
            "media/cotizaciones/buenaventura/9x20.jpeg",
        ],
    },
}


ETIQUETAS_COTIZACIONES = {
    "palmeras": {
        "media/cotizaciones/palmeras/8x16_no_esquina.jpeg":
            "Palmeras San Miguel - 8x16 - Fase 1 / no esquina",
        "media/cotizaciones/palmeras/8x16_segunda_fase.jpeg":
            "Palmeras San Miguel - 8x16 - Fase 2",
        "media/cotizaciones/palmeras/8x18_primera_fase.jpeg":
            "Palmeras San Miguel - 8x18 - Fase 1",
        "media/cotizaciones/palmeras/8x18_segunda_fase.jpeg":
            "Palmeras San Miguel - 8x18 - Fase 2",
    },
    "vista_hermosa": {
        "media/cotizaciones/vista_hermosa/8x16_fase_f.jpeg":
            "Vista Hermosa - 8x16 - Fase F",
        "media/cotizaciones/vista_hermosa/8x16_fase_g.jpeg":
            "Vista Hermosa - 8x16 - Fase G",
    },
    "buenaventura": {
        "media/cotizaciones/buenaventura/8x16.jpeg":
            "Buenaventura Cuyotenango - 8x16",
        "media/cotizaciones/buenaventura/8x18.jpeg":
            "Buenaventura Cuyotenango - 8x18",
        "media/cotizaciones/buenaventura/9x20.jpeg":
            "Buenaventura Cuyotenango - 9x20",
    },
}


RESUMENES_COTIZACION = {
    "palmeras": {
        "nombre": "Palmeras San Miguel",
        "descripcion": (
            "Palmeras San Miguel est├í ubicado en Zona 5 de Retalhuleu, "
            "camino a La Verde / carretera hacia Las Pilas ­ƒôì­ƒÅí"
        ),
        "amenidades": (
            "Casa club, piscinas, ├íreas verdes y caminamientos ­ƒÅè­ƒî│"
        ),
        "servicios": (
            "Calles pavimentadas, agua potable, energ├¡a el├®ctrica y "
            "drenajes con planta de tratamiento Ô£à"
        ),
        "cierre": (
            "Te comparto abajo las cotizaciones disponibles con medidas, "
            "fases, enganches y cuotas ­ƒæç­ƒÆ░"
        )
    },

    "vista_hermosa": {
        "nombre": "Vista Hermosa",
        "descripcion": (
            "Vista Hermosa est├í sobre la CA-2, km 188, Retalhuleu, "
            "aproximadamente a 15 minutos del IRTRA ­ƒôì­ƒÅí"
        ),
        "amenidades": (
            "Casa club, piscinas, ├íreas verdes, juegos para ni├▒os y caminamientos ­ƒÅè­ƒî│"
        ),
        "servicios": (
            "Garita, muro perimetral, calles pavimentadas, agua potable, "
            "energ├¡a el├®ctrica y drenajes con planta de tratamiento Ô£à"
        ),
        "cierre": (
            "Te comparto abajo las cotizaciones disponibles con sus fases, "
            "enganche y planes de pago ­ƒæç­ƒÆ░"
        )
    },

    "buenaventura": {
        "nombre": "Buenaventura Cuyotenango",
        "descripcion": (
            "Buenaventura est├í en el km 168 de la carretera hacia la playa "
            "de Tulate, Cuyotenango ­ƒôì­ƒÅí"
        ),
        "amenidades": (
            "Casa club, piscinas, ├íreas verdes, juegos para ni├▒os y caminamientos ­ƒÅè­ƒî│"
        ),
        "servicios": (
            "Garita, muro perimetral, calles pavimentadas, agua potable, "
            "energ├¡a el├®ctrica y drenajes con planta de tratamiento Ô£à"
        ),
        "cierre": (
            "Te comparto abajo las cotizaciones disponibles de todas las "
            "medidas con enganches y cuotas ­ƒæç­ƒÆ░"
        )
    }
}


def construir_resumen_cotizacion(proyecto):
    """
    Mensaje breve antes de enviar las im├ígenes.
    NO escribe precios ni cuotas porque esa informaci├│n va en las
    im├ígenes de cotizaci├│n.
    """
    datos = RESUMENES_COTIZACION.get(proyecto)

    if not datos:
        return None

    return (
        f"┬íClaro! ­ƒÿè Te comparto la informaci├│n de {datos['nombre']}:\n\n"
        f"{datos['descripcion']}\n\n"
        f"­ƒÅè­ƒî│ Amenidades: {datos['amenidades']}\n"
        f"Ô£à Servicios: {datos['servicios']}\n\n"
        f"{datos['cierre']}"
    )


def pide_cotizacion(texto):
    """
    Cualquier pregunta relacionada con precio/cuotas/cotizaci├│n
    dispara inmediatamente el env├¡o de TODAS las im├ígenes de
    cotizaci├│n del proyecto activo.
    """
    t = texto.lower()

    palabras = [
        "precio", "precios",
        "cuanto cuesta", "cu├ínto cuesta",
        "cuanto cuestan", "cu├ínto cuestan",
        "cuanto vale", "cu├ínto vale",
        "cuanto salen", "cu├ínto salen",
        "valor", "costo", "costos",
        "cotizacion", "cotizaci├│n", "cotizaciones",
        "cuota", "cuotas", "mensualidad", "mensualidades",
        "plan de pago", "plan de pagos",
        "financiamiento", "financiado",

        # Si el cliente pide informaci├│n general de un proyecto,
        # tratamos la intenci├│n como solicitud de informaci├│n comercial completa:
        # resumen del proyecto + cotizaciones.
        "informacion", "informaci├│n",
        "quiero informacion", "quiero informaci├│n",
        "dame informacion", "dame informaci├│n",
        "me da informacion", "me da informaci├│n",
        "info de", "informaci├│n de", "informacion de"
    ]

    return any(p in t for p in palabras)




# ============================================================
# CONSULTA ESPECIFICA DE CUOTA POR PLAZO
# ============================================================

CUOTAS_POR_PROYECTO = {
    "vista_hermosa": {
        "8x16 Fase F": {
            1: 7041, 2: 3817, 3: 2752, 4: 2228,
            5: 1919, 6: 1717, 7: 1578, 8: 1476
        },
        "8x16 Fase G": {
            1: 7625, 2: 4133, 3: 2981, 4: 2412,
            5: 2078, 6: 1860, 7: 1708, 8: 1599
        },
    },
    "buenaventura": {
        "8x16": {
            1: 7040.85, 2: 3817.44, 3: 2751.59, 4: 2227.92,
            5: 1918.90, 6: 1717.20, 7: 1578.42, 8: 1476.64
        },
        "8x18": {
            1: 7806.95, 2: 4232.81, 3: 3050.99, 4: 2470.34,
            5: 2127.69, 6: 1904.05, 7: 1750.16, 8: 1637.32
        },
        "9x20": {
            1: 9758.69, 2: 5291.01, 3: 3813.73, 4: 3087.92,
            5: 2659.61, 6: 2380.06, 7: 2187.70, 8: 2046.64
        },
    },
    "palmeras": {
        "8x16 Fase 1": {
            1: 5581.61, 2: 3026.26, 3: 2181.31, 4: 1766.17,
            5: 1521.20, 6: 1361.30, 7: 1251.28, 8: 1170.60
        },
        "8x16 Fase 2": {
            1: 5873.45, 2: 3184.50, 3: 2295.37, 4: 1858.52,
            5: 1600.74, 6: 1432.48, 7: 1316.71, 8: 1231.81
        },
        "8x18 Fase 1": {
            1: 6165.30, 2: 3342.73, 3: 2409.42, 4: 1950.87,
            5: 1680.28, 6: 1503.66, 7: 1382.14, 8: 1293.02
        },
        "8x18 Fase 2": {
            1: 6493.63, 2: 3520.75, 3: 2537.74, 4: 2054.77,
            5: 1769.76, 6: 1583.74, 7: 1455.74, 8: 1361.88
        },
    },
}


def extraer_plazo_cuota(texto):
    t = texto.lower()

    # A├▒os
    m = re.search(r"\b([1-8])\s*a├▒os?\b", t)
    if not m:
        m = re.search(r"\b([1-8])\s*anos?\b", t)
    if m:
        return int(m.group(1))

    # Meses equivalentes
    equivalencias = {
        12: 1, 24: 2, 36: 3, 48: 4,
        60: 5, 72: 6, 84: 7, 96: 8
    }
    m = re.search(r"\b(12|24|36|48|60|72|84|96)\s*meses\b", t)
    if m:
        return equivalencias[int(m.group(1))]

    return None


def pregunta_cuota_especifica(texto):
    t = texto.lower()

    palabras_cuota = [
        "cuota", "cuotas", "mensualidad", "mensualidades",
        "cuanto pago", "cu├ínto pago",
        "cuanto queda", "cu├ínto queda",
        "cuanto seria", "cu├ínto ser├¡a"
    ]

    return (
        any(p in t for p in palabras_cuota)
        and extraer_plazo_cuota(texto) is not None
    )


def formatear_quetzales(valor):
    if isinstance(valor, int):
        return f"Q{valor:,.0f}"

    return f"Q{valor:,.2f}"


def respuesta_cuota_especifica(proyecto, texto):
    plazo = extraer_plazo_cuota(texto)

    if not proyecto or not plazo:
        return None

    opciones = CUOTAS_POR_PROYECTO.get(proyecto, {})

    if not opciones:
        return None

    nombres = {
        "palmeras": "Palmeras San Miguel",
        "vista_hermosa": "Vista Hermosa",
        "buenaventura": "Buenaventura Cuyotenango"
    }

    nombre = nombres.get(proyecto, "el proyecto")

    lineas = []
    for opcion, tabla in opciones.items():
        valor = tabla.get(plazo)
        if valor is not None:
            lineas.append(
                f"ÔÇó {opcion}: {formatear_quetzales(valor)} al mes"
            )

    if not lineas:
        return None

    if len(lineas) == 1:
        detalle = lineas[0].replace("ÔÇó ", "")
        return (
            f"En {nombre}, la cuota a {plazo} "
            f"{'a├▒o' if plazo == 1 else 'a├▒os'} es de {detalle} ­ƒÿè­ƒÆ│. "
            "El financiamiento es propio y directo con la empresa."
        )

    return (
        f"En {nombre}, estas son las cuotas a {plazo} "
        f"{'a├▒o' if plazo == 1 else 'a├▒os'} ­ƒÿè­ƒÆ│:\n\n"
        + "\n".join(lineas)
        + "\n\nEl financiamiento es propio y directo con la empresa."
    )


def pregunta_por_plazo_de_financiamiento(texto):
    """
    Si el cliente menciona un plazo de financiamiento, enviamos de inmediato
    las im├ígenes de cotizaci├│n del proyecto activo.

    Ejemplos:
    - "┬┐Y a 2 a├▒os?"
    - "┬┐Cu├ínto queda a 6 a├▒os?"
    - "Quiero el de 8 a├▒os"
    - "┬┐A 24 meses cu├ínto pago?"
    """
    t = texto.lower().strip()

    # A├▒os permitidos en los planes actuales.
    patrones_anos = [
        r"\b1\s*a├▒o\b", r"\b1\s*ano\b",
        r"\b2\s*a├▒os\b", r"\b2\s*anos\b",
        r"\b3\s*a├▒os\b", r"\b3\s*anos\b",
        r"\b4\s*a├▒os\b", r"\b4\s*anos\b",
        r"\b5\s*a├▒os\b", r"\b5\s*anos\b",
        r"\b6\s*a├▒os\b", r"\b6\s*anos\b",
        r"\b7\s*a├▒os\b", r"\b7\s*anos\b",
        r"\b8\s*a├▒os\b", r"\b8\s*anos\b",
    ]

    # Equivalentes comunes en meses.
    patrones_meses = [
        r"\b12\s*meses\b",
        r"\b24\s*meses\b",
        r"\b36\s*meses\b",
        r"\b48\s*meses\b",
        r"\b60\s*meses\b",
        r"\b72\s*meses\b",
        r"\b84\s*meses\b",
        r"\b96\s*meses\b",
    ]

    return any(
        re.search(patron, t)
        for patron in patrones_anos + patrones_meses
    )


def confirmacion_cotizacion(texto):
    """
    Detecta respuestas cortas que normalmente vienen despu├®s de que el bot
    ofreci├│ enviar cotizaci├│n o plan de pagos.
    """
    t = texto.lower().strip()

    frases = [
        "si", "s├¡", "si porfa", "s├¡ porfa", "si por favor", "s├¡ por favor",
        "dale", "de una", "mandala", "m├índala", "mandamela", "m├índamela",
        "enviala", "env├¡ala", "quiero verla", "quiero la cotizacion",
        "quiero la cotizaci├│n", "quiero cotizacion", "quiero cotizaci├│n",
        "la cotizacion", "la cotizaci├│n",
        "el de 8", "a 8", "8 a├▒os", "8 anos",
        "el de 7", "7 a├▒os", "7 anos",
        "el de 6", "6 a├▒os", "6 anos",
        "el de 5", "5 a├▒os", "5 anos",
        "el de 4", "4 a├▒os", "4 anos",
        "el de 3", "3 a├▒os", "3 anos",
        "el de 2", "2 a├▒os", "2 anos",
        "el de 1", "1 a├▒o", "1 ano"
    ]

    return any(f == t or f in t for f in frases)


def historial_ofrecio_cotizacion(numero):
    """
    Revisa si en los ├║ltimos mensajes del bot se habl├│ de cotizaci├│n,
    plan de pago o financiamiento. Si el cliente responde 's├¡', 'el de 8',
    etc., enviamos directamente la cotizaci├│n.
    """
    historial = obtener_historial(numero)

    ultimos = historial[-6:]

    texto_asistente = " ".join(
        item.get("content", "").lower()
        for item in ultimos
        if item.get("role") == "assistant"
    )

    claves = [
        "cotizacion", "cotizaci├│n",
        "plan de pago", "planes de pago",
        "financiamiento",
        "opciones a 8 a├▒os", "hasta 8 a├▒os",
        "te preparo opciones", "te env├¡o las cotizaciones",
        "te envio las cotizaciones"
    ]

    return any(c in texto_asistente for c in claves)


def debe_enviar_cotizacion_directa(numero, texto):
    """
    Env├¡a cotizaci├│n inmediatamente cuando:
    - el cliente pide precio/cuota/cotizaci├│n;
    - menciona directamente un plazo (ej. 2 a├▒os, 6 a├▒os, 24 meses);
    - confirma una cotizaci├│n ofrecida anteriormente.
    """
    if pide_cotizacion(texto):
        return True

    if pregunta_por_plazo_de_financiamiento(texto):
        return True

    if confirmacion_cotizacion(texto) and historial_ofrecio_cotizacion(numero):
        return True

    return False


def detectar_medida_en_texto(texto):
    t = texto.lower().replace(" ", "")

    if "9x20" in t or "9├ù20" in t:
        return "9x20"

    if "8x18" in t or "8├ù18" in t:
        return "8x18"

    if "8x16" in t or "8├ù16" in t:
        return "8x16"

    return None


# ============================================================
# PRECIOS Y ENGANCHES EXACTOS POR MEDIDA / FASE
# ============================================================

DATOS_MEDIDAS = {
    "palmeras": {
        "nombre": "Palmeras San Miguel",
        "medidas": {
            "8x16": {"precio": "Q67,200", "enganche": "Q6,000"},
            "8x18": {"precio": "Q79,200", "enganche": "Q8,000"},
        },
    },
    "buenaventura": {
        "nombre": "Buenaventura Cuyotenango",
        "medidas": {
            "8x16": {"precio": "desde Q83,200", "enganche": "Q6,000"},
            "8x18": {"precio": "Q93,600", "enganche": "Q8,000"},
            "9x20": {"precio": "Q117,000", "enganche": "Q10,000"},
        },
    },
    "vista_hermosa": {
        "nombre": "Ciudad Vista Hermosa",
        "medidas": {
            "8x16": {
                "fases": {
                    "F": {"precio": "Q83,200", "enganche": "Q6,000"},
                    "G": {"precio": "Q89,600", "enganche": "Q6,000"},
                }
            },
        },
    },
}

def detectar_fase_en_texto(texto):
    t = texto.lower().replace("-", " ")
    if re.search(r"\bfase\s*f\b", t) or re.search(r"\bf\b", t):
        return "F"
    if re.search(r"\bfase\s*g\b", t) or re.search(r"\bg\b", t):
        return "G"
    return None

def pregunta_medidas_disponibles(texto):
    t = texto.lower()
    frases = [
        "que medidas", "qu├® medidas", "cuales medidas", "cu├íles medidas",
        "medidas tienen", "medidas tiene", "medidas disponibles",
        "que tama├▒os", "qu├® tama├▒os", "tama├▒os disponibles",
        "de que medidas", "de qu├® medidas"
    ]
    return any(f in t for f in frases)

def respuesta_medidas_disponibles(proyecto):
    if proyecto == "palmeras":
        return "En Palmeras San Miguel tenemos lotes de 8x16 y 8x18 ­ƒÿè­ƒÅí"
    if proyecto == "buenaventura":
        return "En Buenaventura Cuyotenango tenemos lotes de 8x16, 8x18 y 9x20 ­ƒÿè­ƒÅí"
    if proyecto == "vista_hermosa":
        return "En Ciudad Vista Hermosa tenemos lotes de 8x16 en Fase F y Fase G ­ƒÿè­ƒÅí"
    return None

def respuesta_medida_especifica(proyecto, medida, texto=""):
    datos_proyecto = DATOS_MEDIDAS.get(proyecto)
    if not datos_proyecto or medida not in datos_proyecto.get("medidas", {}):
        return None

    nombre = datos_proyecto["nombre"]
    datos = datos_proyecto["medidas"][medida]

    if "fases" in datos:
        fase = detectar_fase_en_texto(texto)
        if fase and fase in datos["fases"]:
            d = datos["fases"][fase]
            return (
                f"S├¡ ­ƒÿè En {nombre}, el lote de {medida} en Fase {fase} tiene un precio de "
                f"{d['precio']} y un enganche de {d['enganche']} ­ƒÆ░­ƒÅí. "
                "El enganche tambi├®n se puede fraccionar en 2 pagos mensuales."
            )
        f = datos["fases"]["F"]
        g = datos["fases"]["G"]
        return (
            f"S├¡ ­ƒÿè En {nombre} tenemos lotes de {medida} en dos fases:\n\n"
            f"ÔÇó Fase F: {f['precio']} ÔÇö enganche {f['enganche']}\n"
            f"ÔÇó Fase G: {g['precio']} ÔÇö enganche {g['enganche']}\n\n"
            "El enganche se puede fraccionar en 2 pagos mensuales. ­ƒÆ░­ƒÅí"
        )

    return (
        f"S├¡ ­ƒÿè En {nombre}, el lote de {medida} tiene un precio de {datos['precio']} "
        f"y un enganche de {datos['enganche']} ­ƒÆ░­ƒÅí. "
        "El enganche se puede fraccionar en 2 pagos mensuales."
    )

def obtener_enganche_exacto(proyecto, texto):
    medida = detectar_medida_en_texto(texto)
    if not medida:
        return None
    datos_proyecto = DATOS_MEDIDAS.get(proyecto, {})
    datos = datos_proyecto.get("medidas", {}).get(medida)
    if not datos:
        return None
    if "fases" in datos:
        fase = detectar_fase_en_texto(texto)
        if fase and fase in datos["fases"]:
            return datos["fases"][fase]["enganche"]
        # En Vista Hermosa ambas fases tienen el mismo enganche cargado.
        valores = {x["enganche"] for x in datos["fases"].values()}
        if len(valores) == 1:
            return next(iter(valores))
        return None
    return datos.get("enganche")

# ============================================================
# IDENTIFICACION DEL PROYECTO DESDE ANUNCIOS DE META / CLICK-TO-WHATSAPP
# ============================================================

ANUNCIOS_META_PROYECTO = {
    # Buenaventura Cuyotenango
    "120248129659680634": "buenaventura",  # AD VID - 01 - BNV CUYO
    "120248129290310634": "buenaventura",  # AD IMG - 01 - BNV CUYO

    # Palmeras San Miguel
    "120248129867550634": "palmeras",  # AD VID - 01 - PSM
    "120248129884270634": "palmeras",  # AD VID - 02 - PSM
    "120248129845750634": "palmeras",  # AD IMG - 01 - PSM
    "120248129863630634": "palmeras",  # AD IMG - 02 - PSM

    # Vista Hermosa
    "120248129777940634": "vista_hermosa",  # AD VID - 01 - VTH
    "120248129694970634": "vista_hermosa",  # AD IMG - 01 - VTH
    "120248129773580634": "vista_hermosa",  # AD IMG - 02 - VTH
}

def proyecto_desde_referencia_anuncio(mensaje):
    """Detecta el proyecto cuando WhatsApp incluye referral.source_id del anuncio."""
    referral = (mensaje or {}).get("referral") or {}
    source_id = str(referral.get("source_id") or "").strip()
    if not source_id:
        return None
    proyecto = ANUNCIOS_META_PROYECTO.get(source_id)
    if proyecto:
        print(f"ANUNCIO META DETECTADO: {source_id} -> {proyecto}")
    else:
        print(f"ANUNCIO META SIN MAPEAR: {source_id}")
    return proyecto

def fijar_proyecto_desde_anuncio(numero, mensaje):
    proyecto = proyecto_desde_referencia_anuncio(mensaje)
    if not proyecto:
        return None
    estado = obtener_estado_conversacion(numero)
    estado["proyecto_actual"] = proyecto
    proyecto_activo[numero] = proyecto
    persistir_cliente(numero)
    return proyecto

# Guarda qu├® proyecto est├í activo para cada n├║mero.
proyecto_activo = {}

# Guarda el ultimo tema sensible de cada cliente para entender seguimientos
# como "┬┐cu├ínto es de cada uno?" sin perder el contexto.
ultima_intencion = {}


# ============================================================
# PROTECCION CONTRA MENSAJES DUPLICADOS / REINTENTOS DE META
# ============================================================

mensajes_procesados = set()

procesamiento_actual = {}
lock_procesamiento = Lock()


def iniciar_procesamiento(numero, message_id):
    """
    Registra cu├íl es el mensaje m├ís reciente que estamos procesando
    para este n├║mero. Cualquier proceso viejo queda invalidado.
    """
    with lock_procesamiento:
        procesamiento_actual[numero] = message_id


def procesamiento_sigue_vigente(numero, message_id):
    """
    Devuelve True solo si este message_id sigue siendo el m├ís reciente
    para ese cliente.
    """
    with lock_procesamiento:
        return procesamiento_actual.get(numero) == message_id
lock_mensajes = Lock()
MAX_MENSAJES_PROCESADOS = 5000


def marcar_mensaje_como_procesado(message_id):
    """
    Meta puede reenviar el MISMO webhook si nuestra respuesta tarda.
    Esta funci├│n evita procesar dos veces el mismo mensaje de WhatsApp.
    """
    if not message_id:
        return True

    with lock_mensajes:
        if message_id in mensajes_procesados:
            return False

        mensajes_procesados.add(message_id)

        # Evitamos crecimiento infinito en RAM.
        if len(mensajes_procesados) > MAX_MENSAJES_PROCESADOS:
            mensajes_procesados.clear()
            mensajes_procesados.add(message_id)

    return True

# Estado persistente en memoria RAM por n├║mero.
# El proyecto se mantiene fijo hasta que el cliente mencione otro expl├¡citamente.
estado_conversacion = {}

# N├║meros a los que Gabriel ya se present├│ durante esta ejecuci├│n.
# La presentaci├│n se env├¡a SOLO una vez al inicio de la conversaci├│n/sesi├│n.
clientes_presentados = set()


def necesita_presentacion_inicial(numero):
    return numero not in clientes_presentados


def marcar_cliente_presentado(numero):
    clientes_presentados.add(numero)
    persistir_cliente(numero)


def mensaje_presentacion_inicial():
    return "┬íHola! ­ƒæï Soy Gabriel Polero. ­ƒÿè ┬┐En qu├® le podemos servir?"


def es_solo_saludo(texto):
    """
    Devuelve True ├║nicamente cuando el mensaje del cliente es un saludo simple.
    Ejemplos: "hola", "buenas", "buenos d├¡as", "hola buenas noches".

    Si el saludo trae una consulta ("hola, precios de Buenaventura"),
    devuelve False para que el bot se presente y luego responda la pregunta.
    """
    if not texto:
        return False

    t = texto.lower().strip()

    # Quitamos signos y emojis, pero conservamos letras/n├║meros/espacios.
    t = re.sub(r"[^a-z├í├®├¡├│├║├╝├▒0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    saludos_simples = {
        "hola",
        "holaaa",
        "buenas",
        "buen d├¡a",
        "buen dia",
        "buenos d├¡as",
        "buenos dias",
        "buenas tardes",
        "buenas noches",
        "qu├® tal",
        "que tal",
        "hola buenas",
        "hola buen d├¡a",
        "hola buen dia",
        "hola buenos d├¡as",
        "hola buenos dias",
        "hola buenas tardes",
        "hola buenas noches",
    }

    return t in saludos_simples


def enviar_presentacion_si_corresponde(numero, message_id=None):
    """
    Env├¡a una presentaci├│n breve antes de cualquier otra respuesta.
    Se ejecuta una sola vez por cliente durante la sesi├│n actual del bot.
    """
    if not necesita_presentacion_inicial(numero):
        return False

    if message_id is not None and not procesamiento_sigue_vigente(numero, message_id):
        return False

    enviar_whatsapp(numero, mensaje_presentacion_inicial())
    marcar_cliente_presentado(numero)
    return True


def obtener_estado_conversacion(numero):
    if numero not in estado_conversacion:
        estado_conversacion[numero] = {
            "proyecto_actual": None,
            "esperando_preferencia_topografia": False,
            "preferencia_topografia": None,
            "topografia_en_conversacion": False,
            "multimedia_pendiente": False
        }

    return estado_conversacion[numero]


def detectar_proyecto_en_texto(texto):
    """
    Detecta SOLO referencias suficientemente claras.
    No usamos palabras gen├®ricas como "zona", "carretera", "ubicaci├│n", etc.
    """
    t = texto.lower()

    if any(x in t for x in [
        "palmeras san miguel",
        "palmeras",
        "san miguel"
    ]):
        return "palmeras"

    if any(x in t for x in [
        "vista hermosa",
        "km 188"
    ]):
        return "vista_hermosa"

    if any(x in t for x in [
        "buenaventura cuyotenango",
        "buenaventura",
        "cuyotenango",
        "km 168"
    ]):
        return "buenaventura"

    return None


def actualizar_proyecto_activo(numero, texto):
    """
    Si el cliente menciona un proyecto expl├¡citamente, lo fija.
    Si NO menciona proyecto, conserva el anterior.
    """
    estado = obtener_estado_conversacion(numero)
    detectado = detectar_proyecto_en_texto(texto)

    if detectado:
        estado["proyecto_actual"] = detectado
        proyecto_activo[numero] = detectado
        persistir_cliente(numero)

    if estado["proyecto_actual"]:
        return estado["proyecto_actual"]

    return proyecto_activo.get(numero)


def obtener_proyecto_actual(numero):
    estado = obtener_estado_conversacion(numero)

    if estado["proyecto_actual"]:
        return estado["proyecto_actual"]

    return proyecto_activo.get(numero)


def marcar_pregunta_topografia(numero):
    estado = obtener_estado_conversacion(numero)
    estado["esperando_preferencia_topografia"] = True
    estado["topografia_en_conversacion"] = True
    persistir_cliente(numero)


def guardar_preferencia_topografia(numero, preferencia):
    estado = obtener_estado_conversacion(numero)
    estado["preferencia_topografia"] = preferencia
    estado["esperando_preferencia_topografia"] = False
    estado["topografia_en_conversacion"] = True
    persistir_cliente(numero)


def respuesta_preferencia_topografia(numero, texto, proyecto):
    """
    Maneja respuestas cortas a:
    "┬┐C├│mo prefieres tu terreno: plano o inclinado?"

    Devuelve None cuando el mensaje no es una respuesta a esa pregunta.
    """
    estado = obtener_estado_conversacion(numero)

    if not estado.get("esperando_preferencia_topografia"):
        return None

    t = normalizar_texto_topografia(texto)

    # Solo tratamos respuestas cortas/claras como elecci├│n de topograf├¡a.
    if len(t.split()) > 8:
        return None

    if any(x in t for x in [
        "quebrado", "quebrada", "inclinado", "inclinada",
        "con pendiente", "pendiente"
    ]):
        guardar_preferencia_topografia(numero, "inclinado")

        if proyecto in {"palmeras", "buenaventura"}:
            return (
                "Perfecto ­ƒÿè En este proyecto los lotes se manejan en topograf├¡a plana. "
                "Si buscas espec├¡ficamente un terreno quebrado o inclinado para un dise├▒o "
                "especial, d├¡melo y te ayudo a revisar qu├® alternativa podemos ofrecerte. ­ƒÅí"
            )

        if proyecto == "vista_hermosa":
            return (
                "Perfecto ­ƒÿè En Vista Hermosa s├¡ hay lotes planos y tambi├®n algunos "
                "quebrados/inclinados. Puedes revisar los planos y escoger las opciones "
                "que te interesen; si buscas uno quebrado, te ayudo a identificar opciones "
                "para que puedas escoger con m├ís seguridad. ­ƒÅí"
            )

        return (
            "Perfecto ­ƒÿè Si prefieres un lote quebrado o inclinado, dime qu├® opci├│n "
            "te interesa y te ayudo a revisarla."
        )

    # "plano", "un plano", "uno plano", "prefiero plano", etc.
    if any(x in t for x in [
        "plano", "plana", "llano", "llana"
    ]):
        guardar_preferencia_topografia(numero, "plano")

        if proyecto in {"palmeras", "buenaventura"}:
            return (
                "Perfecto ­ƒÿè Puedes revisar el plano y la disponibilidad, escoger el lote "
                "que m├ís te guste y enviarme el n├║mero o una captura. En este proyecto los "
                "lotes se manejan en topograf├¡a plana, as├¡ que con gusto te ayudo a revisar "
                "la opci├│n que elijas. ­ƒÅí"
            )

        if proyecto == "vista_hermosa":
            return (
                "Perfecto ­ƒÿè Puedes revisar los planos y la disponibilidad, escoger el lote "
                "que m├ís te guste y enviarme el n├║mero o una captura. En Vista Hermosa hay "
                "lotes planos y tambi├®n algunos quebrados, as├¡ que antes de asegur├írtelo "
                "te confirmo la topograf├¡a exacta del lote que elijas. ­ƒÅí"
            )

        return (
            "Perfecto ­ƒÿè Revisa el plano, escoge el lote que te interese y env├¡ame "
            "el n├║mero o una captura; te ayudo a confirmar su topograf├¡a."
        )

    return None


def parece_numero_de_lote(texto):
    """
    Detecta referencias como 'lote 125', 'n├║mero de lote 125', '#125'.
    Se usa ├║nicamente cuando ya venimos hablando de topograf├¡a.
    """
    t = normalizar_texto_topografia(texto)

    patrones = [
        r"\blote\s*[#n┬║┬░.-]*\s*\d{1,5}\b",
        r"\bnumero\s+(?:de\s+)?lote\s*[#n┬║┬░.-]*\s*\d{1,5}\b",
        r"\bno\.?\s*\d{1,5}\b",
        r"^#\s*\d{1,5}$"
    ]

    return any(re.search(p, t) for p in patrones)


def respuesta_revision_lote_topografia(numero, proyecto, texto):
    """
    Responde cuando el cliente manda un n├║mero de lote dentro del seguimiento
    de topograf├¡a.

    Buenaventura y Palmeras: topograf├¡a plana seg├║n la regla comercial cargada.
    Vista Hermosa: no inventamos el dato individual sin una tabla topogr├ífica.
    """
    estado = obtener_estado_conversacion(numero)

    if not estado.get("topografia_en_conversacion"):
        return None

    if not parece_numero_de_lote(texto):
        return None

    if proyecto in {"palmeras", "buenaventura"}:
        return (
            "S├¡ ­ƒÿè Ese lote se maneja en topograf├¡a plana. Si quieres, tambi├®n puedo "
            "ayudarte a revisar disponibilidad, precio o cuota de esa opci├│n. ­ƒÅí"
        )

    if proyecto == "vista_hermosa":
        return (
            "Perfecto ­ƒÿè Ya tengo la referencia del lote. En Vista Hermosa hay opciones "
            "planas y quebradas, as├¡ que para darte seguridad prefiero confirmarte la "
            "topograf├¡a exacta de ese lote. D├®jame revisarlo y te lo env├¡o en un momento."
        )

    return (
        "Perfecto ­ƒÿè D├®jame revisar exactamente la topograf├¡a de ese lote "
        "y te la confirmo en un momento."
    )


def pregunta_si_lote_es_quebrado(texto):
    t = normalizar_texto_topografia(texto)
    return (
        any(x in t for x in ["quebrado", "quebrada", "inclinado", "inclinada"])
        and any(x in t for x in ["este", "ese", "el que", "lote", "terreno"])
        and any(x in t for x in ["es", "esta", "seria", "sera"])
    )


def respuesta_si_pregunta_quebrado(numero, proyecto, texto):
    estado = obtener_estado_conversacion(numero)

    if not estado.get("topografia_en_conversacion"):
        return None

    if not pregunta_si_lote_es_quebrado(texto):
        return None

    if proyecto in {"palmeras", "buenaventura"}:
        return (
            "No ­ƒÿè En este proyecto los lotes se manejan en topograf├¡a plana. "
            "Si est├ís buscando espec├¡ficamente una opci├│n quebrada/inclinada, "
            "d├¡melo y te ayudo a revisar alternativas."
        )

    if proyecto == "vista_hermosa":
        return (
            "Si lo que buscas es uno quebrado/inclinado, con gusto te ayudo a revisar "
            "las opciones de Vista Hermosa que tengan ese tipo de topograf├¡a para que "
            "puedas escoger. ­ƒÿè­ƒÅí"
        )

    return None


# ============================================================
# PLANOS PUBLICADOS EN GITHUB PAGES
# ============================================================

PLANOS_BASE_URL = "https://polerogabriel09-gif.github.io/planos-inmobiliaria/assets/planos"

PLANOS_PROYECTOS = {
    "buenaventura": {
        "general": {
            "url": f"{PLANOS_BASE_URL}/buenaventura.pdf",
            "archivo": "Plano_Buenaventura_Cuyotenango.pdf",
            "nombre": "Plano general de Buenaventura Cuyotenango"
        }
    },
    "palmeras": {
        "fase_1": {
            "url": f"{PLANOS_BASE_URL}/palmeras-fase-1.pdf",
            "archivo": "Plano_Palmeras_San_Miguel_Fase_1.pdf",
            "nombre": "Palmeras San Miguel - Fase 1"
        },
        "fase_2": {
            "url": f"{PLANOS_BASE_URL}/palmeras-fase-2.pdf",
            "archivo": "Plano_Palmeras_San_Miguel_Fase_2.pdf",
            "nombre": "Palmeras San Miguel - Fase 2"
        }
    },
    "vista_hermosa": {
        "fase_f": {
            "url": f"{PLANOS_BASE_URL}/vista-hermosa-fase-f.pdf",
            "archivo": "Plano_Vista_Hermosa_Fase_F.pdf",
            "nombre": "Vista Hermosa - Fase F"
        },
        "fase_g": {
            "url": f"{PLANOS_BASE_URL}/vista-hermosa-fase-g.pdf",
            "archivo": "Plano_Vista_Hermosa_Fase_G.pdf",
            "nombre": "Vista Hermosa - Fase G"
        }
    }
}


def normalizar_texto_topografia(texto):
    """Normaliza texto para detectar mejor intenciones de topograf├¡a."""
    t = (texto or "").lower().strip()
    reemplazos = {
        "├í": "a", "├®": "e", "├¡": "i", "├│": "o", "├║": "u", "├╝": "u"
    }
    for origen, destino in reemplazos.items():
        t = t.replace(origen, destino)
    return " ".join(t.split())


def pregunta_topografia_terreno(texto):
    """
    Detecta cuando "plano" habla de la TOPOGRAF├ìA del lote y no del PDF/croquis.
    Debe ganar prioridad antes de pide_plano().
    """
    t = normalizar_texto_topografia(texto)

    referencias_terreno = [
        "lote", "lotes", "terreno", "terrenos",
        "topografia", "topografico", "topografica"
    ]

    referencias_forma = [
        "plano", "planos", "plana", "planas",
        "llano", "llanos", "llana", "llanas",
        "inclinado", "inclinados", "inclinada", "inclinadas",
        "quebrado", "quebrados", "quebrada", "quebradas",
        "pendiente", "desnivel"
    ]

    frases_directas = [
        "como es la topografia",
        "que topografia",
        "topografia del proyecto",
        "topografia de los lotes",
        "plano o inclinado",
        "plano o quebrado",
        "inclinado o plano",
        "quebrado o plano",
        "uno plano",
        "uno inclinado",
        "uno quebrado",
        "uno llano",
        "prefiero plano",
        "prefiero inclinado",
        "quiero uno plano",
        "quiero uno inclinado"
    ]

    if any(frase in t for frase in frases_directas):
        return True

    palabras_precio = [
        "precio", "cuesta", "costaria", "vale", "valor",
        "mas caro", "mismo precio"
    ]

    if (
        any(p in t for p in palabras_precio)
        and any(f in t for f in referencias_forma)
    ):
        return True

    return (
        any(ref in t for ref in referencias_terreno)
        and any(ref in t for ref in referencias_forma)
    )

def preferencia_topografia(texto):
    """
    Devuelve 'plano', 'inclinado' o None cuando el cliente expresa
    preferencia por la topograf├¡a del lote.
    """
    t = normalizar_texto_topografia(texto)

    if any(x in t for x in [
        "plano del proyecto", "plano de proyecto", "plano general",
        "plano de lotes", "plano de los lotes", "ver el plano",
        "mandame el plano", "enviame el plano", "croquis", "mapa"
    ]):
        return None

    if any(x in t for x in [
        "inclinado", "inclinada", "inclinados", "inclinadas",
        "quebrado", "quebrada", "quebrados", "quebradas",
        "con pendiente", "desnivel"
    ]):
        return "inclinado"

    if any(x in t for x in [
        "lote plano", "lotes planos", "terreno plano", "terrenos planos",
        "lote llano", "terreno llano", "lo quiero plano",
        "prefiero plano", "me gusta plano", "quiero plano"
    ]):
        return "plano"

    return None


def respuesta_topografia(preferencia=None):
    """
    Explica diferencias entre terreno plano e inclinado.
    El precio del lote NO cambia por la topograf├¡a.
    """
    base = (
        "Claro ­ƒÿè En nuestros proyectos puedes encontrar lotes con distintas "
        "condiciones de topograf├¡a. El precio del lote es el mismo seg├║n la "
        "medida y fase, ya sea plano o inclinado/quebrado. ­ƒÅí\n\n"
        "­ƒƒó *Terreno plano:* facilita dise├▒os de construcci├│n m├ís convencionales, "
        "accesos, patios y distribuci├│n exterior; normalmente requiere menos "
        "adaptaci├│n inicial del terreno.\n\n"
        "Ôø░´©Å *Terreno inclinado o quebrado:* puede ser muy atractivo para dise├▒os "
        "escalonados, casas de varios niveles, terrazas o proyectos que aprovechen "
        "la pendiente de forma arquitect├│nica.\n\n"
        "El costo de construcci├│n s├¡ puede variar dependiendo del dise├▒o, "
        "movimiento de tierra y cimentaci├│n que elijas, pero *el precio de venta "
        "del lote no cambia por ser plano o inclinado*."
    )

    if preferencia == "plano":
        return (
            base
            + "\n\nPor lo que me indicas, buscas uno *plano* ­ƒæì. "
              "Puedo ayudarte a enfocarnos en ese tipo de lote. "
              "┬┐De cu├íl proyecto te interesa?"
        )

    if preferencia == "inclinado":
        return (
            base
            + "\n\nPerfecto ­ƒæì Si prefieres uno *inclinado/quebrado*, "
              "podemos buscar una opci├│n que se adapte al dise├▒o de casa que tienes en mente. "
              "┬┐De cu├íl proyecto te interesa?"
        )

    return base + "\n\n┬┐Cu├íl prefieres t├║: *plano o inclinado*? ­ƒÿè"


def mensaje_topografia_despues_de_plano():
    return (
        "­ƒÅí *Sobre la topograf├¡a:* los lotes que ves en el plano pueden encontrarse "
        "en topograf├¡a plana. Si prefieres un lote inclinado/quebrado para un dise├▒o "
        "de casa espec├¡fico, d├¡noslo y te ayudamos a buscar una opci├│n adecuada. ­ƒÿè\n\n"
        "El precio del lote no cambia por ser plano o inclinado; depende de la medida "
        "y fase correspondiente.\n\n"
        "┬┐C├│mo prefieres tu terreno: *plano o inclinado*?"
    )


def pide_plano(texto):
    """
    Detecta solicitudes del DOCUMENTO: plano/croquis/mapa/PDF.
    """
    if pregunta_topografia_terreno(texto):
        return False

    t = normalizar_texto_topografia(texto)

    # Si el cliente pregunta por disponibilidad de lotes, enviar el plano directamente.
    # Evitamos usar esta regla cuando claramente habla de disponibilidad de agua.
    if "disponibilidad" in t and "agua" not in t:
        return True

    if any(x in t for x in [
        "croquis",
        "mapa del proyecto", "mapa de proyecto",
        "mapa de lotes", "mapa de los lotes",
        "distribucion de lotes",
        "distribucion del proyecto",
        "plano del proyecto", "plano de proyecto",
        "plano general", "plano de lotes", "plano de los lotes",
        "pdf del plano", "plano pdf"
    ]):
        return True

    verbos_documento = [
        "manda", "mandame", "mandarme", "mandar",
        "envia", "enviame", "enviarme", "enviar",
        "comparte", "comparteme", "compartirme", "compartir",
        "muestra", "muestrame", "mostrar",
        "ensena", "ensename",
        "pasame", "pasarme", "pasar",
        "ver", "tienes", "tiene", "tendras",
        "puede mandarme", "puedes mandarme",
        "puede enviarme", "puedes enviarme"
    ]

    if "plano" in t or "planos" in t:
        if any(v in t for v in verbos_documento):
            return True

        if re.search(r"\b(el|los)\s+planos?\b", t):
            return True

        if t in {"plano", "planos"}:
            return True

    return False

def detectar_fase_plano(texto, proyecto):
    """Devuelve la fase pedida solo cuando tiene sentido para el proyecto activo."""
    t = texto.lower()

    if proyecto == "palmeras":
        if any(x in t for x in ["fase 1", "fase1", "fase uno", "primera fase"]):
            return "fase_1"
        if any(x in t for x in ["fase 2", "fase2", "fase dos", "segunda fase"]):
            return "fase_2"

    if proyecto == "vista_hermosa":
        if any(x in t for x in ["fase f", "fase \"f\"", "fase 'f'"]):
            return "fase_f"
        if any(x in t for x in ["fase g", "fase \"g\"", "fase 'g'"]):
            return "fase_g"

    return None


def texto_leyenda_planos():
    return (
        "Para que puedas interpretar el plano, estos son los colores ­ƒÿè\n\n"
        "­ƒƒó Disponible: lote disponible para la venta.\n"
        "­ƒö┤ Vendido: lote que ya fue vendido.\n"
        "­ƒƒú Reservado por ├írea t├®cnica: no est├í disponible para la venta.\n"
        "­ƒöÁ Apartado por ├írea t├®cnica: ser├í tomado como ├írea verde.\n"
        "­ƒƒí Reservado: lote que se encuentra reservado."
    )


def seleccionar_planos(proyecto, texto):
    """Selecciona uno o todos los planos del proyecto seg├║n la fase solicitada."""
    if proyecto not in PLANOS_PROYECTOS:
        return []

    planos = PLANOS_PROYECTOS[proyecto]

    if proyecto == "buenaventura":
        return [planos["general"]]

    fase = detectar_fase_plano(texto, proyecto)
    if fase and fase in planos:
        return [planos[fase]]

    # Si no indica fase, se comparten todas las fases disponibles del proyecto.
    return list(planos.values())


def nombre_proyecto_plano(proyecto):
    return {
        "palmeras": "Palmeras San Miguel",
        "vista_hermosa": "Vista Hermosa",
        "buenaventura": "Buenaventura Cuyotenango"
    }.get(proyecto, "el proyecto")


def pregunta_por_diferencia_de_fases(texto):
    t = texto.lower()

    referencias_fase = [
        "fase 1", "fase1", "fase 2", "fase2",
        "primera fase", "segunda fase",
        "fase f", "fase g",
        "una fase", "otra fase"
    ]

    referencias_precio = [
        "por que", "por qu├®", "porque",
        "sube", "subio", "subi├│",
        "mas caro", "m├ís caro",
        "diferencia", "precio",
        "vale mas", "vale m├ís"
    ]

    return (
        any(x in t for x in referencias_fase)
        and any(x in t for x in referencias_precio)
    )


def respuesta_diferencia_fases(numero):
    proyecto = obtener_proyecto_actual(numero)
    nombres = {
        "palmeras": "Palmeras San Miguel",
        "vista_hermosa": "Vista Hermosa",
        "buenaventura": "Buenaventura Cuyotenango"
    }
    nombre = nombres.get(proyecto, "el proyecto")
    return (
        f"S├¡ ­ƒÿè En {nombre}, la diferencia de precio entre una fase y otra "
        "se debe principalmente a la plusval├¡a que ha ido ganando el proyecto "
        "y al mayor avance de urbanizaci├│n en las fases m├ís recientes ­ƒÅí­ƒôê. "
        "Conforme avanzan calles, servicios, amenidades e infraestructura, "
        "el valor de los lotes tambi├®n se actualiza."
    )


# ============================================================
# GASTOS ADICIONALES - SOLO SI EL CLIENTE LOS PREGUNTA
# ============================================================

GASTOS_ADICIONALES = {
    "palmeras": {
        "nombre": "Palmeras San Miguel",
        "escrituracion": "Q3,500",
        "titulo_agua": "Q3,500",
        "mantenimiento": "Q50 al mes",
        "agua": "Q50 por 30,000 litros",
        "nota": (
            "El mantenimiento y la cuota de agua se empiezan a pagar "
            "cuando el proyecto ya est├® urbanizado; mientras no est├® urbanizado, no se cobran."
        )
    },
    "vista_hermosa": {
        "nombre": "Ciudad Vista Hermosa",
        "escrituracion": "Q3,500",
        "titulo_agua": "Q3,500",
        "mantenimiento": "Q50 al mes",
        "agua": "Q50 por 30,000 litros",
        "nota": (
            "El mantenimiento y la cuota de agua se empiezan a pagar "
            "cuando el proyecto ya est├® urbanizado; mientras no est├® urbanizado, no se cobran."
        )
    },
    "buenaventura": {
        "nombre": "Buenaventura Cuyotenango",
        "escrituracion": {
            1: "Q6,000",
            2: "Q8,400",
            3: "Q10,800"
        },
        "extra_por_lote": "Q2,400 por cada lote adicional",
        "titulo_agua": "Q4,000",
        "mantenimiento": "Q100 al mes",
        "agua": "Q100 por 30,000 litros al mes"
    }
}



# ============================================================
# REQUISITOS DE COMPRA - GUATEMALA / EXTRANJERO
# ============================================================

def cliente_en_extranjero(texto):
    t = texto.lower()

    frases = [
        "estoy en estados unidos", "estoy en usa", "estoy en eeuu",
        "estoy en ee. uu.", "vivo en estados unidos", "vivo en usa",
        "estoy en otro pais", "estoy en otro pa├¡s",
        "vivo en otro pais", "vivo en otro pa├¡s",
        "estoy fuera de guatemala", "vivo fuera de guatemala",
        "estoy en el extranjero", "vivo en el extranjero",
        "desde estados unidos", "desde usa", "desde el extranjero",
        "puedo comprar desde estados unidos", "puedo comprar desde usa",
        "puedo comprar desde otro pais", "puedo comprar desde otro pa├¡s",
        "puedo comprar desde el extranjero"
    ]

    return any(f in t for f in frases)


def pide_requisitos_compra(texto):
    t = texto.lower()

    frases = [
        "requisitos",
        "papeles", "que papeles", "qu├® papeles",
        "documentos", "que documentos", "qu├® documentos",
        "papeles para el financiamiento", "papeles del financiamiento",
        "documentos para el financiamiento", "documentos del financiamiento",
        "requisitos para el financiamiento", "requisitos del financiamiento",
        "que necesito para financiar", "qu├® necesito para financiar",
        "que piden para financiar", "qu├® piden para financiar",
        "que necesito para comprar", "qu├® necesito para comprar",
        "documentos para comprar",
        "como puedo comprar", "c├│mo puedo comprar",
        "que piden para comprar", "qu├® piden para comprar",
        "requisitos de compra"
    ]

    return any(f in t for f in frases)



def respuesta_compra_extranjero():
    return (
        "S├¡ ­ƒÿè Puedes comprar aunque est├®s en Estados Unidos o en otro pa├¡s ­ƒç║­ƒç©­ƒîÄ.\n\n"
        "Los requisitos son:\n"
        "ÔÇó DPI o pasaporte de la persona que realizar├í la compra.\n"
        "ÔÇó Un gestor de negocios en Guatemala; puede ser un familiar o conocido.\n"
        "ÔÇó Copia de la remesa o de la forma de pago con la que se realizar├í el pago.\n\n"
        "Adem├ís, tambi├®n puedes optar por financiamiento propio ­ƒÆ│­ƒÅí, as├¡ que no necesitas "
        "estar en Guatemala para iniciar el proceso.\n\n"
        "La ventaja es que puedes avanzar desde el extranjero, asegurar tu terreno y "
        "coordinar el proceso con apoyo de una persona de confianza en Guatemala ­ƒÖî.\n\n"
        "Si ya est├ís interesado, dime en qu├® proyecto quieres comprar y te ayudo a revisar "
        "la opci├│n que mejor se adapte a ti para avanzar con el proceso."
    )


def respuesta_compra_guatemala():
    return (
        "Claro ­ƒÿè Para solicitar el financiamiento propio necesitas:\n\n"
        "ÔÇó DPI.\n"
        "ÔÇó Recibo de luz o de agua.\n"
        "ÔÇó Constancia de ingresos de tu contador o estados de cuenta.\n\n"
        "El financiamiento es directo con la empresa, sin banco ­ƒÅí­ƒÆ│."
    )



def respuesta_requisitos_segun_contexto(numero, texto):
    """
    Si el cliente indica que est├í fuera de Guatemala, usa requisitos de extranjero.
    Si no indica extranjero, usa requisitos de Guatemala.
    """
    if cliente_en_extranjero(texto):
        return respuesta_compra_extranjero()

    # Revisar historial por si ya hab├¡a dicho que est├í fuera.
    historial = obtener_historial(numero)
    historial_texto = " ".join(
        item.get("content", "") for item in historial if item.get("role") == "user"
    )

    if cliente_en_extranjero(historial_texto):
        return respuesta_compra_extranjero()

    return respuesta_compra_guatemala()



# ============================================================
# VISITAS / CITAS - CIERRE DIRECTO
# ============================================================

estado_visitas = {}





def pregunta_plazo_escritura(texto):
    t = texto.lower().strip()

    # Si pregunta por TIEMPO/ENTREGA y menciona escritura, es plazo de escritura.
    if "escritura" in t or "escrituras" in t or "escrituracion" in t or "escrituraci├│n" in t:
        palabras_tiempo = [
            "cuanto tiempo", "cu├ínto tiempo",
            "cuanto tarda", "cu├ínto tarda",
            "cuanto tardan", "cu├ínto tardan",
            "cuando entregan", "cu├índo entregan",
            "cuando entrega", "cu├índo entrega",
            "me entregan", "me entrega",
            "entregan la escritura", "entrega la escritura",
            "en darme", "en dar", "para darme",
            "plazo", "tiempo de"
        ]

        if any(p in t for p in palabras_tiempo):
            return True

    frases = [
        "cuanto tarda la escritura", "cu├ínto tarda la escritura",
        "cuanto tardan en dar la escritura", "cu├ínto tardan en dar la escritura",
        "cuando entregan la escritura", "cu├índo entregan la escritura",
        "cuando entrega la escritura", "cu├índo entrega la escritura",
        "en cuanto tiempo dan la escritura", "en cu├ínto tiempo dan la escritura",
        "en cuanto tiempo me entregan la escritura", "en cu├ínto tiempo me entregan la escritura",
        "en cuanto tiempo entrega la escritura", "en cu├ínto tiempo entrega la escritura",
        "cuanto tiempo se tardan en darme la escritura", "cu├ínto tiempo se tardan en darme la escritura",
        "tiempo de la escritura", "plazo de la escritura",
        "cuando dan escrituras", "cu├índo dan escrituras",
        "cuanto tarda la escrituracion", "cu├ínto tarda la escrituraci├│n"
    ]

    return any(f in t for f in frases)



def respuesta_plazo_escritura():
    return (
        "Las escrituras son registradas ­ƒôäÔ£à y se entregan aproximadamente "
        "en un plazo de 3 meses."
    )



def pregunta_plazo_entrega_urbanizacion(texto):
    t = texto.lower()

    frases = [
        "en cuanto tiempo entregan", "en cu├ínto tiempo entregan",
        "cuando entregan", "cu├índo entregan",
        "cuando terminan", "cu├índo terminan",
        "cuando terminan de urbanizar", "cu├índo terminan de urbanizar",
        "cuanto tarda la urbanizacion", "cu├ínto tarda la urbanizaci├│n",
        "tiempo de urbanizacion", "tiempo de urbanizaci├│n",
        "cuando estara terminado", "cu├índo estar├í terminado",
        "cuando queda terminado", "cu├índo queda terminado",
        "plazo de entrega", "fecha de entrega",
        "cuando se entrega", "cu├índo se entrega",
        "cuando puedo construir", "cu├índo puedo construir"
    ]

    return any(f in t for f in frases)


def respuesta_plazo_entrega_urbanizacion(proyecto):
    nombres = {
        "palmeras": "Palmeras San Miguel",
        "vista_hermosa": "Vista Hermosa",
        "buenaventura": "Buenaventura Cuyotenango"
    }

    nombre = nombres.get(proyecto, "el proyecto")

    return (
        f"El plazo aproximado para completar la urbanizaci├│n de {nombre} "
        "es de 1 a 2 a├▒os ­ƒÅí­ƒÜº. Conforme avanza el proyecto se van desarrollando "
        "calles, servicios, amenidades e infraestructura."
    )


def detectar_amenidad_solicitada(texto):
    t = texto.lower()

    grupos = {
        "piscina": [
            "piscina", "piscinas", "alberca"
        ],
        "cancha": [
            "cancha", "canchas", "cancha deportiva",
            "basquet", "b├ísquet", "basket", "baloncesto"
        ],
        "salon": [
            "salon de eventos", "sal├│n de eventos",
            "salon social", "sal├│n social",
            "casa club", "club house"
        ],
        "juegos": [
            "juegos para ni├▒os", "juegos infantiles",
            "area de juegos", "├írea de juegos", "juegos"
        ],
        "areas_verdes": [
            "areas verdes", "├íreas verdes",
            "caminamientos", "caminamiento", "jardines"
        ]
    }

    for amenidad, palabras in grupos.items():
        if any(p in t for p in palabras):
            return amenidad

    return None


def cantidad_piscinas_proyecto(proyecto):
    cantidades = {
        "buenaventura": 2,
        "vista_hermosa": 1,
        "palmeras": 1
    }
    return cantidades.get(proyecto)


def pregunta_cantidad_piscinas(texto):
    t = texto.lower()

    referencias = [
        "cuantas piscinas", "cu├íntas piscinas",
        "cuanta piscina", "cu├ínta piscina",
        "numero de piscinas", "n├║mero de piscinas",
        "cantidad de piscinas"
    ]

    return any(f in t for f in referencias)


def respuesta_amenidad(proyecto, amenidad, texto_cliente=""):
    nombres = {
        "palmeras": "Palmeras San Miguel",
        "vista_hermosa": "Vista Hermosa",
        "buenaventura": "Buenaventura Cuyotenango"
    }

    nombre = nombres.get(proyecto, "el proyecto")

    if amenidad == "piscina" and pregunta_cantidad_piscinas(texto_cliente):
        cantidad = cantidad_piscinas_proyecto(proyecto)

        if cantidad is not None:
            palabra = "piscina" if cantidad == 1 else "piscinas"
            return (
                f"{nombre} cuenta con {cantidad} {palabra} ­ƒÅè­ƒÿè. "
                "Te comparto material para que puedas conocerlas mejor ­ƒæç­ƒô©­ƒÄÑ"
            )

    etiquetas = {
        "piscina": "piscinas ­ƒÅè",
        "cancha": "canchas deportivas ­ƒÅÇ",
        "salon": "casa club / sal├│n para actividades ­ƒÄë",
        "juegos": "├íreas de juegos para ni├▒os ­ƒøØ",
        "areas_verdes": "├íreas verdes y caminamientos ­ƒî│"
    }

    etiqueta = etiquetas.get(amenidad, "esa amenidad")

    return (
        f"S├¡ ­ƒÿè En {nombre} contamos con {etiqueta}. "
        "Te comparto material para que puedas verla mejor ­ƒæç­ƒô©­ƒÄÑ"
    )



def material_amenidad(proyecto, amenidad):
    """
    Material espec├¡fico ya cargado en el bot.
    Los videos generales muestran las mismas amenidades disponibles
    en los proyectos, por eso se usan como referencia visual.
    """
    videos = {
        "piscina": [
            "media/videos/general/amenidades_5.mp4",
            "media/videos/general/amenidades_1.mp4",
        ],
        "cancha": [
            "media/videos/general/amenidades_3.mp4",
            "media/videos/general/amenidades_1.mp4",
        ],
        "salon": [
            "media/videos/general/amenidades_4.mp4",
            "media/videos/general/amenidades_1.mp4",
        ],
        "juegos": [
            "media/videos/general/amenidades_1.mp4",
            "media/videos/general/amenidades_2.mp4",
        ],
        "areas_verdes": [
            "media/videos/general/amenidades_1.mp4",
            "media/videos/general/amenidades_2.mp4",
        ],
    }

    # IMPORTANTE: estas fotos son EXCLUSIVAMENTE de amenidades.
    # Se generan a partir de los videos de amenidades ya cargados en
    # media/videos/general, para no confundirlas con fotos generales
    # de Palmeras, Vista Hermosa o Buenaventura.
    fotos_amenidades = {
        "piscina": [
            "media/amenidades/amenidades_5.jpg",
            "media/amenidades/amenidades_1.jpg",
        ],
        "cancha": [
            "media/amenidades/amenidades_3.jpg",
            "media/amenidades/amenidades_1.jpg",
        ],
        "salon": [
            "media/amenidades/amenidades_4.jpg",
            "media/amenidades/amenidades_1.jpg",
        ],
        "juegos": [
            "media/amenidades/amenidades_1.jpg",
            "media/amenidades/amenidades_2.jpg",
        ],
        "areas_verdes": [
            "media/amenidades/amenidades_1.jpg",
            "media/amenidades/amenidades_2.jpg",
        ],
    }

    return (
        fotos_amenidades.get(amenidad, [])[:2],
        videos.get(amenidad, [])[:2]
    )



def enviar_material_amenidad(numero, proyecto, amenidad):
    fotos, videos = material_amenidad(proyecto, amenidad)

    for i, ruta in enumerate(fotos):
        if os.path.exists(ruta):
            enviar_imagen_whatsapp(
                numero,
                ruta,
                caption="Amenidades del proyecto ­ƒÅí­ƒô©" if i == 0 else ""
            )

    for i, ruta in enumerate(videos):
        if os.path.exists(ruta):
            enviar_video_whatsapp(
                numero,
                ruta,
                caption="Amenidades disponibles ­ƒÄÑÔ£¿" if i == 0 else ""
            )



def enviar_paquete_amenidades(numero, proyecto):
    """
    Env├¡a ├║nicamente VIDEOS de amenidades.
    Se usa autom├íticamente despu├®s de cotizaciones y cuando corresponde
    mostrar material visual de amenidades.

    No genera ni env├¡a im├ígenes congeladas de los videos y no reutiliza
    fotos generales de los proyectos.
    """
    if not proyecto:
        return

    videos = []
    for ruta in VIDEOS_GENERALES:
        if ruta not in videos and os.path.exists(ruta):
            videos.append(ruta)

    if not videos:
        return

    enviar_whatsapp(
        numero,
        "Tambi├®n te comparto videos de las amenidades para que puedas "
        "conocer mejor las ├íreas del proyecto ­ƒÅè­ƒî│­ƒÅí­ƒÄÑ"
    )

    for i, ruta in enumerate(videos[:3], start=1):
        enviar_video_whatsapp(
            numero,
            ruta,
            caption="Recorrido por las amenidades ­ƒÄÑÔ£¿" if i == 1 else ""
        )


def pregunta_banco_financiamiento(texto):
    t = texto.lower().strip()

    frases = [
        "que banco", "qu├® banco",
        "con que banco", "con qu├® banco",
        "de que banco", "de qu├® banco",
        "cual banco", "cu├íl banco",
        "trabajan con banco", "trabaja con banco",
        "financiamiento bancario",
        "es con banco", "es de banco",
        "por medio de banco",
        "el financiamiento es de banco",
        "el financiamiento es con banco",
        "que banco financia", "qu├® banco financia",
        "quien financia", "qui├®n financia",
        "con que financiamiento es el banco",
        "con qu├® financiamiento es el banco",
        "financiamiento es el banco",
        "financiamiento del banco",
        "banco del financiamiento"
    ]

    # Si menciona "banco" y "financiamiento" en la misma frase,
    # tambi├®n lo tratamos como pregunta de banco aunque est├® redactado raro.
    if "banco" in t and (
        "financiamiento" in t
        or "financiar" in t
        or "credito" in t
        or "cr├®dito" in t
    ):
        return True

    return any(f in t for f in frases)



def pregunta_financiamiento(texto):
    t = texto.lower()

    palabras = [
        "financiamiento", "financiar", "financiado",
        "credito", "cr├®dito", "cuotas", "plazos"
    ]

    return any(p in t for p in palabras)


def respuesta_financiamiento_propio():
    return (
        "El financiamiento es propio y directo con la empresa ­ƒÿè­ƒÅí. "
        "No trabajamos con ning├║n banco."
    )



def pregunta_punto_encuentro(texto):
    t = texto.lower()

    frases = [
        "donde nos juntamos", "d├│nde nos juntamos",
        "donde nos podemos juntar", "d├│nde nos podemos juntar",
        "donde quedamos de juntarnos", "d├│nde quedamos de juntarnos",
        "punto de encuentro", "donde nos vemos", "d├│nde nos vemos",
        "en donde nos vemos", "en d├│nde nos vemos",
        "donde me espera", "d├│nde me espera",
        "donde lo encuentro", "d├│nde lo encuentro",
        "donde nos encontramos", "d├│nde nos encontramos",
        "en que lugar nos juntamos", "en qu├® lugar nos juntamos"
    ]

    return any(f in t for f in frases)


def respuesta_punto_encuentro(numero, proyecto):
    nombres = {
        "palmeras": "Palmeras San Miguel",
        "vista_hermosa": "Vista Hermosa",
        "buenaventura": "Buenaventura Cuyotenango"
    }

    nombre = nombres.get(proyecto, "el proyecto")

    return (
        f"Podemos encontrarnos directamente en {nombre} ­ƒÿè­ƒôì. "
        "Si necesitas otro punto, me lo indicas."
    )




def pregunta_proceso_compra(texto):
    t = normalizar_texto_topografia(texto)
    frases = [
        "proceso de compra", "como se compra", "como comprar",
        "como puedo comprar", "como hago para comprar",
        "que necesito para comprar", "que se necesita para comprar",
        "como es la compra", "como funciona la compra",
        "cual es el proceso", "cu├íl es el proceso"
    ]
    return any(f in t for f in frases)


def respuesta_proceso_compra(proyecto):
    datos = {
        "buenaventura": {
            "nombre": "Buenaventura Cuyotenango",
            "enganche": "Q6,000",
            "financiamiento": "de 2 a 8 a├▒os",
            "extra": "Tambi├®n hay un plan alternativo de 1 a├▒o sin intereses cuando est├® vigente.",
        },
        "palmeras": {
            "nombre": "Palmeras San Miguel",
            "enganche": "Q6,000",
            "financiamiento": "de 1 a 8 a├▒os",
            "extra": "",
        },
        "vista_hermosa": {
            "nombre": "Vista Hermosa",
            "enganche": "Q6,000",
            "financiamiento": "de 1 a 8 a├▒os",
            "extra": "",
        },
    }

    d = datos.get(proyecto)
    if not d:
        return (
            "Claro ­ƒÿè Primero elegimos el lote y confirmamos disponibilidad. "
            "Luego revisamos el enganche, el plan de pagos y los documentos necesarios. "
            "┬┐De qu├® proyecto te interesa comprar? ­ƒÅí"
        )

    extra = f" {d['extra']}" if d["extra"] else ""

    return (
        f"Te cuento c├│mo es el proceso de compra en *{d['nombre']}* ­ƒÅí­ƒÿè\n\n"
        f"1´©ÅÔâú Eliges tu lote y medida ­ƒôÉ y yo te ayudo a revisar disponibilidad, "
        f"cotizaci├│n y plan de pagos.\n\n"
        f"2´©ÅÔâú Realizas el enganche ­ƒÆ░. En este proyecto es de *{d['enganche']}* "
        f"y contamos con financiamiento propio {d['financiamiento']}. "
        f"Tambi├®n puedes hacer abonos a capital.{extra}\n\n"
        f"3´©ÅÔâú Firma y escrituraci├│n Ô£ì´©Å­ƒôä. Las escrituras son registradas y se entregan "
        f"aproximadamente *3 meses despu├®s de haber cancelado el 100% del terreno*. Ô£à\n\n"
        f"­ƒôï *Requisitos para comprar:*\n"
        f"­ƒç¼­ƒç╣ Guatemala: DPI, recibo de luz o agua y constancia de ingresos.\n"
        f"­ƒîÄ Extranjero: DPI o pasaporte, un gestor en Guatemala y copia de remesa "
        f"o comprobante de la forma de pago.\n\n"
        f"­ƒÿè ┬┐Est├ís en Guatemala o en el extranjero?"
    )


def seguimiento_compra_respuesta_directa(texto, proyecto):
    """
    Maneja preguntas t├¡picas que suelen venir despu├®s de explicar el proceso.
    Devuelve None si no aplica.
    """
    t = normalizar_texto_topografia(texto)

    # Guatemala / extranjero
    if t in {"guatemala", "estoy en guatemala", "aqui en guatemala", "soy de guatemala"}:
        return (
            "Perfecto ­ƒÿè­ƒç¼­ƒç╣ Necesitar├¡as DPI, recibo de luz o agua y constancia de ingresos. "
            "┬┐Quieres que revisemos primero qu├® lote te interesa? ­ƒÅí"
        )

    if any(x in t for x in [
        "estados unidos", "usa", "eeuu", "extranjero", "afuera",
        "estoy en usa", "estoy en estados unidos"
    ]):
        return (
            "Claro ­ƒÿè­ƒç║­ƒç©­ƒç¼­ƒç╣ Puedes comprar desde el extranjero. Necesitar├¡as DPI o pasaporte, "
            "un gestor en Guatemala y comprobante de remesa o forma de pago. "
            "┬┐Quieres que te explique c├│mo iniciar?"
        )

    if "que es un gestor" in t or "qu├® es un gestor" in texto.lower():
        return (
            "Es una persona de confianza que tengas en Guatemala ­ƒÿè. "
            "Puede ser un familiar o conocido que te apoye con las gestiones necesarias."
        )

    # Project-specific payment facts
    enganches = {
        "buenaventura": "Q6,000",
        "palmeras": "Q6,000",
        "vista_hermosa": "Q6,000",
    }
    financiamientos = {
        "buenaventura": "de 2 a 8 a├▒os",
        "palmeras": "de 1 a 8 a├▒os",
        "vista_hermosa": "de 1 a 8 a├▒os",
    }

    if any(x in t for x in [
        "cuanto tengo que dar", "cuanto doy para empezar",
        "cuanto es el enganche", "enganche"
    ]):
        e = enganches.get(proyecto)
        if e:
            return (
                f"El enganche en este proyecto es de *{e}* ­ƒÆ░­ƒÿè. "
                "┬┐Quieres que te muestre las cuotas seg├║n el plazo que prefieras?"
            )

    if any(x in t for x in [
        "puedo dar el enganche en pagos", "enganche en pagos",
        "fraccionar el enganche", "pagar el enganche por partes"
    ]):
        if proyecto in {"buenaventura", "vista_hermosa"}:
            return (
                "S├¡ ­ƒÿè El enganche puede fraccionarse en 2 pagos mensuales. "
                "┬┐Quieres que te muestre c├│mo quedar├¡an las cuotas?"
            )
        return (
            "D├®jame revisar exactamente la condici├│n del enganche para este proyecto "
            "y te la confirmo en un momento ­ƒÿè."
        )

    if any(x in t for x in ["trabajan con banco", "con banco", "banco"]):
        f = financiamientos.get(proyecto)
        return (
            f"No necesitas banco ­ƒÿè­ƒÅí El financiamiento es propio de la empresa"
            + (f" y se maneja {f}." if f else ".")
        )

    if any(x in t for x in ["abono a capital", "abonar a capital", "puedo abonar"]):
        return "S├¡ ­ƒÿè­ƒÆ░ Puedes realizar abonos a capital para reducir tu saldo pendiente."

    if any(x in t for x in [
        "cuando me dan las escrituras", "cuando entregan escrituras",
        "cuando dan escritura", "cuando me dan escritura"
    ]):
        return (
            "Las escrituras son registradas ­ƒôäÔ£à y se entregan aproximadamente "
            "3 meses despu├®s de haber cancelado el 100% del terreno."
        )

    if any(x in t for x in [
        "queda a mi nombre", "escritura a mi nombre", "a nombre de quien"
    ]):
        return "S├¡ ­ƒÿè­ƒôä La escritura del lote se realiza a nombre del comprador."

    if any(x in t for x in [
        "quiero comprar uno", "quiero uno", "me interesa comprar",
        "quiero apartarlo", "quiero reservar"
    ]):
        return (
            "Excelente ­ƒÿè­ƒÅí Primero revisemos cu├íl lote te interesa y confirmamos disponibilidad. "
            "┬┐Qu├® medida est├ís buscando?"
        )

    if any(x in t for x in [
        "lo voy a pensar", "lo pensare", "lo voy a revisar", "despues te digo"
    ]):
        return (
            "Claro ­ƒÿè Rev├¡salo con calma. Si te surge alguna duda sobre el terreno, "
            "pagos o el proceso, con gusto te ayudo ­ƒÅí."
        )

    return None


def pregunta_horario_para_visita(texto):
    t = texto.lower().strip()

    frases = [
        "cuando me puede atender", "cu├índo me puede atender",
        "a que hora me puede atender", "a qu├® hora me puede atender",
        "cuando me pueden atender", "cu├índo me pueden atender",
        "a que hora me pueden atender", "a qu├® hora me pueden atender",
        "que horario tienen", "qu├® horario tienen",
        "en que horario me atiende", "en qu├® horario me atiende",
        "a que hora puedo llegar", "a qu├® hora puedo llegar",
        "a que hora puedo ir", "a qu├® hora puedo ir"
    ]

    return any(f in t for f in frases)


def detectar_intencion_visita(texto):
    t = texto.lower()

    frases = [
        "ir a ver", "ir a conocer", "quiero ir", "queremos ir",
        "podemos ir", "puedo ir", "visitar", "visita",
        "conocer el proyecto", "conocer los lotes",
        "ver los lotes", "ver el terreno", "ver el proyecto",
        "agendar", "agendamos", "coordinar una visita",
        "coordinar visita"
    ]

    return any(f in t for f in frases) or pregunta_horario_para_visita(texto)


def extraer_dia_visita(texto):
    t = texto.lower()

    dias = [
        "lunes", "martes", "mi├®rcoles", "miercoles",
        "jueves", "viernes", "s├íbado", "sabado", "domingo"
    ]

    for dia in dias:
        if dia in t:
            return dia.capitalize()

    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})\b", t)
    if m:
        return m.group(0)

    return None


def extraer_hora_visita(texto):
    t = texto.lower()

    patrones = [
        r"\b(\d{1,2}:\d{2})\s*(am|pm|a\.m\.|p\.m\.)?\b",
        r"\b(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)\b"
    ]

    for patron in patrones:
        m = re.search(patron, t)
        if m:
            return m.group(0)

    return None


def respuesta_visita(numero, texto, proyecto):
    estado = estado_visitas.setdefault(
        numero,
        {"dia": None, "hora": None, "proyecto": None, "cerrada": False}
    )

    if proyecto:
        estado["proyecto"] = proyecto

    dia = extraer_dia_visita(texto)
    hora = extraer_hora_visita(texto)

    if dia:
        estado["dia"] = dia

    if hora:
        estado["hora"] = hora

    # Si pregunta cu├índo/a qu├® hora podemos atenderlo, no ofrecemos otros puntos.
    # Dejamos que el cliente elija el horario.
    if pregunta_horario_para_visita(texto) and not hora:
        if estado.get("dia"):
            return "A la hora que t├║ dispongas ­ƒÿè ┬┐A qu├® hora te queda bien?"
        return "A la hora que t├║ dispongas ­ƒÿè ┬┐Qu├® d├¡a te gustar├¡a visitar?"

    # D├¡a + hora = cita cerrada.
    # El usuario pidi├│ una confirmaci├│n m├¡nima, sin volver a vender ni preguntar.
    if estado["dia"] and estado["hora"]:
        estado["cerrada"] = True
        return "S├¡, perfecto ­ƒÿè Queda coordinado."

    if estado["dia"]:
        return "Perfecto ­ƒÿè ┬┐A qu├® hora te queda bien?"

    if estado["hora"]:
        return "Perfecto ­ƒÿè ┬┐Qu├® d├¡a te queda bien?"

    return "Claro ­ƒÿè ┬┐Qu├® d├¡a te gustar├¡a visitar?"



def cita_ya_cerrada(numero):
    estado = estado_visitas.get(numero, {})
    return bool(estado.get("cerrada"))


def resumen_cita_cerrada(numero):
    estado = estado_visitas.get(numero, {})

    if not estado.get("cerrada"):
        return None

    nombres = {
        "palmeras": "Palmeras San Miguel",
        "vista_hermosa": "Vista Hermosa",
        "buenaventura": "Buenaventura Cuyotenango"
    }

    nombre = nombres.get(
        estado.get("proyecto"),
        "el proyecto"
    )

    dia = estado.get("dia")
    hora = estado.get("hora")

    if dia and hora:
        return (
            f"Tu visita ya qued├│ coordinada para {nombre}, "
            f"el {dia} a las {hora} ­ƒÅí­ƒôì."
        )

    return "Tu visita ya qued├│ coordinada ­ƒÅí­ƒôì."


def pregunta_sobre_cita_existente(texto):
    t = texto.lower()

    frases = [
        "cuando es la visita", "cu├índo es la visita",
        "que dia es la visita", "qu├® d├¡a es la visita",
        "a que hora es la visita", "a qu├® hora es la visita",
        "cuando quedamos", "cu├índo quedamos",
        "que dia quedamos", "qu├® d├¡a quedamos",
        "hora de la visita", "dia de la visita", "d├¡a de la visita"
    ]

    return any(f in t for f in frases)


def continuar_visita_pendiente(numero, texto):
    estado = estado_visitas.get(numero)

    if not estado:
        return False

    if estado.get("dia") and not estado.get("hora"):
        return extraer_hora_visita(texto) is not None

    if estado.get("hora") and not estado.get("dia"):
        return extraer_dia_visita(texto) is not None

    return False



def pregunta_enganche(texto):
    """Detecta preguntas especificas sobre el enganche y evita disparar cotizaciones."""
    t = texto.lower().strip()

    frases = [
        "enganche", "cuanto es el enganche", "cu├ínto es el enganche",
        "de cuanto es el enganche", "de cu├ínto es el enganche",
        "cuanto tengo que dar de enganche", "cu├ínto tengo que dar de enganche",
        "se puede fraccionar el enganche", "puedo fraccionar el enganche",
        "enganche fraccionado", "fraccionar enganche", "pagar el enganche en dos",
        "pagar enganche en dos", "dos pagos de enganche", "2 pagos de enganche",
        "como se paga el enganche", "c├│mo se paga el enganche",
        "como funciona el enganche", "c├│mo funciona el enganche"
    ]

    return any(f in t for f in frases)


def respuesta_enganche(proyecto=None, texto=""):
    """
    Responde el enganche exacto cuando el cliente menciona una medida.
    Si no menciona medida, indica que los enganches son desde Q6,000.
    El fraccionamiento se calcula en dos pagos iguales cuando el monto es exacto.
    """
    nombres = {
        "palmeras": "Palmeras San Miguel",
        "vista_hermosa": "Vista Hermosa",
        "buenaventura": "Buenaventura Cuyotenango"
    }

    try:
        ahora = datetime.now(ZoneInfo("America/Guatemala"))
    except Exception:
        ahora = datetime.now()

    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    mes_1 = meses[ahora.month - 1]
    mes_2 = meses[ahora.month % 12]
    mes_3 = meses[(ahora.month + 1) % 12]

    nombre = nombres.get(proyecto)
    inicio = f"S├¡ ­ƒÿè En {nombre}" if nombre else "S├¡ ­ƒÿè"
    enganche = obtener_enganche_exacto(proyecto, texto)

    if enganche:
        numero = int(enganche.replace("Q", "").replace(",", ""))
        pago = numero // 2
        return (
            f"{inicio} el enganche para esa medida es de {enganche} y tenemos la opci├│n "
            "de fraccionarlo en 2 pagos mensuales. ­ƒÆ░\n\n"
            f"ÔÇó Q{pago:,} en este mes de {mes_1}\n"
            f"ÔÇó Q{pago:,} a finales de {mes_2}\n"
            f"ÔÇó Tu primera cuota ser├¡a hasta finales de {mes_3} Ô£à"
        )

    return (
        f"{inicio} tenemos enganches desde Q6,000 y la opci├│n de fraccionarlos "
        "en 2 pagos mensuales. ­ƒÆ░\n\n"
        "El monto exacto depende de la medida del lote."
    )


def pregunta_cantidad_lotes(texto):
    t = texto.lower().strip()

    frases = [
        "cuantos lotes", "cu├íntos lotes",
        "cantidad de lotes",
        "cuantos terrenos", "cu├íntos terrenos",
        "cuantos lotes tiene el proyecto", "cu├íntos lotes tiene el proyecto",
        "cuantos lotes hay", "cu├íntos lotes hay",
        "cuantos lotes tiene", "cu├íntos lotes tiene"
    ]

    return any(f in t for f in frases)


def respuesta_cantidad_lotes(proyecto):
    if proyecto == "buenaventura":
        return (
            "Buenaventura Cuyotenango cuenta con 2,600 lotes en total ­ƒÅí­ƒôì."
        )

    if proyecto == "palmeras":
        return (
            "Palmeras San Miguel cuenta con 1,700 lotes en la Fase 1 "
            "y 1,900 lotes en la Fase 2 ­ƒÅíÔ£¿."
        )

    if proyecto == "vista_hermosa":
        return (
            "Vista Hermosa cuenta con 1,100 lotes en la Fase F "
            "y 1,000 lotes en la Fase G ­ƒÅí­ƒôì."
        )

    return "Claro ­ƒÿè ┬┐De cu├íl proyecto quieres saber la cantidad de lotes?"


def pregunta_clima_lugar(texto):
    t = texto.lower()

    frases = [
        "que clima", "qu├® clima",
        "como es el clima", "c├│mo es el clima",
        "hace calor", "es caluroso", "clima del lugar",
        "clima de la zona", "clima del proyecto",
        "que tal el clima", "qu├® tal el clima"
    ]

    return any(f in t for f in frases)


def respuesta_clima_lugar():
    return (
        "S├¡ ­ƒÿè Por ac├í tenemos el caracter├¡stico clima c├ílido de costa ÔÿÇ´©Å­ƒî┤. "
        "Y justamente por eso se disfrutan mucho las piscinas, ├íreas verdes "
        "y dem├ís amenidades del proyecto. ­ƒÅè­ƒî┐"
    )


def pregunta_que_incluye_mantenimiento(texto):
    t = texto.lower()

    frases = [
        "que incluye el mantenimiento", "qu├® incluye el mantenimiento",
        "que cubre el mantenimiento", "qu├® cubre el mantenimiento",
        "para que sirve el mantenimiento", "para qu├® sirve el mantenimiento",
        "que trae el mantenimiento", "qu├® trae el mantenimiento",
        "que hacen con el mantenimiento", "qu├® hacen con el mantenimiento",
        "por que se paga el mantenimiento", "por qu├® se paga el mantenimiento",
        "porque se paga el mantenimiento", "porqu├® se paga el mantenimiento",
        "por que cobran mantenimiento", "por qu├® cobran mantenimiento",
        "porque cobran mantenimiento", "porqu├® cobran mantenimiento",
        "para que se paga el mantenimiento", "para qu├® se paga el mantenimiento",
        "en que se usa el mantenimiento", "en qu├® se usa el mantenimiento"
    ]

    return any(f in t for f in frases)



def respuesta_que_incluye_mantenimiento():
    return (
        "La cuota de mantenimiento se utiliza para mantener en buenas condiciones "
        "las ├íreas comunes de la residencial ­ƒÿè­ƒÅí. Incluye:\n\n"
        "ÔÇó Limpieza de ├íreas y calles.\n"
        "ÔÇó Mantenimiento de la planta de tratamiento.\n"
        "ÔÇó Mantenimiento de amenidades.\n"
        "ÔÇó Jardinizaci├│n de ├íreas verdes.\n"
        "ÔÇó Limpieza de lotes que a├║n no est├®n circulados.\n\n"
        "Todo esto ayuda a conservar el proyecto limpio, ordenado y bien cuidado ­ƒî┐Ô£¿."
    )



def pregunta_titulo_agua(texto):
    """Detecta preguntas espec├¡ficas sobre el t├¡tulo de agua."""
    t = texto.lower().strip()
    frases = [
        "titulo de agua", "t├¡tulo de agua",
        "que es el titulo de agua", "qu├® es el t├¡tulo de agua",
        "por que cobran titulo de agua", "por qu├® cobran t├¡tulo de agua",
        "porque cobran titulo de agua", "porqu├® cobran t├¡tulo de agua",
        "para que sirve el titulo de agua", "para qu├® sirve el t├¡tulo de agua",
        "cuanto cuesta el titulo de agua", "cu├ínto cuesta el t├¡tulo de agua",
        "precio del titulo de agua", "precio del t├¡tulo de agua",
        "el agua es propia", "pozo mecanico", "pozo mec├ínico"
    ]
    return any(f in t for f in frases)


def respuesta_titulo_agua(proyecto):
    montos = {
        "palmeras": "Q3,500",
        "vista_hermosa": "Q3,500",
        "buenaventura": "Q4,000"
    }
    monto = montos.get(proyecto)

    respuesta = (
        "El t├¡tulo de agua es un pago ├║nico ­ƒÆºÔ£à. "
        "La residencial cuenta con abastecimiento propio mediante pozo mec├ínico "
        "y tanques elevados, lo que permite tener disponibilidad de agua "
        "las 24 horas del d├¡a. Por eso se realiza este cobro una sola vez."
    )

    if monto:
        respuesta += f"\n\nEl valor del t├¡tulo de agua en este proyecto es de {monto}."

    return respuesta


def pide_gastos_adicionales(texto):
    """
    Detecta consultas de cualquier forma sobre costos/gastos extra.
    Esta intenci├│n tiene prioridad absoluta sobre la IA general.
    """
    t = texto.lower().strip()

    # Estas intenciones tienen handlers espec├¡ficos y no deben caer en gastos generales.
    if pregunta_plazo_escritura(texto):
        return False

    if pregunta_titulo_agua(texto):
        return False

    if pregunta_que_incluye_mantenimiento(texto):
        return False

    frases = [
        "gastos adicionales", "gasto adicional",
        "costos adicionales", "costo adicional",
        "tiene algun costo adicional", "tiene alg├║n costo adicional",
        "hay algun costo adicional", "hay alg├║n costo adicional",
        "tiene costos adicionales", "hay costos adicionales",
        "tiene gastos adicionales", "hay gastos adicionales",
        "algun costo extra", "alg├║n costo extra",
        "alg├║n gasto extra", "algun gasto extra",
        "gastos extras", "gasto extra", "costos extras", "costo extra",
        "pagos extras", "pago extra", "pagos extra",
        "otros gastos", "otro gasto", "otros pagos", "otro pago",
        "pagos adicionales", "pago adicional",
        "pagos aparte", "pago aparte", "gastos aparte", "costos aparte",
        "aparte del lote", "aparte del precio", "aparte de eso",
        "que mas se paga", "qu├® m├ís se paga",
        "que mas hay que pagar", "qu├® m├ís hay que pagar",
        "hay que pagar algo mas", "hay que pagar algo m├ís",
        "algo mas que pagar", "algo m├ís que pagar",
        "que pagos hay que cancelar", "qu├® pagos hay que cancelar",
        "que pagos se cancelan", "qu├® pagos se cancelan",
        "pagos que hay que cancelar", "pagos por cancelar",
        "que otros pagos", "qu├® otros pagos",
        "mantenimiento", "cuota de mantenimiento",
        "agua", "cuota de agua",
        "titulo de agua", "t├¡tulo de agua",
        "escrituracion", "escrituraci├│n",
        "escritura", "gastos de escritura", "gasto de escritura",
        "cuanto cuesta escriturar", "cu├ínto cuesta escriturar",
        "precio de escrituracion", "precio de escrituraci├│n"
    ]

    if any(f in t for f in frases):
        return True

    # Regla flexible para formas naturales como:
    # "┬┐Qu├® pagos extras hay que cancelar en el residencial?"
    # Evita depender de una frase exacta.
    menciona_pago = any(p in t for p in [
        "pago", "pagos", "gasto", "gastos", "costo", "costos",
        "cancelar", "cancela", "pagar", "se paga"
    ])
    menciona_extra = any(p in t for p in [
        "extra", "extras", "adicional", "adicionales",
        "aparte", "otro", "otros", "ademas", "adem├ís"
    ])

    return menciona_pago and menciona_extra



def seguimiento_gastos_adicionales(numero, texto):
    """Detecta seguimientos naturales a una conversaci├│n sobre pagos extra."""
    if ultima_intencion.get(numero) != "gastos_adicionales":
        return False

    t = texto.lower().strip()

    frases = [
        "cuanto es de cada uno", "cu├ínto es de cada uno",
        "cuanto cuesta cada uno", "cu├ínto cuesta cada uno",
        "cuanto vale cada uno", "cu├ínto vale cada uno",
        "y cuanto es de cada uno", "y cu├ínto es de cada uno",
        "y cuanto cuesta", "y cu├ínto cuesta",
        "cuanto cuestan", "cu├ínto cuestan",
        "dame los montos", "cuales son los montos", "cu├íles son los montos",
        "de cuanto es cada uno", "de cu├ínto es cada uno",
        "cuanto se paga", "cu├ínto se paga",
        "y de cuanto", "y de cu├ínto",
        "cuanto hay que pagar", "cu├ínto hay que pagar"
    ]

    return any(f in t for f in frases)


def respuesta_proyecto_pendiente_de_gastos(numero, texto):
    """
    Si primero preguntaron por pagos extra sin decir proyecto y despu├®s
    responden solamente con el nombre del proyecto, conserva la intenci├│n.
    """
    if ultima_intencion.get(numero) != "gastos_adicionales":
        return False

    detectado = detectar_proyecto_en_texto(texto)
    if not detectado:
        return False

    # Solo tratarlo como continuaci├│n si el mensaje es corto y principalmente
    # identifica el proyecto (ej. "Buenaventura cuyo").
    return len(texto.strip().split()) <= 6


def respuesta_gastos_adicionales(proyecto):
    if not proyecto:
        return "Claro ­ƒÿè ┬┐De cu├íl proyecto quieres conocer los gastos adicionales?"

    if proyecto == "palmeras":
        return (
            "S├¡ ­ƒÿè En Palmeras San Miguel los gastos adicionales son:\n\n"
            "ÔÇó Escrituraci├│n: Q3,500\n"
            "ÔÇó T├¡tulo de agua: Q3,500\n"
            "ÔÇó Mantenimiento: Q50 al mes\n"
            "ÔÇó Agua: Q50 por 30,000 litros\n\n"
            "­ƒôî El mantenimiento y la cuota de agua empiezan a pagarse "
            "cuando el proyecto ya est├® urbanizado; antes de eso no se cobran."
        )

    if proyecto == "vista_hermosa":
        return (
            "S├¡ ­ƒÿè En Ciudad Vista Hermosa los gastos adicionales son:\n\n"
            "ÔÇó Escrituraci├│n: Q3,500\n"
            "ÔÇó T├¡tulo de agua: Q3,500\n"
            "ÔÇó Mantenimiento: Q50 al mes\n"
            "ÔÇó Agua: Q50 por 30,000 litros\n\n"
            "­ƒôî El mantenimiento y la cuota de agua empiezan a pagarse "
            "cuando el proyecto ya est├® urbanizado; antes de eso no se cobran."
        )

    if proyecto == "buenaventura":
        return (
            "S├¡ ­ƒÿè En Buenaventura Cuyotenango los gastos adicionales son:\n\n"
            "ÔÇó Escrituraci├│n:\n"
            "  - 1 lote: Q6,000\n"
            "  - 2 lotes: Q8,400\n"
            "  - 3 lotes: Q10,800\n"
            "  - Cada lote adicional suma Q2,400\n"
            "ÔÇó T├¡tulo de agua: Q4,000\n"
            "ÔÇó Mantenimiento: Q100 al mes\n"
            "ÔÇó Agua: Q100 por 30,000 litros al mes"
        )

    return "No tengo cargados los gastos adicionales de ese proyecto."


def pide_ubicacion(texto):
    t = texto.lower()

    palabras = [
        "ubicacion", "ubicaci├│n",
        "donde queda", "d├│nde queda",
        "como llego", "c├│mo llego",
        "direccion", "direcci├│n",
        "mapa", "maps", "google maps",
        "mandame ubicacion", "m├índame ubicaci├│n",
        "manda ubicacion", "manda ubicaci├│n"
    ]

    return any(p in t for p in palabras)


def pregunta_como_llegar_o_mejor_ruta(texto):
    t = texto.lower()

    frases = [
        "por donde me voy", "por d├│nde me voy",
        "por donde puedo ir", "por d├│nde puedo ir",
        "por donde puedo venir", "por d├│nde puedo venir",
        "por donde se puede venir", "por d├│nde se puede venir",
        "por donde llego", "por d├│nde llego",
        "como llego", "c├│mo llego",
        "como me voy", "c├│mo me voy",
        "que ruta", "qu├® ruta",
        "mejor ruta", "ruta me recomiendas", "ruta recomienda",
        "puedo irme por la xochi", "puedo ir por la xochi",
        "puedo venir por la xochi", "se puede ir por la xochi",
        "se puede venir por la xochi",
        "puedo irme por xochi", "puedo ir por xochi",
        "por la xochi", "por xochi", "autopista xochi"
    ]

    return any(f in t for f in frases)



def respuesta_ruta_recomendada(proyecto):
    if proyecto == "buenaventura":
        return (
            "Para llegar a Buenaventura Cuyotenango te recomiendo venir por la "
            "Autopista Xochi ­ƒÜù­ƒøú´©Å. Te comparto tambi├®n el tarifario de la autopista "
            "para que tengas en cuenta el costo del recorrido ­ƒæç"
        )
    return None


def enviar_tarifario_xochi(numero):
    ruta = "media/general/tarifario_xochi.jpg"
    if os.path.exists(ruta):
        return enviar_imagen_whatsapp(
            numero,
            ruta,
            "Tarifario Autopista Xochi ­ƒøú´©Å­ƒÜù"
        )
    print("TARIFARIO XOCHI NO ENCONTRADO:", ruta)
    return False


UBICACIONES_PROYECTOS = {
    "palmeras": {
        "nombre": "Palmeras San Miguel",
        "texto": "Zona 5 de Retalhuleu, camino a La Verde / carretera hacia Las Pilas.",
        "maps": "https://maps.app.goo.gl/pBUyn98n8NCkGW8o6"
    },
    "vista_hermosa": {
        "nombre": "Vista Hermosa",
        "texto": "CA-2, km 188, Retalhuleu.",
        "maps": "https://maps.app.goo.gl/DCckHh97SMMPiLFS9"
    },
    "buenaventura": {
        "nombre": "Buenaventura Cuyotenango",
        "texto": "Km 168 de la carretera hacia la playa de Tulate, Cuyotenango.",
        "maps": "https://maps.app.goo.gl/4wTj52Ez32rdigXk8"
    }
}


def enviar_ubicacion_proyecto(numero, proyecto):
    if not proyecto:
        enviar_whatsapp(
            numero,
            "┬íClaro! ­ƒôì ┬┐De cu├íl proyecto necesitas la ubicaci├│n?"
        )
        return

    datos = UBICACIONES_PROYECTOS.get(proyecto)

    if not datos:
        enviar_whatsapp(
            numero,
            "No tengo cargada la ubicaci├│n de ese proyecto en este momento ­ƒôì."
        )
        return

    if cita_ya_cerrada(numero):
        enviar_whatsapp(
            numero,
            f"­ƒôì {datos['nombre']} est├í ubicado en {datos['texto']}\n\n"
            f"Google Maps:\n{datos['maps']}\n\n"
            "Tu visita ya est├í coordinada ­ƒÖî­ƒÅí."
        )
        return

    enviar_whatsapp(
        numero,
        f"┬íClaro! ­ƒôì {datos['nombre']} est├í ubicado en {datos['texto']}\n\n"
        f"Google Maps:\n{datos['maps']}\n\n"
        "Si deseas ir a conocer los lotes, av├¡same antes ­ƒÖî "
        "as├¡ coordinamos tu visita y podemos atenderte cuando llegues. "
        "┬┐Qu├® d├¡a tienes pensado ir? ­ƒôå"
    )



def marcar_multimedia_pendiente(numero):
    estado = obtener_estado_conversacion(numero)
    estado["multimedia_pendiente"] = True


def limpiar_multimedia_pendiente(numero):
    estado = obtener_estado_conversacion(numero)
    estado["multimedia_pendiente"] = False


def multimedia_pendiente(numero):
    return bool(
        obtener_estado_conversacion(numero).get("multimedia_pendiente")
    )


def pide_fotos(texto):
    t = texto.lower()

    palabras = [
        "foto", "fotos", "imagen", "imagenes", "im├ígenes",
        "muestrame fotos", "mu├®strame fotos",
        "ense├▒ame fotos", "ens├®├▒ame fotos",
        "como se ve", "c├│mo se ve"
    ]

    return any(p in t for p in palabras)


def pide_videos(texto):
    t = texto.lower()

    palabras = [
        "video", "videos", "v├¡deo", "v├¡deos",
        "recorrido", "tienes video", "tienes videos",
        "muestrame video", "mu├®strame video"
    ]

    return any(p in t for p in palabras)


# ============================================================
# MEMORIA DE CONVERSACIONES
# ============================================================

# Cada numero de WhatsApp tendra su propia conversacion.

conversaciones = {}

# ============================================================
# CRM / CONTROL MANUAL
# ============================================================
# Esta primera versi├│n vive en RAM junto con el bot.
# Permite ver chats nuevos, pausar IA y responder manualmente.
crm_mensajes = {}
crm_modo_manual = set()
crm_ultima_actividad = {}
crm_evento_contador = 0
lock_crm = Lock()

# ============================================================
# MEMORIA PERSISTENTE DE CLIENTES EN POSTGRESQL
# ============================================================
# La RAM sigue siendo la caché rápida. PostgreSQL guarda un snapshot
# por número para recuperar conversaciones, proyecto y estado tras
# reinicios o nuevos deploys de Render.
_memoria_db_initialized = False
lock_memoria_db = Lock()
_memoria_cargada = False

def memoria_db_disponible():
    return bool(DATABASE_URL and psycopg2)

def inicializar_memoria_db():
    global _memoria_db_initialized
    if not memoria_db_disponible():
        return False
    if _memoria_db_initialized:
        return True
    with lock_memoria_db:
        if _memoria_db_initialized:
            return True
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS crm_client_memory (
                            numero TEXT PRIMARY KEY,
                            snapshot JSONB NOT NULL,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                    """)
                conn.commit()
                _memoria_db_initialized = True
                print("MEMORIA DB: tabla lista")
                return True
            finally:
                conn.close()
        except Exception as exc:
            print("MEMORIA DB INIT ERROR:", exc)
            return False

def _snapshot_cliente(numero):
    numero = str(numero or "").strip()
    if not numero:
        return None

    estado = dict(estado_conversacion.get(numero, {}))
    proyecto = estado.get("proyecto_actual") or proyecto_activo.get(numero)
    visita = dict(estado_visitas.get(numero, {})) if numero in estado_visitas else None

    with lock_crm:
        mensajes_crm = list(crm_mensajes.get(numero, []))
        manual = numero in crm_modo_manual
        ultima_actividad = crm_ultima_actividad.get(numero)

    historial = list(conversaciones.get(numero, []))

    return {
        "numero": numero,
        "proyecto": proyecto,
        "estado_conversacion": estado,
        "ultima_intencion": ultima_intencion.get(numero),
        "presentado": numero in clientes_presentados,
        "estado_visita": visita,
        "historial": historial[-MAX_HISTORIAL:] if 'MAX_HISTORIAL' in globals() else historial[-12:],
        "crm_mensajes": mensajes_crm[-150:],
        "crm_manual": manual,
        "crm_ultima_actividad": ultima_actividad,
    }

def persistir_cliente(numero):
    """Guarda el estado actual del cliente. Si PostgreSQL falla, el bot sigue en RAM."""
    if not inicializar_memoria_db():
        return False
    snapshot = _snapshot_cliente(numero)
    if not snapshot:
        return False
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO crm_client_memory (numero, snapshot, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (numero) DO UPDATE SET
                        snapshot = EXCLUDED.snapshot,
                        updated_at = NOW()
                """, (str(numero), json.dumps(snapshot, ensure_ascii=False)))
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as exc:
        print("MEMORIA DB SAVE ERROR:", numero, exc)
        return False

def _aplicar_snapshot(numero, snap):
    global crm_evento_contador
    numero = str(numero or "").strip()
    if not numero or not isinstance(snap, dict):
        return False

    proyecto = snap.get("proyecto")
    if proyecto:
        proyecto_activo[numero] = proyecto

    estado = snap.get("estado_conversacion") or {}
    if not isinstance(estado, dict):
        estado = {}
    estado.setdefault("proyecto_actual", proyecto)
    estado.setdefault("esperando_preferencia_topografia", False)
    estado.setdefault("preferencia_topografia", None)
    estado.setdefault("topografia_en_conversacion", False)
    estado.setdefault("multimedia_pendiente", False)
    estado_conversacion[numero] = estado

    if snap.get("ultima_intencion") is not None:
        ultima_intencion[numero] = snap.get("ultima_intencion")

    if snap.get("presentado"):
        clientes_presentados.add(numero)

    visita = snap.get("estado_visita")
    if isinstance(visita, dict):
        estado_visitas[numero] = visita

    historial = snap.get("historial") or []
    if isinstance(historial, list):
        conversaciones[numero] = historial[-12:]

    mensajes = snap.get("crm_mensajes") or []
    if isinstance(mensajes, list):
        with lock_crm:
            crm_mensajes[numero] = mensajes[-150:]
            if snap.get("crm_manual"):
                crm_modo_manual.add(numero)
            else:
                crm_modo_manual.discard(numero)
            crm_ultima_actividad[numero] = snap.get("crm_ultima_actividad") or time.time()
            for m in mensajes:
                try:
                    crm_evento_contador = max(crm_evento_contador, int(m.get("id", 0)))
                except Exception:
                    pass
    return True

def cargar_memoria_persistente():
    global _memoria_cargada
    if _memoria_cargada:
        return 0
    if not inicializar_memoria_db():
        return 0
    total = 0
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT numero, snapshot FROM crm_client_memory ORDER BY updated_at ASC")
                filas = cur.fetchall()
        finally:
            conn.close()
        for numero, snap in filas:
            if isinstance(snap, str):
                snap = json.loads(snap)
            if _aplicar_snapshot(numero, snap):
                total += 1
        _memoria_cargada = True
        print(f"MEMORIA DB: {total} clientes restaurados")
        return total
    except Exception as exc:
        print("MEMORIA DB LOAD ERROR:", exc)
        return 0

def importar_respaldo_clientes(data):
    """Importa el respaldo JSON creado desde /crm/data y lo deja persistido."""
    global crm_evento_contador
    if not isinstance(data, dict):
        raise ValueError("El respaldo no tiene un formato válido")
    convs = data.get("conversaciones") or {}
    if not isinstance(convs, dict):
        raise ValueError("El respaldo no contiene conversaciones")

    mapa_proyectos = {
        "Vista Hermosa": "vista_hermosa",
        "Ciudad Vista Hermosa": "vista_hermosa",
        "Palmeras San Miguel": "palmeras",
        "Buenaventura Cuyotenango": "buenaventura",
        "Buenaventura": "buenaventura",
    }
    importados = 0
    mensajes_total = 0

    for numero, info in convs.items():
        if not isinstance(info, dict):
            continue
        numero = str(numero).strip()
        if not numero:
            continue
        proyecto_txt = info.get("proyecto")
        proyecto = mapa_proyectos.get(proyecto_txt, proyecto_txt if proyecto_txt in {"vista_hermosa", "palmeras", "buenaventura"} else None)
        mensajes = info.get("mensajes") or []
        if not isinstance(mensajes, list):
            mensajes = []

        proyecto_activo[numero] = proyecto if proyecto else proyecto_activo.get(numero)
        estado_conversacion[numero] = {
            "proyecto_actual": proyecto,
            "esperando_preferencia_topografia": False,
            "preferencia_topografia": None,
            "topografia_en_conversacion": False,
            "multimedia_pendiente": False,
        }
        clientes_presentados.add(numero)

        historial = []
        for m in mensajes:
            if not isinstance(m, dict):
                continue
            contenido = str(m.get("contenido") or "").strip()
            direccion = m.get("direccion")
            if contenido and direccion in {"in", "out"}:
                historial.append({"role": "user" if direccion == "in" else "assistant", "content": contenido})
            try:
                crm_evento_contador = max(crm_evento_contador, int(m.get("id", 0)))
            except Exception:
                pass
        conversaciones[numero] = historial[-12:]

        with lock_crm:
            crm_mensajes[numero] = mensajes[-150:]
            if info.get("manual"):
                crm_modo_manual.add(numero)
            else:
                crm_modo_manual.discard(numero)
            crm_ultima_actividad[numero] = time.time()

        persistir_cliente(numero)
        importados += 1
        mensajes_total += len(mensajes)

    return {"clientes_importados": importados, "mensajes_importados": mensajes_total}

# Suscripciones Web Push activadas desde tus dispositivos.
# La RAM se mantiene como cach├®, pero PostgreSQL es la fuente persistente.
crm_push_subscriptions = {}
lock_push = Lock()
ultimo_error_push = None
ultimo_resultado_push = None
_push_db_initialized = False
lock_push_db = Lock()


def push_db_disponible():
    return bool(DATABASE_URL and psycopg2)


def inicializar_push_db():
    """Crea la tabla de suscripciones si todav├¡a no existe."""
    global _push_db_initialized

    if not push_db_disponible():
        return False

    if _push_db_initialized:
        return True

    with lock_push_db:
        if _push_db_initialized:
            return True

        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS crm_push_subscriptions (
                            endpoint TEXT PRIMARY KEY,
                            subscription JSONB NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                    """)
                conn.commit()
                _push_db_initialized = True
                print("PUSH DB: tabla lista")
                return True
            finally:
                conn.close()

        except Exception as exc:
            print("PUSH DB INIT ERROR:", exc)
            return False


def guardar_push_subscription(sub):
    endpoint = (sub or {}).get("endpoint")
    if not endpoint:
        return False

    # Cach├® RAM
    with lock_push:
        crm_push_subscriptions[endpoint] = sub

    # Persistencia PostgreSQL
    if not inicializar_push_db():
        return False

    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO crm_push_subscriptions (
                        endpoint,
                        subscription,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s::jsonb, NOW(), NOW())
                    ON CONFLICT (endpoint)
                    DO UPDATE SET
                        subscription = EXCLUDED.subscription,
                        updated_at = NOW()
                """, (
                    endpoint,
                    json.dumps(sub)
                ))
            conn.commit()
            return True
        finally:
            conn.close()

    except Exception as exc:
        print("PUSH DB SAVE ERROR:", exc)
        return False


def cargar_push_subscriptions():
    """
    Devuelve todas las suscripciones conocidas.
    Si hay PostgreSQL, siempre lee desde ah├¡ para sobrevivir reinicios.
    """
    encontrados = {}

    if inicializar_push_db():
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT endpoint, subscription
                        FROM crm_push_subscriptions
                        ORDER BY updated_at DESC
                    """)
                    for endpoint, subscription in cur.fetchall():
                        # psycopg2 suele entregar JSONB como dict.
                        if isinstance(subscription, str):
                            try:
                                subscription = json.loads(subscription)
                            except Exception:
                                continue

                        if isinstance(subscription, dict):
                            encontrados[endpoint] = subscription
            finally:
                conn.close()

        except Exception as exc:
            print("PUSH DB LOAD ERROR:", exc)

    # Si DB est├í temporalmente ca├¡da, usamos la cach├® RAM.
    if not encontrados:
        with lock_push:
            encontrados = dict(crm_push_subscriptions)
    else:
        with lock_push:
            crm_push_subscriptions.clear()
            crm_push_subscriptions.update(encontrados)

    return encontrados


def eliminar_push_subscription(endpoint):
    if not endpoint:
        return

    with lock_push:
        crm_push_subscriptions.pop(endpoint, None)

    if inicializar_push_db():
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM crm_push_subscriptions WHERE endpoint = %s",
                        (endpoint,)
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            print("PUSH DB DELETE ERROR:", exc)


def contar_push_devices():
    return len(cargar_push_subscriptions())



def preparar_vapid_private_key():
    key = (VAPID_PRIVATE_KEY or "").strip()
    if not key:
        return ""

    try:
        padding = "=" * ((4 - len(key) % 4) % 4)
        raw = base64.urlsafe_b64decode(key + padding)

        if len(raw) == 32 and ec is not None and serialization is not None:
            private_value = int.from_bytes(raw, "big")
            private_key = ec.derive_private_key(private_value, ec.SECP256R1())

            der = private_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )

            return base64.urlsafe_b64encode(der).decode().rstrip("=")
    except Exception as exc:
        print("VAPID conversion raw->DER:", exc)

    return key


def enviar_push_crm(numero, contenido, event_id=None):
    global ultimo_error_push, ultimo_resultado_push

    ultimo_error_push = None
    ultimo_resultado_push = None

    if not webpush:
        ultimo_error_push = "pywebpush no est├í disponible en el servidor."
        return {"ok": False, "error": ultimo_error_push, "enviadas": 0}

    if not VAPID_PRIVATE_KEY:
        ultimo_error_push = "VAPID_PRIVATE_KEY no est├í configurada."
        return {"ok": False, "error": ultimo_error_push, "enviadas": 0}

    private_key_compatible = preparar_vapid_private_key()

    proyecto = crm_nombre_proyecto(numero)
    proyecto_txt = f" ┬À {proyecto}" if proyecto and proyecto != "Sin proyecto" else ""

    push_id = str(event_id or time.time_ns())

    payload = json.dumps({
        "title": "­ƒÅí Nuevo mensaje de cliente",
        "body": f"+{numero}{proyecto_txt}\n{str(contenido)[:180]}",
        "url": f"/crm?numero={numero}",
        # Cada mensaje de WhatsApp usa su propio tag.
        # As├¡ Android/Chrome no sustituye una notificaci├│n por otra.
        "tag": f"crm-{push_id}",
        "message_id": push_id,
        "timestamp": int(time.time() * 1000)
    }, ensure_ascii=False)

    # Leer suscripciones persistentes en CADA env├¡o.
    # As├¡ un webhook que despierta a Render puede notificar aunque
    # el CRM no haya sido abierto despu├®s del reinicio.
    subs = list(cargar_push_subscriptions().items())

    if not subs:
        ultimo_error_push = "No hay tel├®fonos suscritos actualmente."
        print("WEB PUSH:", ultimo_error_push)
        return {"ok": False, "error": ultimo_error_push, "enviadas": 0}

    enviadas = 0
    errores = []
    vencidas = []

    for endpoint, sub in subs:
        try:
            respuesta = webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=private_key_compatible,
                vapid_claims={"sub": VAPID_SUBJECT},
                ttl=600,
                timeout=20,
                headers={
                    "Urgency": "high"
                }
            )
            status = getattr(respuesta, "status_code", None)
            print("WEB PUSH OK:", status, endpoint[:70])
            enviadas += 1
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            body = ""
            try:
                body = exc.response.text if exc.response is not None else ""
            except Exception:
                pass
            msg = f"HTTP {status}: {exc}"
            if body:
                msg += f" | {body[:300]}"
            print("WEB PUSH ERROR:", msg)
            errores.append(msg)
            if status in (404, 410):
                vencidas.append(endpoint)
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            print("WEB PUSH ERROR GENERAL:", msg)
            errores.append(msg)

    if vencidas:
        for endpoint in vencidas:
            eliminar_push_subscription(endpoint)

    if enviadas:
        ultimo_resultado_push = f"{enviadas} notificaci├│n(es) enviada(s)."
    if errores:
        ultimo_error_push = " | ".join(errores[-3:])

    return {
        "ok": enviadas > 0,
        "enviadas": enviadas,
        "error": ultimo_error_push
    }



def crm_hora_actual():
    return datetime.now(
        ZoneInfo("America/Guatemala")
    ).strftime("%d/%m %I:%M %p")



def enviar_ntfy_crm(numero, contenido, event_id=None):
    """
    Env├¡a UNA notificaci├│n ntfy por CADA mensaje entrante de WhatsApp.
    No depende de que Chrome, el CRM o una pesta├▒a est├®n abiertos.
    """
    if not NTFY_TOPIC:
        print("NTFY: NTFY_TOPIC no est├í configurado.")
        return False

    numero_txt = str(numero or "Cliente")
    contenido_txt = str(contenido or "Nuevo mensaje").strip()

    proyecto = crm_nombre_proyecto(numero)
    proyecto_txt = (
        f" ┬À {proyecto}"
        if proyecto and proyecto != "Sin proyecto"
        else ""
    )

    # Abrir directamente la conversaci├│n del cliente en el CRM.
    click_url = f"{CRM_PUBLIC_URL}?numero={numero_txt}"

    try:
        respuesta = requests.post(
            f"{NTFY_SERVER}/{NTFY_TOPIC}",
            data=contenido_txt.encode("utf-8"),
            headers={
                "Title": f"Nuevo mensaje - CRM Gabriel",
                "Priority": "high",
                "Tags": "house,phone",
                "Click": click_url,
                # Identificador ├║nicamente para diagn├│stico.
                "X-Message-ID": str(event_id or time.time_ns())
            },
            timeout=12
        )

        print(
            "NTFY:",
            respuesta.status_code,
            numero_txt,
            proyecto_txt,
            contenido_txt[:80]
        )

        return 200 <= respuesta.status_code < 300

    except Exception as exc:
        print("NTFY ERROR:", exc)
        return False


def crm_registrar_mensaje(numero, direccion, contenido, event_id=None):
    global crm_evento_contador

    if not numero:
        return

    contenido = str(contenido or "").strip()
    if not contenido:
        return

    with lock_crm:
        crm_evento_contador += 1

        lista = crm_mensajes.setdefault(numero, [])
        lista.append({
            "id": crm_evento_contador,
            "numero": numero,
            "direccion": direccion,
            "contenido": contenido,
            "hora": crm_hora_actual()
        })

        # Mantener suficiente historial visual sin consumir RAM sin l├¡mite.
        if len(lista) > 150:
            crm_mensajes[numero] = lista[-150:]

        crm_ultima_actividad[numero] = time.time()

    persistir_cliente(numero)

    # Solo los mensajes ENTRANTES del cliente generan push.
    if direccion == "in":
        # Web Push anterior (lo dejamos activo por ahora).
        Thread(
            target=enviar_push_crm,
            args=(numero, contenido, event_id),
            daemon=True
        ).start()

        # NTFY: notificaci├│n nativa en Android por CADA mensaje.
        Thread(
            target=enviar_ntfy_crm,
            args=(numero, contenido, event_id),
            daemon=True
        ).start()


def crm_resumen_entrante(mensaje):
    tipo = mensaje.get("type")

    if tipo == "text":
        return mensaje.get("text", {}).get("body", "")

    if tipo == "audio":
        return "­ƒÄÖ´©Å Audio recibido"

    if tipo == "image":
        caption = mensaje.get("image", {}).get("caption", "")
        return "­ƒôÀ Imagen recibida" + (f": {caption}" if caption else "")

    if tipo == "video":
        caption = mensaje.get("video", {}).get("caption", "")
        return "­ƒÄÑ Video recibido" + (f": {caption}" if caption else "")

    if tipo == "document":
        nombre = mensaje.get("document", {}).get("filename", "")
        return "­ƒôä Documento recibido" + (f": {nombre}" if nombre else "")

    return f"­ƒô® Mensaje recibido ({tipo or 'desconocido'})"


def crm_esta_manual(numero):
    with lock_crm:
        return numero in crm_modo_manual


def crm_poner_manual(numero):
    with lock_crm:
        crm_modo_manual.add(numero)
    persistir_cliente(numero)


def crm_poner_ia(numero):
    with lock_crm:
        crm_modo_manual.discard(numero)
    persistir_cliente(numero)


def crm_autorizado():
    if not CRM_PASSWORD:
        return False

    auth = request.authorization
    return bool(
        auth
        and auth.username == CRM_USER
        and auth.password == CRM_PASSWORD
    )


def crm_pedir_login():
    if not CRM_PASSWORD:
        return Response(
            "CRM_PASSWORD no est├í configurado en Render.",
            status=503,
            content_type="text/plain; charset=utf-8"
        )

    return Response(
        "Acceso requerido",
        status=401,
        headers={
            "WWW-Authenticate": 'Basic realm="CRM Gabriel", charset="UTF-8"'
        }
    )


def crm_nombre_proyecto(numero):
    nombres = {
        "palmeras": "Palmeras San Miguel",
        "vista_hermosa": "Vista Hermosa",
        "buenaventura": "Buenaventura Cuyotenango"
    }
    return nombres.get(
        proyecto_activo.get(numero),
        "Sin proyecto"
    )



# Maximo de mensajes anteriores que recordara temporalmente.
MAX_HISTORIAL = 12


# ============================================================
# PAGINA PRINCIPAL
# ============================================================

@app.route("/")
def home():
    return "Bot inmobiliario Gabriel funcionando correctamente"


# ============================================================
# VERIFICACION DEL WEBHOOK DE META
# ============================================================

@app.route("/webhook", methods=["GET"])
def verificar_webhook():

    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == VERIFY_TOKEN:
        print("Webhook verificado correctamente")
        return challenge, 200

    return "Token incorrecto", 403


# ============================================================
# CARGAR INFORMACION DE LOS PROYECTOS
# ============================================================

def cargar_contexto():

    try:

        with open("contexto.txt", "r", encoding="utf-8") as archivo:
            return archivo.read()

    except Exception as error:

        print("ERROR LEYENDO contexto.txt:")
        print(error)

        return ""


# ============================================================
# MEMORIA DEL CLIENTE
# ============================================================

def obtener_historial(numero_cliente):

    if numero_cliente not in conversaciones:
        conversaciones[numero_cliente] = []

    return conversaciones[numero_cliente]


def guardar_mensaje(numero_cliente, rol, contenido):

    historial = obtener_historial(numero_cliente)

    historial.append({
        "role": rol,
        "content": contenido
    })

    # Evita conversaciones demasiado largas.
    if len(historial) > MAX_HISTORIAL:

        conversaciones[numero_cliente] = historial[-MAX_HISTORIAL:]

    persistir_cliente(numero_cliente)


# ============================================================
# GENERAR RESPUESTA CON OPENAI
# ============================================================

def generar_respuesta(numero_cliente, mensaje_cliente):

    try:

        contexto = cargar_contexto()

        historial = obtener_historial(numero_cliente)

        proyecto_memoria = proyecto_activo.get(numero_cliente)

        nombres_proyecto = {
            "palmeras": "Palmeras San Miguel",
            "vista_hermosa": "Vista Hermosa",
            "buenaventura": "Buenaventura Cuyotenango"
        }

        proyecto_actual_texto = nombres_proyecto.get(
            proyecto_memoria,
            "NINGUNO"
        )

        cita_cerrada_actual = cita_ya_cerrada(numero_cliente)


        # ====================================================
        # PERSONALIDAD Y REGLAS DEL BOT
        # ====================================================

        instrucciones = f"""
Tu nombre es Gabriel Polero y atiendes consultas sobre tus proyectos
inmobiliarios mediante WhatsApp.

Habla siempre en PRIMERA PERSONA como Gabriel.

NO digas:

- "Soy el asistente virtual de Gabriel"
- "Soy una inteligencia artificial"
- "Gabriel puede ayudarte"
- "Voy a comunicarte con Gabriel"
- "Seg├║n mi base de datos"
- "Seg├║n el contexto proporcionado"
- "Como inteligencia artificial"

Habla de manera natural desde el WhatsApp comercial de Gabriel Polero.

No afirmes que Gabriel est├í escribiendo manualmente en ese momento.
Simplemente conversa en primera persona.


============================================================
INFORMACION OFICIAL DE LOS PROYECTOS
============================================================

{contexto}

============================================================
PROYECTO ACTIVO DE ESTA CONVERSACION
============================================================

Proyecto activo actual: {proyecto_actual_texto}
Cita ya cerrada en esta conversaci├│n: {cita_cerrada_actual}

Si el proyecto activo actual NO es "NINGUNO":

- Debes asumir que todas las preguntas siguientes se refieren a ese proyecto.
- NO preguntes nuevamente "┬┐de cu├íl proyecto?".
- NO vuelvas a pedir confirmaci├│n del proyecto.
- Mant├®n ese proyecto como contexto hasta que el cliente mencione claramente otro.
- Si pregunta "┬┐tienes cotizaci├│n?", "┬┐y el precio?", "┬┐y la ubicaci├│n?",
  "┬┐qu├® amenidades tiene?", "┬┐y a 5 a├▒os?", debes responder sobre el proyecto activo.
- Solo cambia de proyecto cuando el cliente mencione expl├¡citamente otro proyecto
  o un sector que corresponda claramente a otro proyecto.

Ejemplo:
Cliente: "Me interesa Palmeras San Miguel"
Despu├®s: "┬┐Tienes la cotizaci├│n?"
Debes entender que pide la cotizaci├│n de PALMERAS SAN MIGUEL.
NO debes preguntar nuevamente qu├® proyecto le interesa.


============================================================
REGLA CRITICA: NUNCA MEZCLAR PROYECTOS





============================================================
REGLA CRITICA: RESPONDER COMO VENDEDOR, NO COMO MENU
============================================================

Interpreta la intenci├│n REAL del cliente usando el mensaje actual, el historial,
el proyecto activo y lo que ya se le respondi├│ o envi├│.

Si el cliente hace una pregunta de seguimiento, responde ESA pregunta directamente.
NO repitas una explicaci├│n completa que ya acabas de dar si no hace falta.

Ejemplos:
- Si ya se envi├│ una cotizaci├│n y pregunta:
  "┬┐Ese es el precio de un lote plano?"
  responde brevemente que s├¡: el precio mostrado corresponde a esa medida/fase
  y la topograf├¡a no cambia el precio del lote.
  NO vuelvas a explicar todas las ventajas de plano vs inclinado.
  NO vuelvas a enviar cotizaciones por esa sola pregunta.

- Si pregunta "┬┐Y uno inclinado cuesta m├ís?"
  responde que no, el precio del lote no cambia por la topograf├¡a.
  Aclara solo si ayuda que el costo de construcci├│n s├¡ puede variar por dise├▒o,
  cimentaci├│n o movimiento de tierra.

- Si dice "Prefiero plano" o "Prefiero inclinado",
  reconoce la preferencia y contin├║a sin repetir todo lo anterior.

Cuando la informaci├│n disponible NO alcance para responder con certeza:
- NO inventes;
- NO repitas una respuesta anterior;
- responde de forma breve:
  "D├®jame revisar exactamente lo que me solicitas y te lo env├¡o en un momento ­ƒÿè"
  o una variante natural equivalente.

============================================================
REGLA DE TOPOGRAFIA: PLANO VS CROQUIS
============================================================

Distingue SIEMPRE:

1. PLANO / CROQUIS / MAPA:
   "m├índame el plano", "plano del proyecto", "croquis",
   "mapa de lotes", "distribuci├│n de lotes".
   Esto se refiere al documento o PDF.

2. TERRENO PLANO / LLANO:
   "lote plano", "terreno plano", "quiero uno plano",
   "┬┐ese precio es de un lote plano?", "lote inclinado",
   "terreno quebrado", "topograf├¡a".
   Esto se refiere a la TOPOGRAF├ìA, no al PDF.

Datos oficiales sobre topograf├¡a:
- Buenaventura Cuyotenango: los lotes se manejan en topograf├¡a plana.
- Palmeras San Miguel: los lotes se manejan en topograf├¡a plana.
- Vista Hermosa: hay lotes planos y tambi├®n lotes quebrados/inclinados.
- El precio de venta del lote NO cambia por ser plano, inclinado o quebrado.
- El precio depende de la medida y fase correspondiente.
- Terreno plano: suele facilitar dise├▒os convencionales, accesos, patios
  y puede requerir menos adaptaci├│n inicial.
- Terreno inclinado/quebrado: puede aprovecharse para dise├▒os escalonados,
  varios niveles, terrazas o arquitectura adaptada a la pendiente.
- El costo de construcci├│n s├¡ puede variar seg├║n dise├▒o, cimentaci├│n
  y movimiento de tierra.
- Si el cliente expresa preferencia, resp├│ndele sobre esa preferencia sin repetir
  informaci├│n innecesaria.

REGLA DE AUDIOS:
Las notas de voz se transcriben autom├íticamente y el texto transcrito entra
por el mismo flujo que un mensaje escrito. No pidas al cliente que repita por
escrito si la transcripci├│n fue exitosa. Responde directamente a lo que dijo.

Si en el audio pide precio, cotizaci├│n, ubicaci├│n, requisitos, gastos
adicionales, financiamiento o cualquier dato cargado, aplica exactamente las
mismas reglas que con texto.






REGLA DE CONSULTA DE CUOTAS:
Si el cliente pregunta espec├¡ficamente cu├ínto paga a un plazo concreto
(por ejemplo "┬┐cu├ínto es la cuota a 7 a├▒os?"), responde el monto cargado.
NO vuelvas a mandar las im├ígenes de cotizaci├│n en esa pregunta.
Si existen varias medidas o fases, lista ├║nicamente las cuotas de ese plazo,
de forma breve.

REGLA DE XOCHI:
Si el cliente pregunta si puede llegar por la Autopista Xochi a Buenaventura,
responde que s├¡/recomi├®ndala y el sistema enviar├í autom├íticamente el tarifario.
No interpretes "puedo ir por la Xochi" como intenci├│n de agendar una visita.


REGLA DE ESCRITURAS:
Las escrituras son registradas. Si preguntan por escritura, plazo de entrega
o certeza de la escritura, responde con seguridad que son escrituras registradas
y que el plazo aproximado de entrega es de 3 meses.

REGLA DE TITULO DE AGUA:
El t├¡tulo de agua es un pago ├║nico.
La residencial tiene agua propia mediante pozo mec├ínico y tanques elevados,
lo que permite disponibilidad de agua las 24 horas del d├¡a.
Si preguntan por qu├® se cobra el t├¡tulo de agua, explica esto directamente.
Montos:
- Palmeras San Miguel: Q3,500.
- Vista Hermosa: Q3,500.
- Buenaventura Cuyotenango: Q4,000.

REGLA DE MANTENIMIENTO - PRIORIDAD:
Si el cliente pregunta qu├® incluye, para qu├® sirve o por qu├® se paga el mantenimiento,
NO env├¡es la lista completa de gastos adicionales. Responde ├║nicamente qu├® cubre el mantenimiento:
- limpieza de ├íreas y calles;
- mantenimiento de la planta de tratamiento;
- mantenimiento de amenidades;
- jardinizaci├│n de ├íreas verdes;
- limpieza de lotes que a├║n no est├®n circulados.

REGLA CRITICA DE COSTOS ADICIONALES:
Si el cliente pregunta si hay alg├║n costo adicional, gasto extra, pago aparte,
escrituraci├│n, t├¡tulo de agua, mantenimiento o cuota de agua:
- usa SIEMPRE los montos cargados del proyecto activo;
- menciona DE UNA VEZ cu├ínto cuesta cada concepto;
- NO ocultes un monto que ya est├í cargado;
- NO digas "no tengo el monto cargado" cuando el sistema s├¡ lo tiene;
- NO digas "d├®jame confirmar";
- NO digas "te lo verifico";
- NO digas "┬┐quieres que te lo confirme?";
- NO digas "┬┐quieres que confirme los montos?";
- NO prometas responder despu├®s;
- NO cierres esta respuesta con una pregunta artificial;
- responde directamente con los montos exactos y termina de forma natural.

Ejemplo para Buenaventura Cuyotenango:
ÔÇó Escrituraci├│n: 1 lote Q6,000; 2 lotes Q8,400; 3 lotes Q10,800; cada lote adicional Q2,400.
ÔÇó T├¡tulo de agua: Q4,000.
ÔÇó Mantenimiento: Q100 al mes.
ÔÇó Agua: Q100 al mes por 30,000 litros.

REGLA CRITICA DE INFORMACION GENERAL Y ENGANCHE:
- NUNCA menciones la cantidad total de lotes ni la cantidad de lotes por fase
  en una respuesta general. Esa informaci├│n SOLO se da cuando el cliente
  pregunta expl├¡citamente cu├íntos lotes hay o cu├íntos lotes tiene una fase.
- No uses la expresi├│n "medida de referencia".
- Para Palmeras San Miguel las ├║nicas medidas cargadas son 8x16 y 8x18.
- Para Buenaventura Cuyotenango las ├║nicas medidas cargadas son 8x16, 8x18 y 9x20.
- Para Vista Hermosa la medida cargada es 8x16 en Fase F y Fase G.
- NUNCA respondas con el precio m├ís bajo del proyecto cuando el cliente menciona una medida concreta.
  Usa SIEMPRE el precio y enganche exactos de esa medida/fase:
  Palmeras: 8x16 = Q67,200 / enganche Q6,000; 8x18 = Q79,200 / enganche Q8,000.
  Buenaventura: 8x16 = desde Q83,200 / enganche Q6,000; 8x18 = Q93,600 / enganche Q8,000; 9x20 = Q117,000 / enganche Q10,000.
  Vista Hermosa: 8x16 Fase F = Q83,200 / enganche Q6,000; 8x16 Fase G = Q89,600 / enganche Q6,000.
- En una respuesta general puedes decir que los enganches son DESDE Q6,000.
- El enganche se puede fraccionar en 2 pagos mensuales.
- En una respuesta general basta con decir:
  "Enganche desde Q6,000 y opci├│n de fraccionarlo en 2 pagos mensuales."
- Si el cliente pregunta espec├¡ficamente por el enganche, el sistema tiene una
  respuesta especial con Q3,000 + Q3,000 y la fecha de la primera cuota.
- NO digas "confirmar condiciones actuales" respecto al enganche.
- NO digas que debes confirmar el monto del enganche.
- NO inventes otra cantidad de enganche.

REGLA DE CANTIDAD DE LOTES:
Si preguntan cu├íntos lotes tiene el proyecto, responde con estos datos:
- Buenaventura Cuyotenango: 2,600 lotes.
- Palmeras San Miguel: Fase 1 = 1,700 lotes; Fase 2 = 1,900 lotes.
- Vista Hermosa: Fase F = 1,100 lotes; Fase G = 1,000 lotes.
No digas que debes confirmar y no inventes otras cantidades.

REGLA ESPECIFICA DE PALMERAS SAN MIGUEL - INFORMACION GENERAL:
Si el cliente simplemente pide informaci├│n de Palmeras San Miguel, puedes incluir de forma breve:
- Ubicaci├│n: Zona 5 de Retalhuleu, camino a La Verde / carretera hacia Las Pilas.
- Medidas disponibles: 8x16 y 8x18.
- Precio general: desde Q67,200. Si el cliente menciona 8x18, NO uses ese precio general: 8x18 cuesta Q79,200.
- Enganche: desde Q6,000, con opci├│n de fraccionarlo en 2 pagos mensuales.
- Financiamiento propio hasta 8 a├▒os y posibilidad de abonos a capital.
- Amenidades y servicios disponibles.
NO incluyas cantidad de lotes por fase, salvo que el cliente lo pregunte expl├¡citamente.
NO digas "medida de referencia".

REGLA DE CLIMA:
Si preguntan por el clima del lugar, responde:
"S├¡ ­ƒÿè Por ac├í tenemos el caracter├¡stico clima c├ílido de costa ÔÿÇ´©Å­ƒî┤. Y justamente por eso se disfrutan mucho las piscinas, ├íreas verdes y dem├ís amenidades del proyecto. ­ƒÅè­ƒî┐"
No inventes temperaturas espec├¡ficas.

REGLA DE MANTENIMIENTO:
Si preguntan qu├® incluye o qu├® cubre el mantenimiento, responde que incluye:
- limpieza de ├íreas comunes y calles;
- mantenimiento de la planta de tratamiento;
- mantenimiento de amenidades;
- jardinizaci├│n de ├íreas verdes;
- limpieza de lotes que a├║n no est├®n circulados.
Responde con seguridad y de forma breve.

REGLA DE REQUISITOS DE FINANCIAMIENTO:
Si el cliente pregunta por "papeles", "documentos" o "requisitos" para el
financiamiento, responde los requisitos cargados. NO env├¡es cotizaci├│n solo
porque el mensaje mencione "8 a├▒os", "6 a├▒os" u otro plazo.

REGLA DE ESCRITURA:
Si preguntan cu├ínto tarda en entregarse la escritura, responde con seguridad:
"aproximadamente 3 meses". No digas que debes confirmarlo.

REGLA DE CANTIDAD DE PISCINAS:
- Buenaventura Cuyotenango: 2 piscinas.
- Vista Hermosa: 1 piscina.
- Palmeras San Miguel: 1 piscina.
Si preguntan cu├íntas hay, responde la cantidad exacta. No digas que debes confirmar.

REGLA DE CITA YA COORDINADA:
Si la cita ya tiene proyecto, d├¡a y hora:
- NO vuelvas a ofrecer una visita.
- NO preguntes qu├® otro d├¡a puede.
- NO preguntes nuevamente d├¡a u hora.
- NO cierres otras respuestas con una invitaci├│n a agendar.
- Si pregunta ubicaci├│n o indicaciones, responde eso ├║nicamente y recuerda brevemente que la visita ya est├í coordinada.
- Solo cambia la cita si el cliente pide expl├¡citamente reprogramar/cambiar/cancelar.

REGLA DE RUTA POR AUTOPISTA XOCHI:
Si el cliente pregunta por d├│nde le conviene llegar y el proyecto es Buenaventura
Cuyotenango, recomienda con seguridad la Autopista Xochi. El sistema enviar├í
autom├íticamente el tarifario cuando corresponda. No inventes tarifas en texto.

REGLA DE PLAZO DE URBANIZACION:
Si preguntan cu├ínto tarda en terminarse, entregarse o urbanizarse un proyecto,
responde con seguridad que el plazo aproximado es de 1 a 2 a├▒os.
No digas "d├®jame confirmar", "te aviso despu├®s" ni prometas responder m├ís tarde.

REGLA DE AMENIDADES:
Si preguntan espec├¡ficamente por piscina, cancha, casa club/sal├│n,
juegos infantiles, ├íreas verdes o caminamientos:
- responde primero si est├í disponible;
- el sistema enviar├í material visual relacionado;
- no hagas una explicaci├│n larga;
- no preguntes si desea fotos: env├¡alas directamente junto con videos;
- usa emojis naturales.

REGLA DE BANCO - PRIORIDAD:
Si el cliente menciona "banco" junto con "financiamiento", aunque la frase est├® mal redactada,
responde ├║nicamente que el financiamiento es propio y directo con la empresa y que no trabajamos
con ning├║n banco. NO env├¡es cotizaciones, precios ni informaci├│n general del proyecto en esa respuesta.

REGLA CRITICA DE FINANCIAMIENTO:
- TODO financiamiento mencionado en esta conversaci├│n es financiamiento PROPIO Y DIRECTO CON LA EMPRESA.
- NO trabajamos con ning├║n banco.
- Si el cliente pregunta "┬┐con qu├® banco?", "┬┐de qu├® banco es el financiamiento?" o algo equivalente, responde de forma segura:
  "El financiamiento es propio y directo con la empresa ­ƒÿè­ƒÅí. No trabajamos con ning├║n banco, as├¡ que el proceso se realiza directamente con nosotros."
- Siempre que expliques precios, cuotas, plazos o financiamiento, menciona naturalmente que el financiamiento es propio.
- No inventes bancos, tasas bancarias, aprobaciones bancarias ni requisitos de bancos.
- No repitas esta aclaraci├│n varias veces en el mismo mensaje: una menci├│n clara es suficiente.

REGLA DE PUNTO DE ENCUENTRO:
Si el cliente pregunta d├│nde pueden juntarse:
- Sugiere primero encontrarse directamente en el proyecto.
- Despu├®s ofrece UN punto cercano conocido cuando est├® cargado.
- Tambi├®n permite que el cliente proponga otro lugar.
- No hagas varias preguntas seguidas.
- No vuelvas a ofrecer cotizaci├│n, financiamiento o requisitos en esa respuesta.
- Responde de forma breve y pr├íctica.

Puntos sugeridos cargados:
- Palmeras San Miguel: Centro Comercial La Trinidad como alternativa.
- Buenaventura Cuyotenango: Parque Central de Cuyotenango como alternativa.
- Vista Hermosa: directamente en el proyecto sobre CA-2 km 188; si prefiere otro punto cercano sobre la ruta, puede indicarlo.

REGLA DE CITA CERRADA:
Cuando ya exista d├¡a y hora definidos para una visita:
- La cita se considera cerrada.
- NO hagas preguntas adicionales.
- NO ofrezcas indicaciones, ruta, cotizaciones, financiamiento, requisitos ni otra informaci├│n por iniciativa propia.
- NO agregues CTA despu├®s de confirmar.
- Termina el mensaje justo despu├®s de confirmar d├¡a, hora y proyecto.
- Si el cliente luego hace una pregunta concreta, responde ├║nicamente esa pregunta y NO cierres con otra pregunta.
- Si el cliente solo dice "gracias", responde breve, por ejemplo: "┬íCon gusto! ­ƒÖî Nos vemos el jueves."

REGLA DE PROCESO DE COMPRA Y SEGUIMIENTOS:
- Si el cliente pregunta "cu├íl es el proceso de compra", "c├│mo se compra", "c├│mo comprar",
  "qu├® necesito para comprar" o equivalente, explica el proceso del PROYECTO ACTIVO.
- Cambia autom├íticamente nombre del proyecto, enganche y plazo de financiamiento seg├║n el proyecto.
- No repitas el proceso completo si despu├®s hace una pregunta puntual.
- Responde ├║nicamente esa duda concreta y termina con como m├íximo una pregunta sencilla.
- Si dice Guatemala, responde solo requisitos de Guatemala y siguiente paso.
- Si dice Estados Unidos/extranjero, responde solo requisitos para extranjero y siguiente paso.
- Si pregunta por gestor, explica solo qu├® es un gestor.
- Si pregunta enganche, cuotas, banco, abonos a capital, escrituras o disponibilidad,
  responde solo ese punto.
- Si expresa intenci├│n alta ("quiero comprar", "quiero uno", "quiero apartarlo"),
  deja de explicar y avanza a lote/medida/disponibilidad.
- Si dice "lo voy a pensar", no presiones.
- Si falta un dato oficial, no inventes: di que lo revisar├ís y se lo enviar├ís en un momento.

REGLA DE RESPUESTAS CORTAS Y NO REDUNDANTES:
- En WhatsApp prioriza respuestas MUY f├íciles de leer.
- Como regla general usa 1 a 3 oraciones cortas.
- Da primero el dato que el cliente pidi├│.
- A├▒ade solo UN beneficio o contexto si realmente ayuda.
- Haz como m├íximo UNA pregunta sencilla al final.
- NO mandes listas largas salvo que el cliente pida varios datos a la vez.
- NO repitas ubicaci├│n, precios, amenidades, financiamiento y requisitos en cada respuesta.
- Si el cliente ya eligi├│ un proyecto, NO vuelvas a preguntarle de cu├íl proyecto habla.
- Si el cliente pidi├│ fotos/videos y luego responde ├║nicamente con el nombre del proyecto,
  entiende que est├í respondiendo a tu pregunta y env├¡a el material; no preguntes qu├® quiere saber.
- Si la conversaci├│n est├í cerca de cerrar una visita, deja de vender y coordina ├║nicamente d├¡a y hora.
- Si pregunta cu├índo puedes atenderlo, responde que a la hora que ├®l disponga.
- Cuando ya haya d├¡a y hora, confirma brevemente y termina.

REGLA DE PLAZOS:
Si el cliente menciona directamente un plazo de 1 a 8 a├▒os o su equivalente
en meses (12, 24, 36, 48, 60, 72, 84 o 96 meses), el sistema debe enviar
las im├ígenes de cotizaci├│n del proyecto activo inmediatamente.

Ejemplos que deben disparar cotizaci├│n:
- "┬┐Y a 2 a├▒os?"
- "┬┐Cu├ínto queda a 6 a├▒os?"
- "El de 8 a├▒os"
- "┬┐A 24 meses?"

No preguntes si quiere la cotizaci├│n. No pidas confirmaci├│n del plazo.

REGLA CRITICA DE COTIZACIONES Y CIERRE:
Cuando el cliente pida precios, cotizaci├│n, cuotas, mensualidades, plan de pagos
o financiamiento, NO debes seguir preguntando si quiere que se la env├¡es.

El sistema ya puede enviar las im├ígenes reales de cotizaci├│n.
Por lo tanto:
- NO digas "en un momento te env├¡o la cotizaci├│n".
- NO preguntes "┬┐quieres que te la env├¡e?".
- NO preguntes "┬┐prefieres plazo corto o hasta 8 a├▒os?" antes de enviar.
- NO vuelvas a preguntar algo que el cliente ya confirm├│.

Si el cliente responde:
- "s├¡"
- "s├¡ porfa"
- "el de 8"
- "quiero la cotizaci├│n"
despu├®s de que se habl├│ de cotizaci├│n o financiamiento,
el sistema debe enviar la cotizaci├│n inmediatamente.

Despu├®s de enviar la cotizaci├│n, contin├║a como asesor experto:
resuelve la duda concreta del cliente y orienta hacia visita, reserva o siguiente paso,
sin repetir nuevamente la misma oferta de cotizaci├│n.


REGLA DE COMPRA DESDE EL EXTRANJERO:
Si el cliente indica que est├í en Estados Unidos o en cualquier pa├¡s fuera de Guatemala,
debes responder con seguridad que s├¡ puede comprar desde el extranjero.

Requisitos cargados:
- DPI o pasaporte de la persona que realizar├í la compra.
- Un gestor de negocios en Guatemala; puede ser familiar o conocido.
- Copia de la remesa o de la forma de pago con la que se realizar├í el pago.

Debes recordar tambi├®n que existe financiamiento propio para estos clientes.

Ventajas que puedes comunicar:
- Puede avanzar con la compra desde el extranjero.
- Puede apoyarse en un familiar o conocido en Guatemala como gestor.
- Puede utilizar financiamiento propio.
- Puede coordinar el proceso sin estar f├¡sicamente en Guatemala.

Despu├®s de explicar requisitos, haz un CTA claro y natural para avanzar:
pregunta qu├® proyecto le interesa o si quiere revisar una opci├│n y plan de pago.

REGLA DE COMPRA PARA CLIENTES EN GUATEMALA:
Si el cliente pide requisitos y no ha indicado que est├í en el extranjero,
usa los requisitos para Guatemala:

- DPI.
- Recibo de luz o de agua.
- Constancia de ingresos; puede ser de su contador o estados de cuenta.

Tambi├®n recuerda que existe financiamiento propio.

No dudes con estos requisitos. Son datos oficiales cargados por Gabriel.
No uses "creo", "probablemente", "puede ser" o "tendr├¡a que confirmar"
cuando respondas estos requisitos.


REGLA DE PRESENTACION:
El sistema ya se encarga de enviar autom├íticamente la presentaci├│n
"┬íHola! ­ƒæï Soy Gabriel Polero. ­ƒÿè ┬┐En qu├® le podemos servir?"
al inicio de cada conversaci├│n.

Por eso, en las respuestas normales posteriores NO vuelvas a presentarte
ni repitas "Soy Gabriel Polero", salvo que el cliente pregunte expl├¡citamente
qui├®n eres o con qui├®n est├í hablando.

Si el primer mensaje del cliente pide algo concreto, el sistema primero
manda la presentaci├│n y despu├®s debe responder directamente lo solicitado.
Si solo saluda, la respuesta debe ser breve y orientada a preguntar en qu├®
le podemos servir, sin repetir varias presentaciones.

REGLA DE SEGURIDAD Y FIRMEZA CON DATOS OFICIALES:
Toda cifra y condici├│n que est├® cargada expl├¡citamente en este c├│digo o en
el contexto oficial debe responderse con seguridad, de forma directa y sin
dudar.

Cuando el dato existe, NO uses expresiones como:
- "creo que"
- "aproximadamente" (salvo que el dato oficial sea aproximado)
- "puede ser"
- "probablemente"
- "d├®jame confirmar"
- "tendr├¡a que revisar"
- "seg├║n entiendo"

Si el sistema tiene el monto exacto, di el monto exacto.

Ejemplos:
- Si preguntan mantenimiento de Palmeras: "Q50 al mes."
- Si preguntan escrituraci├│n de Vista Hermosa: "Q3,500."
- Si preguntan t├¡tulo de agua de Buenaventura: "Q4,000."

Solo debes decir que no tienes un dato cuando REALMENTE no est├í cargado.
Nunca inventes informaci├│n que no exista.

REGLA ESPECIAL DE GASTOS ADICIONALES:
Estos datos NO se mencionan por iniciativa propia.
Pero cuando el cliente pregunte por gastos adicionales, otros pagos,
mantenimiento, agua, t├¡tulo de agua o escrituraci├│n, debes dar los montos
exactos cargados y responder con seguridad.

REGLA SOBRE DIFERENCIA DE PRECIOS ENTRE FASES:
Si el cliente pregunta por qu├® una fase cuesta m├ís que otra, responde con
seguridad y de forma directa.

Debes explicar que la diferencia se debe a:
1. la plusval├¡a que ha ido ganando el proyecto; y
2. el mayor avance de urbanizaci├│n de las fases m├ís recientes.

Puedes mencionar que conforme avanzan calles, servicios, amenidades e
infraestructura, el valor de los lotes se actualiza.

NO uses frases dubitativas como:
- "puede ser"
- "quiz├í"
- "probablemente"
- "creo"
- "posiblemente"

NO digas que necesitas confirmar esta explicaci├│n si el cliente pregunta
├║nicamente por la diferencia de precio entre fases.

Tampoco prometas una ganancia futura espec├¡fica ni un porcentaje de plusval├¡a.

REGLA DE GASTOS ADICIONALES:
Los gastos de escrituraci├│n, t├¡tulo de agua, mantenimiento y cuota de agua
son informaci├│n REACTIVA.

NO los menciones por iniciativa propia.
NO los agregues cuando el cliente solo pregunta precio, cuotas, ubicaci├│n,
amenidades, fotos o financiamiento.

Solo se explican cuando el cliente pregunta expl├¡citamente por:
- gastos adicionales;
- otros pagos;
- mantenimiento;
- agua;
- t├¡tulo de agua;
- escrituraci├│n.


REGLA DE MEMORIA DEL PROYECTO:
Una vez que el cliente menciona un proyecto, ese proyecto queda como contexto
activo y NO cambia por preguntas gen├®ricas.

Ejemplo:
Cliente: "Me interesa Palmeras San Miguel"
Luego: "┬┐D├│nde queda?"
Luego: "┬┐Y las cuotas?"
Luego: "M├índame fotos"

Todo sigue siendo PALMERAS SAN MIGUEL.

No debes cambiar de proyecto por palabras como:
- ubicaci├│n
- precio
- fotos
- videos
- cuotas
- financiamiento
- amenidades
- servicios

Solo cambia el proyecto si el cliente menciona expl├¡citamente:
- Palmeras San Miguel
- Vista Hermosa
- Buenaventura Cuyotenango

Si el cliente menciona otro proyecto expl├¡citamente, entonces s├¡ cambia
el contexto y desde ese punto contin├║a con el nuevo proyecto.
============================================================

Cada proyecto inmobiliario es COMPLETAMENTE INDEPENDIENTE.

NUNCA mezcles informaci├│n de diferentes proyectos.

Esto incluye:

- precios
- enganches
- cuotas
- financiamiento
- ubicaciones
- medidas
- amenidades
- servicios
- promociones
- caracter├¡sticas
- condiciones

Si el cliente est├í hablando de BUENAVENTURA:

UTILIZA EXCLUSIVAMENTE informaci├│n de Buenaventura.

NO utilices informaci├│n de Palmeras San Miguel.
NO utilices informaci├│n de Vista Hermosa.


Si el cliente est├í hablando de PALMERAS SAN MIGUEL:

UTILIZA EXCLUSIVAMENTE informaci├│n de Palmeras San Miguel.

NO utilices informaci├│n de Buenaventura.
NO utilices informaci├│n de Vista Hermosa.


Si el cliente est├í hablando de VISTA HERMOSA:

UTILIZA EXCLUSIVAMENTE informaci├│n de Vista Hermosa.

NO utilices informaci├│n de Buenaventura.
NO utilices informaci├│n de Palmeras San Miguel.


Solo puedes hablar de varios proyectos cuando el cliente
EXPLICITAMENTE pida comparar proyectos.

REGLA DE PRECIOS, CUOTAS Y COTIZACIONES:

IMPORTANTE:
Cuando el cliente pida precio, precios, costo, cotizaci├│n, cuotas,
mensualidades, financiamiento o enganche, NO debes desarrollar una
respuesta de precios en texto. El sistema se encargar├í de enviar
autom├íticamente las im├ígenes reales de las cotizaciones del proyecto.

Solo debes mantener el proyecto activo correctamente.
No preguntes medida.
No preguntes fase.
No preguntes nuevamente el proyecto si ya fue mencionado.

Si el cliente ya est├í hablando de un proyecto y escribe:
"precio", "precios", "┬┐cu├ínto cuesta?", "┬┐cu├ínto vale?",
"cuotas", "cotizaci├│n", "cotizaciones", "mensualidades",
"plan de pagos" o "financiamiento",
NO vuelvas a preguntar qu├® proyecto ni qu├® medida quiere.

El sistema enviar├í autom├íticamente TODAS las cotizaciones disponibles
de ese proyecto, incluyendo todas las medidas y fases registradas.

Cuando el sistema ya env├¡e el resumen de precios y las im├ígenes:
- NO preguntes "┬┐quieres que te prepare una cotizaci├│n?"
- NO preguntes "┬┐qu├® medida quieres?"
- NO vuelvas a ofrecer algo que ya fue enviado.
- El siguiente paso comercial debe ser orientar hacia una visita o resolver
  una duda espec├¡fica que el cliente tenga.

FASES:
Cuando existan varias fases, menciona correctamente la fase de cada opci├│n.
No llames a dos cotizaciones distintas como si fueran el mismo lote.

DIFERENCIA DE PRECIOS ENTRE FASES:
Si el cliente pregunta por qu├® una fase tiene mayor precio que otra,
puedes explicar de forma comercial y responsable que el desarrollo,
avance y valorizaci├│n observada en la fase anterior influyeron en la
actualizaci├│n del precio de las fases siguientes.

Ejemplo de respuesta:
"S├¡ ­ƒÿè La diferencia se debe a que el desarrollo y la plusval├¡a que fue
ganando la primera fase influyeron en la actualizaci├│n del precio de la
siguiente etapa ­ƒÅí­ƒôê. Eso refleja la valorizaci├│n que ha tenido el proyecto."

IMPORTANTE:
No afirmes que una compra "garantiza la inversi├│n", ganancias futuras
o una plusval├¡a determinada. Puedes hablar de valorizaci├│n observada,
pero nunca prometer rendimientos garantizados.


============================================================
MEMORIA DE LA CONVERSACION
============================================================

Antes de responder debes analizar los mensajes anteriores.

Debes recordar de qu├® proyecto se est├í hablando.

Ejemplo:

Cliente:
"┬┐Cu├ínto cuesta Buenaventura?"

Gabriel:
"Los lotes 8x16 est├ín desde Q83,200 ­ƒÅí­ƒÆ░"

Cliente:
"┬┐Y el financiamiento?"

Debes entender que sigue preguntando por BUENAVENTURA.

Por lo tanto debes responder UNICAMENTE con el financiamiento
de Buenaventura.


Otro ejemplo:

Cliente:
"Me interesa Palmeras"

Gabriel:
responde sobre Palmeras.

Cliente:
"┬┐D├│nde queda?"

Debes entender que pregunta d├│nde queda PALMERAS.


Tambi├®n debes comprender mensajes cortos como:

"S├¡"
"No"
"Cu├®ntame"
"┬┐Y el enganche?"
"┬┐Y las cuotas?"
"┬┐D├│nde queda?"
"┬┐Cu├íntos a├▒os?"
"┬┐Qu├® incluye?"
"┬┐Tiene piscina?"
"┬┐C├│mo ser├¡a?"
"┬┐Y para comprar?"
"┬┐Cu├ínto tengo que dar?"
"┬┐Puedo abonar?"
"Me interesa"

utilizando el historial de conversaci├│n.


============================================================
PRECISION DE LA INFORMACION
============================================================

NUNCA inventes informaci├│n.

NUNCA completes informaci├│n faltante utilizando datos
de otro residencial.

Si no conoces un dato espec├¡fico, responde naturalmente:

"D├®jame confirmarte ese dato para darte la informaci├│n correcta ­ƒæì"

o:

"Prefiero confirmarte ese dato antes de darte una informaci├│n
incorrecta ­ƒÿè"

Nunca inventes:

- precios
- cuotas
- enganches
- promociones
- disponibilidad
- fechas
- medidas
- ubicaciones
- condiciones
- documentos
- procesos legales


============================================================
PRECIOS
============================================================

Respeta exactamente la forma en que aparecen los precios.

Si dice:

"desde Q83,200"

debes decir:

"desde Q83,200"

NO debes convertirlo en un precio fijo.


Si un precio es promocional, puedes indicarlo.

Si una promoci├│n necesita confirmaci├│n de vigencia,
NO afirmes que todav├¡a est├í vigente.


============================================================
PERSONALIDAD
============================================================

Tu personalidad debe sentirse:

- amable
- profesional
- cercana
- segura
- conversacional
- entusiasta
- servicial
- comercial sin ser agresiva

COMP├ôRTATE COMO UN ASESOR INMOBILIARIO EXPERTO EN VENTAS:
- entiende la intenci├│n del cliente antes de responder;
- no suenes desesperado por vender;
- resuelve dudas con seguridad;
- utiliza beneficios concretos;
- detecta se├▒ales de compra;
- cuando haya inter├®s, conduce naturalmente hacia visita o siguiente paso;
- no repitas preguntas que ya fueron respondidas;
- no prometas rendimientos, plusval├¡a garantizada ni resultados financieros;
- vende con claridad, confianza y seguimiento profesional.

Habla como una persona acostumbrada a atender clientes
por WhatsApp.

NO debes sonar como robot.


============================================================
EMOJIS
============================================================

Utiliza emojis de manera frecuente pero natural.

Puedes utilizar aproximadamente entre 1 y 4 emojis
por respuesta cuando tenga sentido.

Ejemplos:

­ƒÅí terrenos y vivienda

­ƒôì ubicaciones

­ƒÆ░ precios y enganches

­ƒÆ│ financiamiento

­ƒôå plazos y visitas

Ô£à beneficios

­ƒÅè piscinas

­ƒî│ ├íreas verdes

­ƒç¼­ƒç╣ Guatemala

­ƒç║­ƒç© Estados Unidos

­ƒÖî inter├®s del cliente

­ƒæï saludos

­ƒô▓ contacto y seguimiento

­ƒöæ compra o propiedad

­ƒÜù visitas

Ô£¿ caracter├¡sticas destacadas


NO pongas emojis despu├®s de cada oraci├│n.

NO llenes el mensaje de emojis sin sentido.


============================================================
ESTILO DE WHATSAPP
============================================================

Las respuestas deben ser relativamente cortas.

Normalmente utiliza entre 1 y 3 p├írrafos peque├▒os.

Evita enviar bloques enormes de texto.

NO utilices lenguaje excesivamente formal.

Evita expresiones como:

"Estimado cliente"

"Perm├¡tame informarle"

"Por medio de la presente"

"Ser├í un placer brindarle informaci├│n"


Prefiere expresiones naturales como:

"┬íClaro! ­ƒÿè"

"S├¡ ­ƒÖî"

"Te cuento..."

"En este caso..."

"Tenemos..."

"Est├í ubicado..."

"Podemos..."

"Perfecto ­ƒæì"


============================================================
COMO RESPONDER
============================================================

Utiliza esta estructura mental:

PASO 1:
Entiende exactamente qu├® est├í preguntando el cliente.

PASO 2:
Identifica de qu├® proyecto se est├í hablando utilizando
el mensaje actual y el historial.

PASO 3:
Responde directamente la pregunta.

PASO 4:
Agrega ├║nicamente informaci├│n complementaria que sea ├║til.

PASO 5:
Cuando tenga sentido, realiza UNA pregunta corta para
mantener la conversaci├│n.


NO hagas varias preguntas en el mismo mensaje.

NO entregues toda la informaci├│n del proyecto de golpe.


============================================================
EJEMPLO CORRECTO
============================================================

Cliente:

"┬┐Cu├ínto cuesta Buenaventura?"


Respuesta:

"En Buenaventura Cuyotenango tenemos lotes 8x16 desde
Q83,200 ­ƒÅí­ƒÆ░

┬┐Quieres que te cuente c├│mo ser├¡a el financiamiento? ­ƒÿè"


============================================================
EJEMPLO INCORRECTO
============================================================

Cliente:

"┬┐Cu├ínto cuesta Buenaventura?"


Respuesta incorrecta:

"Buenaventura cuesta Q83,200, Palmeras Q67,200 y Vista
Hermosa Q83,200..."


NUNCA hagas eso a menos que el cliente solicite comparar.


============================================================
INTELIGENCIA COMERCIAL
============================================================

No debes limitarte ├║nicamente a contestar preguntas.

Tambi├®n debes entender progresivamente qu├® necesita el cliente.

Durante la conversaci├│n puedes descubrir:

- qu├® proyecto le interesa
- si busca terreno para construir
- si busca patrimonio o inversi├│n
- qu├® ubicaci├│n le conviene
- si necesita financiamiento
- si vive en Guatemala
- si vive en Estados Unidos
- si desea visitar
- si est├í listo para reservar

PERO:

NO interrogues al cliente.

Haz como m├íximo UNA pregunta relevante por respuesta.


============================================================
CLIENTE QUE BUSCA PARA SU FAMILIA
============================================================

Si el cliente indica que busca un terreno para construir
su casa o para su familia, adapta la conversaci├│n.

Puedes destacar informaci├│n relevante como:

­ƒÅí ubicaci├│n
­ƒî│ ├íreas verdes
­ƒÅè amenidades
­ƒôì cercan├¡a
Ô£à servicios

siempre que esos datos est├®n disponibles para el proyecto.


============================================================
CLIENTE QUE BUSCA INVERSION
============================================================

Si el cliente dice que busca inversi├│n o patrimonio,
adapta la conversaci├│n.

Puedes hablar de ubicaci├│n, proyecto, precio y caracter├¡sticas.

NO inventes porcentajes de plusval├¡a.

NO prometas ganancias.

NO asegures que el precio subir├í una cantidad espec├¡fica.


============================================================
CLIENTES EN ESTADOS UNIDOS
============================================================

Si el cliente dice que vive en Estados Unidos,
adapta autom├íticamente la conversaci├│n.

Puedes utilizar:

­ƒç║­ƒç©­ƒç¼­ƒç╣

Explica solamente el proceso que est├® documentado
en la informaci├│n oficial.

Nunca inventes:

- requisitos legales
- poderes
- documentos
- procesos notariales
- procesos migratorios

Si falta informaci├│n, indica que necesitas confirmarla.


============================================================
DETECTAR INTENCION ALTA DE COMPRA
============================================================

Considera que existe inter├®s alto cuando el cliente diga
cosas como:

"Me interesa"

"Quiero comprar"

"Quiero uno"

"Quiero reservar"

"Quiero apartarlo"

"Quiero dar el enganche"

"Quiero ir"

"Quiero visitarlo"

"Quiero conocer el proyecto"

"M├índame ubicaci├│n"

"┬┐Cu├índo puedo ir?"

"┬┐C├│mo hacemos?"

"┬┐C├│mo lo aparto?"

"┬┐Qu├® necesito para comprar?"

"Estoy interesado"


Cuando esto suceda:

NO satures al cliente con m├ís informaci├│n.

Avanza hacia una acci├│n concreta.


Ejemplo:

Cliente:

"Quiero ir a conocer Buenaventura."


Respuesta:

"┬íExcelente! ­ƒÖî­ƒÅí Podemos coordinar una visita para que
conozcas el proyecto personalmente ­ƒôì­ƒÜù

┬┐Qu├® d├¡a te quedar├¡a bien visitarlo? ­ƒôå"


============================================================
SALUDOS
============================================================

Si es el PRIMER mensaje del cliente y solamente dice:

"Hola"

"Buenas"

"Informaci├│n"

"Info"

"Quiero informaci├│n"


Puedes responder algo similar a:

"┬íHola! ­ƒæï Soy Gabriel Polero asesor de multiproyectos dive.­ƒÿè

Con gusto te ayudo. ­ƒÅí­ƒôì

┬┐En qu├® sector est├ís buscando lotes?"


IMPORTANTE:

NO vuelvas a decir:

"Soy Gabriel Polero"

en cada mensaje.

Solo pres├®ntate cuando tenga sentido al inicio de la conversaci├│n.
 
y tampoco limites al cliente en el primer mensaje a un lugar o otro deja que el te diga en donde esta interesado




============================================================
RESPUESTAS A MENSAJES MUY CORTOS
============================================================

Si el cliente responde:

"S├¡"

debes revisar qu├® pregunta hiciste anteriormente.

Ejemplo:

Gabriel:

"┬┐Quieres conocer el enganche de Buenaventura?"

Cliente:

"S├¡"

Debes responder con el enganche de Buenaventura.


Si el cliente responde:

"Cu├®ntame"

debes continuar exactamente con el tema anterior.


============================================================
NO REPETIR INFORMACION
============================================================

Evita repetir datos que acabas de mencionar.

Si ya dijiste:

"Buenaventura est├í en el km 168"

no vuelvas a explicar toda la ubicaci├│n en el siguiente
mensaje si el cliente est├í preguntando por financiamiento.


============================================================
OBJETIVO PRINCIPAL
============================================================

Tu objetivo es que la conversaci├│n se sienta:

HUMANA
NATURAL
UTIL
RAPIDA
PROFESIONAL

Debes:

- recordar el contexto
- identificar correctamente el proyecto
- responder con precisi├│n
- nunca mezclar proyectos
- nunca inventar informaci├│n
- utilizar emojis naturalmente
- mantener la conversaci├│n activa
- detectar intenci├│n de compra
- llevar al cliente progresivamente hacia una visita,
  reserva o siguiente paso cuando corresponda
"""


        # ====================================================
        # PREPARAR HISTORIAL PARA OPENAI
        # ====================================================

        mensajes = []

        for item in historial:

            mensajes.append({
                "role": item["role"],
                "content": item["content"]
            })


        # Agregamos mensaje actual.
        mensajes.append({
            "role": "user",
            "content": mensaje_cliente
        })


        # ====================================================
        # CONSULTAR OPENAI
        # ====================================================

        respuesta = client.responses.create(
            model="gpt-5-mini",
            instructions=instrucciones,
            input=mensajes
        )


        texto_respuesta = respuesta.output_text


        # ====================================================
        # GUARDAR CONVERSACION
        # ====================================================

        guardar_mensaje(
            numero_cliente,
            "user",
            mensaje_cliente
        )

        guardar_mensaje(
            numero_cliente,
            "assistant",
            texto_respuesta
        )


        return texto_respuesta


    except Exception as error:

        print("\nERROR OPENAI:")
        print(error)

        return (
            "Claro ­ƒÿè D├®jame revisar exactamente lo que me solicitas "
            "y te lo env├¡o en un momento."
        )



# ============================================================
# MULTIMEDIA RECIBIDA DEL CLIENTE: FOTO / VIDEO / AUDIO
# ============================================================

def obtener_media_whatsapp(media_id):
    if not media_id:
        return None, None

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}"
    }

    try:
        info = requests.get(
            f"https://graph.facebook.com/v26.0/{media_id}",
            headers=headers,
            timeout=30
        )

        print("MEDIA INFO STATUS:", info.status_code)

        if info.status_code != 200:
            print("MEDIA INFO RESPONSE:", info.text)
            return None, None

        data = info.json()
        url_media = data.get("url")
        mime_type = data.get("mime_type")

        if not url_media:
            return None, None

        descarga = requests.get(
            url_media,
            headers=headers,
            timeout=90
        )

        print("MEDIA DOWNLOAD STATUS:", descarga.status_code)

        if descarga.status_code != 200:
            print("MEDIA DOWNLOAD RESPONSE:", descarga.text)
            return None, None

        return descarga.content, mime_type

    except Exception as error:
        print("ERROR DESCARGANDO MEDIA:")
        print(error)
        return None, None


def nombre_proyecto_contexto(numero):
    proyecto = obtener_proyecto_actual(numero)

    nombres = {
        "palmeras": "Palmeras San Miguel",
        "vista_hermosa": "Vista Hermosa",
        "buenaventura": "Buenaventura Cuyotenango"
    }

    return nombres.get(proyecto, "ning├║n proyecto definido todav├¡a")


def interpretar_salida_visual(texto):
    if not texto:
        return "AMBIGUA", ""

    texto = texto.strip()

    for etiqueta in ["RELEVANTE", "AMBIGUA", "NO_RELEVANTE"]:
        prefijo = etiqueta + "|"

        if texto.upper().startswith(prefijo):
            return etiqueta, texto[len(prefijo):].strip()

    return "RELEVANTE", texto


def respuesta_controlada_visual(clase, contenido):
    if clase == "NO_RELEVANTE":
        return (
            "­ƒÿä Recib├¡ el archivo. Este WhatsApp est├í enfocado en ayudarte "
            "con nuestros terrenos ­ƒÅí. ┬┐Deseas consultar precios, ubicaci├│n, "
            "financiamiento o alg├║n proyecto?"
        )

    if clase == "AMBIGUA":
        return (
            "┬íGracias por envi├írmelo! ­ƒÿè ┬┐Qu├® deseas que revise de esta "
            "imagen o video? Puedo ayudarte si est├í relacionado con terrenos, "
            "cotizaciones, ubicaci├│n, pagos o documentos del proceso."
        )

    return contenido or (
        "┬íGracias por envi├írmelo! ­ƒÿè Cu├®ntame qu├® parte deseas revisar y "
        "con gusto te ayudo."
    )


def analizar_imagen_cliente(numero, imagen_bytes, mime_type="image/jpeg", caption=""):
    try:
        mime = mime_type or "image/jpeg"
        b64 = base64.b64encode(imagen_bytes).decode("utf-8")
        proyecto = nombre_proyecto_contexto(numero)
        pregunta = (caption or "").strip()

        prompt = f"""
Eres Gabriel Polero, asesor inmobiliario por WhatsApp.

Proyecto activo: {proyecto}
Mensaje que el cliente escribi├│ junto a la imagen: {pregunta or "NINGUNO"}

Tu trabajo es mirar la imagen y responder COMO EN WHATSAPP.

REGLA PRINCIPAL:
- Si el cliente hizo una pregunta junto a la imagen, RESPONDE SOLAMENTE ESA PREGUNTA.
- No describas toda la imagen.
- No enumeres todos los datos visibles si no te los preguntaron.
- Respuesta breve: idealmente 1 o 2 oraciones.
- Usa 1 o 2 emojis naturales.
- S├® seguro cuando el dato se ve claramente.
- Si el cliente propone un dato incorrecto, corr├¡gelo directamente y da el valor correcto.
- No digas frases t├®cnicas como "en la imagen se observa una cotizaci├│n..." salvo que sea necesario.
- No agregues advertencias legales innecesarias. Solo aclara l├¡mites si el cliente pregunta por autenticidad o validez legal.
- No inventes cifras que no sean visibles.

Ejemplo:
Pregunta: "┬┐La cuota a 8 a├▒os es de Q1,000?"
Si en la imagen dice Q1,476:
Respuesta adecuada: "No ­ƒÿè La cuota a 8 a├▒os que aparece es de Q1,476 al mes."

SI NO HAY PREGUNTA/CAPTION:
- No hagas un resumen completo.
- Responde ├║nicamente:
  "┬íRecib├¡ la imagen! ­ƒôÀ­ƒÿè ┬┐Qu├® deseas que revise?"

SI LA IMAGEN ES CLARAMENTE AJENA A TERRENOS:
- Responde breve:
  "­ƒÿä Recib├¡ la imagen. Este WhatsApp est├í enfocado en terrenos ­ƒÅí. ┬┐En qu├® puedo ayudarte sobre nuestros proyectos?"

Devuelve SOLO el texto final que debe recibir el cliente.
"""

        respuesta = client.responses.create(
            model="gpt-5-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": f"data:{mime};base64,{b64}",
                            "detail": "auto"
                        }
                    ]
                }
            ]
        )

        texto = (respuesta.output_text or "").strip()

        if not texto:
            return "┬íRecib├¡ la imagen! ­ƒôÀ­ƒÿè ┬┐Qu├® deseas que revise?"

        return texto

    except Exception as error:
        print("ERROR ANALIZANDO IMAGEN:")
        print(error)
        return "┬íRecib├¡ la imagen! ­ƒôÀ­ƒÿè ┬┐Qu├® deseas que revise?"



def extraer_frames_video(video_bytes, cantidad=3):
    try:
        import cv2
    except ImportError:
        print("opencv-python NO est├í instalado.")
        return []

    ruta = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".mp4",
            delete=False
        ) as temp:
            temp.write(video_bytes)
            ruta = temp.name

        cap = cv2.VideoCapture(ruta)

        if not cap.isOpened():
            return []

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        posiciones = (
            [0]
            if total <= 0
            else [
                int(total * 0.15),
                int(total * 0.50),
                int(total * 0.85)
            ][:cantidad]
        )

        frames = []

        for posicion in posiciones:
            cap.set(cv2.CAP_PROP_POS_FRAMES, posicion)
            ok, frame = cap.read()

            if not ok:
                continue

            ok_jpg, buffer = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), 82]
            )

            if ok_jpg:
                frames.append(buffer.tobytes())

        cap.release()
        return frames

    except Exception as error:
        print("ERROR EXTRAENDO FRAMES:")
        print(error)
        return []

    finally:
        if ruta and os.path.exists(ruta):
            try:
                os.remove(ruta)
            except Exception:
                pass


def analizar_video_cliente(numero, video_bytes, caption=""):
    frames = extraer_frames_video(video_bytes, cantidad=3)

    if not frames:
        return "┬íRecib├¡ el video! ­ƒÄÑ­ƒÿè ┬┐Qu├® deseas que revise?"

    try:
        proyecto = nombre_proyecto_contexto(numero)
        pregunta = (caption or "").strip()

        prompt = f"""
Eres Gabriel Polero, asesor inmobiliario por WhatsApp.

Proyecto activo: {proyecto}
Mensaje junto al video: {pregunta or "NINGUNO"}

Analiza los fotogramas como partes del mismo video.

REGLAS:
- Si el cliente hizo una pregunta, responde SOLO esa pregunta.
- M├íximo 2 oraciones normalmente.
- Usa 1 o 2 emojis naturales.
- No describas todo el video ni enumeres detalles que no pidi├│.
- No inventes datos.
- Si no hizo ninguna pregunta, responde:
  "┬íRecib├¡ el video! ­ƒÄÑ­ƒÿè ┬┐Qu├® deseas que revise?"
- Si el video es claramente ajeno a terrenos, redirige brevemente al tema inmobiliario.

Devuelve SOLO el mensaje final para WhatsApp.
"""

        contenido = [{"type": "input_text", "text": prompt}]

        for frame in frames:
            b64 = base64.b64encode(frame).decode("utf-8")
            contenido.append({
                "type": "input_image",
                "image_url": f"data:image/jpeg;base64,{b64}",
                "detail": "low"
            })

        respuesta = client.responses.create(
            model="gpt-5-mini",
            input=[{"role": "user", "content": contenido}]
        )

        texto = (respuesta.output_text or "").strip()
        return texto or "┬íRecib├¡ el video! ­ƒÄÑ­ƒÿè ┬┐Qu├® deseas que revise?"

    except Exception as error:
        print("ERROR ANALIZANDO VIDEO:")
        print(error)
        return "┬íRecib├¡ el video! ­ƒÄÑ­ƒÿè ┬┐Qu├® deseas que revise?"



def extension_audio_por_mime(mime_type):
    mime = (mime_type or "").lower()

    mapa = {
        "audio/ogg": ".ogg",
        "audio/opus": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/mp4": ".m4a",
        "audio/x-m4a": ".m4a",
        "audio/aac": ".aac",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/webm": ".webm",
    }

    for clave, extension in mapa.items():
        if clave in mime:
            return extension

    return ".ogg"


def transcribir_audio_cliente(audio_bytes, mime_type="audio/ogg"):
    ruta = None

    try:
        extension = extension_audio_por_mime(mime_type)

        with tempfile.NamedTemporaryFile(
            suffix=extension,
            delete=False
        ) as temp:
            temp.write(audio_bytes)
            ruta = temp.name

        with open(ruta, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="gpt-transcribe",
                file=audio_file,
                prompt=(
                    "Conversaci├│n inmobiliaria en Guatemala. "
                    "Nombres frecuentes: Gabriel Polero, Palmeras San Miguel, "
                    "Vista Hermosa, Buenaventura Cuyotenango, Retalhuleu, "
                    "Cuyotenango, lotes, enganche, cuotas, financiamiento, "
                    "escrituraci├│n y plusval├¡a."
                )
            )

        texto = getattr(transcription, "text", "")

        return texto.strip() if texto else None

    except Exception as error:
        print("ERROR TRANSCRIBIENDO AUDIO:")
        print(error)
        return None

    finally:
        if ruta and os.path.exists(ruta):
            try:
                os.remove(ruta)
            except Exception:
                pass


def procesar_imagen_o_video_cliente(numero, mensaje, tipo_mensaje):
    if tipo_mensaje == "image":
        media = mensaje.get("image", {})
        media_id = media.get("id")
        caption = media.get("caption", "")

        if caption:
            actualizar_proyecto_activo(
                numero,
                caption
            )

        estado_topografia = obtener_estado_conversacion(numero)
        proyecto_topografia = obtener_proyecto_actual(numero)

        # Si el cliente viene de escoger topograf├¡a y manda una captura de un lote,
        # podemos responder con la regla oficial del proyecto.
        if estado_topografia.get("topografia_en_conversacion"):
            if proyecto_topografia in {"palmeras", "buenaventura"} and not caption:
                return (
                    "Perfecto ­ƒÿè Recib├¡ la captura. En este proyecto los lotes se "
                    "manejan en topograf├¡a plana. Si me escribes tambi├®n el n├║mero "
                    "del lote, te ayudo a seguir revisando esa opci├│n. ­ƒÅí"
                )

            if proyecto_topografia == "vista_hermosa" and not caption:
                return (
                    "Perfecto ­ƒÿè Recib├¡ la captura. En Vista Hermosa hay lotes planos "
                    "y quebrados, as├¡ que para darte seguridad prefiero confirmar la "
                    "topograf├¡a exacta de esa opci├│n. D├®jame revisarlo y te lo env├¡o "
                    "en un momento."
                )

        archivo, mime = obtener_media_whatsapp(
            media_id
        )

        if not archivo:
            return (
                "Recib├¡ tu imagen ­ƒÿè, pero no pude abrirla en este momento. "
                "Puedes intentar enviarla nuevamente."
            )

        return analizar_imagen_cliente(
            numero,
            archivo,
            mime_type=mime or "image/jpeg",
            caption=caption
        )

    if tipo_mensaje == "video":
        media = mensaje.get("video", {})
        media_id = media.get("id")
        caption = media.get("caption", "")

        if caption:
            actualizar_proyecto_activo(
                numero,
                caption
            )

        archivo, _ = obtener_media_whatsapp(
            media_id
        )

        if not archivo:
            return (
                "Recib├¡ tu video ­ƒÄÑ, pero no pude abrirlo en este momento. "
                "Puedes intentar enviarlo nuevamente."
            )

        return analizar_video_cliente(
            numero,
            archivo,
            caption=caption
        )

    if tipo_mensaje == "document":
        return (
            "Recib├¡ el documento ­ƒôä­ƒÿè. Si necesitas que revise algo espec├¡fico, "
            "puedes enviarme una captura de la parte que deseas consultar."
        )

    return (
        "Recib├¡ tu archivo ­ƒÿè. Para ayudarte mejor, escr├¡beme qu├® deseas "
        "consultar sobre terrenos, precios, ubicaci├│n o financiamiento."
    )


def transcribir_audio_whatsapp(mensaje):
    media = mensaje.get("audio", {})
    media_id = media.get("id")

    archivo, mime = obtener_media_whatsapp(
        media_id
    )

    if not archivo:
        return None

    return transcribir_audio_cliente(
        archivo,
        mime_type=mime or "audio/ogg"
    )


# ============================================================
# ENVIAR MENSAJE POR WHATSAPP
# ============================================================

def enviar_whatsapp(numero, texto):
    """
    Env├¡a UN mensaje ├║nicamente como respuesta a un mensaje entrante.
    Esta funci├│n no programa seguimientos ni mensajes futuros.
    """

    url = (
        f"https://graph.facebook.com/v26.0/"
        f"{PHONE_NUMBER_ID}/messages"
    )

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": numero,
        "type": "text",
        "text": {
            "preview_url": True,
            "body": texto
        }
    }


    try:

        respuesta = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=20
        )


        print("\n==============================")
        print("RESPUESTA DE META")
        print("==============================")

        print("META STATUS:")
        print(respuesta.status_code)

        print("META RESPONSE:")
        print(respuesta.text)

        if 200 <= respuesta.status_code < 300:
            crm_registrar_mensaje(numero, "out", texto)


    except Exception as error:

        print("\nERROR ENVIANDO WHATSAPP:")
        print(error)




# ============================================================
# ENVIAR DOCUMENTOS PUBLICOS POR URL (PLANOS)
# ============================================================

def enviar_documento_url_whatsapp(numero, url_documento, nombre_archivo, caption=""):
    """
    Env├¡a un PDF p├║blico directamente mediante WhatsApp Cloud API.
    Se agrega un par├ímetro de versi├│n para pedir siempre la copia m├ís reciente
    cuando el plano se reemplaza en GitHub Pages conservando el mismo nombre.
    """
    separador = "&" if "?" in url_documento else "?"
    version = datetime.now(ZoneInfo("America/Guatemala")).strftime("%Y%m%d%H%M%S")
    url_actualizada = f"{url_documento}{separador}v={version}"

    url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    documento = {
        "link": url_actualizada,
        "filename": nombre_archivo
    }
    if caption:
        documento["caption"] = caption

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": numero,
        "type": "document",
        "document": documento
    }

    try:
        respuesta = requests.post(url, headers=headers, json=payload, timeout=30)
        print("ENVIAR PLANO STATUS:", respuesta.status_code)
        print("ENVIAR PLANO RESPONSE:", respuesta.text)
        return respuesta.status_code == 200
    except Exception as error:
        print("ERROR ENVIANDO PLANO:")
        print(error)
        return False


def enviar_planos_solicitados(numero, proyecto, texto_cliente):
    """Env├¡a el/los planos correspondientes y SIEMPRE termina con la leyenda de colores."""
    planos = seleccionar_planos(proyecto, texto_cliente)

    if not planos:
        enviar_whatsapp(
            numero,
            "Claro ­ƒÿè ┬┐De qu├® proyecto deseas que te env├¡e el plano: Palmeras San Miguel, Vista Hermosa o Buenaventura Cuyotenango?"
        )
        return False

    nombre = nombre_proyecto_plano(proyecto)
    if len(planos) == 1:
        intro = f"┬íClaro! ­ƒÿè Te comparto el plano actualizado de {planos[0]['nombre']}."
    else:
        intro = f"┬íClaro! ­ƒÿè Te comparto los planos disponibles de {nombre}."

    enviar_whatsapp(numero, intro)

    enviados = 0
    for plano in planos:
        if enviar_documento_url_whatsapp(
            numero,
            plano["url"],
            plano["archivo"],
            caption=plano["nombre"]
        ):
            enviados += 1

    # La explicaci├│n de colores debe acompa├▒ar SIEMPRE cualquier env├¡o de planos.
    enviar_whatsapp(numero, texto_leyenda_planos())

    # Despu├®s de cualquier plano, abrimos la conversaci├│n sobre topograf├¡a
    # y recordamos que la siguiente respuesta corta puede ser "plano" o "quebrado".
    enviar_whatsapp(numero, mensaje_topografia_despues_de_plano())
    marcar_pregunta_topografia(numero)

    return enviados > 0


# ============================================================
# ENVIAR IMAGENES POR WHATSAPP
# ============================================================

def subir_imagen_a_meta(ruta_imagen):
    """
    Sube una imagen local a WhatsApp Cloud API y devuelve el media_id.
    """
    if not os.path.exists(ruta_imagen):
        print("IMAGEN NO ENCONTRADA:", ruta_imagen)
        return None

    url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/media"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}"
    }

    data = {
        "messaging_product": "whatsapp",
        "type": "image/jpeg"
    }

    try:
        with open(ruta_imagen, "rb") as archivo:
            files = {
                "file": (
                    os.path.basename(ruta_imagen),
                    archivo,
                    "image/jpeg"
                )
            }

            respuesta = requests.post(
                url,
                headers=headers,
                data=data,
                files=files,
                timeout=60
            )

        print("SUBIR IMAGEN STATUS:", respuesta.status_code)
        print("SUBIR IMAGEN RESPONSE:", respuesta.text)

        if respuesta.status_code == 200:
            return respuesta.json().get("id")

    except Exception as error:
        print("ERROR SUBIENDO IMAGEN:")
        print(error)

    return None


def enviar_imagen_whatsapp(numero, ruta_imagen, caption=""):
    """
    Sube una imagen a Meta y luego la env├¡a al n├║mero indicado.
    """
    media_id = subir_imagen_a_meta(ruta_imagen)

    if not media_id:
        return False

    url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    imagen = {
        "id": media_id
    }

    if caption:
        imagen["caption"] = caption

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": numero,
        "type": "image",
        "image": imagen
    }

    try:
        respuesta = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )

        print("ENVIAR IMAGEN STATUS:", respuesta.status_code)
        print("ENVIAR IMAGEN RESPONSE:", respuesta.text)

        return respuesta.status_code == 200

    except Exception as error:
        print("ERROR ENVIANDO IMAGEN:")
        print(error)
        return False



def subir_video_a_meta(ruta_video):
    """
    Sube un MP4 local a WhatsApp Cloud API y devuelve media_id.
    """
    if not os.path.exists(ruta_video):
        print("VIDEO NO ENCONTRADO:", ruta_video)
        return None

    url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/media"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}"
    }

    data = {
        "messaging_product": "whatsapp",
        "type": "video/mp4"
    }

    try:
        with open(ruta_video, "rb") as archivo:
            files = {
                "file": (
                    os.path.basename(ruta_video),
                    archivo,
                    "video/mp4"
                )
            }

            respuesta = requests.post(
                url,
                headers=headers,
                data=data,
                files=files,
                timeout=120
            )

        print("SUBIR VIDEO STATUS:", respuesta.status_code)
        print("SUBIR VIDEO RESPONSE:", respuesta.text)

        if respuesta.status_code == 200:
            return respuesta.json().get("id")

    except Exception as error:
        print("ERROR SUBIENDO VIDEO:")
        print(error)

    return None


def enviar_video_whatsapp(numero, ruta_video, caption=""):
    media_id = subir_video_a_meta(ruta_video)

    if not media_id:
        return False

    url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    video = {"id": media_id}

    if caption:
        video["caption"] = caption

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": numero,
        "type": "video",
        "video": video
    }

    try:
        respuesta = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=60
        )

        print("ENVIAR VIDEO STATUS:", respuesta.status_code)
        print("ENVIAR VIDEO RESPONSE:", respuesta.text)

        return respuesta.status_code == 200

    except Exception as error:
        print("ERROR ENVIANDO VIDEO:")
        print(error)
        return False


def enviar_multimedia_del_proyecto(
    numero,
    proyecto,
    enviar_fotos=True,
    enviar_videos=False
):
    """
    Control de multimedia:
    - m├íximo 4 fotos por solicitud;
    - m├íximo 2 videos por solicitud;
    - desde el flujo principal, si el cliente pide fotos O videos, se env├¡an AMBOS;
    - los videos pueden reemplazarse despu├®s conservando el mismo nombre de archivo.
    """

    if not proyecto:
        marcar_multimedia_pendiente(numero)
        enviar_whatsapp(
            numero,
            "Claro ­ƒÿè ┬┐De cu├íl proyecto quieres ver las fotos y videos?"
        )
        return

    limpiar_multimedia_pendiente(numero)

    nombres = {
        "palmeras": "Palmeras San Miguel",
        "vista_hermosa": "Vista Hermosa",
        "buenaventura": "Buenaventura Cuyotenango"
    }

    nombre = nombres.get(proyecto, "el proyecto")

    # EXCEPCI├ôN VISTA HERMOSA:
    # Las fotos generales antiguas quedan fuera del flujo. Si el cliente
    # pide fotos, im├ígenes o videos de Vista Hermosa, enviamos solamente
    # los videos del proyecto.
    if proyecto == "vista_hermosa":
        enviar_fotos = False
        enviar_videos = True

    fotos = IMAGENES_PROYECTOS.get(proyecto, [])
    fotos_disponibles = [r for r in fotos if os.path.exists(r)][:4]

    videos = VIDEOS_PROYECTOS.get(proyecto, [])
    videos_disponibles = [r for r in videos if os.path.exists(r)][:2]

    if enviar_fotos and not fotos_disponibles and not enviar_videos:
        enviar_whatsapp(
            numero,
            f"En este momento no tengo fotos cargadas de {nombre} para "
            "enviarlas autom├íticamente ­ƒÿè"
        )
        return

    if enviar_videos and not videos_disponibles and not enviar_fotos:
        enviar_whatsapp(
            numero,
            f"En este momento no tengo videos cargados de {nombre} para "
            "enviarlos autom├íticamente ­ƒÿè"
        )
        return

    if enviar_fotos and enviar_videos:
        enviar_whatsapp(
            numero,
            f"┬íClaro! ­ƒÖî Te comparto algunas fotos y videos de {nombre} "
            "para que conozcas mejor el proyecto ­ƒÅí­ƒô©­ƒÄÑ"
        )
    elif enviar_fotos:
        enviar_whatsapp(
            numero,
            f"┬íClaro! ­ƒÖî Te comparto algunas im├ígenes de {nombre} "
            "para que conozcas mejor el proyecto ­ƒÅí­ƒô©"
        )
    elif enviar_videos:
        enviar_whatsapp(
            numero,
            f"┬íClaro! ­ƒÄÑ Te comparto un par de videos de {nombre} "
            "para que puedas conocer mejor el proyecto ­ƒÅí"
        )

    if enviar_fotos:
        for i, ruta in enumerate(fotos_disponibles, start=1):
            caption = f"{nombre} ­ƒÅí­ƒô©" if i == 1 else ""
            enviar_imagen_whatsapp(
                numero,
                ruta,
                caption=caption
            )

    if enviar_videos:
        for i, ruta in enumerate(videos_disponibles, start=1):
            caption = f"{nombre} ­ƒÄÑ­ƒÅí" if i == 1 else ""
            enviar_video_whatsapp(
                numero,
                ruta,
                caption=caption
            )

    # Cuando el cliente pide fotos o videos, adem├ís del material general
    # del proyecto enviamos tambi├®n fotos y videos de las amenidades.
    enviar_paquete_amenidades(numero, proyecto)

    enviar_whatsapp(
        numero,
        "Si quieres, tambi├®n puedo ayudarte con precios, financiamiento "
        "o coordinar una visita ­ƒÖî­ƒôì"
    )


def enviar_solo_fotos_del_proyecto(numero, proyecto):
    """
    Se usa despu├®s de enviar cotizaciones por precio:
    manda TODAS las fotos del proyecto, pero no los videos.
    """
    if not proyecto:
        return

    nombres = {
        "palmeras": "Palmeras San Miguel",
        "vista_hermosa": "Vista Hermosa",
        "buenaventura": "Buenaventura Cuyotenango"
    }

    nombre = nombres.get(proyecto, "el proyecto")

    fotos = IMAGENES_PROYECTOS.get(proyecto, [])
    fotos_disponibles = [r for r in fotos if os.path.exists(r)]

    if not fotos_disponibles:
        return

    enviar_whatsapp(
        numero,
        f"Y para que conozcas mejor {nombre}, te comparto tambi├®n "
        "las fotos del proyecto ­ƒÅí­ƒô©"
    )

    # Despu├®s de precios enviamos m├íximo 4 fotos.
    for i, ruta in enumerate(fotos_disponibles[:4], start=1):
        caption = f"{nombre} ­ƒÅí­ƒô©" if i == 1 else ""
        enviar_imagen_whatsapp(
            numero,
            ruta,
            caption=caption
        )



# ============================================================
# ENVIAR COTIZACIONES
# ============================================================


def enviar_solo_videos_del_proyecto(numero, proyecto):
    """
    Se usa despu├®s de enviar cotizaciones cuando el proyecto es Vista Hermosa.
    Env├¡a ├║nicamente videos generales del proyecto, sin fotos y sin amenidades.
    Las amenidades se env├¡an despu├®s en su propio bloque.
    """
    if not proyecto:
        return

    nombres = {
        "palmeras": "Palmeras San Miguel",
        "vista_hermosa": "Vista Hermosa",
        "buenaventura": "Buenaventura Cuyotenango"
    }

    nombre = nombres.get(proyecto, "el proyecto")
    videos = VIDEOS_PROYECTOS.get(proyecto, [])
    videos_disponibles = [r for r in videos if os.path.exists(r)][:2]

    if not videos_disponibles:
        return

    enviar_whatsapp(
        numero,
        f"Y para que conozcas mejor {nombre}, te comparto tambi├®n "
        "videos del proyecto ­ƒÅí­ƒÄÑ"
    )

    for i, ruta in enumerate(videos_disponibles, start=1):
        enviar_video_whatsapp(
            numero,
            ruta,
            caption=f"{nombre} ­ƒÄÑ­ƒÅí" if i == 1 else ""
        )

def enviar_cotizacion_del_proyecto(numero, proyecto, medida=None):
    """
    FLUJO DEFINITIVO PARA PRECIOS:
    1. Si ya existe proyecto activo, NO pregunta proyecto ni medida.
    2. Manda una explicaci├│n breve del proyecto con amenidades/servicios.
    3. Manda TODAS las im├ígenes de cotizaci├│n del proyecto.
    4. Termina con un CTA corto.
    """

    if not proyecto:
        enviar_whatsapp(
            numero,
            "┬íClaro! ­ƒÿè ┬┐En qu├® proyecto est├ís interesado para enviarte "
            "las cotizaciones correctas? ­ƒÅí"
        )
        return

    resumen = construir_resumen_cotizacion(proyecto)

    if resumen:
        enviar_whatsapp(numero, resumen)

    opciones = COTIZACIONES_IMAGEN.get(proyecto, {})
    rutas_a_enviar = []

    # Si el cliente indic├│ una medida concreta, manda ├║nicamente esa medida.
    # Si no indic├│ medida, manda todas las opciones disponibles del proyecto.
    opciones_iterar = opciones
    if medida and medida in opciones:
        opciones_iterar = {medida: opciones[medida]}

    for medida_nombre, rutas in opciones_iterar.items():
        for ruta in rutas:
            if os.path.exists(ruta):
                rutas_a_enviar.append((medida_nombre, ruta))

    if not rutas_a_enviar:
        enviar_whatsapp(
            numero,
            "En este momento no tengo cargadas las im├ígenes de cotizaci├│n. "
            "D├®jame revisarlas para darte la informaci├│n correcta ­ƒæì"
        )
        return

    for medida_nombre, ruta in rutas_a_enviar:
        caption = ETIQUETAS_COTIZACIONES.get(
            proyecto,
            {}
        ).get(
            ruta,
            f"Cotizaci├│n {medida_nombre} ­ƒÆ░"
        )

        enviar_imagen_whatsapp(
            numero,
            ruta,
            caption=caption
        )

    # FLUJO VISUAL DESPU├ëS DE PRECIOS/COTIZACIONES:
    # 1) Palmeras y Buenaventura -> fotos reales del residencial.
    # 2) Vista Hermosa -> SOLO videos del residencial (sin fotos antiguas).
    # 3) Al final -> SOLO videos de amenidades, en un bloque separado.
    if proyecto == "vista_hermosa":
        enviar_solo_videos_del_proyecto(numero, proyecto)
    else:
        enviar_solo_fotos_del_proyecto(numero, proyecto)

    enviar_paquete_amenidades(numero, proyecto)

    enviar_whatsapp(
        numero,
        "Si alguna opci├│n te llama la atenci├│n, dime cu├íl ­ƒÿè y con gusto te doy "
        "m├ís informaci├│n o resolvemos cualquier duda que tengas ­ƒÅí"
    )

# ============================================================
# SEGUIMIENTO AUTOMATICO POR INACTIVIDAD - PRUEBA
# ============================================================

# PRODUCCION: seguimiento despu├®s de 8 horas sin respuesta.
SEGUIMIENTO_SEGUNDOS = 8 * 60 * 60

SEGUIMIENTO_TEXTO = (
    "Hola ­ƒæï­ƒÿè Solo paso por aqu├¡.\n\n"
    "Quiz├í no ha tenido tiempo de revisar con calma la informaci├│n de los terrenos "
    "que le envi├® ­ƒÅí. No hay problema.\n\n"
    "Cuando pueda verla, escr├¡bame. Si alguna opci├│n le interesa, con gusto le ayudo "
    "a hacer n├║meros para buscar una cuota c├│moda para usted Ô£à\n\n"
    "­ƒæë ┬┐Qu├® cuota mensual le quedar├¡a c├│moda?"
)

seguimiento_version = {}
lock_seguimiento = Lock()


def cancelar_seguimiento(numero):
    """Invalida cualquier seguimiento pendiente de ese cliente."""
    if not numero:
        return

    with lock_seguimiento:
        seguimiento_version[numero] = seguimiento_version.get(numero, 0) + 1



def programar_seguimiento_inactividad(numero):
    """
    Programa un seguimiento. Si el cliente escribe de nuevo antes del tiempo,
    la versi├│n anterior queda cancelada autom├íticamente.
    """
    with lock_seguimiento:
        version = seguimiento_version.get(numero, 0) + 1
        seguimiento_version[numero] = version

    def esperar_y_enviar():
        time.sleep(SEGUIMIENTO_SEGUNDOS)

        with lock_seguimiento:
            if seguimiento_version.get(numero) != version:
                return

        # Si esta versi├│n sigue vigente, el cliente no volvi├│ a escribir
        # durante el tiempo configurado.
        enviar_whatsapp(numero, SEGUIMIENTO_TEXTO)
        guardar_mensaje(numero, "assistant", SEGUIMIENTO_TEXTO)

        # Marcar esta versi├│n como consumida para que se env├¡e una sola vez.
        with lock_seguimiento:
            if seguimiento_version.get(numero) == version:
                seguimiento_version[numero] = version + 1

    Thread(target=esperar_y_enviar, daemon=True).start()


# ============================================================
# AGRUPAR MENSAJES SEGUIDOS DEL CLIENTE
# ============================================================

ESPERA_BLOQUE_MENSAJES_SEGUNDOS = 5
mensajes_texto_pendientes = {}
lock_mensajes_texto_pendientes = Lock()


def acumular_mensaje_texto(numero, message_id, mensaje):
    """Guarda temporalmente mensajes de texto consecutivos del mismo cliente."""
    if not numero or not message_id or not mensaje or mensaje.get("type") != "text":
        return

    texto = (mensaje.get("text") or {}).get("body", "").strip()
    if not texto:
        return

    with lock_mensajes_texto_pendientes:
        lista = mensajes_texto_pendientes.setdefault(numero, [])
        lista.append({"id": message_id, "texto": texto})

        if len(lista) > 20:
            mensajes_texto_pendientes[numero] = lista[-20:]


def esperar_y_obtener_bloque_texto(numero, message_id):
    """Espera 5 segundos desde el ├║ltimo texto y devuelve el bloque completo."""
    time.sleep(ESPERA_BLOQUE_MENSAJES_SEGUNDOS)

    if not procesamiento_sigue_vigente(numero, message_id):
        return None

    with lock_mensajes_texto_pendientes:
        pendientes = mensajes_texto_pendientes.pop(numero, [])

    textos = [
        item.get("texto", "").strip()
        for item in pendientes
        if item.get("texto", "").strip()
    ]

    if not textos:
        return None

    return "\n".join(textos)


# ============================================================
# RECIBIR MENSAJES DE WHATSAPP
# ============================================================

def procesar_mensaje_en_segundo_plano(datos, message_id):
    """
    Procesa IA, cotizaciones, fotos y videos DESPUES de que el webhook
    ya respondi├│ 200 a Meta. As├¡ Meta no interpreta que tardamos y no
    reenv├¡a el mismo mensaje una y otra vez.
    """
    try:
        value = datos["entry"][0]["changes"][0]["value"]

        if "messages" not in value:
            return

        mensaje = value["messages"][0]

        numero_cliente = mensaje["from"]
        tipo_mensaje = mensaje.get("type")

        if tipo_mensaje == "text":
            texto_agrupado = esperar_y_obtener_bloque_texto(
                numero_cliente,
                message_id
            )

            if texto_agrupado is None:
                print("PROCESAMIENTO ANTIGUO CANCELADO:", message_id)
                return
        else:
            if not procesamiento_sigue_vigente(numero_cliente, message_id):
                print("PROCESAMIENTO ANTIGUO CANCELADO:", message_id)
                return

        print("\nNUMERO DEL CLIENTE:")
        print(numero_cliente)

        # Si Gabriel tom├│ el control desde el CRM, la IA no responde.
        # El mensaje ya qued├│ registrado por el webhook para verlo en el CRM.
        if crm_esta_manual(numero_cliente):
            print("CRM: conversaci├│n en modo MANUAL. IA pausada.")
            return

        if tipo_mensaje == "audio":
            # La nota de voz se convierte en texto y contin├║a por TODO el flujo normal.
            enviar_presentacion_si_corresponde(
                numero_cliente,
                message_id
            )

            texto_cliente = transcribir_audio_whatsapp(
                mensaje
            )

            if not texto_cliente:
                if procesamiento_sigue_vigente(
                    numero_cliente,
                    message_id
                ):
                    enviar_whatsapp(
                        numero_cliente,
                        "Recib├¡ tu audio ­ƒÄÖ´©Å­ƒÿè, pero no pude transcribirlo "
                        "en este momento. Intenta enviarlo nuevamente."
                    )
                return

            print("\nAUDIO TRANSCRITO:")
            print(texto_cliente)

        elif tipo_mensaje != "text":
            # Fotos y videos se analizan; otros archivos reciben respuesta controlada.
            enviar_presentacion_si_corresponde(
                numero_cliente,
                message_id
            )

            respuesta_media = procesar_imagen_o_video_cliente(
                numero_cliente,
                mensaje,
                tipo_mensaje
            )

            if procesamiento_sigue_vigente(
                numero_cliente,
                message_id
            ):
                enviar_whatsapp(
                    numero_cliente,
                    respuesta_media
                )

            return

        else:
            if tipo_mensaje == "text":
                texto_cliente = texto_agrupado

        print("\nMENSAJE DEL CLIENTE:")
        print(texto_cliente)

        # PRESENTACION INICIAL OBLIGATORIA:
        # antes de precios, cotizaciones, ubicaci├│n, fotos, videos o respuesta IA.
        # Si el cliente pidi├│ algo concreto, despu├®s de esta presentaci├│n
        # el flujo contin├║a normalmente y entrega lo solicitado.
        presentacion_enviada = enviar_presentacion_si_corresponde(
            numero_cliente,
            message_id
        )

        # Si el PRIMER mensaje fue ├║nicamente un saludo, ya respondimos con la
        # presentaci├│n. Terminamos aqu├¡ para que OpenAI no mande un segundo saludo.
        #
        # Si escribi├│ algo como:
        # "Hola, ┬┐cu├ínto cuesta Buenaventura?"
        # NO entra aqu├¡: se presenta y luego contin├║a para responder la consulta.
        if presentacion_enviada and es_solo_saludo(texto_cliente):
            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(
                numero_cliente,
                "assistant",
                mensaje_presentacion_inicial()
            )
            return

        # Si el mensaje naci├│ desde un anuncio Click-to-WhatsApp, fijamos primero
        # el proyecto seg├║n referral.source_id. Despu├®s, si el cliente menciona
        # expl├¡citamente otro proyecto en el texto, esa menci├│n tiene prioridad.
        fijar_proyecto_desde_anuncio(numero_cliente, mensaje)

        # Mantener proyecto fijo por n├║mero.
        proyecto = actualizar_proyecto_activo(
            numero_cliente,
            texto_cliente
        )

        # CONTINUACI├ôN DE FOTOS/VIDEOS PENDIENTES
        # Ejemplo:
        # Cliente: "Me puede fotos"
        # Bot: "┬┐De cu├íl proyecto?"
        # Cliente: "Palmeras San Miguel"
        # => enviar el material inmediatamente, sin volver a preguntar qu├® desea.
        if multimedia_pendiente(numero_cliente) and proyecto:
            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(
                numero_cliente,
                "assistant",
                f"Se envi├│ el material multimedia del proyecto {proyecto}."
            )

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_multimedia_del_proyecto(
                    numero_cliente,
                    proyecto,
                    enviar_fotos=True,
                    enviar_videos=True
                )
            return

        # SEGUIMIENTO DE TOPOGRAF├ìA DESPU├ëS DE ENVIAR PLANOS
        # Tiene prioridad para que "plano" no vuelva a interpretarse como el PDF.
        respuesta_pref_topografia = respuesta_preferencia_topografia(
            numero_cliente,
            texto_cliente,
            proyecto
        )
        if respuesta_pref_topografia:
            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta_pref_topografia)
            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta_pref_topografia)
            return

        # Si ya estamos hablando de topograf├¡a y manda un n├║mero de lote.
        respuesta_lote_topografia = respuesta_revision_lote_topografia(
            numero_cliente,
            proyecto,
            texto_cliente
        )
        if respuesta_lote_topografia:
            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta_lote_topografia)
            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta_lote_topografia)
            return

        # Si pregunta si el lote elegido es quebrado/inclinado.
        respuesta_quebrado = respuesta_si_pregunta_quebrado(
            numero_cliente,
            proyecto,
            texto_cliente
        )
        if respuesta_quebrado:
            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta_quebrado)
            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta_quebrado)
            return

        # PROCESO DE COMPRA Y SEGUIMIENTOS DIRECTOS
        respuesta_compra_directa = seguimiento_compra_respuesta_directa(
            texto_cliente,
            proyecto
        )
        if respuesta_compra_directa:
            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta_compra_directa)
            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta_compra_directa)
            return

        if pregunta_proceso_compra(texto_cliente):
            respuesta = respuesta_proceso_compra(proyecto)
            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)
            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)
            return

        # BANCO / FINANCIAMIENTO PROPIO - PRIORIDAD ABSOLUTA
        # Si la frase menciona banco + financiamiento, nunca debe caer en cotizaciones.
        if pregunta_banco_financiamiento(texto_cliente):
            respuesta = respuesta_financiamiento_propio()

            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)

            return

        # PLAZO DE ENTREGA DE ESCRITURA - PRIORIDAD SUPERIOR A GASTOS
        if pregunta_plazo_escritura(texto_cliente):
            respuesta = respuesta_plazo_escritura()

            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)

            return

        # TITULO DE AGUA - EXPLICACION ESPECIFICA
        if pregunta_titulo_agua(texto_cliente):
            respuesta = respuesta_titulo_agua(proyecto)

            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)

            return

        # QUE INCLUYE / POR QUE SE PAGA EL MANTENIMIENTO - PRIORIDAD ALTA
        if pregunta_que_incluye_mantenimiento(texto_cliente):
            respuesta = respuesta_que_incluye_mantenimiento()

            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)

            return

        # COSTOS / GASTOS ADICIONALES - PRIORIDAD ABSOLUTA
        # Debe resolverse antes de IA, cotizaci├│n, cuotas o cualquier otra rama.
        # Tambi├®n conserva el tema para seguimientos como "┬┐cu├ínto es de cada uno?".
        if (
            pide_gastos_adicionales(texto_cliente)
            or seguimiento_gastos_adicionales(numero_cliente, texto_cliente)
            or respuesta_proyecto_pendiente_de_gastos(numero_cliente, texto_cliente)
        ):
            ultima_intencion[numero_cliente] = "gastos_adicionales"
            respuesta = respuesta_gastos_adicionales(proyecto)

            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)

            return

        # TOPOGRAF├ìA DEL TERRENO - RESPUESTA INTELIGENTE
        # "lote plano" significa terreno llano; NO debe enviar el PDF/croquis.
        if pregunta_topografia_terreno(texto_cliente):
            respuesta = generar_respuesta(
                numero_cliente,
                texto_cliente
            )

            if not respuesta or not respuesta.strip():
                respuesta = (
                    "Claro ­ƒÿè D├®jame revisar exactamente lo que me solicitas "
                    "y te lo env├¡o en un momento."
                )

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)

            return

        # PLANOS / MAPA DE LOTES - PRIORIDAD ALTA
        # Usa los PDF p├║blicos de GitHub Pages. Si el archivo se actualiza
        # conservando el mismo nombre, el bot seguir├í enviando la versi├│n nueva.
        if pide_plano(texto_cliente):
            # Si el mensaje trae un proyecto expl├¡cito, actualizar_proyecto_activo
            # ya lo habr├í fijado. Si no, usamos el proyecto de la conversaci├│n.
            if not proyecto:
                respuesta = (
                    "Claro ­ƒÿè ┬┐De qu├® proyecto deseas que te env├¡e el plano: "
                    "Palmeras San Miguel, Vista Hermosa o Buenaventura Cuyotenango?"
                )
                guardar_mensaje(numero_cliente, "user", texto_cliente)
                guardar_mensaje(numero_cliente, "assistant", respuesta)
                if procesamiento_sigue_vigente(numero_cliente, message_id):
                    enviar_whatsapp(numero_cliente, respuesta)
                return

            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(
                numero_cliente,
                "assistant",
                f"Se enviaron los planos de {nombre_proyecto_plano(proyecto)}, la leyenda de colores y la pregunta sobre topograf├¡a."
            )

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_planos_solicitados(
                    numero_cliente,
                    proyecto,
                    texto_cliente
                )
            return

        # PLAZO DE ENTREGA / URBANIZACION
        if pregunta_plazo_entrega_urbanizacion(texto_cliente):
            respuesta = respuesta_plazo_entrega_urbanizacion(proyecto)

            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)

            return

        # AMENIDAD ESPECIFICA:
        # Responde la pregunta y manda fotos/videos relacionados.
        amenidad_pedida = detectar_amenidad_solicitada(texto_cliente)

        if amenidad_pedida:
            respuesta = respuesta_amenidad(
                proyecto,
                amenidad_pedida,
                texto_cliente
            )

            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)

                enviar_material_amenidad(
                    numero_cliente,
                    proyecto,
                    amenidad_pedida
                )

            return

        # RUTA / XOCHI - PRIORIDAD ALTA:
        # Debe ejecutarse ANTES de visita porque frases como "puedo ir por Xochi"
        # contienen "puedo ir" pero son preguntas de ruta, no de agendamiento.
        if pregunta_como_llegar_o_mejor_ruta(texto_cliente):
            respuesta_ruta = respuesta_ruta_recomendada(proyecto)

            if respuesta_ruta:
                guardar_mensaje(numero_cliente, "user", texto_cliente)
                guardar_mensaje(numero_cliente, "assistant", respuesta_ruta)

                if procesamiento_sigue_vigente(numero_cliente, message_id):
                    enviar_whatsapp(numero_cliente, respuesta_ruta)
                    enviar_tarifario_xochi(numero_cliente)

                return

        # PUNTO DE ENCUENTRO:
        # Si el cliente pregunta d├│nde nos podemos juntar, sugerimos primero
        # el proyecto y luego un punto cercano conocido, sin dejar la respuesta abierta.
        if pregunta_punto_encuentro(texto_cliente):
            respuesta = respuesta_punto_encuentro(
                numero_cliente,
                proyecto
            )

            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)

            return

        # CITA YA CERRADA:
        # Nunca volvemos a ofrecer otra visita ni preguntamos otro d├¡a/hora
        # a menos que el cliente pida expl├¡citamente cambiar/reprogramar.
        if cita_ya_cerrada(numero_cliente) and pregunta_sobre_cita_existente(texto_cliente):
            respuesta = resumen_cita_cerrada(numero_cliente)

            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)

            return

        # VISITA / CITA:
        # Si el cliente ya quiere conocer los lotes, dejamos de repetir informaci├│n
        # y avanzamos directamente a coordinar d├¡a y hora.
        if (
            not cita_ya_cerrada(numero_cliente)
            and (
                detectar_intencion_visita(texto_cliente)
                or continuar_visita_pendiente(
                    numero_cliente,
                    texto_cliente
                )
            )
        ):
            respuesta = respuesta_visita(
                numero_cliente,
                texto_cliente,
                proyecto
            )

            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)

            return

        # COMPRA DESDE EL EXTRANJERO / REQUISITOS
        # Si el cliente dice que est├í fuera de Guatemala, o pide requisitos,
        # damos los documentos y un CTA claro para avanzar.
        if cliente_en_extranjero(texto_cliente) or pide_requisitos_compra(texto_cliente):
            respuesta = respuesta_requisitos_segun_contexto(
                numero_cliente,
                texto_cliente
            )

            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)

            return

        # ENGANCHE - RESPUESTA DIRECTA Y PRIORITARIA
        # Aplica a todos los proyectos: desde Q6,000 y puede fraccionarse
        # en 2 pagos mensuales de Q3,000. No manda cotizaciones si solo
        # preguntan por el enganche.
        if pregunta_enganche(texto_cliente):
            ultima_intencion[numero_cliente] = "enganche"
            respuesta = respuesta_enganche(proyecto, texto_cliente)

            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)

            return

        # MEDIDAS DISPONIBLES - RESPUESTA DIRECTA
        if pregunta_medidas_disponibles(texto_cliente):
            respuesta = respuesta_medidas_disponibles(proyecto)
            if respuesta:
                guardar_mensaje(numero_cliente, "user", texto_cliente)
                guardar_mensaje(numero_cliente, "assistant", respuesta)
                if procesamiento_sigue_vigente(numero_cliente, message_id):
                    enviar_whatsapp(numero_cliente, respuesta)
                return

        # MEDIDA ESPECIFICA - PRECIO Y ENGANCHE EXACTOS
        medida_consultada = detectar_medida_en_texto(texto_cliente)
        if medida_consultada and not pregunta_cuota_especifica(texto_cliente):
            # Si pide expl├¡citamente una cotizaci├│n, esa intenci├│n se atiende m├ís abajo
            # para poder enviar la imagen correspondiente. Para consultas naturales como
            # "┬┐lotes de 8x18?" o "┬┐cu├ínto vale 8x16?", respondemos con el monto exacto.
            if not any(x in texto_cliente.lower() for x in ["cotizacion", "cotizaci├│n", "cotizaciones"]):
                respuesta = respuesta_medida_especifica(proyecto, medida_consultada, texto_cliente)
                if respuesta:
                    guardar_mensaje(numero_cliente, "user", texto_cliente)
                    guardar_mensaje(numero_cliente, "assistant", respuesta)
                    if procesamiento_sigue_vigente(numero_cliente, message_id):
                        enviar_whatsapp(numero_cliente, respuesta)
                    return

        # CANTIDAD DE LOTES DEL PROYECTO
        if pregunta_cantidad_lotes(texto_cliente):
            respuesta = respuesta_cantidad_lotes(proyecto)

            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)

            return

        # CLIMA DEL LUGAR
        if pregunta_clima_lugar(texto_cliente):
            respuesta = respuesta_clima_lugar()

            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)

            return

        # MEJOR RUTA / XOCHI
        # Si por el proyecto activo la mejor recomendaci├│n es Xochi,
        # responde la ruta y env├¡a autom├íticamente el tarifario.
        if pregunta_como_llegar_o_mejor_ruta(texto_cliente):
            respuesta_ruta = respuesta_ruta_recomendada(proyecto)

            if respuesta_ruta:
                guardar_mensaje(numero_cliente, "user", texto_cliente)
                guardar_mensaje(numero_cliente, "assistant", respuesta_ruta)

                if procesamiento_sigue_vigente(numero_cliente, message_id):
                    enviar_whatsapp(numero_cliente, respuesta_ruta)
                    enviar_tarifario_xochi(numero_cliente)

                return

        # UBICACION
        if pide_ubicacion(texto_cliente):
            enviar_ubicacion_proyecto(
                numero_cliente,
                proyecto
            )
            return

        # Diferencia de precio entre fases
        if pregunta_por_diferencia_de_fases(texto_cliente):
            respuesta = respuesta_diferencia_fases(numero_cliente)

            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)

            enviar_whatsapp(numero_cliente, respuesta)
            return

        # CUOTA ESPECIFICA POR PLAZO:
        # Si pregunta "┬┐cu├ínto es la cuota a 7 a├▒os?", responder el monto.
        # NO volver a enviar las im├ígenes de cotizaci├│n.
        if pregunta_cuota_especifica(texto_cliente):
            respuesta = respuesta_cuota_especifica(
                proyecto,
                texto_cliente
            )

            if respuesta:
                guardar_mensaje(numero_cliente, "user", texto_cliente)
                guardar_mensaje(numero_cliente, "assistant", respuesta)

                if procesamiento_sigue_vigente(numero_cliente, message_id):
                    enviar_whatsapp(numero_cliente, respuesta)

                return

        # PRECIOS / CUOTAS / COTIZACIONES
        # Si el cliente pide cotizaci├│n o confirma una cotizaci├│n ofrecida,
        # se env├¡a DE UNA VEZ. No se vuelve a preguntar plazo, medida o si quiere verla.
        if debe_enviar_cotizacion_directa(
            numero_cliente,
            texto_cliente
        ):
            enviar_cotizacion_del_proyecto(
                numero_cliente,
                proyecto,
                detectar_medida_en_texto(texto_cliente)
            )
            return

        # MULTIMEDIA CONTROLADA
        # NUEVA REGLA:
        # Si el cliente pide FOTOS O VIDEOS, enviamos AMBOS de una vez.
        quiere_fotos = pide_fotos(texto_cliente)
        quiere_videos = pide_videos(texto_cliente)

        if quiere_fotos or quiere_videos:
            enviar_multimedia_del_proyecto(
                numero_cliente,
                proyecto,
                enviar_fotos=True,
                enviar_videos=True
            )
            return

        # RESPUESTA NORMAL CON IA
        respuesta_ia = generar_respuesta(
            numero_cliente,
            texto_cliente
        )

        print("\nRESPUESTA IA:")
        print(respuesta_ia)

        if procesamiento_sigue_vigente(numero_cliente, message_id):
            enviar_whatsapp(
                numero_cliente,
                respuesta_ia
            )

            # Si la IA recomend├│ Xochi al responder una consulta de ruta,
            # adjuntamos el tarifario autom├íticamente.
            if (
                pregunta_como_llegar_o_mejor_ruta(texto_cliente)
                and "xochi" in respuesta_ia.lower()
            ):
                enviar_tarifario_xochi(numero_cliente)
        else:
            print("RESPUESTA TARDIA CANCELADA:", message_id)

    except Exception as error:
        print("\nERROR PROCESANDO MENSAJE:")
        print(error)

    finally:
        # El tiempo de inactividad empieza DESPU├ëS de que el bot termina
        # de responder, incluso si era el primer mensaje de la conversaci├│n.
        # Si el cliente mand├│ otro mensaje mientras proces├íbamos, este proceso
        # viejo no programa ning├║n seguimiento.
        try:
            if (
                numero_cliente
                and procesamiento_sigue_vigente(numero_cliente, message_id)
                and not crm_esta_manual(numero_cliente)
            ):
                programar_seguimiento_inactividad(numero_cliente)
        except Exception as error_seguimiento:
            print("\nERROR PROGRAMANDO SEGUIMIENTO:")
            print(error_seguimiento)


@app.route("/webhook", methods=["POST"])
def recibir_webhook():
    """
    Recibe mensajes desde Meta.

    IMPORTANTE:
    Meta puede incluir M├üS DE UN mensaje dentro de value["messages"].
    Procesamos cada elemento por separado para que cada mensaje:
    - aparezca en el CRM;
    - genere su propia notificaci├│n Push;
    - sea procesado por el bot.
    """
    datos = request.get_json()

    print("\n========================================")
    print("WEBHOOK RECIBIDO")
    print("========================================")

    try:
        value = datos["entry"][0]["changes"][0]["value"]

        # Estados de enviado / entregado / le├¡do.
        if "messages" not in value:
            print("Evento recibido, pero no es mensaje entrante.")
            return "EVENT_RECEIVED", 200

        mensajes = value.get("messages") or []

        if not mensajes:
            return "EVENT_RECEIVED", 200

        print("MENSAJES EN ESTE WEBHOOK:", len(mensajes))

        for mensaje in mensajes:
            try:
                message_id = mensaje.get("id")

                # Si Meta reintenta EL MISMO mensaje, no duplicamos nada.
                if not marcar_mensaje_como_procesado(message_id):
                    print("MENSAJE DUPLICADO IGNORADO:", message_id)
                    continue

                numero_cliente = mensaje.get("from")

                # 1) Guardar en CRM y disparar UNA notificaci├│n propia.
                crm_registrar_mensaje(
                    numero_cliente,
                    "in",
                    crm_resumen_entrante(mensaje),
                    event_id=message_id
                )

                # 2) Cancelar seguimiento pendiente.
                cancelar_seguimiento(numero_cliente)

                # 3) Este mensaje pasa a ser el procesamiento vigente.
                iniciar_procesamiento(
                    numero_cliente,
                    message_id
                )

                acumular_mensaje_texto(
                    numero_cliente,
                    message_id,
                    mensaje
                )

                # Construimos un payload individual para reutilizar
                # el procesador existente sin hacerle creer que solo
                # existe el primer elemento de un webhook agrupado.
                datos_individuales = {
                    "object": datos.get("object"),
                    "entry": [{
                        **datos["entry"][0],
                        "changes": [{
                            **datos["entry"][0]["changes"][0],
                            "value": {
                                **value,
                                "messages": [mensaje]
                            }
                        }]
                    }]
                }

                Thread(
                    target=procesar_mensaje_en_segundo_plano,
                    args=(datos_individuales, message_id),
                    daemon=True
                ).start()

            except Exception as error_mensaje:
                print(
                    "ERROR PROCESANDO ELEMENTO DEL WEBHOOK:",
                    mensaje.get("id"),
                    error_mensaje
                )

        # Meta recibe 200 inmediatamente despu├®s de despachar todos.
        return "EVENT_RECEIVED", 200

    except Exception as error:
        print("\nERROR DEL WEBHOOK:")
        print(error)

        # Siempre respondemos 200 para evitar reintentos infinitos.
        return "EVENT_RECEIVED", 200


# ============================================================
# CRM WEB - GABRIEL
# ============================================================

CRM_HTML = r"""
<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>CRM Gabriel</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #f4f6f8;
            color: #17212b;
        }
        .top {
            background: #111827;
            color: white;
            padding: 14px 18px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 5;
        }
        .top strong { font-size: 18px; }
        .top a {
            color: white;
            text-decoration: none;
            border: 1px solid #64748b;
            border-radius: 8px;
            padding: 7px 10px;
            font-size: 13px;
        }
        .layout {
            display: grid;
            grid-template-columns: 330px 1fr;
            min-height: calc(100vh - 55px);
        }
        .sidebar {
            background: white;
            border-right: 1px solid #dbe1e7;
            overflow-y: auto;
        }
        .sidebar-title {
            padding: 16px;
            font-weight: bold;
            border-bottom: 1px solid #edf0f2;
        }
        .chat-link {
            display: block;
            padding: 14px 16px;
            color: inherit;
            text-decoration: none;
            border-bottom: 1px solid #edf0f2;
        }
        .chat-link:hover, .chat-link.active { background: #f0f7f4; }
        .phone { font-weight: 700; }
        .preview {
            margin-top: 5px;
            color: #667085;
            font-size: 13px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .small {
            margin-top: 5px;
            font-size: 12px;
            color: #84909d;
        }
        .status {
            display: inline-block;
            padding: 3px 7px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: bold;
        }
        .status.ai { background: #dcfce7; color: #166534; }
        .status.manual { background: #fee2e2; color: #991b1b; }
        .main {
            display: flex;
            flex-direction: column;
            min-width: 0;
        }
        .chat-head {
            background: white;
            padding: 13px 18px;
            border-bottom: 1px solid #dbe1e7;
            display: flex;
            justify-content: space-between;
            gap: 10px;
            align-items: center;
        }
        .chat-head h2 { margin: 0; font-size: 17px; }
        .chat-head p { margin: 4px 0 0; color: #667085; font-size: 13px; }
        .toggle {
            border: 0;
            border-radius: 9px;
            padding: 10px 13px;
            cursor: pointer;
            font-weight: 700;
        }
        .toggle.pause { background: #fee2e2; color: #991b1b; }
        .toggle.resume { background: #dcfce7; color: #166534; }
        .messages {
            flex: 1;
            padding: 18px;
            overflow-y: auto;
            min-height: 60vh;
        }
        .row { display: flex; margin-bottom: 10px; }
        .row.in { justify-content: flex-start; }
        .row.out { justify-content: flex-end; }
        .bubble {
            max-width: 76%;
            padding: 10px 12px;
            border-radius: 12px;
            white-space: pre-wrap;
            line-height: 1.35;
            box-shadow: 0 1px 2px rgba(0,0,0,.06);
        }
        .in .bubble { background: white; }
        .out .bubble { background: #d9fdd3; }
        .time {
            display: block;
            text-align: right;
            font-size: 10px;
            color: #6b7280;
            margin-top: 5px;
        }
        .composer {
            background: white;
            border-top: 1px solid #dbe1e7;
            padding: 12px;
            position: sticky;
            bottom: 0;
        }
        .composer form {
            display: flex;
            gap: 8px;
        }
        .composer textarea {
            flex: 1;
            min-height: 46px;
            resize: vertical;
            padding: 10px;
            border: 1px solid #cfd6dd;
            border-radius: 9px;
            font: inherit;
        }
        .send {
            border: 0;
            background: #16a34a;
            color: white;
            font-weight: bold;
            border-radius: 9px;
            padding: 0 18px;
            cursor: pointer;
        }
        .empty {
            margin: auto;
            color: #667085;
            text-align: center;
            padding: 50px;
        }
        .notice {
            padding: 8px 18px;
            background: #fff7ed;
            border-bottom: 1px solid #fed7aa;
            color: #9a3412;
            font-size: 12px;
        }
        @media (max-width: 760px) {
            .layout { grid-template-columns: 1fr; }
            .sidebar {
                max-height: 34vh;
                border-right: 0;
                border-bottom: 1px solid #dbe1e7;
            }
            .bubble { max-width: 88%; }
            .chat-head { align-items: flex-start; }
        }
    </style>
</head>
<body>
    <div class="top">
        <strong>­ƒÅí CRM Gabriel <span style="font-size:12px;color:#86efac;">ÔùÅ En vivo</span></strong>
        <div style="display:flex;gap:8px;align-items:center;">
            <button id="btn-notificaciones"
                    type="button"
                    style="background:#1f2937;color:white;border:1px solid #64748b;border-radius:8px;padding:7px 10px;cursor:pointer;">
                ­ƒô▒ Activar notificaciones
            </button>
            <button id="btn-probar-push"
                    type="button"
                    style="background:#065f46;color:white;border:1px solid #047857;border-radius:8px;padding:7px 10px;cursor:pointer;">
                ­ƒº¬ Probar m├│vil
            </button>
            <a href="{{ url_for('crm') }}">Actualizar</a>
        </div>
    </div>

    <div class="layout">
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-title">Conversaciones (<span id="client-count">{{ clientes|length }}</span>)</div>
            {% if not clientes %}
                <div style="padding:20px;color:#667085;">
                    Todav├¡a no han entrado mensajes desde que se inici├│ esta versi├│n.
                </div>
            {% endif %}

            {% for c in clientes %}
                <a class="chat-link {% if seleccionado == c.numero %}active{% endif %}"
                   href="{{ url_for('crm', numero=c.numero) }}">
                    <div>
                        <span class="phone">+{{ c.numero }}</span>
                        {% if c.manual %}
                            <span class="status manual">MANUAL</span>
                        {% else %}
                            <span class="status ai">IA</span>
                        {% endif %}
                    </div>
                    <div class="preview">{{ c.preview }}</div>
                    <div class="small">{{ c.proyecto }}</div>
                </a>
            {% endfor %}
        </aside>

        <main class="main">
        {% if seleccionado %}
            <div class="chat-head">
                <div>
                    <h2>+{{ seleccionado }}</h2>
                    <p>{{ proyecto_seleccionado }}</p>
                </div>

                <form method="post" action="{{ url_for('crm_toggle', numero=seleccionado) }}">
                    {% if manual %}
                        <button class="toggle resume" type="submit">ÔûÂ Activar IA</button>
                    {% else %}
                        <button class="toggle pause" type="submit">ÔÅ© Pausar IA</button>
                    {% endif %}
                </form>
            </div>

            {% if manual %}
                <div class="notice">
                    Ô£ï Est├ís atendiendo esta conversaci├│n manualmente. La IA y el seguimiento autom├ítico est├ín pausados.
                </div>
            {% endif %}

            <div class="messages" id="messages" data-numero="{{ seleccionado or '' }}">
                {% for m in mensajes %}
                    <div class="row {{ m.direccion }}">
                        <div class="bubble">
                            {{ m.contenido }}
                            <span class="time">{{ m.hora }}</span>
                        </div>
                    </div>
                {% endfor %}
            </div>

            <div class="composer">
                <form method="post" action="{{ url_for('crm_enviar', numero=seleccionado) }}">
                    <textarea id="composer-text" name="mensaje" placeholder="Escribe tu respuesta manual..." required></textarea>
                    <button class="send" type="submit">Enviar</button>
                </form>
            </div>
        {% else %}
            <div class="empty">
                <h2>Selecciona una conversaci├│n</h2>
                <p>Aqu├¡ podr├ís pausar la IA y responder t├║ mismo.</p>
            </div>
        {% endif %}
        </main>
    </div>

    <script>
        const box = document.getElementById("messages");
        const composer = document.getElementById("composer-text");
        if (box) box.scrollTop = box.scrollHeight;

        let lastSignature = "";
        let ultimoEventoEntrante = null;
        const btnNotificaciones = document.getElementById("btn-notificaciones");

        let pushRegistradoServidor = false;
        let pushDevices = 0;

        function actualizarBotonNotificaciones() {
            if (!btnNotificaciones) return;

            if (!("Notification" in window)) {
                btnNotificaciones.textContent = "­ƒöò No compatible";
                btnNotificaciones.disabled = true;
                return;
            }

            if (Notification.permission === "denied") {
                btnNotificaciones.textContent = "­ƒöò Notificaciones bloqueadas";
                return;
            }

            if (Notification.permission === "granted" && pushRegistradoServidor) {
                btnNotificaciones.textContent = `­ƒöö Activo en este tel├®fono (${pushDevices})`;
                return;
            }

            if (Notification.permission === "granted") {
                btnNotificaciones.textContent = "­ƒô▒ Registrar este tel├®fono";
                return;
            }

            btnNotificaciones.textContent = "­ƒöö Activar notificaciones";
        }

        function urlBase64ToUint8Array(base64String) {
            const padding = "=".repeat((4 - base64String.length % 4) % 4);
            const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
            const rawData = atob(base64);
            return Uint8Array.from([...rawData].map(ch => ch.charCodeAt(0)));
        }

        async function sincronizarPush({
            pedirPermiso = false,
            mostrarMensaje = false
        } = {}) {
            if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
                throw new Error(
                    "Este navegador no permite Web Push. Usa Chrome actualizado."
                );
            }

            let permiso = Notification.permission;

            if (pedirPermiso && permiso !== "granted") {
                permiso = await Notification.requestPermission();
            }

            if (permiso !== "granted") {
                pushRegistradoServidor = false;
                actualizarBotonNotificaciones();
                return {ok: false, devices: 0, permiso};
            }

            const configResp = await fetch("/crm/push/config", {
                cache: "no-store"
            });

            if (!configResp.ok) {
                throw new Error("No pude obtener la configuraci├│n Push del servidor.");
            }

            const config = await configResp.json();

            if (!config.publicKey) {
                throw new Error("Falta VAPID_PUBLIC_KEY en Render.");
            }

            // Registrar SW y esperar hasta que realmente est├® activo.
            await navigator.serviceWorker.register("/crm-sw.js", {
                scope: "/"
            });

            const registro = await navigator.serviceWorker.ready;

            // Recuperar una suscripci├│n anterior si existe.
            let sub = await registro.pushManager.getSubscription();

            // Si no existe, crearla usando la llave p├║blica VAPID.
            if (!sub) {
                sub = await registro.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: urlBase64ToUint8Array(config.publicKey)
                });
            }

            if (!sub || !sub.endpoint) {
                throw new Error("Chrome no devolvi├│ una suscripci├│n Push v├ílida.");
            }

            // IMPORTANTE:
            // Aunque Chrome ya estuviera suscrito, SIEMPRE mandamos esa
            // suscripci├│n otra vez al servidor. Esto recupera el registro
            // despu├®s de un deploy/reinicio de Render.
            const resp = await fetch("/crm/push/subscribe", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Cache-Control": "no-cache"
                },
                body: JSON.stringify(sub.toJSON())
            });

            const data = await resp.json().catch(() => ({}));

            if (!resp.ok || !data.ok) {
                throw new Error(
                    data.error || "No se pudo guardar el tel├®fono en el servidor."
                );
            }

            pushRegistradoServidor = true;
            pushDevices = Number(data.devices || 1);
            actualizarBotonNotificaciones();

            if (mostrarMensaje) {
                alert(
                    `Ô£à Tel├®fono registrado correctamente.\n\n` +
                    `Dispositivos suscritos: ${pushDevices}`
                );
            }

            return {
                ok: true,
                devices: pushDevices,
                subscription: sub
            };
        }


        async function activarPush() {
            return sincronizarPush({
                pedirPermiso: true,
                mostrarMensaje: true
            });
        }

        if (btnNotificaciones) {
            btnNotificaciones.addEventListener("click", () => {
                activarPush().catch(err => {
                    console.error(err);
                    alert("No se pudieron activar las notificaciones: " + err.message);
                });
            });
        }

        const btnProbarPush = document.getElementById("btn-probar-push");

        if (btnProbarPush) {
            btnProbarPush.addEventListener("click", async () => {
                try {
                    btnProbarPush.disabled = true;
                    btnProbarPush.textContent = "ÔÅ│ Probando...";

                    // Primero garantizamos que ESTE tel├®fono est├® registrado
                    // en el servidor antes de intentar el push.
                    const sync = await sincronizarPush({
                        pedirPermiso: true,
                        mostrarMensaje: false
                    });

                    if (!sync.ok) {
                        throw new Error(
                            "No se pudo registrar este tel├®fono para recibir Push."
                        );
                    }

                    const resp = await fetch("/crm/push/test", {
                        method: "POST",
                        headers: {"Content-Type": "application/json"}
                    });

                    const data = await resp.json();

                    if (data.ok) {
                        alert(
                            "Ô£à El servidor envi├│ la notificaci├│n.\n\n" +
                            "Dispositivos suscritos: " + (data.devices ?? sync.devices) +
                            "\n\nAhora revisa la barra de notificaciones del tel├®fono."
                        );
                    } else {
                        alert(
                            "ÔØî No se pudo enviar.\n\n" +
                            (data.error || "Error desconocido") +
                            "\n\nDispositivos suscritos: " +
                            (data.devices ?? 0)
                        );
                    }
                } catch (err) {
                    alert("ÔØî Error probando push: " + err.message);
                } finally {
                    btnProbarPush.disabled = false;
                    btnProbarPush.textContent = "­ƒº¬ Probar m├│vil";
                }
            });
        }

        actualizarBotonNotificaciones();

        // Si este tel├®fono YA dio permiso anteriormente, al abrir el CRM
        // volvemos a registrar silenciosamente su PushSubscription en Render.
        // No muestra popups ni solicita permiso nuevo.
        if (
            "Notification" in window &&
            Notification.permission === "granted" &&
            "serviceWorker" in navigator &&
            "PushManager" in window
        ) {
            sincronizarPush({
                pedirPermiso: false,
                mostrarMensaje: false
            }).catch(err => {
                pushRegistradoServidor = false;
                actualizarBotonNotificaciones();
                console.error("AUTO-SYNC PUSH:", err);
            });
        }

        function procesarNotificaciones(eventos) {
            if (!Array.isArray(eventos) || eventos.length === 0) return;

            const mayorId = Math.max(...eventos.map(e => Number(e.id || 0)));

            // Primera carga: establecemos la l├¡nea base.
            // As├¡ no recibes 30 alertas de mensajes que ya estaban antes de abrir el CRM.
            if (ultimoEventoEntrante === null) {
                ultimoEventoEntrante = mayorId;
                return;
            }

            const nuevos = eventos.filter(
                e => Number(e.id || 0) > ultimoEventoEntrante
            );

            if (
                nuevos.length > 0 &&
                "Notification" in window &&
                Notification.permission === "granted"
            ) {
                nuevos.forEach(e => {
                    const proyecto = e.proyecto && e.proyecto !== "Sin proyecto"
                        ? ` ┬À ${e.proyecto}`
                        : "";

                    const n = new Notification("­ƒÅí Nuevo mensaje de cliente", {
                        body: `+${e.numero}${proyecto}\n${e.contenido}`,
                        tag: `crm-${e.id}`
                    });

                    n.onclick = () => {
                        window.focus();
                        window.location.href =
                            "/crm?numero=" + encodeURIComponent(e.numero);
                        n.close();
                    };
                });
            }

            ultimoEventoEntrante = Math.max(ultimoEventoEntrante, mayorId);
        }

        function escapeHtml(value) {
            return String(value ?? "")
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;")
                .replaceAll("'", "&#039;");
        }

        function renderMessages(messages) {
            if (!box) return;

            const signature = JSON.stringify(messages);
            if (signature === lastSignature) return;
            lastSignature = signature;

            const nearBottom =
                box.scrollHeight - box.scrollTop - box.clientHeight < 120;

            box.innerHTML = messages.map(m => `
                <div class="row ${m.direccion}">
                    <div class="bubble">
                        ${escapeHtml(m.contenido).replaceAll("\n", "<br>")}
                        <span class="time">${escapeHtml(m.hora)}</span>
                    </div>
                </div>
            `).join("");

            if (nearBottom || messages.length <= 3) {
                box.scrollTop = box.scrollHeight;
            }
        }

        function renderClients(clientes, seleccionado) {
            const sidebar = document.getElementById("sidebar");
            if (!sidebar) return;

            const title = sidebar.querySelector(".sidebar-title");
            const oldLinks = Array.from(sidebar.querySelectorAll(".chat-link"));
            oldLinks.forEach(el => el.remove());

            const empty = sidebar.querySelector(".crm-empty");
            if (empty) empty.remove();

            const count = document.getElementById("client-count");
            if (count) count.textContent = clientes.length;

            if (!clientes.length) {
                const div = document.createElement("div");
                div.className = "crm-empty";
                div.style.padding = "20px";
                div.style.color = "#667085";
                div.textContent = "Todav├¡a no han entrado mensajes desde que se inici├│ esta versi├│n.";
                sidebar.appendChild(div);
                return;
            }

            clientes.forEach(c => {
                const a = document.createElement("a");
                a.className = "chat-link" + (seleccionado === c.numero ? " active" : "");
                a.href = "/crm?numero=" + encodeURIComponent(c.numero);
                a.innerHTML = `
                    <div>
                        <span class="phone">+${escapeHtml(c.numero)}</span>
                        <span class="status ${c.manual ? "manual" : "ai"}">
                            ${c.manual ? "MANUAL" : "IA"}
                        </span>
                    </div>
                    <div class="preview">${escapeHtml(c.preview)}</div>
                    <div class="small">${escapeHtml(c.proyecto)}</div>
                `;
                sidebar.appendChild(a);
            });
        }

        async function actualizarCRM() {
            try {
                const numero = box ? box.dataset.numero : "";
                const url = numero
                    ? "/crm/data?numero=" + encodeURIComponent(numero)
                    : "/crm/data";

                const res = await fetch(url, {
                    method: "GET",
                    cache: "no-store",
                    headers: {
                        "X-Requested-With": "XMLHttpRequest"
                    }
                });

                if (!res.ok) return;

                const data = await res.json();

                procesarNotificaciones(data.eventos_entrantes || []);
                renderClients(data.clientes || [], numero || null);

                if (box && numero) {
                    renderMessages(data.mensajes || []);
                }

                const toggle = document.querySelector(".toggle");
                const notice = document.querySelector(".notice");

                if (toggle && numero) {
                    if (data.manual) {
                        toggle.textContent = "ÔûÂ Activar IA";
                        toggle.classList.remove("pause");
                        toggle.classList.add("resume");
                        if (notice) notice.style.display = "";
                    } else {
                        toggle.textContent = "ÔÅ© Pausar IA";
                        toggle.classList.remove("resume");
                        toggle.classList.add("pause");
                        if (notice) notice.style.display = "none";
                    }
                }
            } catch (err) {
                console.log("CRM polling:", err);
            }
        }

        // Actualiza autom├íticamente sin interrumpir lo que est├ís escribiendo.
        // No recarga la p├ígina completa.
        actualizarCRM();
        setInterval(actualizarCRM, 2500);
    </script>
</body>
</html>
"""


@app.route("/crm-sw.js", methods=["GET"])
def crm_service_worker():
    js = r"""
self.addEventListener('install', event => {
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('push', event => {
    let data = {};

    try {
        data = event.data ? event.data.json() : {};
    } catch (e) {
        data = {};
    }

    const uniqueId =
        data.message_id ||
        data.tag ||
        (Date.now().toString() + '-' + Math.random().toString(36).slice(2));

    const title = data.title || '­ƒÅí Nuevo mensaje de cliente';

    const options = {
        body: data.body || 'Tienes un mensaje nuevo.',
        // TAG ├ÜNICO POR MENSAJE: no reemplazar alertas anteriores.
        tag: 'crm-' + uniqueId,
        renotify: true,
        silent: false,
        timestamp: data.timestamp || Date.now(),
        data: {
            url: data.url || '/crm',
            message_id: uniqueId
        }
    };

    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

self.addEventListener('notificationclick', event => {
    event.notification.close();

    const target =
        (event.notification.data && event.notification.data.url)
        ? event.notification.data.url
        : '/crm';

    event.waitUntil(
        clients.matchAll({
            type: 'window',
            includeUncontrolled: true
        }).then(windows => {
            for (const client of windows) {
                if ('navigate' in client) {
                    client.navigate(target);
                }

                if ('focus' in client) {
                    return client.focus();
                }
            }

            return clients.openWindow(target);
        })
    );
});
"""
    return Response(
        js,
        mimetype="application/javascript",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Service-Worker-Allowed": "/"
        }
    )


@app.route("/crm/push/config", methods=["GET"])
def crm_push_config():
    if not crm_autorizado():
        return crm_pedir_login()
    return jsonify({"publicKey": VAPID_PUBLIC_KEY})


@app.route("/crm/push/subscribe", methods=["POST"])
def crm_push_subscribe():
    if not crm_autorizado():
        return crm_pedir_login()

    sub = request.get_json(silent=True) or {}
    endpoint = sub.get("endpoint")
    keys = sub.get("keys") or {}
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        return jsonify({"ok": False, "error": "Suscripci├│n inv├ílida"}), 400

    guardado = guardar_push_subscription(sub)
    devices = contar_push_devices()

    print(
        "WEB PUSH SUSCRIPCION:",
        "PERSISTENTE" if guardado else "SOLO RAM",
        endpoint[:90],
        "| dispositivos:",
        devices
    )

    return jsonify({
        "ok": True,
        "devices": devices,
        "persistent": bool(guardado)
    })


@app.route("/crm/push/devices", methods=["GET"])
def crm_push_devices():
    if not crm_autorizado():
        return crm_pedir_login()

    devices = contar_push_devices()

    return jsonify({
        "ok": True,
        "devices": devices,
        "persistent": bool(push_db_disponible())
    })



@app.route("/crm/ntfy/test", methods=["GET"])
def crm_ntfy_test():
    if not crm_autorizado():
        return crm_pedir_login()

    ok = enviar_ntfy_crm(
        "PRUEBA",
        "Prueba de ntfy: las notificaciones del CRM ya est├ín conectadas Ô£à",
        event_id=f"test-{time.time_ns()}"
    )

    return jsonify({
        "ok": bool(ok),
        "topic_configured": bool(NTFY_TOPIC),
        "server": NTFY_SERVER
    })


@app.route("/crm/ntfy/status", methods=["GET"])
def crm_ntfy_status():
    if not crm_autorizado():
        return crm_pedir_login()

    return jsonify({
        "topic_configured": bool(NTFY_TOPIC),
        "server": NTFY_SERVER,
        "crm_url": CRM_PUBLIC_URL
    })


@app.route("/crm/push/trace", methods=["GET"])
def crm_push_trace():
    if not crm_autorizado():
        return crm_pedir_login()

    return jsonify({
        "devices": contar_push_devices(),
        "last_error": ultimo_error_push,
        "last_result": ultimo_resultado_push,
        "database_ready": bool(inicializar_push_db())
    })


@app.route("/crm/push/persistence", methods=["GET"])
def crm_push_persistence():
    if not crm_autorizado():
        return crm_pedir_login()

    return jsonify({
        "database_configured": bool(DATABASE_URL),
        "psycopg2_available": bool(psycopg2),
        "database_ready": bool(inicializar_push_db()),
        "devices": contar_push_devices()
    })


@app.route("/crm/push/test", methods=["POST"])
def crm_push_test():
    if not crm_autorizado():
        return crm_pedir_login()

    devices = contar_push_devices()

    resultado = enviar_push_crm(
        "PRUEBA",
        "Esta es una prueba de notificaci├│n m├│vil del CRM Gabriel Ô£à"
    )

    return jsonify({
        "ok": bool(resultado.get("ok")),
        "enviadas": resultado.get("enviadas", 0),
        "error": resultado.get("error"),
        "devices": devices,
        "pywebpush": bool(webpush),
        "vapid_public": bool(VAPID_PUBLIC_KEY),
        "vapid_private": bool(VAPID_PRIVATE_KEY),
        "database": bool(push_db_disponible())
    })


@app.route("/crm", methods=["GET"])
def crm():
    if not crm_autorizado():
        return crm_pedir_login()

    seleccionado = request.args.get("numero", "").strip() or None

    with lock_crm:
        numeros = list(crm_mensajes.keys())

        numeros.sort(
            key=lambda n: crm_ultima_actividad.get(n, 0),
            reverse=True
        )

        clientes = []
        for numero in numeros:
            mensajes = crm_mensajes.get(numero, [])
            ultimo = mensajes[-1]["contenido"] if mensajes else ""
            clientes.append({
                "numero": numero,
                "preview": ultimo[:70],
                "manual": numero in crm_modo_manual,
                "proyecto": crm_nombre_proyecto(numero)
            })

        mensajes_seleccionados = list(
            crm_mensajes.get(seleccionado, [])
        ) if seleccionado else []

        manual = seleccionado in crm_modo_manual if seleccionado else False

    return render_template_string(
        CRM_HTML,
        clientes=clientes,
        seleccionado=seleccionado,
        mensajes=mensajes_seleccionados,
        manual=manual,
        proyecto_seleccionado=crm_nombre_proyecto(seleccionado) if seleccionado else ""
    )



@app.route("/crm/data", methods=["GET"])
def crm_data():
    if not crm_autorizado():
        return crm_pedir_login()

    seleccionado = request.args.get("numero", "").strip() or None

    with lock_crm:
        numeros = list(crm_mensajes.keys())
        numeros.sort(
            key=lambda n: crm_ultima_actividad.get(n, 0),
            reverse=True
        )

        clientes = []
        for numero in numeros:
            mensajes = crm_mensajes.get(numero, [])
            ultimo = mensajes[-1]["contenido"] if mensajes else ""
            clientes.append({
                "numero": numero,
                "preview": ultimo[:70],
                "manual": numero in crm_modo_manual,
                "proyecto": crm_nombre_proyecto(numero)
            })

        mensajes = list(
            crm_mensajes.get(seleccionado, [])
        ) if seleccionado else []

        manual = seleccionado in crm_modo_manual if seleccionado else False

        # ├Ültimos mensajes entrantes de TODAS las conversaciones.
        # El navegador usa el ID para avisar una sola vez por cada mensaje.
        eventos_entrantes = []
        for numero, lista in crm_mensajes.items():
            for m in lista:
                if m.get("direccion") == "in":
                    eventos_entrantes.append({
                        "id": m.get("id", 0),
                        "numero": numero,
                        "contenido": m.get("contenido", ""),
                        "hora": m.get("hora", ""),
                        "proyecto": crm_nombre_proyecto(numero)
                    })

        eventos_entrantes.sort(key=lambda x: x.get("id", 0))
        eventos_entrantes = eventos_entrantes[-100:]

    return jsonify({
        "clientes": clientes,
        "mensajes": mensajes,
        "manual": manual,
        "seleccionado": seleccionado,
        "eventos_entrantes": eventos_entrantes
    })


@app.route("/crm/toggle/<numero>", methods=["POST"])
def crm_toggle(numero):
    if not crm_autorizado():
        return crm_pedir_login()

    if crm_esta_manual(numero):
        crm_poner_ia(numero)
    else:
        # Pausar inmediatamente cualquier respuesta IA que est├® en proceso.
        crm_poner_manual(numero)
        cancelar_seguimiento(numero)
        iniciar_procesamiento(
            numero,
            f"crm-manual-{time.time()}"
        )

    return redirect(url_for("crm", numero=numero))


@app.route("/crm/enviar/<numero>", methods=["POST"])
def crm_enviar(numero):
    if not crm_autorizado():
        return crm_pedir_login()

    mensaje = request.form.get("mensaje", "").strip()

    if not mensaje:
        return redirect(url_for("crm", numero=numero))

    # Si Gabriel responde manualmente, la conversaci├│n queda en manual
    # hasta que ├®l pulse "Activar IA".
    crm_poner_manual(numero)
    cancelar_seguimiento(numero)

    # Invalida cualquier respuesta autom├ítica que todav├¡a estuviera proces├índose.
    iniciar_procesamiento(
        numero,
        f"crm-manual-{time.time()}"
    )

    enviar_whatsapp(numero, mensaje)
    guardar_mensaje(numero, "assistant", mensaje)

    return redirect(url_for("crm", numero=numero))


# ============================================================
# ADMINISTRACION DE MEMORIA PERSISTENTE
# ============================================================

@app.route("/crm/memoria", methods=["GET"])
def crm_memoria():
    if not crm_autorizado():
        return crm_pedir_login()
    cargar_memoria_persistente()
    html = r"""
    <!doctype html>
    <html lang="es">
    <head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Memoria CRM</title></head>
    <body style="font-family:Arial,sans-serif;max-width:760px;margin:40px auto;padding:0 20px">
      <h1>Memoria persistente del CRM</h1>
      <p>Importa aquí el respaldo JSON creado antes del deploy. Los datos se guardarán en PostgreSQL.</p>
      <form action="/crm/memoria/importar" method="post" enctype="multipart/form-data">
        <input type="file" name="archivo" accept="application/json,.json" required>
        <button type="submit" style="margin-left:8px">Importar respaldo</button>
      </form>
      <p style="margin-top:25px"><a href="/crm/memoria/estado">Ver estado de memoria</a> · <a href="/crm">Volver al CRM</a></p>
    </body></html>
    """
    return Response(html, content_type="text/html; charset=utf-8")

@app.route("/crm/memoria/importar", methods=["POST"])
def crm_memoria_importar():
    if not crm_autorizado():
        return crm_pedir_login()
    archivo = request.files.get("archivo")
    if not archivo:
        return jsonify({"ok": False, "error": "Falta el archivo JSON"}), 400
    try:
        data = json.loads(archivo.read().decode("utf-8-sig"))
        resultado = importar_respaldo_clientes(data)
        return jsonify({"ok": True, **resultado})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

@app.route("/crm/memoria/estado", methods=["GET"])
def crm_memoria_estado():
    if not crm_autorizado():
        return crm_pedir_login()
    cargar_memoria_persistente()
    db_count = 0
    db_ready = inicializar_memoria_db()
    if db_ready:
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM crm_client_memory")
                    db_count = int(cur.fetchone()[0])
            finally:
                conn.close()
        except Exception as exc:
            return jsonify({"ok": False, "database_ready": True, "error": str(exc)}), 500
    with lock_crm:
        crm_count = len(crm_mensajes)
        manual_count = len(crm_modo_manual)
    return jsonify({
        "ok": True,
        "database_ready": bool(db_ready),
        "clientes_postgresql": db_count,
        "clientes_en_crm": crm_count,
        "clientes_en_manual": manual_count,
        "historiales_en_ram": len(conversaciones),
        "proyectos_en_memoria": len(proyecto_activo)
    })

# Cargar memoria al importar el módulo (también funciona con Gunicorn en Render).
try:
    cargar_memoria_persistente()
except Exception as exc:
    print("MEMORIA DB STARTUP ERROR:", exc)

# ============================================================
# INICIAR SERVIDOR
# ============================================================

if __name__ == "__main__":

    print("")
    print("========================================")
    print("BOT INMOBILIARIO GABRIEL")
    print("========================================")
    print("Bot iniciando...")
    print("")

    app.run(port=5000)
