# VERSION_INTERVENCION_1357_NOMBRES_CRM_20261004 - seguimientos 10m+1/3/5/7, pausa IA por duda y nombre manual CRM
# VERSION_CTA_PALMERAS_3_PREGUNTAS_20261004 - info y precios siguen protocolo; visita lo rompe
# VERSION_PALMERAS_COTIZACIONES_VISUALES_IA_20261004 - restaura imagenes por modalidad + decisiones sin repetir preguntas
# VERSION_PALMERAS_IA_DECISIONES_MEDIA_CRM_20261004 - IA interpreta decisiones PSM + audio/foto/video visibles en CRM
# VERSION_PALMERAS_PLAN_CONTINUA_20261004 - evita que "Financiamiento" repita el menú y avanza a plazo
# VERSION_PALMERAS_SIN_ALGORITMO_VIEJO_20261004 - flujo PSM nuevo exclusivo, sin paquete completo antiguo
# VERSION_MULTIINTENCION_MENSAJES_8S_20260924 - agrupa 8s y atiende varias solicitudes del mismo bloque
# VERSION_NUEVOS_ANUNCIOS_20260921
# VERSION_BUENAVENTURA_FLUJO_HUMANO_20261004
# VERSION_MEDIA_PRIORIDAD_GLOBAL_20261004
# VERSION_BUENAVENTURA_2_NUEVOS_IDS_20260908
# VERSION_BUENAVENTURA_CTA_CONTROLADOS_20260908 - CTAs de anuncios + contexto de venta controlado
# VERSION_BUENAVENTURA_NUEVA_CAMPANA_20260907
# VERSION_PRECIOS_SIN_REPETIR_INFO_20260907
# VERSION_BOTON_INFO_PALMERAS_20260831 - boton rapido para fijar Palmeras y enviar toda la informacion
# VERSION_ANUNCIOS_PALMERAS_7_IDS_20260831 - 7 anuncios Palmeras identificados
# VERSION_ANUNCIOS_PALMERAS_FIX_PROYECTO_20260831
# VERSION_TRATO_USTED_GENERAL_20260831
from flask import Flask, request, Response, redirect, url_for, render_template_string, jsonify, send_from_directory
from openai import OpenAI
from dotenv import load_dotenv
import requests
import os
import base64
import tempfile
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import re
import json
import html
import mimetypes
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote

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

# Facebook Messenger (independiente de WhatsApp)
MESSENGER_PAGE_ACCESS_TOKEN = os.getenv("MESSENGER_PAGE_ACCESS_TOKEN", "").strip()
MESSENGER_VERIFY_TOKEN = os.getenv("MESSENGER_VERIFY_TOKEN", "").strip()
MESSENGER_PAGE_ID = os.getenv("MESSENGER_PAGE_ID", "").strip()
MESSENGER_CONTACT_PREFIX = "fb:"

# PostgreSQL persistente para conservar las suscripciones Push
# aunque Render se duerma, reinicie o haga deploy.
DATABASE_URL = os.getenv("DATABASE_URL")


# ============================================================
# TRATO FORMAL OBLIGATORIO CON CLIENTES (USTED)
# ============================================================
def _reemplazo_formal(match, reemplazo):
    original = match.group(0)
    if original and original[0].isupper():
        return reemplazo[:1].upper() + reemplazo[1:]
    return reemplazo


def formalizar_trato_usted(texto):
    """Convierte expresiones comunes de tú/vos a trato formal de usted."""
    texto = str(texto or "")
    if not texto:
        return texto

    reemplazos = [
        # Frases y pronombres.
        (r"\bcómo\s+te\s+llamas\b", "cómo se llama"),
        (r"\bcomo\s+te\s+llamas\b", "como se llama"),
        (r"\bpara\s+ti\b", "para usted"),
        (r"\ba\s+ti\b", "a usted"),
        (r"\bde\s+ti\b", "de usted"),
        (r"\bcon\s+vos\b", "con usted"),
        (r"\bcontigo\b", "con usted"),
        (r"\bvos\b", "usted"),
        (r"\btú\b", "usted"),
        (r"\btus\b", "sus"),
        (r"\btu\b", "su"),
        (r"\btuyos\b", "suyos"),
        (r"\btuyas\b", "suyas"),
        (r"\btuyo\b", "suyo"),
        (r"\btuya\b", "suya"),
        (r"\bte\b", "le"),

        # Tuteo/voseo frecuente.
        (r"\bpod[eé]s\b", "puede"),
        (r"\bpuedes\b", "puede"),
        (r"\bpuedas\b", "pueda"),
        (r"\bpodrías\b", "podría"),
        (r"\bpodrias\b", "podría"),
        (r"\bquer[eé]s\b", "quiere"),
        (r"\bquieres\b", "quiere"),
        (r"\bquieras\b", "quiera"),
        (r"\bten[eé]s\b", "tiene"),
        (r"\btienes\b", "tiene"),
        (r"\btengas\b", "tenga"),
        (r"\btendrás\b", "tendrá"),
        (r"\btendras\b", "tendrá"),
        (r"\bnecesit[aá]s\b", "necesita"),
        (r"\bnecesitas\b", "necesita"),
        (r"\bnecesites\b", "necesite"),
        (r"\bnecesitarías\b", "necesitaría"),
        (r"\bnecesitarias\b", "necesitaría"),
        (r"\bdese[aá]s\b", "desea"),
        (r"\bdeseas\b", "desea"),
        (r"\bdesees\b", "desee"),
        (r"\bprefer[ií]s\b", "prefiere"),
        (r"\bprefieres\b", "prefiere"),
        (r"\bprefieras\b", "prefiera"),
        (r"\beres\b", "es"),
        (r"\bestás\b", "está"),
        (r"\bestés\b", "esté"),
        (r"\bhas\b", "ha"),
        (r"\bvas\b", "va"),
        (r"\bvayas\b", "vaya"),
        (r"\bvienes\b", "viene"),
        (r"\bbuscas\b", "busca"),
        (r"\bbusques\b", "busque"),
        (r"\bconoces\b", "conoce"),
        (r"\bconozcas\b", "conozca"),
        (r"\bsabes\b", "sabe"),
        (r"\bsepas\b", "sepa"),
        (r"\bdebes\b", "debe"),
        (r"\bdeberías\b", "debería"),
        (r"\bdeberias\b", "debería"),
        (r"\beliges\b", "elige"),
        (r"\belijas\b", "elija"),
        (r"\bescoges\b", "escoge"),
        (r"\bveas\b", "vea"),
        (r"\bllegues\b", "llegue"),
        (r"\bllegas\b", "llega"),
        (r"\bhagas\b", "haga"),
        (r"\bdigas\b", "diga"),
        (r"\bseas\b", "sea"),
        (r"\bpagas\b", "paga"),
        (r"\bcompras\b", "compra"),
        (r"\brecibes\b", "recibe"),
        (r"\bgustas\b", "gusta"),
        (r"\bindicas\b", "indica"),
        (r"\bpudiste\b", "pudo"),

        # Imperativos frecuentes.
        (r"\bdecime\b", "dígame"),
        (r"\bdime\b", "dígame"),
        (r"\bmand[aá]me\b", "mándeme"),
        (r"\bmándame\b", "mándeme"),
        (r"\benvi[aá]me\b", "envíeme"),
        (r"\benvíame\b", "envíeme"),
        (r"\bescrib[ií]me\b", "escríbame"),
        (r"\bescríbeme\b", "escríbame"),
        (r"\bavis[aá]me\b", "avíseme"),
        (r"\bavísame\b", "avíseme"),
        (r"\bcont[aá]me\b", "cuénteme"),
        (r"\bcuéntame\b", "cuénteme"),
        (r"\bconfirm[aá]me\b", "confírmeme"),
        (r"\bconfírmame\b", "confírmeme"),
        (r"\bindic[aá]me\b", "indíqueme"),
        (r"\bindícame\b", "indíqueme"),
        (r"\bpas[aá]me\b", "páseme"),
        (r"\brespond[eé]me\b", "respóndame"),
        (r"\brevis[aá]\b", "revise"),
        (r"\bmir[aá]\b", "mire"),
        (r"\bintent[aá]\b", "intente"),
        (r"\bdínoslo\b", "díganoslo"),

        # Infinitivos con pronombre.
        (r"\bayudarte\b", "ayudarle"),
        (r"\benviarte\b", "enviarle"),
        (r"\bmostrarte\b", "mostrarle"),
        (r"\bcompartirte\b", "compartirle"),
        (r"\bexplicarte\b", "explicarle"),
        (r"\bcontarte\b", "contarle"),
        (r"\bconfirmarte\b", "confirmarle"),
        (r"\borientarte\b", "orientarle"),
        (r"\batenderte\b", "atenderle"),
        (r"\bacompañarte\b", "acompañarle"),
        (r"\bavisarte\b", "avisarle"),
        (r"\bescribirte\b", "escribirle"),
        (r"\bllamarte\b", "llamarle"),
        (r"\bmandarte\b", "mandarle"),
        (r"\bdarte\b", "darle"),
        (r"\bhacerte\b", "hacerle"),
        (r"\bdecirte\b", "decirle"),
        (r"\bpreguntarte\b", "preguntarle"),
        (r"\bcotizarte\b", "cotizarle"),
        (r"\bcalcularte\b", "calcularle"),
        (r"\brecomendarte\b", "recomendarle"),
        (r"\bagendarte\b", "agendarle"),
    ]

    for patron, reemplazo in reemplazos:
        texto = re.sub(
            patron,
            lambda m, r=reemplazo: _reemplazo_formal(m, r),
            texto,
            flags=re.IGNORECASE,
        )
    return texto

# ============================================================
# NTFY - NOTIFICACIONES NATIVAS EN ANDROID
# ============================================================
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "").strip()
NTFY_SERVER = os.getenv("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
CRM_PUBLIC_URL = os.getenv(
    "CRM_PUBLIC_URL",
    "https://bot-inmobiliario-produccion.onrender.com/crm"
).rstrip("/")

# URL pública usada por Messenger para que Meta pueda descargar fotos/videos locales.
# No requiere una variable nueva: si no existe, se deriva automáticamente de CRM_PUBLIC_URL.
MESSENGER_PUBLIC_BASE_URL = os.getenv("MESSENGER_PUBLIC_BASE_URL", "").strip().rstrip("/")

# Acceso al CRM. Configúralos en Render > Environment.
CRM_USER = os.getenv("CRM_USER", "gabriel")
CRM_PASSWORD = os.getenv("CRM_PASSWORD")

# Número interno que recibirá, por WhatsApp, un resumen separado por cada lead.
# Puede cambiarse luego desde Render > Environment sin tocar el código.
CRM_SEGUIMIENTO_NUMERO = os.getenv("CRM_SEGUIMIENTO_NUMERO", "50236676447").strip().replace("+", "").replace(" ", "")
# Número que recibirá alertas cuando la IA se pause por una pregunta no segura.
CRM_INTERVENCION_NUMERO = os.getenv("CRM_INTERVENCION_NUMERO", CRM_SEGUIMIENTO_NUMERO).strip().replace("+", "").replace(" ", "")

# Web Push para notificaciones reales en computadora y teléfono.
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
    # Vista Hermosa: no enviar fotos generales automáticamente.
    # A solicitud de fotos o videos se enviarán únicamente sus videos,
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
        "8x16_comercial": [
            "media/cotizaciones/buenaventura/8x16_comercial.jpeg",
        ],
    },
}


ETIQUETAS_COTIZACIONES = {
    "palmeras": {
        "media/cotizaciones/palmeras/8x16_no_esquina.jpeg":
            "Palmeras San Miguel - 8x16 - Fase 1 / no esquina",
        "media/cotizaciones/palmeras/8x16_segunda_fase.jpeg":
            "Palmeras San Miguel - 8x16 - Fase 2",
    },
    "vista_hermosa": {
        "media/cotizaciones/vista_hermosa/8x16_fase_f.jpeg":
            "Vista Hermosa - 8x16 - Fase F",
        "media/cotizaciones/vista_hermosa/8x16_fase_g.jpeg":
            "Vista Hermosa - 8x16 - Fase G",
    },
    "buenaventura": {
        "media/cotizaciones/buenaventura/8x16.jpeg":
            "Buenaventura Cuyotenango - 8x16 residencial / inversión",
        "media/cotizaciones/buenaventura/8x18.jpeg":
            "Buenaventura Cuyotenango - 8x18 residencial / inversión",
        "media/cotizaciones/buenaventura/8x16_comercial.jpeg":
            "Buenaventura Cuyotenango - 8x16 comercial",
    },
}


RESUMENES_COTIZACION = {
    "palmeras": {
        "nombre": "Palmeras San Miguel",
        "descripcion": (
            "Palmeras San Miguel está ubicado en Zona 5 de Retalhuleu, "
            "camino a La Verde / carretera hacia Las Pilas 📍🏡"
        ),
        "amenidades": (
            "Fase 1 con piscina y área verde; Fase 2 con área verde 🏊🌳"
        ),
        "servicios": (
            "Calles pavimentadas, agua potable, energía eléctrica y "
            "drenajes con planta de tratamiento ✅"
        ),
        "cierre": (
            "Podemos revisar la modalidad de pago que más le interese 👇💰"
        )
    },

    "vista_hermosa": {
        "nombre": "Vista Hermosa",
        "descripcion": (
            "Vista Hermosa está sobre la CA-2, km 188, Retalhuleu, "
            "aproximadamente a 15 minutos del IRTRA 📍🏡"
        ),
        "amenidades": (
            "Fase F con piscina y área verde; Fase G con área verde 🏊🌳"
        ),
        "servicios": (
            "Calles pavimentadas, agua potable, energía eléctrica y drenajes con planta de tratamiento; "
            "el sector residencial contempla garita y muro perimetral, mientras el área comercial no ✅"
        ),
        "cierre": (
            "Le comparto las opciones disponibles y con gusto revisamos la fase que más le interese 👇💰"
        )
    },

    "buenaventura": {
        "nombre": "Buenaventura Cuyotenango",
        "descripcion": (
            "Buenaventura está en el km 168 de la carretera hacia la playa "
            "de Tulate, Cuyotenango 📍🏡"
        ),
        "amenidades": (
            "Casa club, piscinas, áreas verdes, juegos para niños y caminamientos 🏊🌳"
        ),
        "servicios": (
            "Garita, muro perimetral, calles pavimentadas, agua potable, "
            "energía eléctrica y drenajes con planta de tratamiento ✅"
        ),
        "cierre": (
            "Te comparto abajo las cotizaciones disponibles de todas las "
            "medidas con enganches y cuotas 👇💰"
        )
    }
}


def construir_resumen_cotizacion(proyecto):
    """
    Mensaje breve antes de enviar las imágenes.
    NO escribe precios ni cuotas porque esa información va en las
    imágenes de cotización.
    """
    datos = RESUMENES_COTIZACION.get(proyecto)

    if not datos:
        return None

    return (
        f"¡Claro! 😊 Te comparto la información de {datos['nombre']}:\n\n"
        f"{datos['descripcion']}\n\n"
        f"🏊🌳 Amenidades: {datos['amenidades']}\n"
        f"✅ Servicios: {datos['servicios']}\n"
        "🏗️ Diseño de construcción libre: puedes construir vivienda, apartamentos "
        "o locales, siempre que sea una construcción formal con block.\n\n"
        f"{datos['cierre']}"
    )


def pide_cotizacion(texto):
    """
    Cualquier pregunta relacionada con precio/cuotas/cotización
    dispara inmediatamente el envío de TODAS las imágenes de
    cotización del proyecto activo.
    """
    t = texto.lower()

    palabras = [
        "precio", "precios",
        "cuanto cuesta", "cuánto cuesta",
        "cuanto cuestan", "cuánto cuestan",
        "cuanto vale", "cuánto vale",
        "cuanto salen", "cuánto salen",
        "valor", "costo", "costos",
        "cotizacion", "cotización", "cotizaciones",
        "cuota", "cuotas", "mensualidad", "mensualidades",
        "plan de pago", "plan de pagos",
        "financiamiento", "financiado",

        # Si el cliente pide información general de un proyecto,
        # tratamos la intención como solicitud de información comercial completa:
        # resumen del proyecto + cotizaciones.
        "informacion", "información",
        "quiero informacion", "quiero información",
        "dame informacion", "dame información",
        "me da informacion", "me da información",
        "info de", "información de", "informacion de"
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
            2: 3817, 3: 2752, 4: 2228, 5: 1919,
            6: 1717, 7: 1578, 8: 1476
        },
        "8x18": {
            2: 4232, 3: 3052, 4: 2470, 5: 2127,
            6: 1904, 7: 1749, 8: 1637
        },
        "8x16 Comercial": {
            2: 6032, 3: 4350, 4: 3520, 5: 3032,
            6: 2714, 7: 2493, 8: 2333
        },
    },
    "palmeras": {
        "8x16 Fase 1": {
            1: 5563.64, 2: 3026.26, 3: 2181.31, 4: 1766.17,
            5: 1521.20, 6: 1361.30, 7: 1251.28, 8: 1170.60
        },
        "8x16 Fase 2": {
            1: 5854.55, 2: 3184.50, 3: 2295.37, 4: 1858.52,
            5: 1600.74, 6: 1432.48, 7: 1316.71, 8: 1231.81
        },
    },
}


def extraer_plazo_cuota(texto):
    t = texto.lower()

    # Años
    m = re.search(r"\b([1-8])\s*años?\b", t)
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
        "cuanto pago", "cuánto pago",
        "cuanto queda", "cuánto queda",
        "cuanto seria", "cuánto sería"
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
                f"• {opcion}: {formatear_quetzales(valor)} al mes"
            )

    if not lineas:
        return None

    if len(lineas) == 1:
        detalle = lineas[0].replace("• ", "")
        return (
            f"En {nombre}, la cuota a {plazo} "
            f"{'año' if plazo == 1 else 'años'} es de {detalle} 😊💳. "
            "El financiamiento es propio y directo con la empresa."
        )

    return (
        f"En {nombre}, estas son las cuotas a {plazo} "
        f"{'año' if plazo == 1 else 'años'} 😊💳:\n\n"
        + "\n".join(lineas)
        + "\n\nEl financiamiento es propio y directo con la empresa."
    )


def pregunta_por_plazo_de_financiamiento(texto):
    """
    Si el cliente menciona un plazo de financiamiento, enviamos de inmediato
    las imágenes de cotización del proyecto activo.

    Ejemplos:
    - "¿Y a 2 años?"
    - "¿Cuánto queda a 6 años?"
    - "Quiero el de 8 años"
    - "¿A 24 meses cuánto pago?"
    """
    t = texto.lower().strip()

    # Años permitidos en los planes actuales.
    patrones_anos = [
        r"\b1\s*año\b", r"\b1\s*ano\b",
        r"\b2\s*años\b", r"\b2\s*anos\b",
        r"\b3\s*años\b", r"\b3\s*anos\b",
        r"\b4\s*años\b", r"\b4\s*anos\b",
        r"\b5\s*años\b", r"\b5\s*anos\b",
        r"\b6\s*años\b", r"\b6\s*anos\b",
        r"\b7\s*años\b", r"\b7\s*anos\b",
        r"\b8\s*años\b", r"\b8\s*anos\b",
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
    Detecta respuestas cortas que normalmente vienen después de que el bot
    ofreció enviar cotización o plan de pagos.
    """
    t = texto.lower().strip()

    frases = [
        "si", "sí", "si porfa", "sí porfa", "si por favor", "sí por favor",
        "dale", "de una", "mandala", "mándala", "mandamela", "mándamela",
        "enviala", "envíala", "quiero verla", "quiero la cotizacion",
        "quiero la cotización", "quiero cotizacion", "quiero cotización",
        "la cotizacion", "la cotización",
        "el de 8", "a 8", "8 años", "8 anos",
        "el de 7", "7 años", "7 anos",
        "el de 6", "6 años", "6 anos",
        "el de 5", "5 años", "5 anos",
        "el de 4", "4 años", "4 anos",
        "el de 3", "3 años", "3 anos",
        "el de 2", "2 años", "2 anos",
        "el de 1", "1 año", "1 ano"
    ]

    return any(f == t or f in t for f in frases)


def historial_ofrecio_cotizacion(numero):
    """
    Revisa si en los últimos mensajes del bot se habló de cotización,
    plan de pago o financiamiento. Si el cliente responde 'sí', 'el de 8',
    etc., enviamos directamente la cotización.
    """
    historial = obtener_historial(numero)

    ultimos = historial[-6:]

    texto_asistente = " ".join(
        item.get("content", "").lower()
        for item in ultimos
        if item.get("role") == "assistant"
    )

    claves = [
        "cotizacion", "cotización",
        "plan de pago", "planes de pago",
        "financiamiento",
        "opciones a 8 años", "hasta 8 años",
        "te preparo opciones", "te envío las cotizaciones",
        "te envio las cotizaciones"
    ]

    return any(c in texto_asistente for c in claves)


def debe_enviar_cotizacion_directa(numero, texto):
    """
    Envía cotización inmediatamente cuando:
    - el cliente pide precio/cuota/cotización;
    - menciona directamente un plazo (ej. 2 años, 6 años, 24 meses);
    - confirma una cotización ofrecida anteriormente.
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

    if "9x20" in t or "9×20" in t:
        return "9x20"

    if "8x18" in t or "8×18" in t:
        return "8x18"

    if "8x16" in t or "8×16" in t:
        return "8x16"

    return None


# ============================================================
# PRECIOS Y ENGANCHES EXACTOS POR MEDIDA / FASE
# ============================================================

DATOS_MEDIDAS = {
    "palmeras": {
        "nombre": "Palmeras San Miguel",
        "medidas": {
            "8x16": {
                "fases": {
                    "1": {"precio": "Q67,200", "enganche": "Q6,000"},
                    "2": {"precio": "Q70,400", "enganche": "Q6,000"},
                }
            },
        },
    },
    "buenaventura": {
        "nombre": "Buenaventura Cuyotenango",
        "medidas": {
            "8x16": {"precio": "Q83,200 residencial / inversión o Q128,000 comercial", "enganche": "Q6,000"},
            "8x18": {"precio": "Q93,600", "enganche": "Q8,000"},
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
        "que medidas", "qué medidas", "cuales medidas", "cuáles medidas",
        "medidas tienen", "medidas tiene", "medidas disponibles",
        "que tamaños", "qué tamaños", "tamaños disponibles",
        "de que medidas", "de qué medidas"
    ]
    return any(f in t for f in frases)

def respuesta_medidas_disponibles(proyecto):
    if proyecto == "palmeras":
        return "En Palmeras San Miguel actualmente tenemos lotes de 8x16 (128 m²) en Fase 1 y Fase 2 😊🏡. Todos los lotes tienen calle al frente."
    if proyecto == "buenaventura":
        return "En Buenaventura Cuyotenango tenemos 8x16 y 8x18 para vivir o invertir; para negocio contamos con 8x16 comercial 😊🏡. ¿Lo busca para vivir, invertir o para negocio?"
    if proyecto == "vista_hermosa":
        return "En Ciudad Vista Hermosa tenemos lotes de 8x16 en Fase F y Fase G 😊🏡"
    return None


def es_consulta_general_de_precio(texto):
    """
    Detecta preguntas generales como "¿cuánto valen los terrenos?".

    No intercepta una medida concreta, una cuota, enganche, plazo, cotización
    ni una pregunta sobre diferencia de precios; esos casos conservan sus
    flujos especializados.
    """
    t = normalizar_ventas(texto)

    # Mantener intactos los flujos específicos ya existentes.
    if detectar_medida_en_texto(texto):
        return False
    if pregunta_cuota_especifica(texto):
        return False
    if pregunta_enganche(texto):
        return False
    if pregunta_por_plazo_de_financiamiento(texto):
        return False
    if any(x in t for x in [
        "cotizacion", "cotizaciones", "cuota", "cuotas", "mensualidad",
        "mensualidades", "plan de pago", "planes de pago", "financiamiento",
        "enganche", "diferencia", "dos precios", "fases", "fase f", "fase g"
    ]):
        return False

    frases_precio = [
        "precio", "precios", "cuanto cuesta", "cuanto cuestan",
        "cuanto vale", "cuanto valen", "cuanto salen", "valor",
        "costo", "costos", "que vale", "que valen"
    ]
    return any(x in t for x in frases_precio)


def es_primera_consulta_comercial(numero):
    """
    Considera como primera consulta comercial cuando antes del mensaje actual
    el cliente solo ha saludado o todavía no existe otra pregunta real.
    """
    historial = obtener_historial(numero)
    for item in historial:
        if item.get("role") != "user":
            continue
        contenido = str(item.get("content") or "").strip()
        if not contenido:
            continue
        if es_solo_saludo(contenido):
            continue
        return False
    return True


def respuesta_precio_breve_con_intencion(proyecto):
    """
    Respuesta breve para una consulta general de precio cuando la conversación
    ya venía avanzando. Evita reenviar cotizaciones, fotos y amenidades.
    """
    if proyecto == "buenaventura":
        return (
            "Claro 😊 En Buenaventura Cuyotenango tenemos:\n\n"
            "• 8x16 desde Q83,200\n"
            "• 8x18 Q93,600\n\n"
            "¿Qué medida le interesa y la busca para construir su casa, hacer locales o como inversión?"
        )

    if proyecto == "palmeras":
        return (
            "Claro 😊 En Palmeras San Miguel actualmente tenemos lotes de 8x16 en dos fases:\n\n"
            "• Fase 1: Q67,200 — piscina y área verde 🏊🌳\n"
            "• Fase 2: Q70,400 — área verde 🌳\n\n"
            "¿Cuál de las dos fases le parece más atractiva?"
        )

    if proyecto == "vista_hermosa":
        return (
            "Claro 😊 En Ciudad Vista Hermosa tenemos lotes de 8x16:\n\n"
            "• Fase F Q83,200\n"
            "• Fase G Q89,600\n\n"
            "¿Cuál opción le interesa y la busca para construir su casa, hacer locales o como inversión?"
        )

    return None

def respuesta_medida_especifica(proyecto, medida, texto=""):
    datos_proyecto = DATOS_MEDIDAS.get(proyecto)
    if not datos_proyecto or medida not in datos_proyecto.get("medidas", {}):
        return None

    nombre = datos_proyecto["nombre"]
    datos = datos_proyecto["medidas"][medida]

    if proyecto == "palmeras" and medida == "8x16":
        return (
            "Sí 😊 En Palmeras San Miguel actualmente los lotes son de 8x16 (128 m²) en dos fases:\n\n"
            "• Fase 1: Q67,200 — enganche Q6,000 — piscina y área verde.\n"
            "• Fase 2: Q70,400 — enganche Q6,000 — área verde.\n\n"
            "¿Cuál fase le interesa más?"
        )

    if "fases" in datos:
        fase = detectar_fase_en_texto(texto)
        if fase and fase in datos["fases"]:
            d = datos["fases"][fase]
            return (
                f"Sí 😊 En {nombre}, el lote de {medida} en Fase {fase} tiene un precio de "
                f"{d['precio']} y un enganche de {d['enganche']} 💰🏡."
            )
        f = datos["fases"]["F"]
        g = datos["fases"]["G"]
        return (
            f"Sí 😊 En {nombre} tenemos lotes de {medida} en dos fases:\n\n"
            f"• Fase F: {f['precio']} — enganche {f['enganche']}\n"
            f"• Fase G: {g['precio']} — enganche {g['enganche']} 💰🏡"
        )

    return (
        f"Sí 😊 En {nombre}, el lote de {medida} tiene un precio de {datos['precio']} "
        f"y un enganche de {datos['enganche']} 💰🏡."
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
# CAMPAÑA BUENAVENTURA - BOTONES / PREGUNTAS CONTROLADAS
# ============================================================

def _normalizar_boton_campana(texto):
    """
    Normaliza el texto recibido desde los botones de Meta.
    Quita emojis/signos para que pequeñas diferencias visuales no cambien
    la intención del botón.
    """
    t = normalizar_ventas(texto)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return " ".join(t.split())


def detectar_cta_buenaventura(texto):
    """
    Detecta las cuatro preguntas configuradas en los anuncios de Buenaventura.
    Se evalúan ANTES que la IA y antes de los detectores generales para evitar
    respuestas duplicadas o interpretaciones equivocadas.
    """
    t = _normalizar_boton_campana(texto)

    grupos = {
        "precios_cuotas": {
            "quiero conocer precios y cuotas",
            "precios y cuotas",
        },
        "ubicacion": {
            "quiero ver la ubicacion del proyecto",
            "ver la ubicacion del proyecto",
        },
        "lotes_disponibles": {
            "quiero conocer lotes disponibles",
            "conocer lotes disponibles",
            "lotes disponibles",
        },
        "agendar_visita": {
            "quiero agendar una visita",
            "agendar una visita",
        },
    }

    for accion, frases in grupos.items():
        if t in frases:
            return accion
    return None


def _limpiar_contextos_cta_buenaventura(numero, conservar=None):
    """Evita que una pregunta vieja de un botón interfiera con un botón nuevo."""
    estado = obtener_estado_conversacion(numero)
    claves = [
        "esperando_uso_lote_cta",
        "esperando_medida_lotes_cta",
        "esperando_tipo_dia_visita_cta",
        "esperando_dia_visita_cta",
        "esperando_jornada_visita_cta",
        "esperando_hora_visita_cta",
    ]
    for clave in claves:
        if clave != conservar:
            estado[clave] = False
    persistir_cliente(numero)


def info_completa_ya_enviada(numero, proyecto=None):
    estado = obtener_estado_conversacion(numero)
    if not estado.get("info_completa_enviada"):
        return False
    if proyecto and estado.get("info_completa_proyecto") not in {None, proyecto}:
        return False
    return True


def respuesta_precio_breve_buenaventura():
    return (
        "Claro 😊 En Buenaventura el precio depende del uso del terreno. "
        "Para vivir o invertir tenemos 8x16 en Q83,200 y 8x18 en Q93,600; "
        "para negocio tenemos 8x16 comercial en Q128,000. "
        "¿Lo busca para vivir, invertir o para negocio?"
    )


def respuesta_ubicacion_cta_buenaventura():
    datos = UBICACIONES_PROYECTOS.get("buenaventura", {})
    enlace = datos.get("maps", "https://maps.app.goo.gl/4wTj52Ez32rdigXk8")
    return (
        "Buenaventura Cuyotenango está en el km 168 sobre la carretera hacia Tulate, "
        "a 2 minutos del centro de Cuyotenango y aproximadamente a 15 minutos del IRTRA. 📍\n\n"
        f"Google Maps:\n{enlace}"
    )


def respuesta_lotes_disponibles_cta_buenaventura():
    return (
        "Con gusto 😊 Le comparto el plano general de Buenaventura para revisar las ubicaciones. "
        "¿El terreno lo busca para vivir, invertir o para negocio?"
    )


def respuesta_visita_cta_buenaventura():
    return (
        "Excelente 😊 Podemos coordinar una visita a Buenaventura Cuyotenango para que "
        "conozca el proyecto personalmente.\n\n"
        "¿Le queda mejor entre semana o fin de semana?"
    )


def detectar_uso_lote_buenaventura(texto):
    t = normalizar_ventas(texto)
    if any(x in t for x in [
        "casa", "mi casa", "vivienda", "vivir", "familia", "para mi familia"
    ]):
        return "casa"
    if any(x in t for x in [
        "local", "locales", "negocio", "negocios", "comercial", "comercio"
    ]):
        return "locales"
    if any(x in t for x in [
        "patrimonio", "inversion", "invertir", "guardar mi dinero", "plusvalia"
    ]):
        return "patrimonio"
    return None


def respuesta_seguimiento_uso_lote_buenaventura(numero, texto):
    """
    Entiende respuestas cortas como "para mi casa", "locales" o "patrimonio"
    porque recuerda la pregunta que hizo el botón de disponibilidad.
    """
    estado = obtener_estado_conversacion(numero)
    if not estado.get("esperando_uso_lote_cta"):
        return None

    uso = detectar_uso_lote_buenaventura(texto)
    if not uso:
        return None

    estado["esperando_uso_lote_cta"] = False
    estado["esperando_medida_lotes_cta"] = True
    estado["uso_lote_cta"] = uso
    persistir_cliente(numero)

    if uso == "casa":
        return (
            "Perfecto 😊 Para vivir tenemos 8x16 y 8x18. ¿Qué medida le interesa más?"
        )
    if uso == "locales":
        return (
            "Perfecto 😊 Para negocio contamos con el 8x16 comercial en Q128,000 y enganche Q6,000. "
            "¿Desea revisar el financiamiento de 2 a 8 años?"
        )
    return (
        "Perfecto 😊 Para invertir puede revisar 8x16 en Q83,200 o 8x18 en Q93,600. "
        "¿Qué medida le interesa revisar primero?"
    )


def respuesta_seguimiento_medida_lotes_buenaventura(numero, texto):
    """
    Si el cliente ya explicó para qué quiere el lote y luego elige una medida,
    responde el precio exacto existente y ofrece mostrar la ubicación disponible
    en el plano, sin perder el contexto.
    """
    estado = obtener_estado_conversacion(numero)
    if not estado.get("esperando_medida_lotes_cta"):
        return None

    medida = detectar_medida_en_texto(texto)
    if not medida:
        return None

    respuesta = respuesta_medida_especifica("buenaventura", medida, texto)
    if not respuesta:
        return None

    estado["esperando_medida_lotes_cta"] = False
    estado["esperando_disponibilidad_desde_cta"] = True
    persistir_cliente(numero)

    return (
        respuesta
        + "\n\n¿Quiere que le muestre en el plano las ubicaciones disponibles de esa medida?"
    )


def detectar_tipo_dia_visita_cta(texto):
    t = normalizar_ventas(texto)
    if any(x in t for x in ["fin de semana", "sabado", "domingo"]):
        return "fin_semana"
    if any(x in t for x in [
        "entre semana", "lunes", "martes", "miercoles", "jueves", "viernes"
    ]):
        return "entre_semana"
    return None


def detectar_jornada_visita_cta(texto):
    t = normalizar_ventas(texto)
    if any(x in t for x in ["manana", "por la manana", "en la manana", "am"]):
        return "mañana"
    if any(x in t for x in ["tarde", "por la tarde", "en la tarde", "pm"]):
        return "tarde"
    return None


def respuesta_seguimiento_visita_cta(numero, texto, proyecto):
    """
    Flujo corto y contextual:
    entre semana/fin de semana -> día -> mañana/tarde -> hora.
    No sustituye el sistema de visitas existente; lo alimenta y, al tener día+hora,
    usa respuesta_visita() para cerrar la cita como antes.
    """
    estado = obtener_estado_conversacion(numero)
    visita = estado_visitas.setdefault(
        numero,
        {"dia": None, "hora": None, "proyecto": proyecto or "buenaventura", "cerrada": False}
    )
    if proyecto:
        visita["proyecto"] = proyecto

    if estado.get("esperando_tipo_dia_visita_cta"):
        tipo = detectar_tipo_dia_visita_cta(texto)
        dia = extraer_dia_visita(texto)
        hora = extraer_hora_visita(texto)

        if dia:
            visita["dia"] = dia
            estado["esperando_tipo_dia_visita_cta"] = False
            if hora:
                estado["esperando_jornada_visita_cta"] = False
                estado["esperando_hora_visita_cta"] = False
                persistir_cliente(numero)
                return respuesta_visita(numero, texto, proyecto)
            estado["esperando_jornada_visita_cta"] = True
            persistir_cliente(numero)
            return "Perfecto 😊 ¿Le quedaría mejor por la mañana o por la tarde?"

        if tipo:
            estado["esperando_tipo_dia_visita_cta"] = False
            estado["esperando_dia_visita_cta"] = True
            estado["tipo_dia_visita_cta"] = tipo
            persistir_cliente(numero)
            if tipo == "fin_semana":
                return "Perfecto 😊 ¿Qué día le queda mejor, sábado o domingo?"
            return "Perfecto 😊 ¿Qué día le queda mejor de lunes a viernes?"

        return None

    if estado.get("esperando_dia_visita_cta"):
        dia = extraer_dia_visita(texto)
        if not dia:
            return None

        visita["dia"] = dia
        estado["esperando_dia_visita_cta"] = False

        hora = extraer_hora_visita(texto)
        if hora:
            estado["esperando_jornada_visita_cta"] = False
            estado["esperando_hora_visita_cta"] = False
            persistir_cliente(numero)
            return respuesta_visita(numero, texto, proyecto)

        estado["esperando_jornada_visita_cta"] = True
        persistir_cliente(numero)
        return "Perfecto 😊 ¿Le quedaría mejor por la mañana o por la tarde?"

    if estado.get("esperando_jornada_visita_cta"):
        jornada = detectar_jornada_visita_cta(texto)
        hora = extraer_hora_visita(texto)

        if hora:
            estado["esperando_jornada_visita_cta"] = False
            estado["esperando_hora_visita_cta"] = False
            persistir_cliente(numero)
            return respuesta_visita(numero, texto, proyecto)

        if not jornada:
            return None

        estado["jornada_visita_cta"] = jornada
        estado["esperando_jornada_visita_cta"] = False
        estado["esperando_hora_visita_cta"] = True
        persistir_cliente(numero)
        return f"Perfecto 😊 ¿Qué hora por la {jornada} le quedaría mejor?"

    if estado.get("esperando_hora_visita_cta"):
        if not extraer_hora_visita(texto):
            return None
        estado["esperando_hora_visita_cta"] = False
        persistir_cliente(numero)
        return respuesta_visita(numero, texto, proyecto)

    return None


def manejar_cta_buenaventura(numero, texto, proyecto, message_id):
    """
    Ejecuta las cuatro opciones del anuncio sin pasar por OpenAI.
    Devuelve True si el mensaje fue atendido por este flujo.
    """
    accion = detectar_cta_buenaventura(texto)
    if not accion:
        return False

    # Estos botones pertenecen a la campaña actual de Buenaventura.
    estado = obtener_estado_conversacion(numero)
    estado["proyecto_actual"] = "buenaventura"
    proyecto_activo[numero] = "buenaventura"
    proyecto = "buenaventura"
    ultima_intencion[numero] = f"cta_buenaventura_{accion}"

    guardar_mensaje(numero, "user", texto)

    if accion == "precios_cuotas":
        _limpiar_contextos_cta_buenaventura(numero)

        primera = es_primera_consulta_comercial(numero)
        # guardar_mensaje() ya añadió el mensaje actual; por eso, si el historial
        # anterior estaba vacío, comprobamos también si todavía no se envió el paquete.
        # Restamos el efecto del mensaje actual mirando cuántos mensajes de usuario reales hay.
        usuarios_reales = [
            x for x in obtener_historial(numero)
            if x.get("role") == "user" and not es_solo_saludo(str(x.get("content") or ""))
        ]
        primera = (len(usuarios_reales) <= 1) and not info_completa_ya_enviada(numero, "buenaventura")

        if primera:
            estado["info_completa_enviada"] = True
            estado["info_completa_proyecto"] = "buenaventura"
            persistir_cliente(numero)

            if procesamiento_sigue_vigente(numero, message_id):
                enviar_info_completa_proyecto(numero, "buenaventura", cierre=False)
                cierre = (
                    "Para orientarle mejor 😊 ¿Qué cuota mensual aproximadamente "
                    "le resultaría cómoda?"
                )
                enviar_whatsapp(numero, cierre)
                guardar_mensaje(numero, "assistant", cierre)
            return True

        respuesta = respuesta_precio_breve_buenaventura()
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    if accion == "ubicacion":
        _limpiar_contextos_cta_buenaventura(numero)
        respuesta = respuesta_ubicacion_cta_buenaventura()
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    if accion == "lotes_disponibles":
        _limpiar_contextos_cta_buenaventura(numero, conservar="esperando_uso_lote_cta")
        estado["esperando_uso_lote_cta"] = True
        persistir_cliente(numero)
        respuesta = respuesta_lotes_disponibles_cta_buenaventura()
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    if accion == "agendar_visita":
        _limpiar_contextos_cta_buenaventura(numero, conservar="esperando_tipo_dia_visita_cta")
        estado["esperando_tipo_dia_visita_cta"] = True
        estado_visitas[numero] = {
            "dia": None,
            "hora": None,
            "proyecto": "buenaventura",
            "cerrada": False,
        }
        persistir_cliente(numero)
        respuesta = respuesta_visita_cta_buenaventura()
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    return False


def manejar_seguimiento_cta_buenaventura(numero, texto, proyecto, message_id):
    """Atiende respuestas cortas a preguntas que hizo uno de los botones."""
    if proyecto != "buenaventura":
        return False

    respuesta = respuesta_seguimiento_visita_cta(numero, texto, proyecto)
    if not respuesta:
        respuesta = respuesta_seguimiento_uso_lote_buenaventura(numero, texto)
    if not respuesta:
        respuesta = respuesta_seguimiento_medida_lotes_buenaventura(numero, texto)

    if not respuesta:
        return False

    guardar_mensaje(numero, "user", texto)
    guardar_mensaje(numero, "assistant", respuesta)
    if procesamiento_sigue_vigente(numero, message_id):
        enviar_whatsapp(numero, respuesta)
    return True


# ============================================================
# IDENTIFICACION DEL PROYECTO DESDE ANUNCIOS DE META / CLICK-TO-WHATSAPP
# ============================================================

ANUNCIOS_META_PROYECTO = {
    # Buenaventura Cuyotenango - anuncios históricos
    "120248129659680634": "buenaventura",  # AD VID - 01 - BNV CUYO
    "120248129290310634": "buenaventura",  # AD IMG - 01 - BNV CUYO

    # Buenaventura Cuyotenango - campaña anterior (se conserva como respaldo)
    "120248470171920634": "buenaventura",
    "120248470434590634": "buenaventura",
    "120248470398980634": "buenaventura",
    "120248470410070634": "buenaventura",
    "120248470403240634": "buenaventura",

    # Buenaventura Cuyotenango - nueva campaña actual (septiembre 2026)
    "120248487845740634": "buenaventura",
    "120248488028640634": "buenaventura",

    # Palmeras San Miguel - anuncios actuales (agosto 2026)
    "120248361771430634": "palmeras",
    "120248361520120634": "palmeras",
    "120248361871880634": "palmeras",
    "120248361895820634": "palmeras",
    "120248361823610634": "palmeras",
    "120248362032520634": "palmeras",
    "120248362063450634": "palmeras",


    # Vista Hermosa - campaña nueva septiembre 2026
    "120248674470520634": "vista_hermosa",

    # Palmeras San Miguel - campaña nueva septiembre 2026
    "120248674098970634": "palmeras",
    "120248673963430634": "palmeras",
    "120248673718320634": "palmeras",

    # Buenaventura Cuyotenango - campaña nueva septiembre 2026
    "120248674333730634": "buenaventura",
    "120248674412860634": "buenaventura",
    "120248674277790634": "buenaventura",
    "120248674320740634": "buenaventura",

    # Vista Hermosa
    "120248129777940634": "vista_hermosa",  # AD VID - 01 - VTH
    "120248129694970634": "vista_hermosa",  # AD IMG - 01 - VTH
    "120248129773580634": "vista_hermosa",  # AD IMG - 02 - VTH
}

PROYECTO_CAMPANA_ACTIVA = "buenaventura"


def _mensaje_generico_de_anuncio(texto):
    """Mensajes cortos típicos de los botones/plantillas de los anuncios actuales."""
    t = normalizar_ventas(str(texto or ""))
    t = re.sub(r"[^a-z0-9áéíóúüñ\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    exactos = {
        "informacion", "información", "mas informacion", "más información",
        "quiero informacion", "quiero información", "deseo informacion", "deseo información",
        "ubicacion", "ubicación", "precio", "precios", "cotizacion", "cotización",
        "me interesa", "estoy interesado", "estoy interesada", "hola quiero informacion",
        "hola quiero información", "quiero saber mas", "quiero saber más",
        # Nuevos botones de la campaña de Buenaventura Cuyotenango.
        "quiero conocer precios y cuotas",
        "quiero ver la ubicacion del proyecto",
        "quiero conocer lotes disponibles",
        "quiero agendar una visita"
    }
    return t in exactos


def proyecto_desde_referencia_anuncio(mensaje):
    """
    Detecta el proyecto desde anuncios de Meta.

    Para la campaña actual, todos los anuncios activos corresponden a Buenaventura Cuyotenango.
    Si Meta entrega un referral de anuncio pero cambia/omite el ID esperado, usamos Buenaventura
    como respaldo para no perder el contexto comercial.
    """
    mensaje = mensaje or {}
    referral = mensaje.get("referral") or {}

    if referral:
        try:
            print("REFERRAL META RECIBIDO:", json.dumps(referral, ensure_ascii=False))
        except Exception:
            print("REFERRAL META RECIBIDO:", referral)

    ads_context = referral.get("ads_context_data") or {}
    anuncio_id = str(
        referral.get("source_id")
        or referral.get("ad_id")
        or ads_context.get("ad_id")
        or ads_context.get("source_id")
        or ""
    ).strip()

    if anuncio_id:
        proyecto = ANUNCIOS_META_PROYECTO.get(anuncio_id)
        if proyecto:
            print(f"ANUNCIO META DETECTADO: {anuncio_id} -> {proyecto}")
            return proyecto
        # Todos los anuncios de la campaña activa actual corresponden a Buenaventura.
        if referral:
            print(f"ANUNCIO META ID NO MAPEADO ({anuncio_id}); FALLBACK ACTUAL -> buenaventura")
            return PROYECTO_CAMPANA_ACTIVA

    # Si existe referral pero Meta no incluyó source_id/ad_id, igualmente sabemos
    # que la campaña activa actual es Buenaventura Cuyotenango.
    if referral:
        print("ANUNCIO META CON REFERRAL SIN ID; FALLBACK ACTUAL -> buenaventura")
        return PROYECTO_CAMPANA_ACTIVA

    return None


def fijar_proyecto_desde_anuncio(numero, mensaje):
    proyecto = proyecto_desde_referencia_anuncio(mensaje)

    # Respaldo adicional: Meta permite que el usuario quite los datos de referencia.
    # Como EN ESTE MOMENTO la campaña activa es Buenaventura, si llega
    # una conversación todavía sin proyecto y el texto es el típico CTA corto del anuncio
    # (por ejemplo "Ubicación" o "Información"), la fijamos como Buenaventura.
    if not proyecto:
        existente = obtener_proyecto_actual(numero)
        if existente:
            return existente
        if (mensaje or {}).get("type") == "text":
            texto = ((mensaje or {}).get("text") or {}).get("body", "")
            if _mensaje_generico_de_anuncio(texto):
                proyecto = PROYECTO_CAMPANA_ACTIVA
                print(f"FALLBACK MENSAJE DE CAMPANA: {numero} -> buenaventura | texto={texto!r}")

    if not proyecto:
        return None

    estado = obtener_estado_conversacion(numero)
    estado["proyecto_actual"] = proyecto
    proyecto_activo[numero] = proyecto
    persistir_cliente(numero)
    print(f"PROYECTO FIJADO PARA CLIENTE: {numero} -> {proyecto}")
    return proyecto

# Guarda qué proyecto está activo para cada número.
proyecto_activo = {}

# Guarda el ultimo tema sensible de cada cliente para entender seguimientos
# como "¿cuánto es de cada uno?" sin perder el contexto.
ultima_intencion = {}


# ============================================================
# PROTECCION CONTRA MENSAJES DUPLICADOS / REINTENTOS DE META
# ============================================================

mensajes_procesados = set()

procesamiento_actual = {}
lock_procesamiento = Lock()


def iniciar_procesamiento(numero, message_id):
    """
    Registra cuál es el mensaje más reciente que estamos procesando
    para este número. Cualquier proceso viejo queda invalidado.
    """
    with lock_procesamiento:
        procesamiento_actual[numero] = message_id


def procesamiento_sigue_vigente(numero, message_id):
    """
    Devuelve True solo si este message_id sigue siendo el más reciente
    para ese cliente.
    """
    with lock_procesamiento:
        return procesamiento_actual.get(numero) == message_id
lock_mensajes = Lock()
MAX_MENSAJES_PROCESADOS = 5000


def marcar_mensaje_como_procesado(message_id):
    """
    Meta puede reenviar el MISMO webhook si nuestra respuesta tarda.
    Esta función evita procesar dos veces el mismo mensaje de WhatsApp.
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

# Estado persistente en memoria RAM por número.
# El proyecto se mantiene fijo hasta que el cliente mencione otro explícitamente.
estado_conversacion = {}

# Números a los que Gabriel ya se presentó durante esta ejecución.
# La presentación se envía SOLO una vez al inicio de la conversación/sesión.
clientes_presentados = set()


def necesita_presentacion_inicial(numero):
    return numero not in clientes_presentados


def marcar_cliente_presentado(numero):
    clientes_presentados.add(numero)
    persistir_cliente(numero)


def mensaje_presentacion_inicial():
    return "¡Hola! 👋 Soy Gabriel Polero. 😊 ¿En qué le podemos servir?"


def es_solo_saludo(texto):
    """
    Devuelve True únicamente cuando el mensaje del cliente es un saludo simple.
    Ejemplos: "hola", "buenas", "buenos días", "hola buenas noches".

    Si el saludo trae una consulta ("hola, precios de Buenaventura"),
    devuelve False para que el bot se presente y luego responda la pregunta.
    """
    if not texto:
        return False

    t = texto.lower().strip()

    # Quitamos signos y emojis, pero conservamos letras/números/espacios.
    t = re.sub(r"[^a-záéíóúüñ0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    saludos_simples = {
        "hola",
        "holaaa",
        "buenas",
        "buen día",
        "buen dia",
        "buenos días",
        "buenos dias",
        "buenas tardes",
        "buenas noches",
        "qué tal",
        "que tal",
        "hola buenas",
        "hola buen día",
        "hola buen dia",
        "hola buenos días",
        "hola buenos dias",
        "hola buenas tardes",
        "hola buenas noches",
    }

    return t in saludos_simples


def enviar_presentacion_si_corresponde(numero, message_id=None):
    """
    Envía una presentación breve antes de cualquier otra respuesta.
    Se ejecuta una sola vez por cliente durante la sesión actual del bot.
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
            "multimedia_pendiente": False,
            "esperando_cantidad_descuento_contado": False,
            "esperando_disponibilidad_desde_cta": False,
            "esperando_proyecto_despues_tres": False,
            # Contexto de los botones de la campaña de Buenaventura.
            "info_completa_enviada": False,
            "info_completa_proyecto": None,
            "esperando_uso_lote_cta": False,
            "esperando_medida_lotes_cta": False,
            "uso_lote_cta": None,
            "esperando_tipo_dia_visita_cta": False,
            "esperando_dia_visita_cta": False,
            "esperando_jornada_visita_cta": False,
            "esperando_hora_visita_cta": False,
            "tipo_dia_visita_cta": None,
            "jornada_visita_cta": None,
            # Flujo humano de Palmeras San Miguel.
            "psm_etapa": None,
            "psm_fase": None,
            "psm_plan": None,
            "psm_plazo": None,
            "psm_cotizacion_enviada": False,
            "psm_video_amenidades_enviado": False,
            "psm_pregunta_pendiente": None,
            "psm_visita_ofrecida": False,
            "psm_recordatorio_token": None,
            # Flujo humano de Vista Hermosa.
            "vh_etapa": None,
            "vh_fase": None,
            "vh_plan": None,
            "vh_plazo": None,
            "vh_cotizacion_enviada": False,
            "vh_video_amenidades_enviado": False,
            "vh_pregunta_pendiente": None,
            "vh_visita_ofrecida": False,
            # Control genérico de intervención humana.
            "requiere_intervencion_ia": False,
            "esperando_respuesta_gabriel": False,
            "intervencion_pregunta": None,
            # Alias/nombre editable manualmente desde el CRM.
            "crm_nombre_manual": ""
        }

    return estado_conversacion[numero]


def detectar_proyecto_en_texto(texto):
    """
    Detecta SOLO referencias suficientemente claras.
    No usamos palabras genéricas como "zona", "carretera", "ubicación", etc.
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


def es_seleccion_simple_de_proyecto(texto):
    """
    Detecta cuando el cliente únicamente está indicando qué proyecto le interesa.

    Ejemplos:
    - "Buenaventura"
    - "De Buenaventura"
    - "Me interesa Palmeras San Miguel"
    - "Información de Vista Hermosa"

    No intercepta preguntas concretas como precio, ubicación, cuotas, fotos,
    planos, amenidades, etc.; esas siguen pasando por sus flujos existentes.
    """
    proyecto = detectar_proyecto_en_texto(texto)
    if not proyecto:
        return False

    t = normalizar_texto_topografia(texto)
    t = re.sub(r"[^a-z0-9ñ\s]", " ", t)
    t = " ".join(t.split())

    aliases = {
        "buenaventura": {
            "buenaventura",
            "buenaventura cuyotenango",
            "cuyotenango",
        },
        "palmeras": {
            "palmeras",
            "palmeras san miguel",
            "san miguel",
        },
        "vista_hermosa": {
            "vista hermosa",
        },
    }

    prefijos = [
        "",
        "de ",
        "el de ",
        "quiero el de ",
        "me interesa ",
        "me interesa el de ",
        "informacion de ",
        "info de ",
        "quiero informacion de ",
        "quiero info de ",
        "quiero saber de ",
        "sobre ",
        "del proyecto ",
    ]

    candidatos = set()
    for alias in aliases.get(proyecto, set()):
        for prefijo in prefijos:
            candidatos.add((prefijo + alias).strip())

    return t in candidatos


def actualizar_proyecto_activo(numero, texto):
    """
    Si el cliente menciona un proyecto explícitamente, lo fija.
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
    "¿Cómo prefieres tu terreno: plano o inclinado?"

    Devuelve None cuando el mensaje no es una respuesta a esa pregunta.
    """
    estado = obtener_estado_conversacion(numero)

    if not estado.get("esperando_preferencia_topografia"):
        return None

    t = normalizar_texto_topografia(texto)

    # Solo tratamos respuestas cortas/claras como elección de topografía.
    if len(t.split()) > 8:
        return None

    if any(x in t for x in [
        "quebrado", "quebrada", "inclinado", "inclinada",
        "con pendiente", "pendiente"
    ]):
        guardar_preferencia_topografia(numero, "inclinado")

        if proyecto in {"palmeras", "buenaventura"}:
            return (
                "Perfecto 😊 En este proyecto los lotes se manejan en topografía plana. "
                "Si buscas específicamente un terreno quebrado o inclinado para un diseño "
                "especial, dímelo y te ayudo a revisar qué alternativa podemos ofrecerte. 🏡"
            )

        if proyecto == "vista_hermosa":
            return (
                "Perfecto 😊 En Vista Hermosa sí hay lotes planos y también algunos "
                "quebrados/inclinados. Puedes revisar los planos y escoger las opciones "
                "que te interesen; si buscas uno quebrado, te ayudo a identificar opciones "
                "para que puedas escoger con más seguridad. 🏡"
            )

        return (
            "Perfecto 😊 Si prefieres un lote quebrado o inclinado, dime qué opción "
            "te interesa y te ayudo a revisarla."
        )

    # "plano", "un plano", "uno plano", "prefiero plano", etc.
    if any(x in t for x in [
        "plano", "plana", "llano", "llana"
    ]):
        guardar_preferencia_topografia(numero, "plano")

        if proyecto in {"palmeras", "buenaventura"}:
            return (
                "Perfecto 😊 Puedes revisar el plano y la disponibilidad, escoger el lote "
                "que más te guste y enviarme el número o una captura. En este proyecto los "
                "lotes se manejan en topografía plana, así que con gusto te ayudo a revisar "
                "la opción que elijas. 🏡"
            )

        if proyecto == "vista_hermosa":
            return (
                "Perfecto 😊 Puedes revisar los planos y la disponibilidad, escoger el lote "
                "que más te guste y enviarme el número o una captura. En Vista Hermosa hay "
                "lotes planos y también algunos quebrados, así que antes de asegurártelo "
                "te confirmo la topografía exacta del lote que elijas. 🏡"
            )

        return (
            "Perfecto 😊 Revisa el plano, escoge el lote que te interese y envíame "
            "el número o una captura; te ayudo a confirmar su topografía."
        )

    return None


def parece_numero_de_lote(texto):
    """
    Detecta referencias como 'lote 125', 'número de lote 125', '#125'.
    Se usa únicamente cuando ya venimos hablando de topografía.
    """
    t = normalizar_texto_topografia(texto)

    patrones = [
        r"\blote\s*[#nº°.-]*\s*\d{1,5}\b",
        r"\bnumero\s+(?:de\s+)?lote\s*[#nº°.-]*\s*\d{1,5}\b",
        r"\bno\.?\s*\d{1,5}\b",
        r"^#\s*\d{1,5}$"
    ]

    return any(re.search(p, t) for p in patrones)


def respuesta_revision_lote_topografia(numero, proyecto, texto):
    """
    Responde cuando el cliente manda un número de lote dentro del seguimiento
    de topografía.

    Buenaventura y Palmeras: topografía plana según la regla comercial cargada.
    Vista Hermosa: no inventamos el dato individual sin una tabla topográfica.
    """
    estado = obtener_estado_conversacion(numero)

    if not estado.get("topografia_en_conversacion"):
        return None

    if not parece_numero_de_lote(texto):
        return None

    if proyecto in {"palmeras", "buenaventura"}:
        return (
            "Sí 😊 Ese lote se maneja en topografía plana. Si quieres, también puedo "
            "ayudarte a revisar disponibilidad, precio o cuota de esa opción. 🏡"
        )

    if proyecto == "vista_hermosa":
        return (
            "Perfecto 😊 Ya tengo la referencia del lote. En Vista Hermosa hay opciones "
            "planas y quebradas, así que para darte seguridad prefiero confirmarte la "
            "topografía exacta de ese lote. Déjame revisarlo y te lo envío en un momento."
        )

    return (
        "Perfecto 😊 Déjame revisar exactamente la topografía de ese lote "
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
            "No 😊 En este proyecto los lotes se manejan en topografía plana. "
            "Si estás buscando específicamente una opción quebrada/inclinada, "
            "dímelo y te ayudo a revisar alternativas."
        )

    if proyecto == "vista_hermosa":
        return (
            "Si lo que buscas es uno quebrado/inclinado, con gusto te ayudo a revisar "
            "las opciones de Vista Hermosa que tengan ese tipo de topografía para que "
            "puedas escoger. 😊🏡"
        )

    return None



# ============================================================
# REGLAS COMERCIALES NUEVAS: CONTADO, CONSTRUCCION Y ESTADO DE AMENIDADES
# ============================================================

def normalizar_ventas(texto):
    t = (texto or "").lower().strip()
    reemplazos = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u", "ñ": "n"
    }
    for a, b in reemplazos.items():
        t = t.replace(a, b)
    return " ".join(t.split())


def pregunta_descuento_contado(texto):
    t = normalizar_ventas(texto)
    referencias_contado = [
        "de contado", "al contado", "pago contado", "pagar contado",
        "pago de una vez", "pagar de una vez", "cancelar de una vez"
    ]
    referencias_descuento = [
        "descuento", "rebaja", "mejor precio", "precio especial",
        "cuanto me baja", "cuanto baja", "me descuentan"
    ]
    return (
        any(x in t for x in referencias_contado)
        and (any(x in t for x in referencias_descuento) or "contado" in t)
    )


def extraer_cantidad_lotes_compra(texto):
    t = normalizar_ventas(texto)
    palabras = {
        "uno": 1, "un": 1, "una": 1,
        "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
        "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10
    }
    m = re.search(r"\b(\d{1,2})\s*(?:lotes?|terrenos?)?\b", t)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 50:
            return n
    for palabra, n in palabras.items():
        if re.search(rf"\b{re.escape(palabra)}\s+(?:lotes?|terrenos?)\b", t):
            return n
    if t in palabras:
        return palabras[t]
    return None


def respuesta_descuento_contado(numero, texto):
    estado = obtener_estado_conversacion(numero)
    cantidad = extraer_cantidad_lotes_compra(texto)

    if cantidad is None:
        estado["esperando_cantidad_descuento_contado"] = True
        persistir_cliente(numero)
        return (
            "Sí 😊 Manejamos descuento por pago de contado. "
            "Si es 1 lote aplicamos 3% de descuento y si son 2 lotes o más aplicamos 5%. 🏡💰\n\n"
            "¿Cuántos lotes te interesan?"
        )

    estado["esperando_cantidad_descuento_contado"] = False
    estado["esperando_disponibilidad_desde_cta"] = True
    persistir_cliente(numero)

    if cantidad == 1:
        return (
            "¡Perfecto! 😊 Si compras 1 lote y realizas el pago de contado, "
            "podemos aplicarte un 3% de descuento sobre la compra. 🏡💰\n\n"
            "Además, el diseño de construcción es libre: puedes hacer vivienda, apartamentos "
            "o locales, siempre que sea una construcción formal con block. 🏗️\n\n"
            "¿Quieres que te muestre las opciones disponibles? 😊"
        )

    return (
        f"¡Excelente! 😊 Al ser {cantidad} lotes y realizar el pago de contado, "
        "podemos aplicarte un 5% de descuento sobre la compra. 🏡💰\n\n"
        "Además, el diseño de construcción es libre: puedes hacer vivienda, apartamentos "
        "o locales, siempre que sea una construcción formal con block. 🏗️\n\n"
        f"¿Quieres que te muestre la disponibilidad de {cantidad} lotes juntos? 😊"
    )


def respuesta_cantidad_descuento_pendiente(numero, texto):
    estado = obtener_estado_conversacion(numero)
    if not estado.get("esperando_cantidad_descuento_contado"):
        return None
    cantidad = extraer_cantidad_lotes_compra(texto)
    if cantidad is None:
        return None
    return respuesta_descuento_contado(numero, texto)


def pregunta_diseno_construccion(texto):
    t = normalizar_ventas(texto)
    claves = [
        "casas iguales", "casa igual", "tienen que ser iguales", "tiene que ser igual",
        "deben ser iguales", "mismo diseno", "diseño igual",
        "diseno obligatorio", "diseño obligatorio", "puedo construir como quiera",
        "puedo hacer apartamentos", "puedo hacer apartamento", "puedo hacer locales",
        "puedo hacer local", "tipo de construccion", "reglas para construir",
        "modelo de casa", "diseno de casa", "diseño de casa"
    ]
    return any(normalizar_ventas(x) in t for x in claves)


def respuesta_diseno_construccion():
    return (
        "Sí 😊 El diseño de construcción es libre. Puedes construir vivienda, apartamentos "
        "o locales en tu terreno, siempre que sea una construcción formal con block. 🏗️🏡\n\n"
        "Así puedes adaptar el terreno al proyecto que tengas pensado."
    )


def pregunta_por_que_sin_garita_palmeras(texto, proyecto=None):
    """Solo activa la explicación comercial cuando preguntan POR QUÉ Palmeras no tiene garita."""
    t = normalizar_ventas(texto)
    if proyecto != "palmeras" and "palmeras" not in t and "san miguel" not in t:
        return False

    menciona_garita = "garita" in t or "muro perimetral" in t
    pregunta_motivo = any(x in t for x in [
        "por que", "porque", "por qué", "cual es la razon", "cuál es la razón",
        "por que no tiene", "porque no tiene", "por que no cuenta", "porque no cuenta",
        "por que es abierta", "porque es abierta"
    ])
    return menciona_garita and pregunta_motivo


def respuesta_por_que_sin_garita_palmeras():
    return (
        "Claro 😊 Palmeras San Miguel se desarrolló como una *lotificación abierta*, por eso no cuenta con garita ni muro perimetral.\n\n"
        "Esto también tiene algunas ventajas 🏡: el acceso al proyecto es más directo y no tendrá un cobro adicional relacionado específicamente con seguridad o funcionamiento de garita.\n\n"
        "Además, mantiene las principales características del proyecto, como calles pavimentadas, agua potable, energía eléctrica, drenajes con planta de tratamiento y sus áreas de amenidades. 🌳🏊\n\n"
        "Es una opción pensada para quien busca tener su terreno con mayor libertad de acceso y sin ese costo adicional. 😊\n\n"
        "¿Le gustaría que le muestre las medidas y precios disponibles en Palmeras San Miguel?"
    )


def pregunta_estado_amenidades_o_garita(texto):
    t = normalizar_ventas(texto)
    elementos = [
        "garita", "muro perimetral", "amenidades", "piscina", "piscinas",
        "casa club", "salon", "juegos", "areas verdes", "caminamientos"
    ]
    estado = [
        "ya esta", "ya estan", "ya hicieron", "ya hicieron la", "ya hay",
        "esta construida", "estan construidas", "esta hecha", "estan hechas",
        "ya existe", "ya existen", "como se ve en el video", "como aparece en el video",
        "del video", "de las fotos"
    ]
    return any(x in t for x in elementos) and any(x in t for x in estado)


def respuesta_estado_amenidades(numero, proyecto):
    estado = obtener_estado_conversacion(numero)
    estado["esperando_disponibilidad_desde_cta"] = True
    persistir_cliente(numero)

    cta = "¿Ya vio alguna medida que le interese o quiere que le muestre cuáles tenemos disponibles? 😊"

    if proyecto == "vista_hermosa":
        return (
            "Vista Hermosa sí cuenta con *garita y muro perimetral* y tendrá sus áreas de amenidades 🏡🌴. "
            "El proyecto todavía se encuentra en proceso de urbanización, por lo que no se debe dar por terminada toda la obra.\n\n"
            + cta
        )

    if proyecto == "buenaventura":
        return (
            "Aún no 😊 Buenaventura Cuyotenango se encuentra en proceso de urbanización, "
            "por lo que la garita y las amenidades todavía no están construidas. 🏗️\n\n"
            "Las imágenes o videos que te mostramos sirven como referencia de nuestros otros proyectos. "
            "Buenaventura sí contará con garita, muro perimetral y sus amenidades. 🏡🌴\n\n"
            + cta
        )

    if proyecto == "palmeras":
        return (
            "En Palmeras San Miguel las amenidades todavía no están construidas, ya que actualmente "
            "estamos en proceso de urbanización. 🏗️🌴\n\n"
            "Las imágenes o videos sirven como referencia de nuestros otros proyectos. "
            "En Palmeras San Miguel sí tendremos las amenidades indicadas, pero este proyecto "
            "NO contará con garita ni muro perimetral.\n\n"
            + cta
        )

    return (
        "Déjame confirmar el estado exacto de esa parte del proyecto para darte la información correcta 😊"
    )


def confirmacion_para_mostrar_disponibilidad(numero, texto):
    estado = obtener_estado_conversacion(numero)
    if not estado.get("esperando_disponibilidad_desde_cta"):
        return False
    t = normalizar_ventas(texto)
    afirmaciones = [
        "si", "si por favor", "si porfa", "dale", "de una", "muestrame",
        "muestreme", "quiero ver", "ensename", "enseneme", "mandame",
        "enviame", "cuales", "cuales hay", "disponibles", "ver disponibilidad"
    ]
    return any(t == x or x in t for x in afirmaciones)


def limpiar_confirmacion_disponibilidad(numero):
    estado = obtener_estado_conversacion(numero)
    estado["esperando_disponibilidad_desde_cta"] = False
    persistir_cliente(numero)

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
    """Normaliza texto para detectar mejor intenciones de topografía."""
    t = (texto or "").lower().strip()
    reemplazos = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u"
    }
    for origen, destino in reemplazos.items():
        t = t.replace(origen, destino)
    return " ".join(t.split())


def pregunta_topografia_terreno(texto):
    """
    Detecta cuando "plano" habla de la TOPOGRAFÍA del lote y no del PDF/croquis.
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
    preferencia por la topografía del lote.
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
    El precio del lote NO cambia por la topografía.
    """
    base = (
        "Claro 😊 En nuestros proyectos puedes encontrar lotes con distintas "
        "condiciones de topografía. El precio del lote es el mismo según la "
        "medida y fase, ya sea plano o inclinado/quebrado. 🏡\n\n"
        "🟢 *Terreno plano:* facilita diseños de construcción más convencionales, "
        "accesos, patios y distribución exterior; normalmente requiere menos "
        "adaptación inicial del terreno.\n\n"
        "⛰️ *Terreno inclinado o quebrado:* puede ser muy atractivo para diseños "
        "escalonados, casas de varios niveles, terrazas o proyectos que aprovechen "
        "la pendiente de forma arquitectónica.\n\n"
        "El costo de construcción sí puede variar dependiendo del diseño, "
        "movimiento de tierra y cimentación que elijas, pero *el precio de venta "
        "del lote no cambia por ser plano o inclinado*."
    )

    if preferencia == "plano":
        return (
            base
            + "\n\nPor lo que me indicas, buscas uno *plano* 👍. "
              "Puedo ayudarte a enfocarnos en ese tipo de lote. "
              "¿De cuál proyecto te interesa?"
        )

    if preferencia == "inclinado":
        return (
            base
            + "\n\nPerfecto 👍 Si prefieres uno *inclinado/quebrado*, "
              "podemos buscar una opción que se adapte al diseño de casa que tienes en mente. "
              "¿De cuál proyecto te interesa?"
        )

    return base + "\n\n¿Cuál prefieres tú: *plano o inclinado*? 😊"


def mensaje_topografia_despues_de_plano():
    return (
        "🏡 *Sobre la topografía:* los lotes que ves en el plano pueden encontrarse "
        "en topografía plana. Si prefieres un lote inclinado/quebrado para un diseño "
        "de casa específico, dínoslo y te ayudamos a buscar una opción adecuada. 😊\n\n"
        "El precio del lote no cambia por ser plano o inclinado; depende de la medida "
        "y fase correspondiente.\n\n"
        "¿Cómo prefieres tu terreno: *plano o inclinado*?"
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
        # Peticiones directas como "plano vista hermosa", "plano palmeras"
        # o "plano buenaventura" deben enviar el documento sin caer en IA.
        if any(x in t for x in [
            "vista hermosa", "palmeras", "san miguel",
            "buenaventura", "cuyotenango", "km 188", "km 168"
        ]):
            return True

        if t.startswith("plano") or t.startswith("planos"):
            return True

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
        "Para que puedas interpretar el plano, estos son los colores 😊\n\n"
        "🟢 Disponible: lote disponible para la venta.\n"
        "🔴 Vendido: lote que ya fue vendido.\n"
        "🟣 Reservado por área técnica: no está disponible para la venta.\n"
        "🔵 Apartado por área técnica: será tomado como área verde.\n"
        "🟡 Reservado: lote que se encuentra reservado."
    )


def seleccionar_planos(proyecto, texto):
    """Selecciona uno o todos los planos del proyecto según la fase solicitada."""
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


def pregunta_por_diferencia_de_fases(texto, proyecto=None):
    """Detecta preguntas sobre por qué existen precios distintos entre fases.

    Debe reconocer tanto menciones explícitas de fases como preguntas naturales
    del tipo "¿a qué se debe la diferencia del precio?" o "¿por qué hay dos precios?".
    """
    t = " ".join((texto or "").lower().strip().split())

    referencias_fase = [
        "fase 1", "fase1", "fase 2", "fase2",
        "primera fase", "segunda fase",
        "fase f", "fase g",
        "una fase", "otra fase"
    ]
    referencias_precio = [
        "precio", "precios", "diferencia", "caro", "cara",
        "cuesta", "vale", "valor", "sube", "subió", "subio"
    ]

    # Caso explícito: menciona fases + precio/diferencia.
    if any(x in t for x in referencias_fase) and any(x in t for x in referencias_precio):
        return True

    # Solo Vista Hermosa y Palmeras tienen fases con precios distintos cargados.
    if proyecto not in {"vista_hermosa", "palmeras"}:
        return False

    # Caso natural: no obliga al cliente a escribir la palabra "fase".
    # Esto cubre incluso errores de escritura como "a que s debe la diferencia del precio".
    if "diferencia" in t and any(x in t for x in ["precio", "precios", "cuesta", "vale", "valor"]):
        return True

    if "dos precios" in t or "precios diferentes" in t or "precios distintos" in t:
        return True

    if any(x in t for x in [
        "por que uno cuesta mas", "por qué uno cuesta más",
        "por que uno vale mas", "por qué uno vale más",
        "por que uno es mas caro", "por qué uno es más caro",
        "por que cambia el precio", "por qué cambia el precio"
    ]):
        return True

    return False


def respuesta_diferencia_fases(numero):
    proyecto = obtener_proyecto_actual(numero)

    if proyecto == "palmeras":
        return (
            "En Palmeras San Miguel ambas fases tienen lotes de 8x16 y están en proceso de urbanización 😊. "
            "La diferencia comercial actual es que la Fase 1 cuesta Q67,200 y contará con piscina y área verde; "
            "la Fase 2 cuesta Q70,400 y contará con área verde. 🏡🌳"
        )

    if proyecto == "vista_hermosa":
        return (
            "Sí 😊 En Vista Hermosa ambos lotes son de 8x16, pero pertenecen a fases diferentes. "
            "La Fase F tiene un precio de Q83,200 y la Fase G de Q89,600. "
            "La diferencia se debe principalmente a la plusvalía que ha ido ganando el proyecto "
            "y al avance de urbanización conforme se desarrollan calles, servicios, amenidades e infraestructura 🏡📈."
        )

    nombres = {"buenaventura": "Buenaventura Cuyotenango"}
    nombre = nombres.get(proyecto, "el proyecto")
    return (
        f"Sí 😊 En {nombre}, la diferencia de precio entre una fase y otra "
        "se debe principalmente a la plusvalía que ha ido ganando el proyecto "
        "y al mayor avance de urbanización en las fases más recientes 🏡📈."
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
            "cuando el proyecto ya esté urbanizado; mientras no esté urbanizado, no se cobran."
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
            "cuando el proyecto ya esté urbanizado; mientras no esté urbanizado, no se cobran."
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
        "estoy en otro pais", "estoy en otro país",
        "vivo en otro pais", "vivo en otro país",
        "estoy fuera de guatemala", "vivo fuera de guatemala",
        "estoy en el extranjero", "vivo en el extranjero",
        "desde estados unidos", "desde usa", "desde el extranjero",
        "puedo comprar desde estados unidos", "puedo comprar desde usa",
        "puedo comprar desde otro pais", "puedo comprar desde otro país",
        "puedo comprar desde el extranjero"
    ]

    return any(f in t for f in frases)


def pide_requisitos_compra(texto):
    t = texto.lower()

    frases = [
        "requisitos",
        "papeles", "que papeles", "qué papeles",
        "documentos", "que documentos", "qué documentos",
        "papeles para el financiamiento", "papeles del financiamiento",
        "documentos para el financiamiento", "documentos del financiamiento",
        "requisitos para el financiamiento", "requisitos del financiamiento",
        "que necesito para financiar", "qué necesito para financiar",
        "que piden para financiar", "qué piden para financiar",
        "que necesito para comprar", "qué necesito para comprar",
        "documentos para comprar",
        "como puedo comprar", "cómo puedo comprar",
        "que piden para comprar", "qué piden para comprar",
        "requisitos de compra"
    ]

    return any(f in t for f in frases)



def respuesta_compra_extranjero():
    return (
        "Sí 😊 puede comprar aunque se encuentre en Estados Unidos o en otro país 🇺🇸🌎.\n\n"
        "Los requisitos principales son:\n"
        "• Datos generales del comprador y del gestor en Guatemala.\n"
        "• DPI o pasaporte del comprador.\n"
        "• DPI o documento del gestor.\n"
        "• Constancia de que el comprador envía el dinero por remesa: captura, comprobante o voucher de retiro.\n\n"
        "El financiamiento es propio y directo con la empresa. Con los documentos completos, el gestor o comprador "
        "coordina con el asesor la firma correspondiente."
    )


def respuesta_compra_guatemala():
    return (
        "Claro 😊 Para realizar la compra necesita:\n\n"
        "• DPI.\n"
        "• Completar el enganche correspondiente.\n"
        "• Recibo de luz.\n"
        "• Carta de ingresos o estados de cuenta.\n"
        "• Datos generales del comprador.\n\n"
        "El financiamiento es propio y directo con la empresa, sin banco 🏡💳."
    )



def respuesta_requisitos_segun_contexto(numero, texto):
    """
    Si el cliente indica que está fuera de Guatemala, usa requisitos de extranjero.
    Si no indica extranjero, usa requisitos de Guatemala.
    """
    if cliente_en_extranjero(texto):
        return respuesta_compra_extranjero()

    # Revisar historial por si ya había dicho que está fuera.
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
    if "escritura" in t or "escrituras" in t or "escrituracion" in t or "escrituración" in t:
        palabras_tiempo = [
            "cuanto tiempo", "cuánto tiempo",
            "cuanto tarda", "cuánto tarda",
            "cuanto tardan", "cuánto tardan",
            "cuando entregan", "cuándo entregan",
            "cuando entrega", "cuándo entrega",
            "me entregan", "me entrega",
            "entregan la escritura", "entrega la escritura",
            "en darme", "en dar", "para darme",
            "plazo", "tiempo de"
        ]

        if any(p in t for p in palabras_tiempo):
            return True

    frases = [
        "cuanto tarda la escritura", "cuánto tarda la escritura",
        "cuanto tardan en dar la escritura", "cuánto tardan en dar la escritura",
        "cuando entregan la escritura", "cuándo entregan la escritura",
        "cuando entrega la escritura", "cuándo entrega la escritura",
        "en cuanto tiempo dan la escritura", "en cuánto tiempo dan la escritura",
        "en cuanto tiempo me entregan la escritura", "en cuánto tiempo me entregan la escritura",
        "en cuanto tiempo entrega la escritura", "en cuánto tiempo entrega la escritura",
        "cuanto tiempo se tardan en darme la escritura", "cuánto tiempo se tardan en darme la escritura",
        "tiempo de la escritura", "plazo de la escritura",
        "cuando dan escrituras", "cuándo dan escrituras",
        "cuanto tarda la escrituracion", "cuánto tarda la escrituración"
    ]

    return any(f in t for f in frases)



def respuesta_plazo_escritura(proyecto=None):
    if proyecto == "palmeras":
        return (
            "Sí 😊 La escritura es registrada. Después de cancelar el terreno, el trámite "
            "de escrituración y registro tarda aproximadamente entre 3 y 6 meses 📄✅. "
            "Mientras se completa el proceso, se entrega documentación legal que respalda la compra."
        )
    return (
        "Las escrituras son registradas 📄✅ y se entregan aproximadamente "
        "en un plazo de 3 meses."
    )



def pregunta_plazo_entrega_urbanizacion(texto):
    t = texto.lower()

    frases = [
        "en cuanto tiempo entregan", "en cuánto tiempo entregan",
        "cuando entregan", "cuándo entregan",
        "cuando terminan", "cuándo terminan",
        "cuando terminan de urbanizar", "cuándo terminan de urbanizar",
        "cuanto tarda la urbanizacion", "cuánto tarda la urbanización",
        "tiempo de urbanizacion", "tiempo de urbanización",
        "cuando estara terminado", "cuándo estará terminado",
        "cuando queda terminado", "cuándo queda terminado",
        "plazo de entrega", "fecha de entrega",
        "cuando se entrega", "cuándo se entrega",
        "cuando puedo construir", "cuándo puedo construir"
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
        f"El plazo aproximado para completar la urbanización de {nombre} "
        "es de 1 a 2 años 🏡🚧. Conforme avanza el proyecto se van desarrollando "
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
            "basquet", "básquet", "basket", "baloncesto"
        ],
        "salon": [
            "salon de eventos", "salón de eventos",
            "salon social", "salón social",
            "casa club", "club house"
        ],
        "juegos": [
            "juegos para niños", "juegos infantiles",
            "area de juegos", "área de juegos", "juegos"
        ],
        "areas_verdes": [
            "areas verdes", "áreas verdes",
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
        "cuantas piscinas", "cuántas piscinas",
        "cuanta piscina", "cuánta piscina",
        "numero de piscinas", "número de piscinas",
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

    if proyecto == "vista_hermosa":
        if amenidad == "piscina":
            return (
                "Sí 😊 La piscina corresponde a la *Fase F* de Vista Hermosa, junto con su área verde. "
                "La Fase G cuenta con área verde. ¿Desea que le comparta los planos para comparar ambas fases?"
            )
        if amenidad == "areas_verdes":
            return (
                "Sí 😊 Tanto la *Fase F* como la *Fase G* de Vista Hermosa cuentan con área verde 🌳. "
                "¿Cuál de las dos fases le interesa más?"
            )
        return (
            "Esa amenidad no la tengo confirmada como parte de Vista Hermosa y prefiero no inventarle información 😊. "
            "¿Desea que le confirme únicamente las amenidades oficiales que sí tenemos cargadas?"
        )

    if proyecto == "palmeras":
        if amenidad == "piscina":
            return (
                "Sí 😊 La piscina corresponde a la Fase 1 de Palmeras San Miguel, junto con su área verde. "
                "La Fase 2 contará con área verde, pero no con piscina."
            )
        if amenidad == "areas_verdes":
            return "Sí 😊 Tanto la Fase 1 como la Fase 2 de Palmeras San Miguel contarán con área verde 🌳."
        return (
            "Esa amenidad no la tengo confirmada como parte de Palmeras San Miguel. "
            "Prefiero no indicarle algo que no esté contemplado oficialmente 😊."
        )

    if amenidad == "piscina" and pregunta_cantidad_piscinas(texto_cliente):
        cantidad = cantidad_piscinas_proyecto(proyecto)
        if cantidad is not None:
            palabra = "piscina" if cantidad == 1 else "piscinas"
            return (
                f"{nombre} cuenta con {cantidad} {palabra} 🏊😊. "
                "Le comparto material para que pueda conocerlas mejor 👇📸🎥"
            )

    etiquetas = {
        "piscina": "piscinas 🏊",
        "cancha": "canchas deportivas 🏀",
        "salon": "casa club / salón para actividades 🎉",
        "juegos": "áreas de juegos para niños 🛝",
        "areas_verdes": "áreas verdes y caminamientos 🌳"
    }

    etiqueta = etiquetas.get(amenidad, "esa amenidad")
    return (
        f"Sí 😊 En {nombre} contamos con {etiqueta}. "
        "Le comparto material para que pueda verla mejor 👇📸🎥"
    )



def material_amenidad(proyecto, amenidad):
    """
    Material específico ya cargado en el bot.
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
                caption="Amenidades del proyecto 🏡📸" if i == 0 else ""
            )

    for i, ruta in enumerate(videos):
        if os.path.exists(ruta):
            enviar_video_whatsapp(
                numero,
                ruta,
                caption="Amenidades disponibles 🎥✨" if i == 0 else ""
            )



def enviar_paquete_amenidades(numero, proyecto):
    """
    Envía únicamente VIDEOS de amenidades.
    Se usa automáticamente después de cotizaciones y cuando corresponde
    mostrar material visual de amenidades.

    No genera ni envía imágenes congeladas de los videos y no reutiliza
    fotos generales de los proyectos.
    """
    if proyecto == "palmeras":
        enviar_whatsapp(
            numero,
            "Le comparto un video de amenidades realizadas en otros proyectos de la empresa 🏡✨. "
            "Sirve como referencia del tipo de espacios que desarrollamos; en Palmeras San Miguel "
            "la Fase 1 contará con piscina y área verde, y la Fase 2 con área verde."
        )
        for ruta in VIDEOS_GENERALES:
            if os.path.exists(ruta):
                enviar_video_whatsapp(numero, ruta, caption="Video de referencia de amenidades 🎥✨")
                return
        return

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
        "También te comparto videos de las amenidades para que puedas "
        "conocer mejor las áreas del proyecto 🏊🌳🏡🎥"
    )

    for i, ruta in enumerate(videos[:3], start=1):
        enviar_video_whatsapp(
            numero,
            ruta,
            caption="Recorrido por las amenidades 🎥✨" if i == 1 else ""
        )


def pregunta_banco_financiamiento(texto):
    t = texto.lower().strip()

    frases = [
        "que banco", "qué banco",
        "con que banco", "con qué banco",
        "de que banco", "de qué banco",
        "cual banco", "cuál banco",
        "trabajan con banco", "trabaja con banco",
        "financiamiento bancario",
        "es con banco", "es de banco",
        "por medio de banco",
        "el financiamiento es de banco",
        "el financiamiento es con banco",
        "que banco financia", "qué banco financia",
        "quien financia", "quién financia",
        "con que financiamiento es el banco",
        "con qué financiamiento es el banco",
        "financiamiento es el banco",
        "financiamiento del banco",
        "banco del financiamiento"
    ]

    # Si menciona "banco" y "financiamiento" en la misma frase,
    # también lo tratamos como pregunta de banco aunque esté redactado raro.
    if "banco" in t and (
        "financiamiento" in t
        or "financiar" in t
        or "credito" in t
        or "crédito" in t
    ):
        return True

    return any(f in t for f in frases)



def pregunta_financiamiento(texto):
    t = texto.lower()

    palabras = [
        "financiamiento", "financiar", "financiado",
        "credito", "crédito", "cuotas", "plazos"
    ]

    return any(p in t for p in palabras)


def respuesta_financiamiento_propio():
    return (
        "El financiamiento es propio y directo con la empresa 😊🏡. "
        "No trabajamos con ningún banco."
    )



def pregunta_punto_encuentro(texto):
    t = texto.lower()

    frases = [
        "donde nos juntamos", "dónde nos juntamos",
        "donde nos podemos juntar", "dónde nos podemos juntar",
        "donde quedamos de juntarnos", "dónde quedamos de juntarnos",
        "punto de encuentro", "donde nos vemos", "dónde nos vemos",
        "en donde nos vemos", "en dónde nos vemos",
        "donde me espera", "dónde me espera",
        "donde lo encuentro", "dónde lo encuentro",
        "donde nos encontramos", "dónde nos encontramos",
        "en que lugar nos juntamos", "en qué lugar nos juntamos"
    ]

    return any(f in t for f in frases)


def respuesta_punto_encuentro(numero, proyecto):
    nombres = {
        "palmeras": "Palmeras San Miguel",
        "vista_hermosa": "Vista Hermosa",
        "buenaventura": "Buenaventura Cuyotenango"
    }

    nombre = nombres.get(proyecto, "el proyecto")

    if proyecto == "palmeras":
        return (
            "Normalmente nos reunimos en Centro Comercial La Trinidad 😊📍 y desde allí le acompaño a Palmeras San Miguel. "
            "Es importante coordinar antes de llegar para asegurarme de poder atenderle personalmente."
        )

    return (
        f"Podemos encontrarnos directamente en {nombre} 😊📍. "
        "Si necesita otro punto, me lo indica."
    )




def pregunta_proceso_compra(texto):
    t = normalizar_texto_topografia(texto)
    frases = [
        "proceso de compra", "como se compra", "como comprar",
        "como puedo comprar", "como hago para comprar",
        "que necesito para comprar", "que se necesita para comprar",
        "como es la compra", "como funciona la compra",
        "cual es el proceso", "cuál es el proceso"
    ]
    return any(f in t for f in frases)


def respuesta_proceso_compra(proyecto):
    if proyecto == "vista_hermosa":
        return (
            "En Vista Hermosa el proceso empieza escogiendo la ubicación disponible que más le interese 🏡. "
            "Puede reservarla con *Q1,500*; ese monto forma parte del enganche total de *Q6,000*.\n\n"
            "Después completa requisitos y elige entre financiamiento propio de *2 a 8 años*, "
            "plan de *1 año sin intereses* o pago al contado. "
            "¿Desea que le comparta los planos de Fase F y Fase G para revisar ubicaciones?"
        )

    if proyecto == "palmeras":
        return (
            "En Palmeras San Miguel el proceso empieza escogiendo el lote disponible que más le interese 🏡. "
            "Para reservarlo se depositan Q3,000 a la cuenta de la empresa; ese monto forma parte del enganche de Q6,000, "
            "se emite factura y la ubicación queda apartada exclusivamente para usted por un máximo de 15 días.\n\n"
            "Dentro de ese plazo se completan el enganche, los requisitos y la modalidad de pago. "
            "Si compra financiado se firma contrato de compraventa; si compra al contado se firma el protocolo de escrituración. "
            "¿Desea que le comparta los planos para revisar ubicaciones disponibles?"
        )

    datos = {
        "buenaventura": {
            "nombre": "Buenaventura Cuyotenango",
            "enganche": "Q6,000",
            "financiamiento": "de 2 a 8 años",
            "extra": "También hay un plan alternativo de 1 año sin intereses cuando esté vigente.",
        },
        "palmeras": {
            "nombre": "Palmeras San Miguel",
            "enganche": "Q6,000",
            "financiamiento": "de 2 a 8 años",
            "extra": "También existe plan de 1 año sin intereses y pago al contado.",
        },
        "vista_hermosa": {
            "nombre": "Vista Hermosa",
            "enganche": "Q6,000",
            "financiamiento": "de 2 a 8 años",
            "extra": "También existe plan de 1 año sin intereses y pago al contado.",
        },
    }

    d = datos.get(proyecto)
    if not d:
        return (
            "Claro 😊 Primero elegimos el lote y confirmamos disponibilidad. "
            "Luego revisamos el enganche, el plan de pagos y los documentos necesarios. "
            "¿De qué proyecto te interesa comprar? 🏡"
        )

    extra = f" {d['extra']}" if d["extra"] else ""

    return (
        f"Te cuento cómo es el proceso de compra en *{d['nombre']}* 🏡😊\n\n"
        f"1️⃣ Eliges tu lote y medida 📐 y yo te ayudo a revisar disponibilidad, "
        f"cotización y plan de pagos.\n\n"
        f"2️⃣ Realizas el enganche 💰. En este proyecto es de *{d['enganche']}* "
        f"y contamos con financiamiento propio {d['financiamiento']}. "
        f"También puedes hacer abonos a capital.{extra}\n\n"
        f"3️⃣ Firma y escrituración ✍️📄. Las escrituras son registradas y se entregan "
        f"aproximadamente *3 meses después de haber cancelado el 100% del terreno*. ✅\n\n"
        f"📋 *Requisitos para comprar:*\n"
        f"🇬🇹 Guatemala: DPI, recibo de luz o agua y constancia de ingresos.\n"
        f"🌎 Extranjero: DPI o pasaporte, un gestor en Guatemala y copia de remesa "
        f"o comprobante de la forma de pago.\n\n"
        f"😊 ¿Estás en Guatemala o en el extranjero?"
    )


def pide_info_todos_proyectos(texto):
    """Detecta cuando el cliente pide información/comparación de los tres proyectos."""
    t = normalizar_texto_topografia(texto)
    referencias_tres = [
        "los 3", "las 3", "los tres", "las tres", "3 opciones", "tres opciones",
        "3 proyectos", "tres proyectos", "todos los proyectos", "todas las opciones"
    ]
    pide_info = any(x in t for x in [
        "info", "informacion", "precios", "precio", "financiamiento",
        "como funciona", "opciones", "terrenos", "lotes"
    ])
    return pide_info and any(x in t for x in referencias_tres)


def marcar_espera_proyecto_despues_tres(numero):
    estado = obtener_estado_conversacion(numero)
    estado["esperando_proyecto_despues_tres"] = True
    # Evita reutilizar por error un proyecto viejo mientras el cliente compara los 3.
    estado["proyecto_actual"] = None
    proyecto_activo.pop(numero, None)
    persistir_cliente(numero)


def limpiar_espera_proyecto_despues_tres(numero):
    estado = obtener_estado_conversacion(numero)
    estado["esperando_proyecto_despues_tres"] = False
    persistir_cliente(numero)


def esperando_proyecto_despues_tres(numero):
    return bool(obtener_estado_conversacion(numero).get("esperando_proyecto_despues_tres"))


def proyecto_elegido_despues_tres(texto):
    detectado = detectar_proyecto_en_texto(texto)
    if detectado:
        return detectado

    t = normalizar_texto_topografia(texto)
    # Atajos opcionales por orden del mensaje: 1 Buenaventura, 2 Palmeras, 3 Vista Hermosa.
    if t in {"1", "el 1", "primero", "la primera", "buenaventura"}:
        return "buenaventura"
    if t in {"2", "el 2", "segundo", "la segunda", "palmeras"}:
        return "palmeras"
    if t in {"3", "el 3", "tercero", "la tercera", "vista"}:
        return "vista_hermosa"
    return None


def enviar_ubicacion_breve(numero, proyecto):
    datos = UBICACIONES_PROYECTOS.get(proyecto)
    if not datos:
        return
    enviar_whatsapp(
        numero,
        f"📍 *Ubicación:* {datos['texto']}\n{datos['maps']}"
    )


def enviar_info_completa_proyecto(numero, proyecto, cierre=True):
    """
    Envía la información comercial completa de un proyecto usando el mismo material
    que el flujo normal: resumen, ubicación, cotizaciones, fotos/videos y amenidades.
    """
    if not proyecto:
        return

    # Recordar que el cliente ya recibió el paquete completo para no repetirlo
    # cuando más adelante vuelva a preguntar únicamente por precios.
    estado = obtener_estado_conversacion(numero)
    estado["info_completa_enviada"] = True
    estado["info_completa_proyecto"] = proyecto
    persistir_cliente(numero)

    resumen = construir_resumen_cotizacion(proyecto)
    if resumen:
        enviar_whatsapp(numero, resumen)

    enviar_ubicacion_breve(numero, proyecto)

    # Cotizaciones oficiales del proyecto.
    opciones = COTIZACIONES_IMAGEN.get(proyecto, {})
    for medida_nombre, rutas in opciones.items():
        for ruta in rutas:
            if not os.path.exists(ruta):
                continue
            caption = ETIQUETAS_COTIZACIONES.get(proyecto, {}).get(
                ruta, f"Cotización {medida_nombre} 💰"
            )
            enviar_imagen_whatsapp(numero, ruta, caption=caption)

    # Material real del proyecto + videos de amenidades.
    if proyecto == "vista_hermosa":
        enviar_solo_videos_del_proyecto(numero, proyecto)
    else:
        enviar_solo_fotos_del_proyecto(numero, proyecto)

    enviar_paquete_amenidades(numero, proyecto)

    if cierre:
        enviar_whatsapp(
            numero,
            "Si alguna opción te llama la atención, dime cuál 😊 y con gusto seguimos "
            "con disponibilidad, plano, cuota o visita. 🏡"
        )


def enviar_fotos_amenidades_comparacion(numero):
    """Envía solo fotos de amenidades como referencia al comparar los 3 proyectos."""
    rutas = [
        "media/amenidades/amenidades_1.jpg",
        "media/amenidades/amenidades_2.jpg",
        "media/amenidades/amenidades_4.jpg",
        "media/amenidades/amenidades_5.jpg",
    ]

    disponibles = []
    for ruta in rutas:
        if ruta not in disponibles and os.path.exists(ruta):
            disponibles.append(ruta)

    if not disponibles:
        return

    enviar_whatsapp(
        numero,
        "🏊🌳 *Amenidades*\n\n"
        "Nuestros proyectos cuentan con espacios pensados para disfrutar en familia, "
        "como casa club, piscinas, áreas verdes, juegos para niños y caminamientos. 😊\n\n"
        "Te comparto algunas imágenes de referencia 👇📸"
    )

    for i, ruta in enumerate(disponibles[:4], start=1):
        enviar_imagen_whatsapp(
            numero,
            ruta,
            caption="Amenidades de nuestros proyectos 🏡📸" if i == 1 else ""
        )


def enviar_info_todos_proyectos(numero):
    """
    Envía un resumen comparativo de los 3 proyectos + fotos de amenidades.
    Después espera que el cliente elija un proyecto y, desde ahí, continúa
    con el flujo completo normal de ese proyecto como proyecto raíz.
    """
    resumen = (
        "¡Claro! 😊 Te comparto un resumen de nuestras 3 opciones para que puedas compararlas:\n\n"
        "🏡 *Buenaventura Cuyotenango*\n"
        "📍 Km 168 de la carretera hacia la playa de Tulate, Cuyotenango.\n"
        "📌 https://maps.app.goo.gl/4wTj52Ez32rdigXk8\n"
        "• Para vivir o invertir: 8x16 Q83,200 | enganche Q6,000; 8x18 Q93,600 | enganche Q8,000\n"
        "• Para negocio: 8x16 comercial Q128,000 | enganche Q6,000\n"
        "• Financiamiento propio de 2 a 8 años + abonos a capital.\n"
        "• Amenidades: casa club, piscinas, áreas verdes, juegos para niños y caminamientos.\n"
        "• Servicios: calles pavimentadas, agua potable, energía eléctrica y drenajes con planta de tratamiento. El sector residencial contempla garita y muro; el área comercial no.\n\n"
        "🌴 *Palmeras San Miguel*\n"
        "📍 Zona 5 de Retalhuleu, camino a La Verde / carretera hacia Las Pilas.\n"
        "📌 https://maps.app.goo.gl/pBUyn98n8NCkGW8o6\n"
        "• 8x16 Fase 1 Q67,200 | enganche Q6,000\n"
        "• 8x16 Fase 2 Q70,400 | enganche Q6,000\n"
        "• Financiamiento propio de 2 a 8 años + plan de 1 año sin intereses.\n"
        "• Amenidades: casa club, piscinas, áreas verdes y caminamientos.\n"
        "• Servicios: calles pavimentadas, agua potable, energía eléctrica y drenajes con planta de tratamiento.\n\n"
        "🏘️ *Ciudad Vista Hermosa*\n"
        "📍 CA-2, km 188, Retalhuleu.\n"
        "• 8x16 Fase F Q83,200 | enganche Q6,000\n"
        "• 8x16 Fase G Q89,600 | enganche Q6,000\n"
        "• Reserva Q1,500 | enganche Q6,000.\n"
        "• Financiamiento propio de 2 a 8 años + plan de 1 año sin intereses.\n"
        "• Amenidades: piscina y áreas verdes.\n"
        "• Servicios: garita, muro perimetral, calles pavimentadas, agua potable, energía eléctrica y drenajes con planta de tratamiento.\n\n"
        "🏗️ En los 3 proyectos el diseño de construcción es libre: puedes construir vivienda, apartamentos o locales, siempre que sea una construcción formal con block."
    )
    enviar_whatsapp(numero, resumen)

    enviar_fotos_amenidades_comparacion(numero)

    enviar_whatsapp(
        numero,
        "Estas son algunas de las amenidades que podrás disfrutar 😊🏡\n\n"
        "Le informamos que *Palmeras San Miguel es una lotificación abierta, por lo que no cuenta con garita ni muro perimetral*. "
        "Buenaventura Cuyotenango y Vista Hermosa sí cuentan con estos servicios.\n\n"
        "¿Cuál de los 3 proyectos le interesa más para enviarle toda la información? 😊"
    )

    marcar_espera_proyecto_despues_tres(numero)


def respuesta_info_todos_proyectos():
    return (
        "¡Claro! 😊 Te puedo compartir un resumen comparativo de Buenaventura Cuyotenango, "
        "Palmeras San Miguel y Vista Hermosa con ubicación, precios, financiamiento, "
        "servicios y fotos de amenidades. 🏡"
    )

def seguimiento_compra_respuesta_directa(texto, proyecto):
    """
    Maneja preguntas típicas que suelen venir después de explicar el proceso.
    Devuelve None si no aplica.
    """
    t = normalizar_texto_topografia(texto)

    # Guatemala / extranjero
    if t in {"guatemala", "estoy en guatemala", "aqui en guatemala", "soy de guatemala"}:
        return (
            "Perfecto 😊🇬🇹 Necesitarías DPI, recibo de luz o agua y constancia de ingresos. "
            "¿Quieres que revisemos primero qué lote te interesa? 🏡"
        )

    if any(x in t for x in [
        "estados unidos", "usa", "eeuu", "extranjero", "afuera",
        "estoy en usa", "estoy en estados unidos"
    ]):
        return (
            "Claro 😊🇺🇸🇬🇹 Puedes comprar desde el extranjero. Necesitarías DPI o pasaporte, "
            "un gestor en Guatemala y comprobante de remesa o forma de pago. "
            "¿Quieres que te explique cómo iniciar?"
        )

    if "que es un gestor" in t or "qué es un gestor" in texto.lower():
        return (
            "Es una persona de confianza que tengas en Guatemala 😊. "
            "Puede ser un familiar o conocido que te apoye con las gestiones necesarias."
        )

    # Project-specific payment facts
    enganches = {
        "buenaventura": "Q6,000",
        "palmeras": "Q6,000",
        "vista_hermosa": "Q6,000",
    }
    financiamientos = {
        "buenaventura": "de 2 a 8 años",
        "palmeras": "de 2 a 8 años",
        "vista_hermosa": "de 2 a 8 años",
    }

    if any(x in t for x in [
        "cuanto tengo que dar", "cuanto doy para empezar",
        "cuanto es el enganche", "enganche"
    ]):
        e = enganches.get(proyecto)
        if e:
            return (
                f"El enganche en este proyecto es de *{e}* 💰😊. "
                "¿Quieres que te muestre las cuotas según el plazo que prefieras?"
            )

    if any(x in t for x in [
        "puedo dar el enganche en pagos", "enganche en pagos",
        "fraccionar el enganche", "pagar el enganche por partes"
    ]):
        if proyecto in {"buenaventura", "vista_hermosa"}:
            return (
                "Sí 😊 El enganche puede fraccionarse en 2 pagos mensuales. "
                "¿Quieres que te muestre cómo quedarían las cuotas?"
            )
        return (
            "Déjame revisar exactamente la condición del enganche para este proyecto "
            "y te la confirmo en un momento 😊."
        )

    if any(x in t for x in ["trabajan con banco", "con banco", "banco"]):
        f = financiamientos.get(proyecto)
        return (
            f"No necesitas banco 😊🏡 El financiamiento es propio de la empresa"
            + (f" y se maneja {f}." if f else ".")
        )

    if any(x in t for x in ["abono a capital", "abonar a capital", "puedo abonar"]):
        return "Sí 😊💰 Puedes realizar abonos a capital para reducir tu saldo pendiente."

    if any(x in t for x in [
        "cuando me dan las escrituras", "cuando entregan escrituras",
        "cuando dan escritura", "cuando me dan escritura"
    ]):
        return (
            "Las escrituras son registradas 📄✅ y se entregan aproximadamente "
            "3 meses después de haber cancelado el 100% del terreno."
        )

    if any(x in t for x in [
        "queda a mi nombre", "escritura a mi nombre", "a nombre de quien"
    ]):
        return "Sí 😊📄 La escritura del lote se realiza a nombre del comprador."

    if any(x in t for x in [
        "quiero comprar uno", "quiero uno", "me interesa comprar",
        "quiero apartarlo", "quiero reservar"
    ]):
        return (
            "Excelente 😊🏡 Primero revisemos cuál lote te interesa y confirmamos disponibilidad. "
            "¿Qué medida estás buscando?"
        )

    if any(x in t for x in [
        "lo voy a pensar", "lo pensare", "lo voy a revisar", "despues te digo"
    ]):
        return (
            "Claro 😊 Revísalo con calma. Si te surge alguna duda sobre el terreno, "
            "pagos o el proceso, con gusto te ayudo 🏡."
        )

    return None


def pregunta_horario_para_visita(texto):
    t = texto.lower().strip()

    frases = [
        "cuando me puede atender", "cuándo me puede atender",
        "a que hora me puede atender", "a qué hora me puede atender",
        "cuando me pueden atender", "cuándo me pueden atender",
        "a que hora me pueden atender", "a qué hora me pueden atender",
        "que horario tienen", "qué horario tienen",
        "en que horario me atiende", "en qué horario me atiende",
        "a que hora puedo llegar", "a qué hora puedo llegar",
        "a que hora puedo ir", "a qué hora puedo ir"
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
    t = normalizar_texto_topografia(texto)

    if re.search(r"\bmanana\b", t):
        return "Mañana"
    if re.search(r"\bhoy\b", t):
        return "Hoy"

    dias = [
        "lunes", "martes", "miércoles", "miercoles",
        "jueves", "viernes", "sábado", "sabado", "domingo"
    ]

    for dia in dias:
        if dia in t:
            return dia.capitalize()

    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})\b", t)
    if m:
        return m.group(0)

    return None


def extraer_hora_visita(texto):
    t = normalizar_texto_topografia(texto)

    # Formatos directos: 3pm, 3:30 pm, 15:30.
    patrones = [
        r"\b(\d{1,2}:\d{2})\s*(am|pm|a\.m\.|p\.m\.)?\b",
        r"\b(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)\b"
    ]
    for patron in patrones:
        m = re.search(patron, t)
        if m:
            return m.group(0)

    # Lenguaje natural: "a las 3", "3 de la tarde", "3 de la mañana".
    m = re.search(r"(?:a\s+las?\s+)?(\d{1,2})(?::(\d{2}))?\s*(?:de\s+la\s+)?(manana|tarde|noche)?", t)
    if m:
        hora = int(m.group(1))
        minutos = m.group(2) or "00"
        jornada = m.group(3) or ""
        if 1 <= hora <= 12:
            if jornada in {"tarde", "noche"} and hora != 12:
                return f"{hora}:{minutos} p. m."
            if jornada == "manana":
                return f"{hora}:{minutos} a. m."
            return f"{hora}:{minutos}"

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

    # Palmeras: visitas coordinadas, normalmente desde La Trinidad.
    if proyecto == "palmeras" and not estado.get("dia") and not estado.get("hora"):
        return (
            "Con gusto podemos coordinar una visita a Palmeras San Miguel 😊🏡. "
            "Podemos atenderle cualquier día entre 6:00 a. m. y 6:00 p. m.; normalmente "
            "nos reunimos en Centro Comercial La Trinidad para acompañarle al proyecto. "
            "Es importante avisarme antes de llegar, ya que no permanece personal esperando visitas. "
            "¿Qué día le quedaría bien? 📆"
        )

    # Vista Hermosa: la visita se coordina directamente en el residencial.
    # El enlace se entrega únicamente cuando ya existe día y hora confirmados.
    if proyecto == "vista_hermosa" and not estado.get("dia") and not estado.get("hora"):
        return (
            "Con gusto podemos coordinar una visita a *Vista Hermosa* 😊🏡. "
            "Normalmente nos reunimos directamente en el residencial sobre la CA-2 km 188. "
            "¿Qué día le quedaría bien visitarlo? 📆"
        )

    if pregunta_horario_para_visita(texto) and not hora:
        if estado.get("dia"):
            return "Podemos atenderle entre 6:00 a. m. y 6:00 p. m. 😊 ¿A qué hora le quedaría bien?"
        return "Podemos atenderle cualquier día entre 6:00 a. m. y 6:00 p. m. 😊 ¿Qué día le gustaría visitar?"

    if estado["dia"] and estado["hora"]:
        estado["cerrada"] = True
        persistir_cliente(numero)
        if proyecto == "palmeras":
            return (
                "Sí, perfecto 😊 Queda coordinada su visita a Palmeras San Miguel. "
                "Nos ponemos de acuerdo para encontrarnos en Centro Comercial La Trinidad y acompañarle al proyecto. "
                "¿Necesita que le indique algo más antes de la visita?"
            )
        if proyecto == "vista_hermosa":
            enlace = UBICACIONES_PROYECTOS.get("vista_hermosa", {}).get("maps", "")
            return (
                f"Perfecto 😊 Queda coordinada su visita a *Vista Hermosa* para *{estado['dia']} a las {estado['hora']}*.\n\n"
                "Nos reunimos directamente en el residencial. Le comparto el enlace para que pueda llegar sin problema 📍:\n"
                f"{enlace}\n\n"
                "¿Necesita que le indique algo más antes de llegar?"
            )
        return "Sí, perfecto 😊 Queda coordinado. ¿Necesita que le indique algo más antes de la visita?"

    if estado["dia"]:
        persistir_cliente(numero)
        return "Perfecto 😊 ¿A qué hora le quedaría bien?"

    if estado["hora"]:
        persistir_cliente(numero)
        return "Perfecto 😊 ¿Qué día le quedaría bien?"

    persistir_cliente(numero)
    return "Claro 😊 ¿Qué día le gustaría visitar?"



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
            f"Tu visita ya quedó coordinada para {nombre}, "
            f"el {dia} a las {hora} 🏡📍."
        )

    return "Tu visita ya quedó coordinada 🏡📍."


def pregunta_sobre_cita_existente(texto):
    t = texto.lower()

    frases = [
        "cuando es la visita", "cuándo es la visita",
        "que dia es la visita", "qué día es la visita",
        "a que hora es la visita", "a qué hora es la visita",
        "cuando quedamos", "cuándo quedamos",
        "que dia quedamos", "qué día quedamos",
        "hora de la visita", "dia de la visita", "día de la visita"
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
        "enganche", "cuanto es el enganche", "cuánto es el enganche",
        "de cuanto es el enganche", "de cuánto es el enganche",
        "cuanto tengo que dar de enganche", "cuánto tengo que dar de enganche",
        "se puede fraccionar el enganche", "puedo fraccionar el enganche",
        "enganche fraccionado", "fraccionar enganche", "pagar el enganche en dos",
        "pagar enganche en dos", "dos pagos de enganche", "2 pagos de enganche",
        "como se paga el enganche", "cómo se paga el enganche",
        "como funciona el enganche", "cómo funciona el enganche"
    ]

    return any(f in t for f in frases)


def respuesta_enganche(proyecto=None, texto=""):
    """Responde enganche; en Palmeras el fraccionamiento es únicamente reactivo."""
    nombres = {
        "palmeras": "Palmeras San Miguel",
        "vista_hermosa": "Vista Hermosa",
        "buenaventura": "Buenaventura Cuyotenango"
    }

    if proyecto == "palmeras":
        t = normalizar_texto_topografia(texto)
        pregunta_fraccionar = any(x in t for x in [
            "dividir", "fraccionar", "dos pagos", "2 pagos", "no tengo completo",
            "medio enganche", "pagar por partes", "puedo dar 3000", "puedo dar q3000"
        ])
        if pregunta_fraccionar:
            return (
                "Sí 😊 si lo necesita podemos facilitar el enganche de Q6,000 en dos pagos de Q3,000. "
                "Puede realizar Q3,000 el primer mes, completar los otros Q3,000 el segundo mes y "
                "comenzar su primera cuota en el tercer mes. Esta facilidad aplica en ambas fases."
            )
        return "En Palmeras San Miguel el enganche es de Q6,000 💰🏡."

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
    inicio = f"Sí 😊 En {nombre}" if nombre else "Sí 😊"
    enganche = obtener_enganche_exacto(proyecto, texto)

    if enganche:
        numero = int(enganche.replace("Q", "").replace(",", ""))
        pago = numero // 2
        return (
            f"{inicio} el enganche para esa medida es de {enganche} y tenemos la opción "
            "de fraccionarlo en 2 pagos mensuales. 💰\n\n"
            f"• Q{pago:,} en este mes de {mes_1}\n"
            f"• Q{pago:,} a finales de {mes_2}\n"
            f"• Su primera cuota sería hasta finales de {mes_3} ✅"
        )

    return (
        f"{inicio} tenemos enganches desde Q6,000 y la opción de fraccionarlos "
        "en 2 pagos mensuales. 💰"
    )



def pregunta_cantidad_lotes(texto):
    t = texto.lower().strip()

    frases = [
        "cuantos lotes", "cuántos lotes",
        "cantidad de lotes",
        "cuantos terrenos", "cuántos terrenos",
        "cuantos lotes tiene el proyecto", "cuántos lotes tiene el proyecto",
        "cuantos lotes hay", "cuántos lotes hay",
        "cuantos lotes tiene", "cuántos lotes tiene"
    ]

    return any(f in t for f in frases)


def respuesta_cantidad_lotes(proyecto):
    if proyecto == "buenaventura":
        return (
            "Buenaventura Cuyotenango cuenta con 2,600 lotes en total 🏡📍."
        )

    if proyecto == "palmeras":
        return (
            "Palmeras San Miguel cuenta con 1,700 lotes en la Fase 1 "
            "y 1,900 lotes en la Fase 2 🏡✨."
        )

    if proyecto == "vista_hermosa":
        return (
            "Vista Hermosa cuenta con 1,100 lotes en la Fase F "
            "y 1,000 lotes en la Fase G 🏡📍."
        )

    return "Claro 😊 ¿De cuál proyecto quieres saber la cantidad de lotes?"


def pregunta_clima_lugar(texto):
    t = texto.lower()

    frases = [
        "que clima", "qué clima",
        "como es el clima", "cómo es el clima",
        "hace calor", "es caluroso", "clima del lugar",
        "clima de la zona", "clima del proyecto",
        "que tal el clima", "qué tal el clima"
    ]

    return any(f in t for f in frases)


def respuesta_clima_lugar():
    return (
        "Sí 😊 Por acá tenemos el característico clima cálido de costa ☀️🌴. "
        "Y justamente por eso se disfrutan mucho las piscinas, áreas verdes "
        "y demás amenidades del proyecto. 🏊🌿"
    )


def pregunta_que_incluye_mantenimiento(texto):
    t = texto.lower()

    frases = [
        "que incluye el mantenimiento", "qué incluye el mantenimiento",
        "que cubre el mantenimiento", "qué cubre el mantenimiento",
        "para que sirve el mantenimiento", "para qué sirve el mantenimiento",
        "que trae el mantenimiento", "qué trae el mantenimiento",
        "que hacen con el mantenimiento", "qué hacen con el mantenimiento",
        "por que se paga el mantenimiento", "por qué se paga el mantenimiento",
        "porque se paga el mantenimiento", "porqué se paga el mantenimiento",
        "por que cobran mantenimiento", "por qué cobran mantenimiento",
        "porque cobran mantenimiento", "porqué cobran mantenimiento",
        "para que se paga el mantenimiento", "para qué se paga el mantenimiento",
        "en que se usa el mantenimiento", "en qué se usa el mantenimiento"
    ]

    return any(f in t for f in frases)



def respuesta_que_incluye_mantenimiento():
    return (
        "La cuota de mantenimiento se utiliza para mantener en buenas condiciones "
        "las áreas comunes de la residencial 😊🏡. Incluye:\n\n"
        "• Limpieza de áreas y calles.\n"
        "• Mantenimiento de la planta de tratamiento.\n"
        "• Mantenimiento de amenidades.\n"
        "• Jardinización de áreas verdes.\n"
        "• Limpieza de lotes que aún no estén circulados.\n\n"
        "Todo esto ayuda a conservar el proyecto limpio, ordenado y bien cuidado 🌿✨."
    )



def pregunta_titulo_agua(texto):
    """Detecta preguntas específicas sobre el título de agua."""
    t = texto.lower().strip()
    frases = [
        "titulo de agua", "título de agua",
        "que es el titulo de agua", "qué es el título de agua",
        "por que cobran titulo de agua", "por qué cobran título de agua",
        "porque cobran titulo de agua", "porqué cobran título de agua",
        "para que sirve el titulo de agua", "para qué sirve el título de agua",
        "cuanto cuesta el titulo de agua", "cuánto cuesta el título de agua",
        "precio del titulo de agua", "precio del título de agua",
        "el agua es propia", "pozo mecanico", "pozo mecánico"
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
        "El título de agua es un pago único 💧✅. "
        "La residencial cuenta con abastecimiento propio mediante pozo mecánico "
        "y tanques elevados, lo que permite tener disponibilidad de agua "
        "las 24 horas del día. Por eso se realiza este cobro una sola vez."
    )

    if monto:
        respuesta += f"\n\nEl valor del título de agua en este proyecto es de {monto}."

    return respuesta


def pide_gastos_adicionales(texto):
    """
    Detecta consultas de cualquier forma sobre costos/gastos extra.
    Esta intención tiene prioridad absoluta sobre la IA general.
    """
    t = texto.lower().strip()

    # Estas intenciones tienen handlers específicos y no deben caer en gastos generales.
    if pregunta_plazo_escritura(texto):
        return False

    if pregunta_titulo_agua(texto):
        return False

    if pregunta_que_incluye_mantenimiento(texto):
        return False

    frases = [
        "gastos adicionales", "gasto adicional",
        "costos adicionales", "costo adicional",
        "tiene algun costo adicional", "tiene algún costo adicional",
        "hay algun costo adicional", "hay algún costo adicional",
        "tiene costos adicionales", "hay costos adicionales",
        "tiene gastos adicionales", "hay gastos adicionales",
        "algun costo extra", "algún costo extra",
        "algún gasto extra", "algun gasto extra",
        "gastos extras", "gasto extra", "costos extras", "costo extra",
        "pagos extras", "pago extra", "pagos extra",
        "otros gastos", "otro gasto", "otros pagos", "otro pago",
        "pagos adicionales", "pago adicional",
        "pagos aparte", "pago aparte", "gastos aparte", "costos aparte",
        "aparte del lote", "aparte del precio", "aparte de eso",
        "que mas se paga", "qué más se paga",
        "que mas hay que pagar", "qué más hay que pagar",
        "hay que pagar algo mas", "hay que pagar algo más",
        "algo mas que pagar", "algo más que pagar",
        "que pagos hay que cancelar", "qué pagos hay que cancelar",
        "que pagos se cancelan", "qué pagos se cancelan",
        "pagos que hay que cancelar", "pagos por cancelar",
        "que otros pagos", "qué otros pagos",
        "mantenimiento", "cuota de mantenimiento",
        "agua", "cuota de agua",
        "titulo de agua", "título de agua",
        "escrituracion", "escrituración",
        "escritura", "gastos de escritura", "gasto de escritura",
        "cuanto cuesta escriturar", "cuánto cuesta escriturar",
        "precio de escrituracion", "precio de escrituración"
    ]

    if any(f in t for f in frases):
        return True

    # Regla flexible para formas naturales como:
    # "¿Qué pagos extras hay que cancelar en el residencial?"
    # Evita depender de una frase exacta.
    menciona_pago = any(p in t for p in [
        "pago", "pagos", "gasto", "gastos", "costo", "costos",
        "cancelar", "cancela", "pagar", "se paga"
    ])
    menciona_extra = any(p in t for p in [
        "extra", "extras", "adicional", "adicionales",
        "aparte", "otro", "otros", "ademas", "además"
    ])

    return menciona_pago and menciona_extra



def seguimiento_gastos_adicionales(numero, texto):
    """Detecta seguimientos naturales a una conversación sobre pagos extra."""
    if ultima_intencion.get(numero) != "gastos_adicionales":
        return False

    t = texto.lower().strip()

    frases = [
        "cuanto es de cada uno", "cuánto es de cada uno",
        "cuanto cuesta cada uno", "cuánto cuesta cada uno",
        "cuanto vale cada uno", "cuánto vale cada uno",
        "y cuanto es de cada uno", "y cuánto es de cada uno",
        "y cuanto cuesta", "y cuánto cuesta",
        "cuanto cuestan", "cuánto cuestan",
        "dame los montos", "cuales son los montos", "cuáles son los montos",
        "de cuanto es cada uno", "de cuánto es cada uno",
        "cuanto se paga", "cuánto se paga",
        "y de cuanto", "y de cuánto",
        "cuanto hay que pagar", "cuánto hay que pagar"
    ]

    return any(f in t for f in frases)


def respuesta_proyecto_pendiente_de_gastos(numero, texto):
    """
    Si primero preguntaron por pagos extra sin decir proyecto y después
    responden solamente con el nombre del proyecto, conserva la intención.
    """
    if ultima_intencion.get(numero) != "gastos_adicionales":
        return False

    detectado = detectar_proyecto_en_texto(texto)
    if not detectado:
        return False

    # Solo tratarlo como continuación si el mensaje es corto y principalmente
    # identifica el proyecto (ej. "Buenaventura cuyo").
    return len(texto.strip().split()) <= 6


def respuesta_gastos_adicionales(proyecto):
    if not proyecto:
        return "Claro 😊 ¿De cuál proyecto quieres conocer los gastos adicionales?"

    if proyecto == "palmeras":
        return (
            "Sí 😊 En Palmeras San Miguel los gastos adicionales son:\n\n"
            "• Escrituración: Q3,500\n"
            "• Título de agua: Q3,500\n"
            "• Mantenimiento: Q50 al mes\n"
            "• Agua: Q50 por 30,000 litros\n\n"
            "📌 El mantenimiento y la cuota de agua empiezan a pagarse "
            "cuando el proyecto ya esté urbanizado; antes de eso no se cobran."
        )

    if proyecto == "vista_hermosa":
        return (
            "Sí 😊 En Ciudad Vista Hermosa los gastos adicionales son:\n\n"
            "• Escrituración: Q3,500\n"
            "• Título de agua: Q3,500\n"
            "• Mantenimiento: Q50 al mes\n"
            "• Agua: Q50 por 30,000 litros\n\n"
            "📌 El mantenimiento y la cuota de agua empiezan a pagarse "
            "cuando el proyecto ya esté urbanizado; antes de eso no se cobran."
        )

    if proyecto == "buenaventura":
        return (
            "Sí 😊 En Buenaventura Cuyotenango los gastos adicionales son:\n\n"
            "• Escrituración:\n"
            "  - 1 lote: Q6,000\n"
            "  - 2 lotes: Q8,400\n"
            "  - 3 lotes: Q10,800\n"
            "  - Cada lote adicional suma Q2,400\n"
            "• Título de agua: Q4,000\n"
            "• Mantenimiento: Q100 al mes\n"
            "• Agua: Q100 por 30,000 litros al mes"
        )

    return "No tengo cargados los gastos adicionales de ese proyecto."


def pide_ubicacion(texto):
    t = texto.lower()

    palabras = [
        "ubicacion", "ubicación",
        "donde queda", "dónde queda",
        "como llego", "cómo llego",
        "direccion", "dirección",
        "mapa", "maps", "google maps",
        "mandame ubicacion", "mándame ubicación",
        "manda ubicacion", "manda ubicación"
    ]

    return any(p in t for p in palabras)


def pregunta_como_llegar_o_mejor_ruta(texto):
    t = texto.lower()

    frases = [
        "por donde me voy", "por dónde me voy",
        "por donde puedo ir", "por dónde puedo ir",
        "por donde puedo venir", "por dónde puedo venir",
        "por donde se puede venir", "por dónde se puede venir",
        "por donde llego", "por dónde llego",
        "como llego", "cómo llego",
        "como me voy", "cómo me voy",
        "que ruta", "qué ruta",
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
            "Autopista Xochi 🚗🛣️. Te comparto también el tarifario de la autopista "
            "para que tengas en cuenta el costo del recorrido 👇"
        )
    return None


def enviar_tarifario_xochi(numero):
    ruta = "media/general/tarifario_xochi.jpg"
    if os.path.exists(ruta):
        return enviar_imagen_whatsapp(
            numero,
            ruta,
            "Tarifario Autopista Xochi 🛣️🚗"
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
            "¡Claro! 📍 ¿De cuál proyecto necesitas la ubicación?"
        )
        return

    datos = UBICACIONES_PROYECTOS.get(proyecto)

    if not datos:
        enviar_whatsapp(
            numero,
            "No tengo cargada la ubicación de ese proyecto en este momento 📍."
        )
        return

    if cita_ya_cerrada(numero):
        enviar_whatsapp(
            numero,
            f"📍 {datos['nombre']} está ubicado en {datos['texto']}\n\n"
            f"Google Maps:\n{datos['maps']}\n\n"
            "Tu visita ya está coordinada 🙌🏡."
        )
        return

    enviar_whatsapp(
        numero,
        f"¡Claro! 📍 {datos['nombre']} está ubicado en {datos['texto']}\n\n"
        f"Google Maps:\n{datos['maps']}\n\n"
        "Si deseas ir a conocer los lotes, avísame antes 🙌 "
        "así coordinamos tu visita y podemos atenderte cuando llegues. "
        "¿Qué día tienes pensado ir? 📆"
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
        "foto", "fotos", "imagen", "imagenes", "imágenes",
        "muestrame fotos", "muéstrame fotos",
        "enseñame fotos", "enséñame fotos",
        "como se ve", "cómo se ve"
    ]

    return any(p in t for p in palabras)


def pide_videos(texto):
    t = texto.lower()

    palabras = [
        "video", "videos", "vídeo", "vídeos",
        "recorrido", "tienes video", "tienes videos",
        "muestrame video", "muéstrame video"
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
# Esta primera versión vive en RAM junto con el bot.
# Permite ver chats nuevos, pausar IA y responder manualmente.
crm_mensajes = {}
crm_modo_manual = set()
crm_ultima_actividad = {}
crm_evento_contador = 0
lock_crm = Lock()


def crm_es_facebook(contacto):
    """True cuando el identificador interno pertenece a Messenger."""
    return str(contacto or "").startswith(MESSENGER_CONTACT_PREFIX)


def crm_psid_facebook(contacto):
    """Extrae el PSID real de Messenger desde la llave interna fb:<psid>."""
    contacto = str(contacto or "")
    if not crm_es_facebook(contacto):
        return ""
    return contacto[len(MESSENGER_CONTACT_PREFIX):].strip()


def crm_canal_contacto(contacto):
    return "facebook" if crm_es_facebook(contacto) else "whatsapp"


def crm_identificador_visible(contacto):
    """Texto corto para mostrar el origen del lead sin confundir PSID con teléfono."""
    contacto = str(contacto or "")
    if crm_es_facebook(contacto):
        psid = crm_psid_facebook(contacto)
        corto = psid[-8:] if len(psid) > 8 else psid
        return f"Facebook · {corto or 'cliente'}"
    return f"+{contacto}" if contacto else ""


def crm_nombre_manual(contacto):
    """Nombre/etiqueta que Gabriel escribe manualmente desde el CRM."""
    contacto = str(contacto or "").strip()
    if not contacto:
        return ""
    try:
        estado = obtener_estado_conversacion(contacto)
        return str(estado.get("crm_nombre_manual") or "").strip()
    except Exception:
        return ""


def crm_etiqueta_cliente(contacto):
    return crm_nombre_manual(contacto) or crm_identificador_visible(contacto)


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
    estado.setdefault("esperando_cantidad_descuento_contado", False)
    estado.setdefault("esperando_disponibilidad_desde_cta", False)
    estado.setdefault("esperando_proyecto_despues_tres", False)
    estado.setdefault("info_completa_enviada", False)
    estado.setdefault("info_completa_proyecto", None)
    estado.setdefault("esperando_uso_lote_cta", False)
    estado.setdefault("esperando_medida_lotes_cta", False)
    estado.setdefault("uso_lote_cta", None)
    estado.setdefault("esperando_tipo_dia_visita_cta", False)
    estado.setdefault("esperando_dia_visita_cta", False)
    estado.setdefault("esperando_jornada_visita_cta", False)
    estado.setdefault("esperando_hora_visita_cta", False)
    estado.setdefault("tipo_dia_visita_cta", None)
    estado.setdefault("jornada_visita_cta", None)
    estado.setdefault("psm_etapa", None)
    estado.setdefault("psm_fase", None)
    estado.setdefault("psm_plan", None)
    estado.setdefault("psm_plazo", None)
    estado.setdefault("psm_cotizacion_enviada", False)
    estado.setdefault("psm_video_amenidades_enviado", False)
    estado.setdefault("psm_pregunta_pendiente", None)
    estado.setdefault("psm_visita_ofrecida", False)
    estado.setdefault("psm_recordatorio_token", None)
    estado.setdefault("vh_etapa", None)
    estado.setdefault("vh_fase", None)
    estado.setdefault("vh_plan", None)
    estado.setdefault("vh_plazo", None)
    estado.setdefault("vh_cotizacion_enviada", False)
    estado.setdefault("vh_video_amenidades_enviado", False)
    estado.setdefault("vh_pregunta_pendiente", None)
    estado.setdefault("vh_visita_ofrecida", False)
    estado.setdefault("requiere_intervencion_ia", False)
    estado.setdefault("esperando_respuesta_gabriel", False)
    estado.setdefault("intervencion_pregunta", None)
    estado.setdefault("crm_nombre_manual", "")
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
            "esperando_cantidad_descuento_contado": False,
            "esperando_disponibilidad_desde_cta": False,
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
# La RAM se mantiene como caché, pero PostgreSQL es la fuente persistente.
crm_push_subscriptions = {}
lock_push = Lock()
ultimo_error_push = None
ultimo_resultado_push = None
_push_db_initialized = False
lock_push_db = Lock()


def push_db_disponible():
    return bool(DATABASE_URL and psycopg2)


def inicializar_push_db():
    """Crea la tabla de suscripciones si todavía no existe."""
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

    # Caché RAM
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
    Si hay PostgreSQL, siempre lee desde ahí para sobrevivir reinicios.
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

    # Si DB está temporalmente caída, usamos la caché RAM.
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
        ultimo_error_push = "pywebpush no está disponible en el servidor."
        return {"ok": False, "error": ultimo_error_push, "enviadas": 0}

    if not VAPID_PRIVATE_KEY:
        ultimo_error_push = "VAPID_PRIVATE_KEY no está configurada."
        return {"ok": False, "error": ultimo_error_push, "enviadas": 0}

    private_key_compatible = preparar_vapid_private_key()

    proyecto = crm_nombre_proyecto(numero)
    proyecto_txt = f" · {proyecto}" if proyecto and proyecto != "Sin proyecto" else ""

    push_id = str(event_id or time.time_ns())

    payload = json.dumps({
        "title": "🏡 Nuevo mensaje de cliente",
        "body": f"+{numero}{proyecto_txt}\n{str(contenido)[:180]}",
        "url": f"/crm?numero={numero}",
        # Cada mensaje de WhatsApp usa su propio tag.
        # Así Android/Chrome no sustituye una notificación por otra.
        "tag": f"crm-{push_id}",
        "message_id": push_id,
        "timestamp": int(time.time() * 1000)
    }, ensure_ascii=False)

    # Leer suscripciones persistentes en CADA envío.
    # Así un webhook que despierta a Render puede notificar aunque
    # el CRM no haya sido abierto después del reinicio.
    subs = list(cargar_push_subscriptions().items())

    if not subs:
        ultimo_error_push = "No hay teléfonos suscritos actualmente."
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
        ultimo_resultado_push = f"{enviadas} notificación(es) enviada(s)."
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
    Envía UNA notificación ntfy por CADA mensaje entrante de WhatsApp.
    No depende de que Chrome, el CRM o una pestaña estén abiertos.
    """
    if not NTFY_TOPIC:
        print("NTFY: NTFY_TOPIC no está configurado.")
        return False

    numero_txt = str(numero or "Cliente")
    contenido_txt = str(contenido or "Nuevo mensaje").strip()

    proyecto = crm_nombre_proyecto(numero)
    proyecto_txt = (
        f" · {proyecto}"
        if proyecto and proyecto != "Sin proyecto"
        else ""
    )

    # Abrir directamente la conversación del cliente en el CRM.
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
                # Identificador únicamente para diagnóstico.
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


def crm_registrar_mensaje(numero, direccion, contenido, event_id=None, media_url=None, media_tipo=None):
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
            "hora": crm_hora_actual(),
            "event_id": event_id,
            "media_url": media_url,
            "media_tipo": media_tipo,
            "canal": crm_canal_contacto(numero)
        })

        # Mantener suficiente historial visual sin consumir RAM sin límite.
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

        # NTFY: notificación nativa en Android por CADA mensaje.
        Thread(
            target=enviar_ntfy_crm,
            args=(numero, contenido, event_id),
            daemon=True
        ).start()



def crm_actualizar_contenido_por_evento(numero, event_id, contenido):
    """Actualiza el texto visible de un mensaje ya registrado (ej. transcripción de audio)."""
    if not numero or not event_id:
        return False
    contenido = str(contenido or "").strip()
    if not contenido:
        return False

    actualizado = False
    with lock_crm:
        lista = crm_mensajes.get(numero, [])
        for item in reversed(lista):
            if str(item.get("event_id") or "") == str(event_id):
                item["contenido"] = contenido
                actualizado = True
                break

    if actualizado:
        persistir_cliente(numero)
    return actualizado


# ============================================================
# FACEBOOK MESSENGER - MISMO MOTOR COMERCIAL DE WHATSAPP
# ============================================================

def _messenger_base_publica():
    """Devuelve la URL base pública del servicio Render, sin /crm."""
    if MESSENGER_PUBLIC_BASE_URL:
        return MESSENGER_PUBLIC_BASE_URL
    base = str(CRM_PUBLIC_URL or "").rstrip("/")
    if base.endswith("/crm"):
        base = base[:-4]
    return base.rstrip("/")


def _dividir_texto_messenger(texto, limite=1900):
    """Messenger limita el tamaño de texto; conserva el mismo contenido dividiéndolo."""
    texto = str(texto or "").strip()
    if not texto:
        return []
    if len(texto) <= limite:
        return [texto]
    partes = []
    restante = texto
    while len(restante) > limite:
        corte = restante.rfind("\n", 0, limite)
        if corte < limite // 2:
            corte = restante.rfind(" ", 0, limite)
        if corte < limite // 2:
            corte = limite
        partes.append(restante[:corte].strip())
        restante = restante[corte:].strip()
    if restante:
        partes.append(restante)
    return [p for p in partes if p]


def enviar_messenger_texto(contacto, texto, formalizar=True):
    """
    Envía texto por Messenger usando el Page Access Token.
    Se utiliza tanto para respuestas manuales como para TODO el flujo automático
    que originalmente envía por WhatsApp.
    """
    if formalizar:
        texto = formalizar_trato_usted(texto)
    psid = crm_psid_facebook(contacto)
    partes = _dividir_texto_messenger(texto)

    if not psid or not partes:
        return False

    if not MESSENGER_PAGE_ACCESS_TOKEN:
        print("MESSENGER: falta MESSENGER_PAGE_ACCESS_TOKEN en Render.")
        return False

    url = "https://graph.facebook.com/v26.0/me/messages"
    todo_ok = True

    for parte in partes:
        payload = {
            "recipient": {"id": psid},
            "messaging_type": "RESPONSE",
            "message": {"text": parte}
        }
        try:
            respuesta = requests.post(
                url,
                params={"access_token": MESSENGER_PAGE_ACCESS_TOKEN},
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=20
            )
            print("\n==============================")
            print("RESPUESTA DE MESSENGER")
            print("==============================")
            print("META STATUS:", respuesta.status_code)
            print("META RESPONSE:", respuesta.text[:1200])

            if 200 <= respuesta.status_code < 300:
                crm_registrar_mensaje(contacto, "out", parte)
            else:
                todo_ok = False
        except Exception as exc:
            print("ERROR ENVIANDO MESSENGER:", exc)
            todo_ok = False

    return todo_ok


def enviar_messenger_adjunto_url(contacto, tipo, url_archivo, caption=""):
    """Envía image, video o file por Messenger desde una URL pública."""
    psid = crm_psid_facebook(contacto)
    url_archivo = str(url_archivo or "").strip()
    tipo = str(tipo or "file").lower()
    if tipo not in {"image", "video", "audio", "file"}:
        tipo = "file"

    if not psid or not url_archivo or not MESSENGER_PAGE_ACCESS_TOKEN:
        return False

    # Messenger no usa caption embebido como WhatsApp; enviamos el mismo texto antes.
    if caption:
        enviar_messenger_texto(contacto, caption)

    payload = {
        "recipient": {"id": psid},
        "messaging_type": "RESPONSE",
        "message": {
            "attachment": {
                "type": tipo,
                "payload": {
                    "url": url_archivo,
                    "is_reusable": True
                }
            }
        }
    }

    try:
        respuesta = requests.post(
            "https://graph.facebook.com/v26.0/me/messages",
            params={"access_token": MESSENGER_PAGE_ACCESS_TOKEN},
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=60
        )
        print("MESSENGER ADJUNTO STATUS:", respuesta.status_code)
        print("MESSENGER ADJUNTO RESPONSE:", respuesta.text[:1200])
        if 200 <= respuesta.status_code < 300:
            etiqueta = {
                "image": "🖼️ Imagen enviada",
                "video": "🎥 Video enviado",
                "audio": "🎙️ Audio enviado",
                "file": "📄 Archivo enviado",
            }.get(tipo, "📎 Archivo enviado")
            media_tipo = "document" if tipo == "file" else tipo
            crm_registrar_mensaje(
                contacto,
                "out",
                etiqueta,
                media_url=url_archivo,
                media_tipo=media_tipo if media_tipo in {"image", "video", "audio", "document"} else None
            )
            return True
        return False
    except Exception as exc:
        print("ERROR ENVIANDO ADJUNTO MESSENGER:", exc)
        return False


def url_publica_media_messenger(ruta_local):
    """Convierte media/... local en una URL pública temporalmente servida por Flask."""
    try:
        raiz = os.path.abspath("media")
        ruta_abs = os.path.abspath(str(ruta_local or ""))
        if not ruta_abs or os.path.commonpath([raiz, ruta_abs]) != raiz:
            return ""
        relativo = os.path.relpath(ruta_abs, raiz).replace(os.sep, "/")
        base = _messenger_base_publica()
        if not base:
            return ""
        return f"{base}/messenger-media/{quote(relativo, safe='/')}"
    except Exception as exc:
        print("MESSENGER URL MEDIA ERROR:", exc)
        return ""


@app.route("/messenger-media/<path:archivo>", methods=["GET"])
def messenger_media_publica(archivo):
    """Sirve únicamente archivos dentro de media/ para que Meta pueda descargarlos."""
    return send_from_directory(
        os.path.abspath("media"),
        archivo,
        as_attachment=False,
        max_age=3600
    )

def crm_resumen_entrante_facebook(evento):
    """Convierte un evento de Messenger en texto legible para el CRM."""
    evento = evento or {}
    mensaje = evento.get("message") or {}

    texto = str(mensaje.get("text") or "").strip()
    if texto:
        return texto

    attachments = mensaje.get("attachments") or []
    if attachments:
        tipos = []
        for item in attachments:
            tipo = str((item or {}).get("type") or "").lower()
            if tipo == "image":
                tipos.append("📷 Imagen recibida por Facebook")
            elif tipo == "video":
                tipos.append("🎥 Video recibido por Facebook")
            elif tipo == "audio":
                tipos.append("🎙️ Audio recibido por Facebook")
            elif tipo == "file":
                tipos.append("📄 Archivo recibido por Facebook")
            else:
                tipos.append("📎 Adjunto recibido por Facebook")
        return " · ".join(tipos)

    postback = evento.get("postback") or {}
    if postback:
        titulo = str(postback.get("title") or "").strip()
        payload = str(postback.get("payload") or "").strip()
        return titulo or payload or "🔘 Opción seleccionada en Facebook"

    referral = evento.get("referral") or {}
    if referral:
        return "📣 Cliente llegó desde un anuncio o enlace de Facebook"

    return "📩 Mensaje recibido por Facebook"


def guardar_media_facebook_crm(contacto, evento):
    """
    Descarga el primer adjunto visual/archivo de Messenger y lo conserva en PostgreSQL,
    para que no dependa de la URL temporal que entrega Meta.
    """
    mensaje = (evento or {}).get("message") or {}
    attachments = mensaje.get("attachments") or []
    if not attachments:
        return None, None

    adjunto = attachments[0] or {}
    tipo_meta = str(adjunto.get("type") or "").lower()
    url_media = str(((adjunto.get("payload") or {}).get("url")) or "").strip()

    if not url_media or tipo_meta not in {"image", "video", "audio", "file"}:
        return None, None

    try:
        r = requests.get(url_media, timeout=45)
        if not (200 <= r.status_code < 300) or not r.content:
            print("MESSENGER MEDIA DOWNLOAD:", r.status_code)
            return None, None

        mime = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if not mime:
            if tipo_meta == "image":
                mime = "image/jpeg"
            elif tipo_meta == "video":
                mime = "video/mp4"
            elif tipo_meta == "audio":
                mime = "audio/mpeg"
            else:
                mime = "application/octet-stream"

        media_tipo = None
        if mime.startswith("image/"):
            media_tipo = "image"
        elif mime.startswith("video/"):
            media_tipo = "video"
        elif mime.startswith("audio/"):
            media_tipo = "audio"
        elif mime == "application/pdf":
            media_tipo = "document"

        if not media_tipo:
            return None, None

        media_url = guardar_media_crm_bytes(contacto, r.content, mime)
        return media_url, media_tipo if media_url else None

    except Exception as exc:
        print("MESSENGER MEDIA CRM ERROR:", exc)
        return None, None



def procesar_adjunto_facebook_en_segundo_plano(contacto, evento, event_id):
    """Hace que Messenger también pueda comprender fotos, videos y notas de voz."""
    try:
        if crm_esta_manual(contacto):
            print("MESSENGER MEDIA: conversación en MANUAL; IA pausada.")
            return

        mensaje = (evento or {}).get("message") or {}
        adjuntos = mensaje.get("attachments") or []
        if not adjuntos:
            return

        adjunto = adjuntos[0] or {}
        tipo = str(adjunto.get("type") or "").lower()
        url_media = str(((adjunto.get("payload") or {}).get("url")) or "").strip()
        if not url_media:
            return

        try:
            r = requests.get(url_media, timeout=60)
        except Exception as exc:
            print("MESSENGER MEDIA IA DOWNLOAD ERROR:", exc)
            return

        if not (200 <= r.status_code < 300) or not r.content:
            print("MESSENGER MEDIA IA DOWNLOAD:", r.status_code)
            return

        mime = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if not mime:
            mime = {
                "image": "image/jpeg",
                "video": "video/mp4",
                "audio": "audio/mpeg",
            }.get(tipo, "application/octet-stream")

        # Igual que WhatsApp, se presenta solo si corresponde.
        enviar_presentacion_si_corresponde(contacto, event_id)

        if tipo == "image":
            respuesta = analizar_imagen_cliente(
                contacto,
                r.content,
                mime_type=mime or "image/jpeg",
                caption=""
            )
            if respuesta:
                enviar_whatsapp(contacto, respuesta)
            return

        if tipo == "video":
            respuesta = analizar_video_cliente(contacto, r.content, caption="")
            if respuesta:
                enviar_whatsapp(contacto, respuesta)
            return

        if tipo == "audio":
            texto = transcribir_audio_cliente(r.content, mime_type=mime or "audio/mpeg")
            if not texto:
                enviar_whatsapp(
                    contacto,
                    "Recibí su audio 🎙️😊, pero no pude transcribirlo en este momento. "
                    "Puede intentar enviarlo nuevamente."
                )
                return

            crm_actualizar_contenido_por_evento(
                contacto,
                event_id,
                f"🎙️ Audio recibido por Facebook\n📝 {texto}"
            )

            # Reinyectamos la transcripción al MISMO motor comercial que usa WhatsApp.
            audio_id = f"{event_id}:transcripcion"
            iniciar_procesamiento(contacto, audio_id)
            payload = {
                "object": "whatsapp_business_account",
                "entry": [{
                    "changes": [{
                        "value": {
                            "messages": [{
                                "from": contacto,
                                "id": audio_id,
                                "type": "text",
                                "text": {"body": texto}
                            }]
                        }
                    }]
                }]
            }
            procesar_mensaje_en_segundo_plano(payload, audio_id)
            return

        if tipo == "file":
            enviar_whatsapp(
                contacto,
                "Recibí el documento 📄😊. Si desea que revise algo específico, "
                "puede enviarme una captura de la parte que quiere consultar."
            )

    except Exception as exc:
        print("ERROR PROCESANDO MEDIA MESSENGER:", exc)


@app.route("/webhook-facebook", methods=["GET"])
def verificar_webhook_facebook():
    """Verificación independiente del webhook de WhatsApp."""
    modo = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge", "")

    if modo == "subscribe" and MESSENGER_VERIFY_TOKEN and token == MESSENGER_VERIFY_TOKEN:
        print("MESSENGER: webhook verificado correctamente")
        return challenge, 200

    print("MESSENGER: verificación rechazada")
    return "Token incorrecto", 403


@app.route("/webhook-facebook", methods=["POST"])
def recibir_webhook_facebook():
    """
    Recibe Messenger y, cuando la conversación está en IA, reutiliza EXACTAMENTE
    el mismo procesador comercial de WhatsApp: proyecto activo, precios, cuotas,
    ubicación, planos, cotizaciones, multimedia, visitas y respuesta OpenAI.
    """
    datos = request.get_json(silent=True) or {}

    if datos.get("object") != "page":
        return "EVENT_RECEIVED", 200

    try:
        for entry in datos.get("entry") or []:
            for evento in entry.get("messaging") or []:
                if not any(k in evento for k in ("message", "postback", "referral")):
                    continue

                mensaje_fb = evento.get("message") or {}
                if mensaje_fb.get("is_echo"):
                    continue

                sender_id = str(((evento.get("sender") or {}).get("id")) or "").strip()
                if not sender_id:
                    continue

                contacto = f"{MESSENGER_CONTACT_PREFIX}{sender_id}"
                mid = str(mensaje_fb.get("mid") or "").strip()
                if not mid:
                    postback = evento.get("postback") or {}
                    mid = str(postback.get("mid") or "").strip()

                dedupe_id = f"facebook:{mid}" if mid else f"facebook:{sender_id}:{evento.get('timestamp')}"
                if dedupe_id and not marcar_mensaje_como_procesado(dedupe_id):
                    print("MESSENGER DUPLICADO IGNORADO:", dedupe_id)
                    continue

                contenido = crm_resumen_entrante_facebook(evento)
                media_url_crm, media_tipo_crm = guardar_media_facebook_crm(contacto, evento)

                # Messenger puede adjuntar el origen del anuncio directamente en
                # evento.referral o dentro de postback.referral. Lo guardamos ANTES
                # de registrar el mensaje en CRM, incluso si el chat está en MANUAL.
                referral_fb = (evento.get("referral") or (evento.get("postback") or {}).get("referral") or {})
                fijar_proyecto_desde_anuncio(contacto, {"referral": referral_fb})

                # 1) Siempre entra al mismo CRM, esté en MANUAL o IA.
                crm_registrar_mensaje(
                    contacto,
                    "in",
                    contenido,
                    event_id=dedupe_id,
                    media_url=media_url_crm,
                    media_tipo=media_tipo_crm
                )

                # 2) Igual que WhatsApp: cancelar cualquier seguimiento pendiente.
                # Los textos se agrupan abajo; NO invalidamos una tanda que ya
                # esté siendo respondida.
                cancelar_seguimiento(contacto)

                # 3) Texto/postback/referral entra al MISMO motor de WhatsApp.
                texto_real = str(mensaje_fb.get("text") or "").strip()
                if not texto_real:
                    postback = evento.get("postback") or {}
                    texto_real = str(postback.get("title") or postback.get("payload") or "").strip()
                if not texto_real and evento.get("referral"):
                    texto_real = contenido

                if texto_real:
                    # referral_fb ya se extrajo y guardó antes de registrar el mensaje
                    # en CRM, para que el proyecto sea visible de inmediato.
                    mensaje_equivalente = {
                        "from": contacto,
                        "id": dedupe_id,
                        "type": "text",
                        "text": {"body": texto_real},
                        "referral": referral_fb
                    }

                    acumular_mensaje_texto(
                        contacto,
                        dedupe_id,
                        mensaje_equivalente
                    )

                    # El agrupador inicia y administra el único worker de texto
                    # para este contacto. Si llegan más mensajes mientras el bot
                    # responde, quedarán como una segunda tanda.
                else:
                    # Los adjuntos quedan visibles en CRM y, si la conversación está en IA,
                    # también se analizan: fotos/videos con visión y audios con transcripción.
                    Thread(
                        target=procesar_adjunto_facebook_en_segundo_plano,
                        args=(contacto, evento, dedupe_id),
                        daemon=True
                    ).start()
                    print("MESSENGER ADJUNTO EN CRM + IA:", contacto, contenido[:120])

                print("MESSENGER EN CRM:", contacto, contenido[:120])

        return "EVENT_RECEIVED", 200

    except Exception as exc:
        print("ERROR WEBHOOK MESSENGER:", exc)
        return "EVENT_RECEIVED", 200


_media_db_initialized = False
lock_media_db = Lock()


def inicializar_media_db():
    """Crea almacenamiento persistente para fotos recibidas por WhatsApp."""
    global _media_db_initialized
    if not DATABASE_URL or not psycopg2:
        return False
    if _media_db_initialized:
        return True
    with lock_media_db:
        if _media_db_initialized:
            return True
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS crm_media (
                            media_key TEXT PRIMARY KEY,
                            numero TEXT NOT NULL,
                            mime_type TEXT NOT NULL,
                            contenido BYTEA NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                    """)
                conn.commit()
                _media_db_initialized = True
                print("MEDIA DB: tabla lista")
                return True
            finally:
                conn.close()
        except Exception as exc:
            print("MEDIA DB INIT ERROR:", exc)
            return False


def guardar_media_whatsapp_crm(numero, mensaje):
    """
    Conserva en PostgreSQL imágenes, audios, videos y documentos recibidos
    por WhatsApp para poder abrirlos/reproducirlos después desde el CRM.
    """
    mensaje = mensaje or {}
    tipo = str(mensaje.get("type") or "").lower()
    if tipo not in {"image", "audio", "video", "document"}:
        return None, None

    media = mensaje.get(tipo) or {}
    media_id = str(media.get("id") or "").strip()
    if not media_id or not inicializar_media_db():
        return None, None

    archivo, mime = obtener_media_whatsapp(media_id)
    if not archivo:
        return None, None

    mime_defaults = {
        "image": "image/jpeg",
        "audio": "audio/ogg",
        "video": "video/mp4",
        "document": "application/octet-stream",
    }
    mime = mime or mime_defaults.get(tipo, "application/octet-stream")

    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO crm_media (media_key, numero, mime_type, contenido, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (media_key) DO NOTHING
                """, (media_id, str(numero), mime, psycopg2.Binary(archivo)))
            conn.commit()
        finally:
            conn.close()
        return f"/crm/media/{media_id}", tipo
    except Exception as exc:
        print("MEDIA DB SAVE ERROR:", exc)
        return None, None


def guardar_imagen_crm(numero, mensaje):
    """Compatibilidad con código anterior: conserva una imagen y devuelve solo su URL."""
    media_url, media_tipo = guardar_media_whatsapp_crm(numero, mensaje)
    return media_url if media_tipo == "image" else None


@app.route("/crm/media/<media_key>", methods=["GET"])
def crm_media(media_key):
    """Sirve una foto únicamente a usuarios autenticados del CRM."""
    if not crm_autorizado():
        return crm_pedir_login()
    if not inicializar_media_db():
        return Response("Imagen no disponible", status=404)
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT mime_type, contenido FROM crm_media WHERE media_key = %s",
                    (str(media_key),)
                )
                fila = cur.fetchone()
        finally:
            conn.close()
        if not fila:
            return Response("Imagen no encontrada", status=404)
        mime, contenido = fila
        return Response(bytes(contenido), content_type=mime or "image/jpeg", headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff"
        })
    except Exception as exc:
        print("MEDIA CRM READ ERROR:", exc)
        return Response("No se pudo abrir la imagen", status=500)

def crm_resumen_entrante(mensaje):
    tipo = mensaje.get("type")

    if tipo == "text":
        return mensaje.get("text", {}).get("body", "")

    if tipo == "audio":
        return "🎙️ Audio recibido"

    if tipo == "image":
        caption = mensaje.get("image", {}).get("caption", "")
        return "📷 Imagen recibida" + (f": {caption}" if caption else "")

    if tipo == "video":
        caption = mensaje.get("video", {}).get("caption", "")
        return "🎥 Video recibido" + (f": {caption}" if caption else "")

    if tipo == "document":
        nombre = mensaje.get("document", {}).get("filename", "")
        return "📄 Documento recibido" + (f": {nombre}" if nombre else "")

    return f"📩 Mensaje recibido ({tipo or 'desconocido'})"


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
            "CRM_PASSWORD no está configurado en Render.",
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


# ============================================================
# CRM - EMBUDO DE VENTAS Y PROXIMA ACCION
# ============================================================
# Esta metadata es independiente de la memoria conversacional del bot.
# Se guarda en PostgreSQL para sobrevivir reinicios y deploys de Render.
CRM_ETAPAS = [
    "Nuevo lead",
    "Información enviada",
    "Interesado",
    "Cotización enviada",
    "Visita pendiente",
    "Visita realizada",
    "Reserva",
    "Venta",
    "Perdido",
]

crm_lead_meta = {}
_crm_lead_meta_cargada = False
_crm_lead_meta_db_inicializada = False
lock_crm_lead_meta = Lock()


def inicializar_crm_lead_meta_db():
    global _crm_lead_meta_db_inicializada
    if not DATABASE_URL or not psycopg2:
        return False
    if _crm_lead_meta_db_inicializada:
        return True

    with lock_crm_lead_meta:
        if _crm_lead_meta_db_inicializada:
            return True
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS crm_lead_meta (
                            numero TEXT PRIMARY KEY,
                            etapa TEXT NOT NULL DEFAULT 'Nuevo lead',
                            proxima_accion TEXT NOT NULL DEFAULT '',
                            proxima_accion_fecha TEXT NOT NULL DEFAULT '',
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                    """)
                conn.commit()
                _crm_lead_meta_db_inicializada = True
                print("CRM LEADS DB: tabla lista")
                return True
            finally:
                conn.close()
        except Exception as exc:
            print("CRM LEADS DB INIT ERROR:", exc)
            return False


def cargar_crm_lead_meta():
    global _crm_lead_meta_cargada
    if _crm_lead_meta_cargada:
        return
    if not inicializar_crm_lead_meta_db():
        _crm_lead_meta_cargada = True
        return

    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT numero, etapa, proxima_accion, proxima_accion_fecha
                    FROM crm_lead_meta
                """)
                filas = cur.fetchall()
        finally:
            conn.close()

        with lock_crm_lead_meta:
            for numero, etapa, accion, fecha in filas:
                crm_lead_meta[str(numero)] = {
                    "etapa": etapa if etapa in CRM_ETAPAS else "Nuevo lead",
                    "proxima_accion": accion or "",
                    "proxima_accion_fecha": fecha or "",
                }
            _crm_lead_meta_cargada = True
    except Exception as exc:
        print("CRM LEADS DB LOAD ERROR:", exc)
        _crm_lead_meta_cargada = True


def crm_obtener_meta(numero):
    numero = str(numero or "").strip()
    cargar_crm_lead_meta()
    if not numero:
        return {
            "etapa": "Nuevo lead",
            "proxima_accion": "",
            "proxima_accion_fecha": "",
        }
    with lock_crm_lead_meta:
        meta = crm_lead_meta.get(numero) or {}
        return {
            "etapa": meta.get("etapa") if meta.get("etapa") in CRM_ETAPAS else "Nuevo lead",
            "proxima_accion": str(meta.get("proxima_accion") or ""),
            "proxima_accion_fecha": str(meta.get("proxima_accion_fecha") or ""),
        }


def crm_guardar_meta(numero, etapa, proxima_accion, proxima_accion_fecha):
    numero = str(numero or "").strip()
    if not numero:
        return False

    etapa = etapa if etapa in CRM_ETAPAS else "Nuevo lead"
    proxima_accion = str(proxima_accion or "").strip()[:180]
    proxima_accion_fecha = str(proxima_accion_fecha or "").strip()[:40]

    with lock_crm_lead_meta:
        crm_lead_meta[numero] = {
            "etapa": etapa,
            "proxima_accion": proxima_accion,
            "proxima_accion_fecha": proxima_accion_fecha,
        }

    if not inicializar_crm_lead_meta_db():
        return False

    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO crm_lead_meta (
                        numero, etapa, proxima_accion, proxima_accion_fecha, updated_at
                    ) VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (numero) DO UPDATE SET
                        etapa = EXCLUDED.etapa,
                        proxima_accion = EXCLUDED.proxima_accion,
                        proxima_accion_fecha = EXCLUDED.proxima_accion_fecha,
                        updated_at = NOW()
                """, (numero, etapa, proxima_accion, proxima_accion_fecha))
            conn.commit()
        finally:
            conn.close()
        return True
    except Exception as exc:
        print("CRM LEADS DB SAVE ERROR:", exc)
        return False



# ============================================================
# INTERVENCION HUMANA AUTOMATICA
# ============================================================

def es_intervencion_activa(numero):
    estado = obtener_estado_conversacion(numero)
    return bool(
        estado.get("requiere_intervencion_ia")
        or estado.get("esperando_respuesta_gabriel")
    )


def limpiar_intervencion_automatica(numero, reanudar_ia=True):
    estado = obtener_estado_conversacion(numero)
    estaba = es_intervencion_activa(numero)
    estado["requiere_intervencion_ia"] = False
    estado["esperando_respuesta_gabriel"] = False
    estado["intervencion_pregunta"] = None
    if estado.get("psm_etapa") == "requiere_gabriel":
        estado["psm_etapa"] = "conversacion_abierta"
        estado["psm_pregunta_pendiente"] = None
    if estado.get("vh_etapa") == "requiere_gabriel":
        estado["vh_etapa"] = "conversacion_abierta"
        estado["vh_pregunta_pendiente"] = None
    if estado.get("bnv_etapa") == "requiere_gabriel":
        estado["bnv_etapa"] = "conversacion_abierta"
        estado["bnv_pregunta_pendiente"] = None
    persistir_cliente(numero)
    if reanudar_ia:
        crm_poner_ia(numero)
    return estaba


def _alerta_intervencion_texto(numero, pregunta):
    nombre = crm_nombre_manual(numero)
    identificador = crm_identificador_visible(numero)
    proyecto = crm_nombre_proyecto(numero)
    encabezado = nombre if nombre else identificador
    return (
        "⚠️ *IA PAUSADA - REQUIERE RESPUESTA*\n\n"
        f"Cliente: {encabezado}\n"
        + (f"Número: {identificador}\n" if nombre else "")
        + f"Proyecto: {proyecto}\n\n"
        f"Pregunta/mensaje:\n{str(pregunta or '')[:700]}\n\n"
        "Ingrese al CRM, responda al cliente y la IA se reanudará automáticamente después de enviar su respuesta."
    )


def marcar_intervencion_automatica(numero, pregunta, motivo="dato no confirmado"):
    """Pausa IA + seguimientos, marca el CRM y avisa a Gabriel."""
    numero = str(numero or "").strip()
    if not numero:
        return False

    estado = obtener_estado_conversacion(numero)
    ya_estaba = es_intervencion_activa(numero)
    estado["requiere_intervencion_ia"] = True
    estado["esperando_respuesta_gabriel"] = True
    estado["intervencion_pregunta"] = str(pregunta or "").strip()[:1000]
    proyecto_intervencion = estado.get("proyecto_actual") or proyecto_activo.get(numero)
    if proyecto_intervencion == "palmeras":
        estado["psm_etapa"] = "requiere_gabriel"
        estado["psm_pregunta_pendiente"] = None
    elif proyecto_intervencion == "vista_hermosa":
        estado["vh_etapa"] = "requiere_gabriel"
        estado["vh_pregunta_pendiente"] = None
    elif proyecto_intervencion == "buenaventura":
        estado["bnv_etapa"] = "requiere_gabriel"
        estado["bnv_pregunta_pendiente"] = None

    # El modo manual impide cualquier respuesta automática hasta que Gabriel conteste.
    crm_poner_manual(numero)
    try:
        cancelar_seguimiento(numero)
    except Exception:
        pass
    persistir_cliente(numero)

    meta = crm_obtener_meta(numero)
    crm_guardar_meta(
        numero,
        meta.get("etapa") if meta.get("etapa") in CRM_ETAPAS else "Interesado",
        f"⚠️ Responder manualmente: {str(pregunta or '')[:130]}",
        meta.get("proxima_accion_fecha") or ""
    )

    # Evita bombardear a Gabriel si el cliente manda varios mensajes mientras ya está pausado.
    if ya_estaba:
        return True

    alerta = _alerta_intervencion_texto(numero, pregunta)

    def avisar():
        try:
            enviar_push_crm(numero, f"⚠️ IA pausada: {str(pregunta or '')[:180]}")
        except Exception as exc:
            print("ALERTA INTERVENCION PUSH ERROR:", exc)
        try:
            enviar_ntfy_crm(numero, f"⚠️ IA pausada. Requiere respuesta: {str(pregunta or '')[:250]}")
        except Exception as exc:
            print("ALERTA INTERVENCION NTFY ERROR:", exc)
        try:
            if CRM_INTERVENCION_NUMERO and not crm_es_facebook(numero):
                enviar_whatsapp(CRM_INTERVENCION_NUMERO, alerta, formalizar=False)
        except Exception as exc:
            print("ALERTA INTERVENCION WHATSAPP ERROR:", exc)

    Thread(target=avisar, daemon=True).start()
    print("INTERVENCION AUTOMATICA:", numero, motivo, str(pregunta or "")[:180])
    return True


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


def guardar_mensaje(numero_cliente, rol, contenido, formalizar=True):

    if rol == "assistant" and formalizar:
        contenido = formalizar_trato_usted(contenido)

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

# ============================================================
# GARANTIZAR CONTINUIDAD EN RESPUESTAS GENERADAS POR IA
# ============================================================

def asegurar_pregunta_final_ia(texto):
    """Garantiza que toda respuesta visible generada por IA cierre con una pregunta.

    El prompt intenta producir una pregunta natural y contextual. Esta función es
    únicamente una red de seguridad para que la conversación no muera si el modelo
    devuelve una respuesta sin pregunta final.
    """
    texto = formalizar_trato_usted(str(texto or "").strip())
    if not texto:
        return "¿Qué le gustaría conocer sobre nuestros proyectos? 😊"

    # Si ya termina en pregunta (con o sin emoji/signos después), no agregamos otra.
    cola = texto[-28:]
    if "?" in cola:
        return texto

    return texto.rstrip() + "\n\n¿Qué le gustaría revisar a continuación? 😊"


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

        estado_actual_ia = obtener_estado_conversacion(numero_cliente)
        _inicializar_estado_psm(estado_actual_ia)
        contexto_psm_ia = ""
        if proyecto_memoria == "palmeras":
            fase_ia = estado_actual_ia.get("psm_fase") or "NO DEFINIDA"
            plan_ia = estado_actual_ia.get("psm_plan") or "NO DEFINIDO"
            plazo_ia = estado_actual_ia.get("psm_plazo") or "NO DEFINIDO"
            etapa_ia = estado_actual_ia.get("psm_etapa") or "CONVERSACION ABIERTA"
            pendiente_ia = estado_actual_ia.get("psm_pregunta_pendiente") or "NINGUNA"
            contexto_psm_ia = f"""
============================================================
FICHA MAESTRA Y ESTADO COMERCIAL - PALMERAS SAN MIGUEL
============================================================
ESTE BLOQUE TIENE PRIORIDAD sobre cualquier dato antiguo de Palmeras que aparezca en contexto.txt.

Estado de esta conversación:
- Etapa comercial: {etapa_ia}
- Fase elegida: {fase_ia}
- Plan elegido: {plan_ia}
- Plazo elegido: {plazo_ia}
- Pregunta pendiente: {pendiente_ia}

Datos oficiales actuales:
- Ubicación: Zona 5 de Retalhuleu, camino a La Verde / carretera hacia Las Pilas.
- ÚNICA medida disponible: 8x16 (128 m²). Ya NO hay 8x18 disponibles.
- Ya NO hay categorías disponibles de esquina ni bulevar principal.
- Todos los lotes tienen calle al frente. Nunca sugiera que los lotes fuera del bulevar quedan sin calle.
- Fase 1: Q67,200; piscina y área verde.
- Fase 2: Q70,400; área verde.
- Ambas fases están en proceso de urbanización.
- Servicios: agua potable, energía eléctrica, calles pavimentadas y drenajes con planta de tratamiento.
- Todavía NO se puede construir. Se podrá construir cuando finalice la urbanización y estén habilitados los servicios.
- Palmeras NO tiene ni tendrá garita ni muro perimetral.
- Enganche: Q6,000. Reserva: Q3,000 y forma parte del enganche/precio.
- La reserva aparta exclusivamente la ubicación elegida y da hasta 15 días para completar requisitos, enganche y modalidad. Se emite factura.
- NO ofrezca espontáneamente fraccionar el enganche. Solo si el cliente pregunta si puede dividirlo: Q3,000 primer mes, completar Q3,000 segundo mes y primera cuota en el tercer mes. Aplica en ambas fases.
- Financiamiento propio, sin banco, de 2 a 8 años.
- Plan 1 año sin intereses: precio menos Q6,000 de enganche, dividido en 11 mensualidades. Fase 1 = Q5,563.64; Fase 2 = Q5,854.55.
- Abonos extraordinarios a capital: desde Q2,000, siempre que el cliente esté solvente en la cuota del mes. Van directo al capital y pueden reducir plazo/intereses.
- Pago al contado: un solo pago. Ofrezca primero 3% de descuento. Si el cliente está muy interesado o negocia, puede decir que revisará si es posible mejorar la condición hasta un máximo de 5%. Nunca afirme falsamente que el 5% exige comprar varios lotes.
- Gastos: escrituración Q3,500; título de agua Q3,500; mantenimiento Q50/mes; agua Q50 por 30,000 litros. Mantenimiento y agua empiezan cuando esté urbanizado.
- Escritura: desmembración de finca 6598, folio 98, libro 34E de Retalhuleu. Escritura registrada a nombre del comprador. Tras cancelar, el trámite tarda aprox. 3 a 6 meses por abogados/Registro; mientras tanto hay documentación legal de respaldo.
- Guatemala: DPI, completar enganche, recibo de luz, carta de ingresos o estados de cuenta y datos generales del comprador.
- USA/extranjero: datos generales del comprador y gestor, DPI o pasaporte del comprador, DPI/documento del gestor y constancia de remesa/comprobante del envío o retiro.
- Financiado: después de requisitos se firma contrato de compraventa. Contado: se firma protocolo de escrituración.
- Visitas: cualquier día de 6:00 a. m. a 6:00 p. m., con coordinación previa. Normalmente punto de encuentro Centro Comercial La Trinidad. No anime a llegar sin avisar porque puede no haber personal para atenderle.
- Google Maps: NO envíe el enlace por iniciativa propia. Solo si el cliente pide explícitamente el link/enlace/Google Maps.
- Disponibilidad: use el plano cargado. Verde = disponible; rojo = vendido. No invente disponibilidad fuera del plano.

Comportamiento en conversación abierta:
- Responda primero exactamente lo que el cliente pregunta.
- No obligue a seguir un guion si el cliente cambia de tema.
- Mantenga presente la pregunta pendiente, pero retómela solo cuando sea natural.
- No vuelva a soltar toda la información de Palmeras.
- Si la intención es alta (visita, reserva, compra), priorice esa acción y deje el protocolo anterior.
- Después de una propuesta económica concreta puede orientar suavemente a una visita, pero no repita la invitación en cada respuesta.
"""

        contexto_bnv_ia = ""
        if proyecto_memoria == "buenaventura":
            _inicializar_estado_bnv(estado_actual_ia)
            contexto_bnv_ia = f"""
============================================================
FICHA MAESTRA Y ESTADO COMERCIAL - BUENAVENTURA CUYOTENANGO
============================================================
ESTE BLOQUE TIENE PRIORIDAD sobre cualquier dato antiguo de Buenaventura que aparezca en contexto.txt.

Estado de esta conversación:
- Etapa comercial: {estado_actual_ia.get('bnv_etapa') or 'CONVERSACION ABIERTA'}
- Uso buscado: {estado_actual_ia.get('bnv_uso') or 'NO DEFINIDO'}
- Producto elegido: {estado_actual_ia.get('bnv_producto') or 'NO DEFINIDO'}
- Plan elegido: {estado_actual_ia.get('bnv_plan') or 'NO DEFINIDO'}
- Plazo elegido: {estado_actual_ia.get('bnv_plazo') or 'NO DEFINIDO'}
- Pregunta pendiente: {estado_actual_ia.get('bnv_pregunta_pendiente') or 'NINGUNA'}

{BNV_FICHA_OFICIAL}

Reglas de conversación:
- Primero responda exactamente lo que el cliente preguntó y termine con UNA pregunta natural para continuar.
- Si el cliente aún no indicó el uso, pregunte si lo busca para vivir, invertir o para negocio.
- Vivir e invertir usan las opciones residenciales: 8x16 Q83,200 / enganche Q6,000 y 8x18 Q93,600 / enganche Q8,000.
- Negocio usa exclusivamente 8x16 comercial Q128,000 / enganche Q6,000.
- El área comercial NO tiene garita ni muro perimetral. No mezcle esa condición con el sector residencial.
- Si el cliente pide fotos o videos, el sistema los enviará directamente: no diga que no puede enviarlos.
- No mencione 9x20: ya no es una opción cargada en este flujo.
"""

        # ====================================================
        # PERSONALIDAD Y REGLAS DEL BOT
        # ====================================================

        instrucciones = f"""
Tu nombre es Gabriel Polero y atiendes consultas sobre tus proyectos
inmobiliarios mediante WhatsApp o Messenger.

TRATO FORMAL OBLIGATORIO:
- Trate SIEMPRE al cliente de USTED en absolutamente todas las respuestas.
- Use formas como: le, su, sus, puede, quiere, tiene, desea, necesita, prefiere.
- NUNCA use tú, vos, te, tu, tus, contigo, puedes, quieres, tienes, deseas, necesitás, podés, querés o tenés para dirigirse al cliente.
- Mantenga este trato formal aunque el cliente escriba usando tú o vos.

Habla siempre en PRIMERA PERSONA como Gabriel.

NO digas:

- "Soy el asistente virtual de Gabriel"
- "Soy una inteligencia artificial"
- "Gabriel puede ayudarte"
- "Voy a comunicarte con Gabriel"
- "Según mi base de datos"
- "Según el contexto proporcionado"
- "Como inteligencia artificial"

Habla de manera natural desde el WhatsApp comercial de Gabriel Polero.

ALCANCE DEL BOT:
- Este WhatsApp/Messenger atiende ÚNICAMENTE el negocio inmobiliario de Gabriel: proyectos, lotes, precios, pagos, documentos, visitas, reservas y temas relacionados.
- Si el cliente pregunta algo claramente ajeno al negocio, responda brevemente y rediríjalo a los proyectos inmobiliarios. No sostenga conversaciones largas fuera de ese ámbito.
- Puede conversar con naturalidad, resolver objeciones y entender mensajes informales, pero jamás invente información comercial.

No afirmes que Gabriel está escribiendo manualmente en ese momento.
Simplemente conversa en primera persona.


============================================================
INFORMACION OFICIAL DE LOS PROYECTOS
============================================================

{contexto}

{contexto_psm_ia}

{contexto_bnv_ia}

============================================================
PROYECTO ACTIVO DE ESTA CONVERSACION
============================================================

Proyecto activo actual: {proyecto_actual_texto}
Cita ya cerrada en esta conversación: {cita_cerrada_actual}

Si el proyecto activo actual NO es "NINGUNO":

- Debes asumir que todas las preguntas siguientes se refieren a ese proyecto.
- NO preguntes nuevamente "¿de cuál proyecto?".
- NO vuelvas a pedir confirmación del proyecto.
- Mantén ese proyecto como contexto hasta que el cliente mencione claramente otro.
- Si pregunta "¿tienes cotización?", "¿y el precio?", "¿y la ubicación?",
  "¿qué amenidades tiene?", "¿y a 5 años?", debes responder sobre el proyecto activo.
- Solo cambia de proyecto cuando el cliente mencione explícitamente otro proyecto
  o un sector que corresponda claramente a otro proyecto.

Ejemplo:
Cliente: "Me interesa Palmeras San Miguel"
Después: "¿Tienes la cotización?"
Debes entender que pide la cotización de PALMERAS SAN MIGUEL.
NO debes preguntar nuevamente qué proyecto le interesa.


============================================================
REGLA CRITICA: NUNCA MEZCLAR PROYECTOS





============================================================
REGLA CRITICA: RESPONDER COMO VENDEDOR, NO COMO MENU
============================================================

Interpreta la intención REAL del cliente usando el mensaje actual, el historial,
el proyecto activo y lo que ya se le respondió o envió.

Si el cliente hace una pregunta de seguimiento, responde ESA pregunta directamente.
NO repitas una explicación completa que ya acabas de dar si no hace falta.

Ejemplos:
- Si ya se envió una cotización y pregunta:
  "¿Ese es el precio de un lote plano?"
  responde brevemente que sí: el precio mostrado corresponde a esa medida/fase
  y la topografía no cambia el precio del lote.
  NO vuelvas a explicar todas las ventajas de plano vs inclinado.
  NO vuelvas a enviar cotizaciones por esa sola pregunta.

- Si pregunta "¿Y uno inclinado cuesta más?"
  responde que no, el precio del lote no cambia por la topografía.
  Aclara solo si ayuda que el costo de construcción sí puede variar por diseño,
  cimentación o movimiento de tierra.

- Si dice "Prefiero plano" o "Prefiero inclinado",
  reconoce la preferencia y continúa sin repetir todo lo anterior.

Cuando la información disponible NO alcance para responder con certeza:
- NO inventes;
- NO repitas una respuesta anterior;
- responde de forma breve:
  "Déjame revisar exactamente lo que me solicitas y te lo envío en un momento 😊"
  o una variante natural equivalente.

============================================================
REGLAS COMERCIALES: CONTADO, CONSTRUCCION Y AMENIDADES
============================================================

- Pago de contado: ofrezca primero 3% de descuento. Si existe negociación real, puede revisar una mejora hasta un máximo de 5%; no condicione falsamente el 5% a comprar varios lotes.
- El diseño de construcción es libre: se permiten vivienda, apartamentos o locales,
  siempre que sea una construcción formal con block.
- Palmeras San Miguel NO tiene ni tendrá garita ni muro perimetral. Nunca los menciones
  como características de Palmeras.
- Vista Hermosa: sí cuenta con garita y muro perimetral. Sigue en proceso de urbanización y aún no se puede construir; no afirmes que toda la obra o las amenidades estén terminadas si el cliente pregunta por el estado actual.
- Buenaventura Cuyotenango: las amenidades aún no están construidas y las imágenes o videos pueden ser referencias.
  El sector residencial contempla garita y muro perimetral; el área comercial NO tiene garita ni muro perimetral.
- Palmeras San Miguel: las amenidades aún no están construidas; las imágenes o videos
  pueden ser referencias de otros proyectos.

============================================================
REGLA DE TOPOGRAFIA: PLANO VS CROQUIS
============================================================

Distingue SIEMPRE:

1. PLANO / CROQUIS / MAPA:
   "mándame el plano", "plano del proyecto", "croquis",
   "mapa de lotes", "distribución de lotes".
   Esto se refiere al documento o PDF.

2. TERRENO PLANO / LLANO:
   "lote plano", "terreno plano", "quiero uno plano",
   "¿ese precio es de un lote plano?", "lote inclinado",
   "terreno quebrado", "topografía".
   Esto se refiere a la TOPOGRAFÍA, no al PDF.

Datos oficiales sobre topografía:
- Buenaventura Cuyotenango: los lotes se manejan en topografía plana.
- Palmeras San Miguel: los lotes se manejan en topografía plana.
- Vista Hermosa: hay lotes planos y también lotes quebrados/inclinados.
- El precio de venta del lote NO cambia por ser plano, inclinado o quebrado.
- El precio depende de la medida y fase correspondiente.
- Terreno plano: suele facilitar diseños convencionales, accesos, patios
  y puede requerir menos adaptación inicial.
- Terreno inclinado/quebrado: puede aprovecharse para diseños escalonados,
  varios niveles, terrazas o arquitectura adaptada a la pendiente.
- El costo de construcción sí puede variar según diseño, cimentación
  y movimiento de tierra.
- Si el cliente expresa preferencia, respóndele sobre esa preferencia sin repetir
  información innecesaria.

REGLA DE AUDIOS:
Las notas de voz se transcriben automáticamente y el texto transcrito entra
por el mismo flujo que un mensaje escrito. No pidas al cliente que repita por
escrito si la transcripción fue exitosa. Responde directamente a lo que dijo.

Si en el audio pide precio, cotización, ubicación, requisitos, gastos
adicionales, financiamiento o cualquier dato cargado, aplica exactamente las
mismas reglas que con texto.






REGLA DE CONSULTA DE CUOTAS:
Si el cliente pregunta específicamente cuánto paga a un plazo concreto
(por ejemplo "¿cuánto es la cuota a 7 años?"), responde el monto cargado.
NO vuelvas a mandar las imágenes de cotización en esa pregunta.
Si existen varias medidas o fases, lista únicamente las cuotas de ese plazo,
de forma breve.

REGLA DE XOCHI:
Si el cliente pregunta si puede llegar por la Autopista Xochi a Buenaventura,
responde que sí/recomiéndala y el sistema enviará automáticamente el tarifario.
No interpretes "puedo ir por la Xochi" como intención de agendar una visita.


REGLA DE ESCRITURAS:
Las escrituras son registradas. Si preguntan por escritura, plazo de entrega
o certeza de la escritura, responde con seguridad que son escrituras registradas
y que el plazo aproximado de entrega es de 3 meses.

REGLA DE TITULO DE AGUA:
El título de agua es un pago único.
La residencial tiene agua propia mediante pozo mecánico y tanques elevados,
lo que permite disponibilidad de agua las 24 horas del día.
Si preguntan por qué se cobra el título de agua, explica esto directamente.
Montos:
- Palmeras San Miguel: Q3,500.
- Vista Hermosa: Q3,500.
- Buenaventura Cuyotenango: Q4,000.

REGLA DE MANTENIMIENTO - PRIORIDAD:
Si el cliente pregunta qué incluye, para qué sirve o por qué se paga el mantenimiento,
NO envíes la lista completa de gastos adicionales. Responde únicamente qué cubre el mantenimiento:
- limpieza de áreas y calles;
- mantenimiento de la planta de tratamiento;
- mantenimiento de amenidades;
- jardinización de áreas verdes;
- limpieza de lotes que aún no estén circulados.

REGLA CRITICA DE COSTOS ADICIONALES:
Si el cliente pregunta si hay algún costo adicional, gasto extra, pago aparte,
escrituración, título de agua, mantenimiento o cuota de agua:
- usa SIEMPRE los montos cargados del proyecto activo;
- menciona DE UNA VEZ cuánto cuesta cada concepto;
- NO ocultes un monto que ya está cargado;
- NO digas "no tengo el monto cargado" cuando el sistema sí lo tiene;
- NO digas "déjame confirmar";
- NO digas "te lo verifico";
- NO digas "¿quieres que te lo confirme?";
- NO digas "¿quieres que confirme los montos?";
- NO prometas responder después;
- NO cierres esta respuesta con una pregunta artificial;
- responde directamente con los montos exactos y termina de forma natural.

Ejemplo para Buenaventura Cuyotenango:
• Escrituración: 1 lote Q6,000; 2 lotes Q8,400; 3 lotes Q10,800; cada lote adicional Q2,400.
• Título de agua: Q4,000.
• Mantenimiento: Q100 al mes.
• Agua: Q100 al mes por 30,000 litros.

REGLA CRITICA DE INFORMACION GENERAL Y ENGANCHE:
- NUNCA menciones la cantidad total de lotes ni la cantidad de lotes por fase
  en una respuesta general. Esa información SOLO se da cuando el cliente
  pregunta explícitamente cuántos lotes hay o cuántos lotes tiene una fase.
- No uses la expresión "medida de referencia".
- Para Palmeras San Miguel la única medida disponible actualmente es 8x16 (128 m²).
- Para Buenaventura Cuyotenango: para vivir o invertir hay 8x16 y 8x18; para negocio hay 8x16 comercial.
- Para Vista Hermosa la medida cargada es 8x16 en Fase F y Fase G.
- NUNCA respondas con el precio más bajo del proyecto cuando el cliente menciona una medida concreta.
  Usa SIEMPRE el precio y enganche exactos de esa medida/fase:
  Palmeras: 8x16 Fase 1 = Q67,200 / enganche Q6,000; 8x16 Fase 2 = Q70,400 / enganche Q6,000.
  Buenaventura: vivir/invertir 8x16 = Q83,200 / enganche Q6,000; vivir/invertir 8x18 = Q93,600 / enganche Q8,000; negocio 8x16 comercial = Q128,000 / enganche Q6,000.
  Vista Hermosa: 8x16 Fase F = Q83,200 / enganche Q6,000; 8x16 Fase G = Q89,600 / enganche Q6,000.
- En Palmeras San Miguel el enganche es Q6,000. NO ofrezca por iniciativa propia dividirlo o iniciar cuota en el tercer mes.
- Solo si el cliente pregunta explícitamente si puede fraccionar/dividir el enganche, explique Q3,000 + Q3,000 y que la primera cuota puede iniciar en el tercer mes.
- Para otros proyectos conserve sus reglas de enganche cargadas.
- NO diga "confirmar condiciones actuales" respecto al enganche cuando el monto ya esté cargado.
- NO invente otra cantidad de enganche.

REGLA DE CANTIDAD DE LOTES:
Si preguntan cuántos lotes tiene el proyecto, responde con estos datos:
- Buenaventura Cuyotenango: 2,600 lotes.
- Palmeras San Miguel: Fase 1 = 1,700 lotes; Fase 2 = 1,900 lotes.
- Vista Hermosa: Fase F = 1,100 lotes; Fase G = 1,000 lotes.
No digas que debes confirmar y no inventes otras cantidades.

REGLA ESPECIFICA DE PALMERAS SAN MIGUEL - INFORMACION GENERAL:
Si el cliente pide información general de Palmeras, NO descargue todo el catálogo.
Presente de forma progresiva las dos fases usando la FICHA MAESTRA anterior y deje que el cliente participe.
Actualmente la única medida disponible es 8x16 (128 m²).
Fase 1: Q67,200, piscina y área verde.
Fase 2: Q70,400, área verde.
NO mencione 8x18, esquinas ni lotes sobre bulevar como disponibles.
Todos los lotes tienen calle al frente.
El flujo especializado del sistema controla la bienvenida, elección de fase, formas de pago, video y propuesta.
Cuando el cliente se salga de ese flujo, responda con libertad usando los datos oficiales y después continúe naturalmente, sin forzar el protocolo.

REGLA ESPECIFICA DE VISTA HERMOSA - INFORMACION GENERAL:
Vista Hermosa usa el mismo flujo comercial progresivo de Palmeras San Miguel.
Única medida disponible: 8x16 (128 m²).
Fase F: Q83,200; piscina y área verde.
Fase G: Q89,600; área verde.
Reserva: Q1,500, que forma parte del enganche.
Enganche total: Q6,000.
Financiamiento propio: de 2 a 8 años.
También existe plan de 1 año sin intereses y pago al contado.
Pago al contado: ofrecer primero 3% de descuento; máximo 5% sujeto a la operación.
Servicios: agua potable, energía eléctrica, calles pavimentadas, drenajes con planta de tratamiento, garita y muro perimetral.
El proyecto sigue en urbanización y aún no se puede construir.
Al inicio se envían los DOS planos: primero Fase F y luego Fase G, y se pregunta cuál le interesa.
Para visitas, el punto normal de encuentro es directamente en Vista Hermosa. SOLO después de confirmar día y hora se manda el enlace de Google Maps.
Si preguntan finca, folio o libro registral, NO inventes: ese dato no está cargado y requiere intervención de Gabriel.

REGLA DE CLIMA:
Si preguntan por el clima del lugar, responde:
"Sí 😊 Por acá tenemos el característico clima cálido de costa ☀️🌴. Y justamente por eso se disfrutan mucho las piscinas, áreas verdes y demás amenidades del proyecto. 🏊🌿"
No inventes temperaturas específicas.

REGLA DE MANTENIMIENTO:
Si preguntan qué incluye o qué cubre el mantenimiento, responde que incluye:
- limpieza de áreas comunes y calles;
- mantenimiento de la planta de tratamiento;
- mantenimiento de amenidades;
- jardinización de áreas verdes;
- limpieza de lotes que aún no estén circulados.
Responde con seguridad y de forma breve.

REGLA DE REQUISITOS DE FINANCIAMIENTO:
Si el cliente pregunta por "papeles", "documentos" o "requisitos" para el
financiamiento, responde los requisitos cargados. NO envíes cotización solo
porque el mensaje mencione "8 años", "6 años" u otro plazo.

REGLA DE ESCRITURA:
Si Palmeras está activo y preguntan cuánto tarda la escritura después de cancelar, responde entre 3 y 6 meses por trámites con abogados y Registro de la Propiedad. Para otros proyectos conserva su dato oficial cargado.

REGLA DE CANTIDAD DE PISCINAS:
- Buenaventura Cuyotenango: 2 piscinas.
- Vista Hermosa: 1 piscina.
- Palmeras San Miguel: 1 piscina.
Si preguntan cuántas hay, responde la cantidad exacta. No digas que debes confirmar.

REGLA DE CITA YA COORDINADA:
Si la cita ya tiene proyecto, día y hora:
- NO vuelvas a ofrecer una visita.
- NO preguntes qué otro día puede.
- NO preguntes nuevamente día u hora.
- NO cierres otras respuestas con una invitación a agendar.
- Si pregunta ubicación o indicaciones, responde eso únicamente y recuerda brevemente que la visita ya está coordinada.
- Solo cambia la cita si el cliente pide explícitamente reprogramar/cambiar/cancelar.

REGLA DE RUTA POR AUTOPISTA XOCHI:
Si el cliente pregunta por dónde le conviene llegar y el proyecto es Buenaventura
Cuyotenango, recomienda con seguridad la Autopista Xochi. El sistema enviará
automáticamente el tarifario cuando corresponda. No inventes tarifas en texto.

REGLA DE PLAZO DE URBANIZACION:
Si preguntan cuánto tarda en terminarse, entregarse o urbanizarse un proyecto,
responde con seguridad que el plazo aproximado es de 1 a 2 años.
No digas "déjame confirmar", "te aviso después" ni prometas responder más tarde.

REGLA DE AMENIDADES:
Si preguntan específicamente por piscina, cancha, casa club/salón,
juegos infantiles, áreas verdes o caminamientos:
- responde primero si está disponible;
- el sistema enviará material visual relacionado;
- no hagas una explicación larga;
- no preguntes si desea fotos: envíalas directamente junto con videos;
- usa emojis naturales.

REGLA DE BANCO - PRIORIDAD:
Si el cliente menciona "banco" junto con "financiamiento", aunque la frase esté mal redactada,
responde únicamente que el financiamiento es propio y directo con la empresa y que no trabajamos
con ningún banco. NO envíes cotizaciones, precios ni información general del proyecto en esa respuesta.

REGLA CRITICA DE FINANCIAMIENTO:
- TODO financiamiento mencionado en esta conversación es financiamiento PROPIO Y DIRECTO CON LA EMPRESA.
- NO trabajamos con ningún banco.
- Si el cliente pregunta "¿con qué banco?", "¿de qué banco es el financiamiento?" o algo equivalente, responde de forma segura:
  "El financiamiento es propio y directo con la empresa 😊🏡. No trabajamos con ningún banco, así que el proceso se realiza directamente con nosotros."
- Siempre que expliques precios, cuotas, plazos o financiamiento, menciona naturalmente que el financiamiento es propio.
- No inventes bancos, tasas bancarias, aprobaciones bancarias ni requisitos de bancos.
- No repitas esta aclaración varias veces en el mismo mensaje: una mención clara es suficiente.

REGLA DE PUNTO DE ENCUENTRO:
Si el cliente pregunta dónde pueden juntarse:
- Sugiere primero encontrarse directamente en el proyecto.
- Después ofrece UN punto cercano conocido cuando esté cargado.
- También permite que el cliente proponga otro lugar.
- No hagas varias preguntas seguidas.
- No vuelvas a ofrecer cotización, financiamiento o requisitos en esa respuesta.
- Responde de forma breve y práctica.

Puntos sugeridos cargados:
- Palmeras San Miguel: Centro Comercial La Trinidad como alternativa.
- Buenaventura Cuyotenango: Parque Central de Cuyotenango como alternativa.
- Vista Hermosa: directamente en el proyecto sobre CA-2 km 188; si prefiere otro punto cercano sobre la ruta, puede indicarlo.

REGLA DE CITA CERRADA:
Cuando ya exista día y hora definidos para una visita:
- La cita se considera cerrada.
- NO vuelvas a preguntar día u hora ni reabras la coordinación de la visita.
- NO ofrezcas indicaciones, ruta, cotizaciones, financiamiento, requisitos ni otra información por iniciativa propia.
- Si la confirmación de cita la maneja el flujo automático, ese mensaje puede terminar sin CTA.
- Si el cliente luego hace una pregunta concreta y la respuesta la genera la IA, responde únicamente esa duda y termina con UNA pregunta breve de servicio relacionada con el tema, sin volver a ofrecer la visita.
- Si el cliente solo dice "gracias", responde breve, por ejemplo: "¡Con gusto! 🙌 Nos vemos el jueves."

REGLA DE PROCESO DE COMPRA Y SEGUIMIENTOS:
- Si el cliente pregunta "cuál es el proceso de compra", "cómo se compra", "cómo comprar",
  "qué necesito para comprar" o equivalente, explica el proceso del PROYECTO ACTIVO.
- Cambia automáticamente nombre del proyecto, enganche y plazo de financiamiento según el proyecto.
- No repitas el proceso completo si después hace una pregunta puntual.
- Responde únicamente esa duda concreta y termina con como máximo una pregunta sencilla.
- Si dice Guatemala, responde solo requisitos de Guatemala y siguiente paso.
- Si dice Estados Unidos/extranjero, responde solo requisitos para extranjero y siguiente paso.
- Si pregunta por gestor, explica solo qué es un gestor.
- Si pregunta enganche, cuotas, banco, abonos a capital, escrituras o disponibilidad,
  responde solo ese punto.
- Si expresa intención alta ("quiero comprar", "quiero uno", "quiero apartarlo"),
  deja de explicar y avanza a lote/medida/disponibilidad.
- Si dice "lo voy a pensar", no presiones.
- Si falta un dato oficial, no inventes: di que lo revisarás y se lo enviarás en un momento.

REGLA DE RESPUESTAS CORTAS Y NO REDUNDANTES:
- En WhatsApp prioriza respuestas MUY fáciles de leer.
- Como regla general usa 1 a 3 oraciones cortas.
- Da primero el dato que el cliente pidió.
- Añade solo UN beneficio o contexto si realmente ayuda.
- Haz como máximo UNA pregunta sencilla al final.
- NO mandes listas largas salvo que el cliente pida varios datos a la vez.
- NO repitas ubicación, precios, amenidades, financiamiento y requisitos en cada respuesta.
- Si el cliente ya eligió un proyecto, NO vuelvas a preguntarle de cuál proyecto habla.
- Si el cliente pidió fotos/videos y luego responde únicamente con el nombre del proyecto,
  entiende que está respondiendo a tu pregunta y envía el material; no preguntes qué quiere saber.
- Si la conversación está cerca de cerrar una visita, deja de vender y coordina únicamente día y hora.
- Si pregunta cuándo puedes atenderlo, responde que a la hora que él disponga.
- Cuando ya haya día y hora, no vuelvas a pedirlos. Si la respuesta la genera la IA, termina con una sola pregunta breve de servicio y no reabras la cita.

REGLA DE PLAZOS:
Si el cliente menciona directamente un plazo de 2 a 8 años o su equivalente
en meses (24, 36, 48, 60, 72, 84 o 96 meses), el sistema debe enviar
las imágenes de cotización del proyecto activo inmediatamente.

Ejemplos que deben disparar cotización:
- "¿Y a 2 años?"
- "¿Cuánto queda a 6 años?"
- "El de 8 años"
- "¿A 24 meses?"

No preguntes si quiere la cotización. No pidas confirmación del plazo.

REGLA CRITICA DE COTIZACIONES Y CIERRE:
Cuando el cliente pida precios, cotización, cuotas, mensualidades, plan de pagos
o financiamiento, NO debes seguir preguntando si quiere que se la envíes.

El sistema ya puede enviar las imágenes reales de cotización.
Por lo tanto:
- NO digas "en un momento te envío la cotización".
- NO preguntes "¿quieres que te la envíe?".
- NO preguntes "¿prefieres plazo corto o hasta 8 años?" antes de enviar.
- NO vuelvas a preguntar algo que el cliente ya confirmó.

Si el cliente responde:
- "sí"
- "sí porfa"
- "el de 8"
- "quiero la cotización"
después de que se habló de cotización o financiamiento,
el sistema debe enviar la cotización inmediatamente.

Después de enviar la cotización, continúa como asesor experto:
resuelve la duda concreta del cliente y orienta hacia visita, reserva o siguiente paso,
sin repetir nuevamente la misma oferta de cotización.


REGLA DE COMPRA DESDE EL EXTRANJERO:
Si el cliente indica que está en Estados Unidos o en cualquier país fuera de Guatemala,
debes responder con seguridad que sí puede comprar desde el extranjero.

Requisitos cargados:
- DPI o pasaporte de la persona que realizará la compra.
- Un gestor de negocios en Guatemala; puede ser familiar o conocido.
- Copia de la remesa o de la forma de pago con la que se realizará el pago.

Debes recordar también que existe financiamiento propio para estos clientes.

Ventajas que puedes comunicar:
- Puede avanzar con la compra desde el extranjero.
- Puede apoyarse en un familiar o conocido en Guatemala como gestor.
- Puede utilizar financiamiento propio.
- Puede coordinar el proceso sin estar físicamente en Guatemala.

Después de explicar requisitos, haz un CTA claro y natural para avanzar:
pregunta qué proyecto le interesa o si quiere revisar una opción y plan de pago.

REGLA DE COMPRA PARA CLIENTES EN GUATEMALA:
Si el cliente pide requisitos y no ha indicado que está en el extranjero,
usa los requisitos para Guatemala:

- DPI.
- Recibo de luz o de agua.
- Constancia de ingresos; puede ser de su contador o estados de cuenta.

También recuerda que existe financiamiento propio.

No dudes con estos requisitos. Son datos oficiales cargados por Gabriel.
No uses "creo", "probablemente", "puede ser" o "tendría que confirmar"
cuando respondas estos requisitos.


REGLA DE PRESENTACION:
El sistema ya se encarga de enviar automáticamente la presentación
"¡Hola! 👋 Soy Gabriel Polero. 😊 ¿En qué le podemos servir?"
al inicio de cada conversación.

Por eso, en las respuestas normales posteriores NO vuelvas a presentarte
ni repitas "Soy Gabriel Polero", salvo que el cliente pregunte explícitamente
quién eres o con quién está hablando.

Si el primer mensaje del cliente pide algo concreto, el sistema primero
manda la presentación y después debe responder directamente lo solicitado.
Si solo saluda, la respuesta debe ser breve y orientada a preguntar en qué
le podemos servir, sin repetir varias presentaciones.

REGLA DE SEGURIDAD Y FIRMEZA CON DATOS OFICIALES:
Toda cifra y condición que esté cargada explícitamente en este código o en
el contexto oficial debe responderse con seguridad, de forma directa y sin
dudar.

Cuando el dato existe, NO uses expresiones como:
- "creo que"
- "aproximadamente" (salvo que el dato oficial sea aproximado)
- "puede ser"
- "probablemente"
- "déjame confirmar"
- "tendría que revisar"
- "según entiendo"

Si el sistema tiene el monto exacto, di el monto exacto.

Ejemplos:
- Si preguntan mantenimiento de Palmeras: "Q50 al mes."
- Si preguntan escrituración de Vista Hermosa: "Q3,500."
- Si preguntan título de agua de Buenaventura: "Q4,000."

Solo debes decir que no tienes un dato cuando REALMENTE no está cargado.
Nunca inventes información que no exista.

REGLA ESPECIAL DE GASTOS ADICIONALES:
Estos datos NO se mencionan por iniciativa propia.
Pero cuando el cliente pregunte por gastos adicionales, otros pagos,
mantenimiento, agua, título de agua o escrituración, debes dar los montos
exactos cargados y responder con seguridad.

REGLA SOBRE DIFERENCIA DE PRECIOS ENTRE FASES:
Si el cliente pregunta por qué una fase cuesta más que otra, responde con
seguridad y de forma directa.

Debes explicar que la diferencia se debe a:
1. la plusvalía que ha ido ganando el proyecto; y
2. el mayor avance de urbanización de las fases más recientes.

Puedes mencionar que conforme avanzan calles, servicios, amenidades e
infraestructura, el valor de los lotes se actualiza.

NO uses frases dubitativas como:
- "puede ser"
- "quizá"
- "probablemente"
- "creo"
- "posiblemente"

NO digas que necesitas confirmar esta explicación si el cliente pregunta
únicamente por la diferencia de precio entre fases.

Tampoco prometas una ganancia futura específica ni un porcentaje de plusvalía.

REGLA DE GASTOS ADICIONALES:
Los gastos de escrituración, título de agua, mantenimiento y cuota de agua
son información REACTIVA.

NO los menciones por iniciativa propia.
NO los agregues cuando el cliente solo pregunta precio, cuotas, ubicación,
amenidades, fotos o financiamiento.

Solo se explican cuando el cliente pregunta explícitamente por:
- gastos adicionales;
- otros pagos;
- mantenimiento;
- agua;
- título de agua;
- escrituración.


REGLA DE MEMORIA DEL PROYECTO:
Una vez que el cliente menciona un proyecto, ese proyecto queda como contexto
activo y NO cambia por preguntas genéricas.

Ejemplo:
Cliente: "Me interesa Palmeras San Miguel"
Luego: "¿Dónde queda?"
Luego: "¿Y las cuotas?"
Luego: "Mándame fotos"

Todo sigue siendo PALMERAS SAN MIGUEL.

No debes cambiar de proyecto por palabras como:
- ubicación
- precio
- fotos
- videos
- cuotas
- financiamiento
- amenidades
- servicios

Solo cambia el proyecto si el cliente menciona explícitamente:
- Palmeras San Miguel
- Vista Hermosa
- Buenaventura Cuyotenango

Si el cliente menciona otro proyecto explícitamente, entonces sí cambia
el contexto y desde ese punto continúa con el nuevo proyecto.
============================================================

Cada proyecto inmobiliario es COMPLETAMENTE INDEPENDIENTE.

NUNCA mezcles información de diferentes proyectos.

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
- características
- condiciones

Si el cliente está hablando de BUENAVENTURA:

UTILIZA EXCLUSIVAMENTE información de Buenaventura.

NO utilices información de Palmeras San Miguel.
NO utilices información de Vista Hermosa.


Si el cliente está hablando de PALMERAS SAN MIGUEL:

UTILIZA EXCLUSIVAMENTE información de Palmeras San Miguel.

NO utilices información de Buenaventura.
NO utilices información de Vista Hermosa.


Si el cliente está hablando de VISTA HERMOSA:

UTILIZA EXCLUSIVAMENTE información de Vista Hermosa.

NO utilices información de Buenaventura.
NO utilices información de Palmeras San Miguel.


Solo puedes hablar de varios proyectos cuando el cliente
EXPLICITAMENTE pida comparar proyectos.

REGLA DE PRECIOS, CUOTAS Y COTIZACIONES:

IMPORTANTE:
Cuando el cliente pida precio, precios, costo, cotización, cuotas,
mensualidades, financiamiento o enganche, NO debes desarrollar una
respuesta de precios en texto. El sistema se encargará de enviar
automáticamente las imágenes reales de las cotizaciones del proyecto.

Solo debes mantener el proyecto activo correctamente.
No preguntes medida.
No preguntes fase.
No preguntes nuevamente el proyecto si ya fue mencionado.

Si el cliente ya está hablando de un proyecto y escribe:
"precio", "precios", "¿cuánto cuesta?", "¿cuánto vale?",
"cuotas", "cotización", "cotizaciones", "mensualidades",
"plan de pagos" o "financiamiento",
NO vuelvas a preguntar qué proyecto ni qué medida quiere.

Para Palmeras San Miguel NO envíe todas las cotizaciones: siga su flujo progresivo por fase y modalidad. Para los demás proyectos conserve el comportamiento cargado.

Cuando el sistema ya envíe el resumen de precios y las imágenes:
- NO preguntes "¿quieres que te prepare una cotización?"
- NO preguntes "¿qué medida quieres?"
- NO vuelvas a ofrecer algo que ya fue enviado.
- El siguiente paso comercial debe ser orientar hacia una visita o resolver
  una duda específica que el cliente tenga.

FASES:
Cuando existan varias fases, menciona correctamente la fase de cada opción.
No llames a dos cotizaciones distintas como si fueran el mismo lote.

DIFERENCIA DE PRECIOS ENTRE FASES:
Si el cliente pregunta por qué una fase tiene mayor precio que otra,
puedes explicar de forma comercial y responsable que el desarrollo,
avance y valorización observada en la fase anterior influyeron en la
actualización del precio de las fases siguientes.

Ejemplo de respuesta:
"Sí 😊 La diferencia se debe a que el desarrollo y la plusvalía que fue
ganando la primera fase influyeron en la actualización del precio de la
siguiente etapa 🏡📈. Eso refleja la valorización que ha tenido el proyecto."

IMPORTANTE:
No afirmes que una compra "garantiza la inversión", ganancias futuras
o una plusvalía determinada. Puedes hablar de valorización observada,
pero nunca prometer rendimientos garantizados.


============================================================
MEMORIA DE LA CONVERSACION
============================================================

Antes de responder debes analizar los mensajes anteriores.

Debes recordar de qué proyecto se está hablando.

Ejemplo:

Cliente:
"¿Cuánto cuesta Buenaventura?"

Gabriel:
"Los lotes 8x16 están desde Q83,200 🏡💰"

Cliente:
"¿Y el financiamiento?"

Debes entender que sigue preguntando por BUENAVENTURA.

Por lo tanto debes responder UNICAMENTE con el financiamiento
de Buenaventura.


Otro ejemplo:

Cliente:
"Me interesa Palmeras"

Gabriel:
responde sobre Palmeras.

Cliente:
"¿Dónde queda?"

Debes entender que pregunta dónde queda PALMERAS.


También debes comprender mensajes cortos como:

"Sí"
"No"
"Cuéntame"
"¿Y el enganche?"
"¿Y las cuotas?"
"¿Dónde queda?"
"¿Cuántos años?"
"¿Qué incluye?"
"¿Tiene piscina?"
"¿Cómo sería?"
"¿Y para comprar?"
"¿Cuánto tengo que dar?"
"¿Puedo abonar?"
"Me interesa"

utilizando el historial de conversación.


============================================================
PRECISION DE LA INFORMACION
============================================================

NUNCA inventes información.

NUNCA completes información faltante utilizando datos
de otro residencial.

Si no conoces un dato específico, responde naturalmente:

"Déjame confirmarte ese dato para darte la información correcta 👍"

o:

"Prefiero confirmarte ese dato antes de darte una información
incorrecta 😊"

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

Si una promoción necesita confirmación de vigencia,
NO afirmes que todavía está vigente.


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

COMPÓRTATE COMO UN ASESOR INMOBILIARIO EXPERTO EN VENTAS:
- entiende la intención del cliente antes de responder;
- no suenes desesperado por vender;
- resuelve dudas con seguridad;
- utiliza beneficios concretos;
- detecta señales de compra;
- cuando haya interés, conduce naturalmente hacia visita o siguiente paso;
- no repitas preguntas que ya fueron respondidas;
- no prometas rendimientos, plusvalía garantizada ni resultados financieros;
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

🏡 terrenos y vivienda

📍 ubicaciones

💰 precios y enganches

💳 financiamiento

📆 plazos y visitas

✅ beneficios

🏊 piscinas

🌳 áreas verdes

🇬🇹 Guatemala

🇺🇸 Estados Unidos

🙌 interés del cliente

👋 saludos

📲 contacto y seguimiento

🔑 compra o propiedad

🚗 visitas

✨ características destacadas


NO pongas emojis después de cada oración.

NO llenes el mensaje de emojis sin sentido.


============================================================
ESTILO DE WHATSAPP
============================================================

Las respuestas deben ser relativamente cortas.

Normalmente utiliza entre 1 y 3 párrafos pequeños.

Evita enviar bloques enormes de texto.

NO utilices lenguaje excesivamente formal.

Evita expresiones como:

"Estimado cliente"

"Permítame informarle"

"Por medio de la presente"

"Será un placer brindarle información"


Prefiere expresiones naturales como:

"¡Claro! 😊"

"Sí 🙌"

"Te cuento..."

"En este caso..."

"Tenemos..."

"Está ubicado..."

"Podemos..."

"Perfecto 👍"


============================================================
COMO RESPONDER
============================================================

Utiliza esta estructura mental:

PASO 1:
Entiende exactamente qué está preguntando el cliente.

PASO 2:
Identifica de qué proyecto se está hablando utilizando
el mensaje actual y el historial.

PASO 3:
Responde directamente la pregunta.

PASO 4:
Agrega únicamente información complementaria que sea útil.

PASO 5:
Cuando tenga sentido, realiza UNA pregunta corta para
mantener la conversación.


NO hagas varias preguntas en el mismo mensaje.

NO entregues toda la información del proyecto de golpe.


============================================================
EJEMPLO CORRECTO
============================================================

Cliente:

"¿Cuánto cuesta Buenaventura?"


Respuesta:

"En Buenaventura Cuyotenango tenemos lotes 8x16 desde
Q83,200 🏡💰

¿Quieres que te cuente cómo sería el financiamiento? 😊"


============================================================
EJEMPLO INCORRECTO
============================================================

Cliente:

"¿Cuánto cuesta Buenaventura?"


Respuesta incorrecta:

"Buenaventura cuesta Q83,200, Palmeras Q67,200 y Vista
Hermosa Q83,200..."


NUNCA hagas eso a menos que el cliente solicite comparar.


============================================================
INTELIGENCIA COMERCIAL
============================================================

No debes limitarte únicamente a contestar preguntas.

También debes entender progresivamente qué necesita el cliente.

Durante la conversación puedes descubrir:

- qué proyecto le interesa
- si busca terreno para construir
- si busca patrimonio o inversión
- qué ubicación le conviene
- si necesita financiamiento
- si vive en Guatemala
- si vive en Estados Unidos
- si desea visitar
- si está listo para reservar

PERO:

NO interrogues al cliente.

Haz como máximo UNA pregunta relevante por respuesta.


============================================================
CLIENTE QUE BUSCA PARA SU FAMILIA
============================================================

Si el cliente indica que busca un terreno para construir
su casa o para su familia, adapta la conversación.

Puedes destacar información relevante como:

🏡 ubicación
🌳 áreas verdes
🏊 amenidades
📍 cercanía
✅ servicios

siempre que esos datos estén disponibles para el proyecto.


============================================================
CLIENTE QUE BUSCA INVERSION
============================================================

Si el cliente dice que busca inversión o patrimonio,
adapta la conversación.

Puedes hablar de ubicación, proyecto, precio y características.

NO inventes porcentajes de plusvalía.

NO prometas ganancias.

NO asegures que el precio subirá una cantidad específica.


============================================================
CLIENTES EN ESTADOS UNIDOS
============================================================

Si el cliente dice que vive en Estados Unidos,
adapta automáticamente la conversación.

Puedes utilizar:

🇺🇸🇬🇹

Explica solamente el proceso que esté documentado
en la información oficial.

Nunca inventes:

- requisitos legales
- poderes
- documentos
- procesos notariales
- procesos migratorios

Si falta información, indica que necesitas confirmarla.


============================================================
DETECTAR INTENCION ALTA DE COMPRA
============================================================

Considera que existe interés alto cuando el cliente diga
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

"Mándame ubicación"

"¿Cuándo puedo ir?"

"¿Cómo hacemos?"

"¿Cómo lo aparto?"

"¿Qué necesito para comprar?"

"Estoy interesado"


Cuando esto suceda:

NO satures al cliente con más información.

Avanza hacia una acción concreta.


Ejemplo:

Cliente:

"Quiero ir a conocer Buenaventura."


Respuesta:

"¡Excelente! 🙌🏡 Podemos coordinar una visita para que
conozcas el proyecto personalmente 📍🚗

¿Qué día te quedaría bien visitarlo? 📆"


============================================================
SALUDOS
============================================================

Si es el PRIMER mensaje del cliente y solamente dice:

"Hola"

"Buenas"

"Información"

"Info"

"Quiero información"


Puedes responder algo similar a:

"¡Hola! 👋 Soy Gabriel Polero asesor de multiproyectos dive.😊

Con gusto te ayudo. 🏡📍

¿En qué sector estás buscando lotes?"


IMPORTANTE:

NO vuelvas a decir:

"Soy Gabriel Polero"

en cada mensaje.

Solo preséntate cuando tenga sentido al inicio de la conversación.
 
y tampoco limites al cliente en el primer mensaje a un lugar o otro deja que el te diga en donde esta interesado




============================================================
RESPUESTAS A MENSAJES MUY CORTOS
============================================================

Si el cliente responde:

"Sí"

debes revisar qué pregunta hiciste anteriormente.

Ejemplo:

Gabriel:

"¿Quieres conocer el enganche de Buenaventura?"

Cliente:

"Sí"

Debes responder con el enganche de Buenaventura.


Si el cliente responde:

"Cuéntame"

debes continuar exactamente con el tema anterior.


============================================================
NO REPETIR INFORMACION
============================================================

Evita repetir datos que acabas de mencionar.

Si ya dijiste:

"Buenaventura está en el km 168"

no vuelvas a explicar toda la ubicación en el siguiente
mensaje si el cliente está preguntando por financiamiento.


============================================================
OBJETIVO PRINCIPAL
============================================================

Tu objetivo es que la conversación se sienta:

HUMANA
NATURAL
UTIL
RAPIDA
PROFESIONAL

Debes:

- recordar el contexto
- identificar correctamente el proyecto
- responder con precisión
- nunca mezclar proyectos
- nunca inventar información
- utilizar emojis naturalmente
- mantener la conversación activa
- detectar intención de compra
- llevar al cliente progresivamente hacia una visita,
  reserva o siguiente paso cuando corresponda

REGLA ABSOLUTA DE CONTINUIDAD:
- TODA respuesta que generes para el cliente debe terminar con EXACTAMENTE UNA pregunta breve y natural.
- La pregunta debe nacer de lo que el cliente acaba de decir y ayudar a avanzar la conversación.
- NO uses preguntas tipo menú si no hacen falta.
- NO repitas una pregunta que el cliente ya respondió.
- Primero resuelve completamente la duda actual y DESPUÉS haz la pregunta.
- Si el cliente cambió de decisión, adapta la pregunta a su nueva decisión.
- Si ya existe visita coordinada, no vuelvas a preguntar día u hora; haz una pregunta breve de servicio relacionada con su duda actual.

REGLA DE INTERVENCIÓN HUMANA AUTOMÁTICA:
- Si el cliente hace una pregunta INMOBILIARIA o comercial que no puedes responder con seguridad usando la información oficial y el historial, NO inventes ni adivines.
- Si la consulta es inusual y necesita criterio/confirmación humana (por ejemplo disponibilidad exacta no confirmada, excepción comercial, trámite no documentado, condición especial o dato que no aparece), coloca EXACTAMENTE esta marca en la primera línea:
[[REQUIERE_INTERVENCION]]
- Después de la marca escribe una respuesta breve y natural en primera persona, por ejemplo: "Permítame confirmarle ese detalle para darle la información correcta 😊. ¿Me permite revisarlo y le respondo enseguida?"
- La marca es interna y será eliminada antes de enviar el mensaje al cliente.
- NO uses la marca simplemente porque el cliente haga una pregunta ajena al negocio; en temas ajenos al negocio solo redirige brevemente al tema inmobiliario.
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


        raw_respuesta = str(respuesta.output_text or "").strip()
        marca_intervencion = "[[REQUIERE_INTERVENCION]]"
        requiere_intervencion = marca_intervencion in raw_respuesta

        # Red de seguridad: si la IA expresa explícitamente que debe confirmar un dato,
        # tratamos la conversación como intervención aunque haya olvidado la marca.
        raw_lower = normalizar_ventas(raw_respuesta)
        frases_incertidumbre = [
            "prefiero confirmar", "permitame confirmar", "permítame confirmar",
            "necesito confirmar", "voy a confirmar", "debo confirmar",
            "no tengo confirmado", "para darle la informacion correcta",
            "para darle la información correcta"
        ]
        if any(frase in raw_lower for frase in frases_incertidumbre):
            requiere_intervencion = True

        texto_limpio = raw_respuesta.replace(marca_intervencion, "").strip()
        if requiere_intervencion and not texto_limpio:
            texto_limpio = (
                "Permítame confirmarle ese detalle para darle la información correcta 😊. "
                "¿Me permite revisarlo y le respondo enseguida?"
            )

        texto_respuesta = asegurar_pregunta_final_ia(texto_limpio)

        if requiere_intervencion:
            marcar_intervencion_automatica(
                numero_cliente,
                mensaje_cliente,
                motivo="la IA indicó que requiere confirmación humana"
            )


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
        try:
            marcar_intervencion_automatica(
                numero_cliente,
                mensaje_cliente,
                motivo=f"error al generar respuesta: {type(error).__name__}"
            )
        except Exception as exc_intervencion:
            print("ERROR MARCANDO INTERVENCION TRAS OPENAI:", exc_intervencion)

        return (
            "Permítame confirmarle ese detalle para darle la información correcta 😊. "
            "¿Me permite revisarlo y le respondo enseguida?"
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

    return nombres.get(proyecto, "ningún proyecto definido todavía")


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
            "😄 Recibí el archivo. Este WhatsApp está enfocado en ayudarte "
            "con nuestros terrenos 🏡. ¿Deseas consultar precios, ubicación, "
            "financiamiento o algún proyecto?"
        )

    if clase == "AMBIGUA":
        return (
            "¡Gracias por enviármelo! 😊 ¿Qué deseas que revise de esta "
            "imagen o video? Puedo ayudarte si está relacionado con terrenos, "
            "cotizaciones, ubicación, pagos o documentos del proceso."
        )

    return contenido or (
        "¡Gracias por enviármelo! 😊 Cuéntame qué parte deseas revisar y "
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
Mensaje que el cliente escribió junto a la imagen: {pregunta or "NINGUNO"}

Tu trabajo es mirar la imagen y responder COMO EN WHATSAPP.

REGLA PRINCIPAL:
- Si el cliente hizo una pregunta junto a la imagen, RESPONDE SOLAMENTE ESA PREGUNTA.
- No describas toda la imagen.
- No enumeres todos los datos visibles si no te los preguntaron.
- Respuesta breve: idealmente 1 o 2 oraciones.
- Usa 1 o 2 emojis naturales.
- Sé seguro cuando el dato se ve claramente.
- Si el cliente propone un dato incorrecto, corrígelo directamente y da el valor correcto.
- No digas frases técnicas como "en la imagen se observa una cotización..." salvo que sea necesario.
- No agregues advertencias legales innecesarias. Solo aclara límites si el cliente pregunta por autenticidad o validez legal.
- No inventes cifras que no sean visibles.
- Si el cliente pide un dato inmobiliario que NO se ve con claridad y no puedes confirmarlo con seguridad, escribe [[REQUIERE_INTERVENCION]] en la primera línea y luego responde: "Permítame confirmarle ese detalle para darle la información correcta 😊. ¿Me permite revisarlo?"
- Trate SIEMPRE al cliente de USTED.
- Termine SIEMPRE con EXACTAMENTE UNA pregunta breve relacionada con lo que el cliente envió.
- Primero responda la duda de la imagen y después haga la pregunta.

Ejemplo:
Pregunta: "¿La cuota a 8 años es de Q1,000?"
Si en la imagen dice Q1,476:
Respuesta adecuada: "No 😊 La cuota a 8 años que aparece es de Q1,476 al mes. ¿Desea que revisemos otro plazo?"

SI NO HAY PREGUNTA/CAPTION:
- No hagas un resumen completo.
- Responde únicamente:
  "¡Recibí la imagen! 📷😊 ¿Qué desea que revise?"

SI LA IMAGEN ES CLARAMENTE AJENA A TERRENOS:
- Responde breve:
  "😄 Recibí la imagen. Este WhatsApp está enfocado en terrenos 🏡. ¿En qué puedo ayudarle sobre nuestros proyectos?"

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

        raw = str(respuesta.output_text or "").strip()
        marca = "[[REQUIERE_INTERVENCION]]"
        requiere = marca in raw
        texto = asegurar_pregunta_final_ia(raw.replace(marca, "").strip())

        if requiere:
            marcar_intervencion_automatica(
                numero,
                pregunta or "Consulta relacionada con una imagen recibida",
                motivo="la imagen no permite confirmar el dato con seguridad"
            )

        if not texto:
            return "¡Recibí la imagen! 📷😊 ¿Qué desea que revise?"

        return texto

    except Exception as error:
        print("ERROR ANALIZANDO IMAGEN:")
        print(error)
        return "¡Recibí la imagen! 📷😊 ¿Qué desea que revise?"



def extraer_frames_video(video_bytes, cantidad=3):
    try:
        import cv2
    except ImportError:
        print("opencv-python NO está instalado.")
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
        return "¡Recibí el video! 🎥😊 ¿Qué desea que revise?"

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
- Máximo 2 oraciones normalmente.
- Usa 1 o 2 emojis naturales.
- No describas todo el video ni enumeres detalles que no pidió.
- No inventes datos.
- Si el cliente pide un dato inmobiliario que NO puede confirmarse con seguridad usando los fotogramas, escribe [[REQUIERE_INTERVENCION]] en la primera línea y luego una respuesta breve pidiendo tiempo para confirmarlo.
- Trate SIEMPRE al cliente de USTED.
- Termine SIEMPRE con EXACTAMENTE UNA pregunta breve relacionada con el video o con el siguiente paso comercial.
- Primero responda la duda y después haga la pregunta.
- Si no hizo ninguna pregunta, responde:
  "¡Recibí el video! 🎥😊 ¿Qué desea que revise?"
- Si el video es claramente ajeno a terrenos, redirige brevemente al tema inmobiliario y termina con una pregunta.

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

        raw = str(respuesta.output_text or "").strip()
        marca = "[[REQUIERE_INTERVENCION]]"
        requiere = marca in raw
        texto = asegurar_pregunta_final_ia(raw.replace(marca, "").strip())
        if requiere:
            marcar_intervencion_automatica(
                numero,
                pregunta or "Consulta relacionada con un video recibido",
                motivo="el video no permite confirmar el dato con seguridad"
            )
        return texto or "¡Recibí el video! 🎥😊 ¿Qué desea que revise?"

    except Exception as error:
        print("ERROR ANALIZANDO VIDEO:")
        print(error)
        return "¡Recibí el video! 🎥😊 ¿Qué desea que revise?"



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
                    "Conversación inmobiliaria en Guatemala. "
                    "Nombres frecuentes: Gabriel Polero, Palmeras San Miguel, "
                    "Vista Hermosa, Buenaventura Cuyotenango, Retalhuleu, "
                    "Cuyotenango, lotes, enganche, cuotas, financiamiento, "
                    "escrituración y plusvalía."
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

        # Si el cliente viene de escoger topografía y manda una captura de un lote,
        # podemos responder con la regla oficial del proyecto.
        if estado_topografia.get("topografia_en_conversacion"):
            if proyecto_topografia in {"palmeras", "buenaventura"} and not caption:
                return (
                    "Perfecto 😊 Recibí la captura. En este proyecto los lotes se "
                    "manejan en topografía plana. Si me escribes también el número "
                    "del lote, te ayudo a seguir revisando esa opción. 🏡"
                )

            if proyecto_topografia == "vista_hermosa" and not caption:
                marcar_intervencion_automatica(
                    numero,
                    "Confirmar la topografía exacta del lote mostrado en la captura de Vista Hermosa",
                    motivo="topografía exacta no confirmada"
                )
                return (
                    "Perfecto 😊 Recibí la captura. En Vista Hermosa hay lotes planos "
                    "y quebrados, así que para darle seguridad prefiero confirmar la "
                    "topografía exacta de esa opción. ¿Me permite revisarlo y le respondo enseguida?"
                )

        archivo, mime = obtener_media_whatsapp(
            media_id
        )

        if not archivo:
            return (
                "Recibí tu imagen 😊, pero no pude abrirla en este momento. "
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
                "Recibí tu video 🎥, pero no pude abrirlo en este momento. "
                "Puedes intentar enviarlo nuevamente."
            )

        return analizar_video_cliente(
            numero,
            archivo,
            caption=caption
        )

    if tipo_mensaje == "document":
        return (
            "Recibí el documento 📄😊. Si necesitas que revise algo específico, "
            "puedes enviarme una captura de la parte que deseas consultar."
        )

    return (
        "Recibí tu archivo 😊. Para ayudarte mejor, escríbeme qué deseas "
        "consultar sobre terrenos, precios, ubicación o financiamiento."
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

def enviar_whatsapp(numero, texto, formalizar=True):
    """
    Envía UN mensaje únicamente como respuesta a un mensaje entrante.
    Esta función no programa seguimientos ni mensajes futuros.
    """

    if formalizar:
        texto = formalizar_trato_usted(texto)

    # MISMA LÓGICA, DISTINTO CANAL: todo el motor sigue llamando a enviar_whatsapp(),
    # pero un contacto fb:<psid> sale por Messenger sin tocar la lógica comercial.
    if crm_es_facebook(numero):
        return enviar_messenger_texto(numero, texto, formalizar=False)

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
            return True
        return False


    except Exception as error:

        print("\nERROR ENVIANDO WHATSAPP:")
        print(error)
        return False




# ============================================================
# ENVIAR DOCUMENTOS PUBLICOS POR URL (PLANOS)
# ============================================================

def enviar_documento_url_whatsapp(numero, url_documento, nombre_archivo, caption=""):
    """
    Envía un PDF público directamente mediante WhatsApp Cloud API.
    Se agrega un parámetro de versión para pedir siempre la copia más reciente
    cuando el plano se reemplaza en GitHub Pages conservando el mismo nombre.
    """
    caption = formalizar_trato_usted(caption)
    if crm_es_facebook(numero):
        return enviar_messenger_adjunto_url(
            numero,
            "file",
            url_documento,
            caption=caption or nombre_archivo
        )

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
    """Envía el/los planos correspondientes y SIEMPRE termina con la leyenda de colores."""
    planos = seleccionar_planos(proyecto, texto_cliente)

    if not planos:
        enviar_whatsapp(
            numero,
            "Claro 😊 ¿De qué proyecto deseas que te envíe el plano: Palmeras San Miguel, Vista Hermosa o Buenaventura Cuyotenango?"
        )
        return False

    nombre = nombre_proyecto_plano(proyecto)
    if len(planos) == 1:
        intro = f"¡Claro! 😊 Te comparto el plano actualizado de {planos[0]['nombre']}."
    else:
        intro = f"¡Claro! 😊 Te comparto los planos disponibles de {nombre}."

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

    # La explicación de colores debe acompañar SIEMPRE cualquier envío de planos.
    enviar_whatsapp(numero, texto_leyenda_planos())

    # Después de cualquier plano, abrimos la conversación sobre topografía
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
    Sube una imagen a Meta y luego la envía al número indicado.
    """
    caption = formalizar_trato_usted(caption)
    if crm_es_facebook(numero):
        url_publica = url_publica_media_messenger(ruta_imagen)
        if not url_publica:
            print("MESSENGER: no se pudo crear URL pública para", ruta_imagen)
            return False
        return enviar_messenger_adjunto_url(numero, "image", url_publica, caption=caption)

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
    caption = formalizar_trato_usted(caption)
    if crm_es_facebook(numero):
        url_publica = url_publica_media_messenger(ruta_video)
        if not url_publica:
            print("MESSENGER: no se pudo crear URL pública para", ruta_video)
            return False
        return enviar_messenger_adjunto_url(numero, "video", url_publica, caption=caption)

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
    Envía el material que el cliente pidió y respeta el proyecto activo.

    Reglas:
    - si pide fotos, manda fotos;
    - si pide videos, manda videos;
    - si pide ambos, manda ambos;
    - máximo 4 fotos y 2 videos por solicitud para no saturar;
    - si no hay fotos cargadas pero sí videos, se ofrece/envía el video como alternativa;
    - siempre termina con una pregunta para mantener viva la conversación.
    """
    if not proyecto:
        marcar_multimedia_pendiente(numero)
        enviar_whatsapp(
            numero,
            "Claro 😊 ¿De cuál proyecto desea ver fotos o videos: Palmeras San Miguel, Vista Hermosa o Buenaventura Cuyotenango?"
        )
        return False

    limpiar_multimedia_pendiente(numero)

    nombres = {
        "palmeras": "Palmeras San Miguel",
        "vista_hermosa": "Vista Hermosa",
        "buenaventura": "Buenaventura Cuyotenango"
    }
    nombre = nombres.get(proyecto, "el proyecto")

    fotos = IMAGENES_PROYECTOS.get(proyecto, [])
    fotos_disponibles = [r for r in fotos if os.path.exists(r)][:4]

    videos = VIDEOS_PROYECTOS.get(proyecto, [])
    videos_disponibles = [r for r in videos if os.path.exists(r)][:2]

    # Vista Hermosa actualmente no tiene fotos generales habilitadas en la lista.
    # Si el cliente pide fotos y no existen, no ignoramos la petición: le explicamos
    # brevemente y le mostramos los videos reales ya cargados del proyecto.
    if enviar_fotos and not fotos_disponibles and videos_disponibles and not enviar_videos:
        enviar_whatsapp(
            numero,
            f"En este momento no tengo fotos generales habilitadas de *{nombre}*, pero sí tengo videos del proyecto 😊. Se los comparto para que pueda conocerlo mejor."
        )
        enviar_videos = True

    if enviar_fotos and fotos_disponibles:
        enviar_whatsapp(
            numero,
            f"Claro 😊 Le comparto algunas fotos de *{nombre}* para que pueda conocer mejor el proyecto 🏡📸"
        )
        for i, ruta in enumerate(fotos_disponibles, start=1):
            enviar_imagen_whatsapp(
                numero,
                ruta,
                caption=f"{nombre} 🏡📸" if i == 1 else ""
            )
    elif enviar_fotos and not fotos_disponibles and not enviar_videos:
        enviar_whatsapp(
            numero,
            f"En este momento no tengo fotos cargadas de *{nombre}* para enviarlas automáticamente."
        )

    if enviar_videos:
        if videos_disponibles:
            enviar_whatsapp(
                numero,
                f"Claro 🎥 Le comparto videos de *{nombre}* para que pueda conocer mejor el proyecto 🏡"
            )
            for i, ruta in enumerate(videos_disponibles, start=1):
                enviar_video_whatsapp(
                    numero,
                    ruta,
                    caption=f"{nombre} 🎥🏡" if i == 1 else ""
                )
        else:
            enviar_whatsapp(
                numero,
                f"En este momento no tengo videos cargados de *{nombre}* para enviarlos automáticamente."
            )

    # Las amenidades se muestran en video únicamente cuando el cliente pidió videos
    # (o cuando videos fue el fallback porque no había fotos habilitadas).
    if enviar_videos:
        enviar_paquete_amenidades(numero, proyecto)

    enviar_whatsapp(
        numero,
        "¿Desea que le muestre también los precios y las formas de pago disponibles? 😊"
    )
    return True

def enviar_solo_fotos_del_proyecto(numero, proyecto):
    """
    Se usa después de enviar cotizaciones por precio:
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
        f"Y para que conozcas mejor {nombre}, te comparto también "
        "las fotos del proyecto 🏡📸"
    )

    # Después de precios enviamos máximo 4 fotos.
    for i, ruta in enumerate(fotos_disponibles[:4], start=1):
        caption = f"{nombre} 🏡📸" if i == 1 else ""
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
    Se usa después de enviar cotizaciones cuando el proyecto es Vista Hermosa.
    Envía únicamente videos generales del proyecto, sin fotos y sin amenidades.
    Las amenidades se envían después en su propio bloque.
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
        f"Y para que conozcas mejor {nombre}, te comparto también "
        "videos del proyecto 🏡🎥"
    )

    for i, ruta in enumerate(videos_disponibles, start=1):
        enviar_video_whatsapp(
            numero,
            ruta,
            caption=f"{nombre} 🎥🏡" if i == 1 else ""
        )

def enviar_cotizacion_del_proyecto(numero, proyecto, medida=None):
    """
    FLUJO DEFINITIVO PARA PRECIOS:
    1. Si ya existe proyecto activo, NO pregunta proyecto ni medida.
    2. Manda una explicación breve del proyecto con amenidades/servicios.
    3. Manda TODAS las imágenes de cotización del proyecto.
    4. Termina con un CTA corto.
    """

    if not proyecto:
        enviar_whatsapp(
            numero,
            "¡Claro! 😊 ¿En qué proyecto estás interesado para enviarte "
            "las cotizaciones correctas? 🏡"
        )
        return

    resumen = construir_resumen_cotizacion(proyecto)

    if resumen:
        enviar_whatsapp(numero, resumen)

    opciones = COTIZACIONES_IMAGEN.get(proyecto, {})
    rutas_a_enviar = []

    # Si el cliente indicó una medida concreta, manda únicamente esa medida.
    # Si no indicó medida, manda todas las opciones disponibles del proyecto.
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
            "En este momento no tengo cargadas las imágenes de cotización. "
            "Déjame revisarlas para darte la información correcta 👍"
        )
        return

    for medida_nombre, ruta in rutas_a_enviar:
        caption = ETIQUETAS_COTIZACIONES.get(
            proyecto,
            {}
        ).get(
            ruta,
            f"Cotización {medida_nombre} 💰"
        )

        enviar_imagen_whatsapp(
            numero,
            ruta,
            caption=caption
        )

    # FLUJO VISUAL DESPUÉS DE PRECIOS/COTIZACIONES:
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
        "Si alguna opción te llama la atención, dime cuál 😊 y con gusto te doy "
        "más información o resolvemos cualquier duda que tengas 🏡"
    )

# ============================================================
# SEGUIMIENTO AUTOMATICO CONTEXTUAL - 10 MIN + 1 / 3 / 5 / 7
# ============================================================
# 10 minutos y Día 1 se envían dentro de la ventana normal de WhatsApp.
# Para Día 3 / 5 / 7, WhatsApp exige plantillas aprobadas por Meta.
# Si las variables de entorno no están configuradas, esos envíos se omiten
# de forma segura y quedan registrados en los logs de Render.

SEGUIMIENTO_10_MIN = 10 * 60
SEGUIMIENTO_DIA1 = 23 * 60 * 60  # 23h para permanecer dentro de la ventana de 24h.
SEGUIMIENTO_DIA3_ESPERA = 2 * 24 * 60 * 60
SEGUIMIENTO_DIA5_ESPERA = 2 * 24 * 60 * 60
SEGUIMIENTO_DIA7_ESPERA = 2 * 24 * 60 * 60

WA_TEMPLATE_LANGUAGE = os.getenv("WA_TEMPLATE_LANGUAGE", "es").strip() or "es"
WA_TEMPLATE_SEGUIMIENTO_DIA3 = os.getenv("WA_TEMPLATE_SEGUIMIENTO_DIA3", "").strip()
WA_TEMPLATE_SEGUIMIENTO_DIA5 = os.getenv("WA_TEMPLATE_SEGUIMIENTO_DIA5", "").strip()
WA_TEMPLATE_SEGUIMIENTO_DIA7 = os.getenv("WA_TEMPLATE_SEGUIMIENTO_DIA7", "").strip()

seguimiento_version = {}
lock_seguimiento = Lock()


def cancelar_seguimiento(numero):
    """Invalida cualquier seguimiento pendiente de ese cliente."""
    if not numero:
        return
    with lock_seguimiento:
        seguimiento_version[numero] = seguimiento_version.get(numero, 0) + 1


def _seguimiento_debe_detenerse(numero, version):
    with lock_seguimiento:
        if seguimiento_version.get(numero) != version:
            return True

    if crm_esta_manual(numero):
        return True
    if cita_ya_cerrada(numero):
        return True

    meta = crm_obtener_meta(numero)
    if meta.get("etapa") in {"Venta", "Reserva", "Perdido"}:
        return True

    estado = obtener_estado_conversacion(numero)
    if estado.get("requiere_intervencion_ia") or estado.get("esperando_respuesta_gabriel"):
        return True
    if estado.get("palmeras_esperando_gabriel") or estado.get("palmeras_requiere_intervencion"):
        return True
    return False


def _seguimiento_contexto(numero):
    estado = obtener_estado_conversacion(numero)
    proyecto = estado.get("proyecto_actual") or proyecto_activo.get(numero)
    nombres = {
        "palmeras": "Palmeras San Miguel",
        "buenaventura": "Buenaventura Cuyotenango",
        "vista_hermosa": "Vista Hermosa",
    }
    return proyecto, nombres.get(proyecto, "el proyecto"), estado


def _mensaje_seguimiento_contextual(numero, momento="10m"):
    proyecto, nombre, estado = _seguimiento_contexto(numero)
    pendiente = str(estado.get("psm_pregunta_pendiente") or "").lower() if proyecto == "palmeras" else ""

    if momento == "10m":
        if proyecto == "palmeras":
            if "fase" in pendiente:
                return (
                    "Quedó pendiente saber cuál de las dos fases le parece más atractiva 😊. "
                    "¿Le interesa más *Fase 1* o *Fase 2*?"
                )
            if "plan" in pendiente or "modalidad" in pendiente or "forma de pago" in pendiente:
                return (
                    "Quedó pendiente la forma de pago 😊. "
                    "¿Le gustaría revisar *financiamiento*, *1 año sin intereses* o *contado*?"
                )
            if "visita" in pendiente or "dia" in pendiente or "día" in pendiente or "hora" in pendiente:
                return (
                    "Quedó pendiente coordinar su visita a *Palmeras San Miguel* 😊. "
                    "¿Qué día le quedaría bien?"
                )
            if "reaccion" in pendiente or "propuesta" in pendiente:
                return "¿Qué le pareció la propuesta que le compartí? 😊"
        return (
            f"Quedó pendiente nuestra conversación sobre *{nombre}* 😊. "
            "¿Desea que continuemos desde donde quedamos?"
        )

    # Día 1: retoma la conversación sin repetir todo el catálogo.
    if proyecto == "palmeras":
        if "fase" in pendiente:
            return (
                "¡Hola! 👋 Ayer dejamos pendiente cuál fase de *Palmeras San Miguel* le interesaba más. "
                "¿Desea que continuemos con Fase 1 o Fase 2? 😊"
            )
        if "plan" in pendiente or "modalidad" in pendiente or "forma de pago" in pendiente:
            return (
                "¡Hola! 👋 Ayer dejamos pendiente revisar la forma de pago que mejor se adapte a usted en *Palmeras San Miguel*. "
                "¿Desea que retomemos las opciones? 😊"
            )
        if "visita" in pendiente or "dia" in pendiente or "día" in pendiente or "hora" in pendiente:
            return (
                "¡Hola! 👋 Ayer quedó pendiente coordinar su visita a *Palmeras San Miguel*. "
                "¿Qué día le quedaría cómodo para conocerlo? 😊"
            )
    return (
        f"¡Hola! 👋 Ayer dejamos pendiente la información de *{nombre}*. "
        "¿Desea que retomemos la conversación desde donde quedamos? 😊"
    )


def enviar_template_whatsapp(numero, template_name):
    """Envía una plantilla aprobada por Meta para seguimientos fuera de 24 horas."""
    if not template_name or crm_es_facebook(numero):
        return False

    url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": WA_TEMPLATE_LANGUAGE},
        },
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        print("SEGUIMIENTO TEMPLATE", template_name, "STATUS:", r.status_code, r.text)
        if 200 <= r.status_code < 300:
            crm_registrar_mensaje(numero, "out", f"📨 Seguimiento automático: {template_name}")
            return True
    except Exception as exc:
        print("SEGUIMIENTO TEMPLATE ERROR:", exc)
    return False


def _enviar_seguimiento_libre(numero, texto):
    if not texto:
        return False
    ok = enviar_whatsapp(numero, texto)
    if ok:
        guardar_mensaje(numero, "assistant", texto)
    return ok


def programar_seguimiento_inactividad(numero):
    """
    Cadencia global tras quedar el CLIENTE pendiente de responder:
    - 10 minutos: recordatorio contextual.
    - Día 1: seguimiento contextual dentro de 24h.
    - Día 3 / 5 / 7: plantilla aprobada por Meta, si está configurada.

    Cualquier mensaje nuevo del cliente cancela la secuencia anterior.
    También se detiene si Gabriel toma control manual, hay visita cerrada,
    reserva/venta/perdido o el bot está esperando intervención humana.
    """
    if not numero:
        return

    # No iniciar seguimientos si ya estamos esperando a Gabriel.
    estado = obtener_estado_conversacion(numero)
    if estado.get("requiere_intervencion_ia") or estado.get("esperando_respuesta_gabriel"):
        return

    with lock_seguimiento:
        version = seguimiento_version.get(numero, 0) + 1
        seguimiento_version[numero] = version

    def esperar_y_enviar():
        time.sleep(SEGUIMIENTO_10_MIN)
        if _seguimiento_debe_detenerse(numero, version):
            return
        _enviar_seguimiento_libre(numero, _mensaje_seguimiento_contextual(numero, "10m"))

        # Total aproximado: 23h desde que se programó.
        time.sleep(max(0, SEGUIMIENTO_DIA1 - SEGUIMIENTO_10_MIN))
        if _seguimiento_debe_detenerse(numero, version):
            return
        _enviar_seguimiento_libre(numero, _mensaje_seguimiento_contextual(numero, "dia1"))

        # Día 3: requiere plantilla aprobada.
        time.sleep(SEGUIMIENTO_DIA3_ESPERA)
        if _seguimiento_debe_detenerse(numero, version):
            return
        if WA_TEMPLATE_SEGUIMIENTO_DIA3:
            enviar_template_whatsapp(numero, WA_TEMPLATE_SEGUIMIENTO_DIA3)
        else:
            print("SEGUIMIENTO DIA 3 OMITIDO: falta WA_TEMPLATE_SEGUIMIENTO_DIA3")

        # Día 5.
        time.sleep(SEGUIMIENTO_DIA5_ESPERA)
        if _seguimiento_debe_detenerse(numero, version):
            return
        if WA_TEMPLATE_SEGUIMIENTO_DIA5:
            enviar_template_whatsapp(numero, WA_TEMPLATE_SEGUIMIENTO_DIA5)
        else:
            print("SEGUIMIENTO DIA 5 OMITIDO: falta WA_TEMPLATE_SEGUIMIENTO_DIA5")

        # Día 7.
        time.sleep(SEGUIMIENTO_DIA7_ESPERA)
        if _seguimiento_debe_detenerse(numero, version):
            return
        if WA_TEMPLATE_SEGUIMIENTO_DIA7:
            enviar_template_whatsapp(numero, WA_TEMPLATE_SEGUIMIENTO_DIA7)
        else:
            print("SEGUIMIENTO DIA 7 OMITIDO: falta WA_TEMPLATE_SEGUIMIENTO_DIA7")

        with lock_seguimiento:
            if seguimiento_version.get(numero) == version:
                seguimiento_version[numero] = version + 1

    Thread(target=esperar_y_enviar, daemon=True).start()


# ============================================================
# AGRUPAR MENSAJES SEGUIDOS DEL CLIENTE
# ============================================================

# Esperamos 8 segundos DE SILENCIO desde el último mensaje de texto.
# Cada mensaje nuevo reinicia de forma natural la ventana porque el worker
# vuelve a calcular el tiempo restante usando la hora del último mensaje.
ESPERA_BLOQUE_MENSAJES_SEGUNDOS = 8
MAX_MENSAJES_POR_BLOQUE = 20

# numero -> [{"id", "texto", "mensaje", "recibido_en"}, ...]
mensajes_texto_pendientes = {}
# Números que ya tienen un worker encargado de sus mensajes.
workers_texto_activos = set()
lock_mensajes_texto_pendientes = Lock()


def _texto_de_mensaje(mensaje):
    if not mensaje or mensaje.get("type") != "text":
        return ""
    return str((mensaje.get("text") or {}).get("body") or "").strip()


def acumular_mensaje_texto(numero, message_id, mensaje):
    """
    Encola un mensaje de texto y garantiza UN solo worker por cliente.

    El worker:
    - espera 8 s desde el último mensaje;
    - une todos los textos de la tanda en orden;
    - procesa la tanda como una sola entrada;
    - si llegan más mensajes mientras el bot responde, los deja para una
      segunda tanda y NO los pierde.
    """
    if not numero or not message_id or not mensaje:
        return False

    texto = _texto_de_mensaje(mensaje)
    if not texto:
        return False

    iniciar_worker = False

    with lock_mensajes_texto_pendientes:
        lista = mensajes_texto_pendientes.setdefault(numero, [])
        lista.append({
            "id": message_id,
            "texto": texto,
            # Copia superficial suficiente: solo necesitamos los campos del
            # mensaje para construir luego un payload de texto equivalente.
            "mensaje": dict(mensaje),
            "recibido_en": time.monotonic(),
        })

        # Protección de RAM ante una conversación anormalmente larga.
        if len(lista) > MAX_MENSAJES_POR_BLOQUE:
            mensajes_texto_pendientes[numero] = lista[-MAX_MENSAJES_POR_BLOQUE:]

        if numero not in workers_texto_activos:
            workers_texto_activos.add(numero)
            iniciar_worker = True

    if iniciar_worker:
        Thread(
            target=_worker_bloques_texto,
            args=(numero,),
            daemon=True
        ).start()

    return True


def _construir_payload_bloque_texto(numero, pendientes):
    """Crea un payload compatible con el procesador existente usando toda la tanda."""
    textos = [
        str(item.get("texto") or "").strip()
        for item in pendientes
        if str(item.get("texto") or "").strip()
    ]

    if not textos:
        return None, None

    ultimo = pendientes[-1]
    message_id = ultimo.get("id")
    mensaje_base = dict(ultimo.get("mensaje") or {})
    mensaje_base["from"] = numero
    mensaje_base["id"] = message_id
    mensaje_base["type"] = "text"
    mensaje_base["text"] = {"body": "\n".join(textos)}
    # Marca interna: indica que el texto YA pasó por el agrupador.
    mensaje_base["_texto_agrupado"] = True

    datos_bloque = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [mensaje_base]
                }
            }]
        }]
    }

    return datos_bloque, message_id


def _worker_bloques_texto(numero):
    """
    Worker secuencial por cliente.

    Mientras este worker procesa una tanda, los mensajes nuevos continúan
    acumulándose. Al terminar, vuelve al principio y procesa la siguiente tanda.
    De esta forma no existen dos respuestas del bot compitiendo para el mismo
    cliente y no se descartan mensajes que llegaron mientras la IA respondía.
    """
    try:
        while True:
            # 1) Esperar hasta completar 8 s de silencio real.
            while True:
                with lock_mensajes_texto_pendientes:
                    pendientes_actuales = mensajes_texto_pendientes.get(numero) or []

                    if not pendientes_actuales:
                        workers_texto_activos.discard(numero)
                        return

                    recibido_en = pendientes_actuales[-1].get("recibido_en", time.monotonic())

                restante = ESPERA_BLOQUE_MENSAJES_SEGUNDOS - (
                    time.monotonic() - recibido_en
                )

                if restante <= 0:
                    break

                # Dormimos como máximo 1 s para reaccionar con precisión si
                # llega otro mensaje y la ventana debe extenderse.
                time.sleep(min(restante, 1.0))

            # 2) Sacar SOLO la tanda que quedó lista. Los mensajes nuevos que
            # lleguen desde este punto se guardarán en una lista nueva.
            with lock_mensajes_texto_pendientes:
                pendientes = mensajes_texto_pendientes.pop(numero, [])

            if not pendientes:
                continue

            datos_bloque, message_id = _construir_payload_bloque_texto(
                numero,
                pendientes
            )

            if not datos_bloque or not message_id:
                continue

            textos_debug = [p.get("texto", "") for p in pendientes]
            print("\n========================================")
            print("BLOQUE DE MENSAJES LISTO")
            print("========================================")
            print("CLIENTE:", numero)
            print("MENSAJES AGRUPADOS:", len(textos_debug))
            print("TEXTO AGRUPADO:")
            print("\n".join(textos_debug))

            # Este batch pasa a ser el procesamiento vigente. Los mensajes de
            # texto que lleguen mientras se responde NO cambian este id; quedan
            # esperando para la siguiente vuelta del worker.
            iniciar_procesamiento(numero, message_id)
            procesar_mensaje_en_segundo_plano(datos_bloque, message_id)

            # 3) Al volver del procesador repetimos el ciclo. Si durante la
            # respuesta entraron nuevos mensajes, serán la siguiente tanda.

    except Exception as error:
        print("ERROR EN WORKER DE MENSAJES AGRUPADOS:", numero, error)

    finally:
        # Liberación segura. Si un mensaje entró justo antes de liberar el worker,
        # arrancamos uno nuevo para que jamás quede una cola huérfana.
        reiniciar = False
        with lock_mensajes_texto_pendientes:
            workers_texto_activos.discard(numero)
            if mensajes_texto_pendientes.get(numero):
                workers_texto_activos.add(numero)
                reiniciar = True

        if reiniciar:
            Thread(
                target=_worker_bloques_texto,
                args=(numero,),
                daemon=True
            ).start()




# ============================================================
# PALMERAS SAN MIGUEL - FLUJO COMERCIAL HUMANO / PROGRESIVO
# ============================================================

PSM_FASES = {
    "fase_1": {
        "nombre": "Fase 1",
        "precio": 67200,
        "precio_texto": "Q67,200",
        "enganche": 6000,
        "amenidad": "piscina y área verde",
        "imagen_cotizacion": "media/cotizaciones/palmeras/8x16_no_esquina.jpeg",
    },
    "fase_2": {
        "nombre": "Fase 2",
        "precio": 70400,
        "precio_texto": "Q70,400",
        "enganche": 6000,
        "amenidad": "área verde",
        "imagen_cotizacion": "media/cotizaciones/palmeras/8x16_segunda_fase.jpeg",
    },
}

PSM_PLANES_IMAGEN = {
    "fase_1": {
        "financiamiento": "media/cotizaciones/palmeras_nuevo/fase1_financiamiento.png",
        "sin_intereses": "media/cotizaciones/palmeras_nuevo/fase1_semicontado.png",
        "contado": "media/cotizaciones/palmeras_nuevo/fase1_contado.png",
    },
    "fase_2": {
        "financiamiento": "media/cotizaciones/palmeras_nuevo/fase2_financiamiento.png",
        "sin_intereses": "media/cotizaciones/palmeras_nuevo/fase2_semicontado.png",
        "contado": "media/cotizaciones/palmeras_nuevo/fase2_contado.png",
    },
}


PSM_CUOTAS_FINANCIAMIENTO = {
    "fase_1": {
        2: 3026.26, 3: 2181.31, 4: 1766.17, 5: 1521.20,
        6: 1361.30, 7: 1251.28, 8: 1170.60,
    },
    "fase_2": {
        2: 3184.50, 3: 2295.37, 4: 1858.52, 5: 1600.74,
        6: 1432.48, 7: 1316.71, 8: 1231.81,
    },
}

PSM_RECORDATORIO_PLAN_SEGUNDOS = 10 * 60


def _inicializar_estado_psm(estado):
    estado.setdefault("psm_etapa", None)
    estado.setdefault("psm_fase", None)
    estado.setdefault("psm_plan", None)
    estado.setdefault("psm_plazo", None)
    estado.setdefault("psm_cotizacion_enviada", False)
    estado.setdefault("psm_video_amenidades_enviado", False)
    estado.setdefault("psm_pregunta_pendiente", None)
    estado.setdefault("psm_visita_ofrecida", False)
    estado.setdefault("psm_recordatorio_token", None)
    return estado


def estado_psm(numero):
    return _inicializar_estado_psm(obtener_estado_conversacion(numero))


def invalidar_recordatorio_psm(numero):
    estado = estado_psm(numero)
    if estado.get("psm_recordatorio_token"):
        estado["psm_recordatorio_token"] = None
        persistir_cliente(numero)


def programar_recordatorio_plan_psm(numero):
    """
    Compatibilidad con el flujo PSM. El recordatorio de 10 minutos ahora lo
    gestiona la cadencia global 10m + 1/3/5/7 para evitar mensajes duplicados.
    """
    estado = estado_psm(numero)
    estado["psm_recordatorio_token"] = None
    persistir_cliente(numero)
    return True


def detectar_fase_psm(texto):
    t = normalizar_texto_topografia(texto)
    if any(x in t for x in [
        "las dos", "ambas", "las 2", "cualquiera", "quiero comparar"
    ]):
        return "ambas"
    if any(x in t for x in [
        "fase 1", "fase1", "fase uno", "primera fase", "la primera",
        "67200", "67,200", "la de piscina", "con piscina"
    ]):
        return "fase_1"
    if any(x in t for x in [
        "fase 2", "fase2", "fase dos", "segunda fase", "la segunda",
        "70400", "70,400", "la de area verde", "solo area verde"
    ]):
        return "fase_2"
    return None


def detectar_plan_psm(texto):
    t = normalizar_texto_topografia(texto)
    if any(x in t for x in ["las tres", "los tres", "las 3", "todos", "todas", "ver las tres"]):
        return "todos"
    if any(x in t for x in [
        "sin intereses", "sin interes", "1 ano", "un ano", "11 cuotas",
        "semicontado", "semi contado"
    ]):
        return "sin_intereses"
    if any(x in t for x in ["contado", "de contado", "un solo pago", "pago completo"]):
        return "contado"
    if any(x in t for x in [
        "financiamiento", "financiado", "cuotas", "mensualidades", "credito",
        "2 anos", "3 anos", "4 anos", "5 anos", "6 anos", "7 anos", "8 anos"
    ]):
        return "financiamiento"
    return None




def interpretar_decision_psm_ia(numero, texto, estado):
    """
    Interpreta respuestas humanas cortas cuando un cliente no usa las palabras
    exactas del menú. NO reemplaza los detectores seguros; solo ayuda cuando
    existe una decisión pendiente de Palmeras.

    Ejemplos que puede entender:
    - "la más barata" -> Fase 1
    - "la que tiene piscina" -> Fase 1
    - "quiero la que me deje menor cuota" -> financiamiento
    - "muéstreme las opciones" -> todos
    - "unos cinco" cuando se esperaba plazo -> 5 años
    - "esa me sirve" después de propuesta -> reacción positiva
    """
    texto = str(texto or "").strip()
    if not texto:
        return None

    etapa = str((estado or {}).get("psm_etapa") or "")
    pendiente = str((estado or {}).get("psm_pregunta_pendiente") or "")

    if etapa not in {
        "esperando_fase", "esperando_plan", "esperando_plazo",
        "propuesta_enviada", "esperando_reaccion_propuesta"
    } and pendiente not in {
        "fase", "plan_pago", "plazo_financiamiento", "reaccion_propuesta"
    }:
        return None

    opciones = {
        "esperando_fase": "fase_1, fase_2, ambas, ninguna",
        "esperando_plan": "financiamiento, sin_intereses, contado, todos, ninguna",
        "esperando_plazo": "plazo_2, plazo_3, plazo_4, plazo_5, plazo_6, plazo_7, plazo_8, ninguna",
        "propuesta_enviada": "positivo, comparar, visita, reserva, ninguna",
        "esperando_reaccion_propuesta": "positivo, comparar, visita, reserva, ninguna",
    }.get(etapa, "ninguna")

    prompt = f"""
Clasifique UNA respuesta de un cliente inmobiliario de Palmeras San Miguel.

Estado actual: {etapa or 'sin etapa'}
Pregunta pendiente: {pendiente or 'ninguna'}
Fase guardada: {(estado or {}).get('psm_fase') or 'ninguna'}
Plan guardado: {(estado or {}).get('psm_plan') or 'ninguno'}
Mensaje del cliente: {texto}

Responda SOLO con una de estas etiquetas:
{opciones}

Reglas:
- No invente una decisión si el mensaje realmente es una pregunta distinta.
- "la más económica", "la de menor precio" durante selección de fase = fase_1.
- "la de piscina" = fase_1; "la otra", si ya se compararon las dos y habla del área verde = fase_2.
- Si pide ver/comparar las tres formas de pago = todos.
- Si busca pagos mensuales cómodos o pagar poco a poco = financiamiento.
- Si dice un número 2..8 mientras se espera plazo, clasifique plazo_N aunque no escriba "años".
- Si después de una propuesta dice que le gusta, le sirve, le interesa o está de acuerdo = positivo.
- Si quiere conocer/ver/ir al proyecto = visita.
- Si quiere apartar/comprar/reservar = reserva.
- Ante duda, responda ninguna.
"""
    try:
        r = client.responses.create(
            model="gpt-5-mini",
            instructions="Clasifique la intención. Devuelva únicamente una etiqueta permitida, sin explicación.",
            input=[{"role": "user", "content": prompt}]
        )
        etiqueta = (r.output_text or "").strip().lower()
        permitidas = {
            "fase_1", "fase_2", "ambas",
            "financiamiento", "sin_intereses", "contado", "todos",
            "plazo_2", "plazo_3", "plazo_4", "plazo_5", "plazo_6", "plazo_7", "plazo_8",
            "positivo", "comparar", "visita", "reserva", "ninguna"
        }
        return etiqueta if etiqueta in permitidas else None
    except Exception as exc:
        print("ERROR INTERPRETANDO DECISION PSM:", exc)
        return None


def es_reaccion_positiva_propuesta_psm(texto):
    t = normalizar_texto_topografia(texto)
    frases = [
        "me interesa", "me sirve", "me gusta", "me parece bien", "esta bien",
        "me conviene", "esa opcion", "esa me gusta", "esa me sirve", "quiero esa",
        "si me interesa", "si esta bien", "perfecto", "excelente", "me parece"
    ]
    return len(t.split()) <= 18 and any(x in t for x in frases)

def es_reaccion_video_psm(texto):
    t = normalizar_texto_topografia(texto)
    frases = [
        "que bonito", "que bonita", "muy bonito", "muy bonita", "esta bonito",
        "esta bonita", "me gusta", "me gusto", "gracias por el video", "gracias",
        "bonitas amenidades", "bonito proyecto", "que chilero", "esta bien bonito"
    ]
    return len(t.split()) <= 12 and any(x in t for x in frases)


def es_intencion_reserva_psm(texto):
    t = normalizar_texto_topografia(texto)
    return any(x in t for x in [
        "quiero reservar", "quiero apartar", "quiero apartarlo", "quiero apartarla",
        "como reservo", "como aparto", "quiero comprar", "quiero uno",
        "dar la reserva", "pagar la reserva", "mandeme la cuenta", "envieme la cuenta"
    ])


def pide_enlace_maps_psm(texto):
    t = normalizar_texto_topografia(texto)
    return any(x in t for x in [
        "google maps", "maps", "link de ubicacion", "enlace de ubicacion",
        "link de maps", "enlace de maps", "ubicacion exacta", "mandeme la ubicacion",
        "envieme la ubicacion"
    ])


def es_inicio_general_psm(texto):
    """Inicio genérico: aquí sí usamos el protocolo de presentación progresiva."""
    t = normalizar_texto_topografia(texto)

    # Intenciones que deben romper el protocolo desde el primer mensaje.
    if es_intencion_reserva_psm(texto) or detectar_intencion_visita(texto):
        return False
    if pide_enlace_maps_psm(texto):
        return False
    if any(x in t for x in [
        "precio", "cuanto cuesta", "cuanto vale", "cuota", "financiamiento",
        "enganche", "requisitos", "documentos", "escritur", "mantenimiento",
        "gastos", "plano", "disponibilidad", "foto", "video", "donde queda",
        "ubicacion", "agua", "construir", "abono", "capital"
    ]):
        return False

    if es_solo_saludo(texto):
        return True

    frases = [
        "quiero informacion", "quisiera informacion", "mas informacion", "deseo informacion",
        "me interesa", "estoy interesado", "informacion de palmeras", "info de palmeras",
        "palmeras san miguel", "palmeras", "vi el anuncio", "vengo del anuncio"
    ]
    return any(x in t for x in frases)


def detectar_cta_palmeras(texto):
    """
    Detecta las 3 preguntas rápidas actuales del anuncio de Palmeras.

    Comportamiento:
    - informacion -> entra al protocolo inicial completo.
    - precios_cuotas -> entra al MISMO protocolo inicial completo.
    - visita -> rompe el protocolo y va directo a coordinar visita.
    """
    t = normalizar_texto_topografia(texto)

    if any(x in t for x in [
        "quiero mas informacion de palmeras san miguel",
        "quiero mas informacion de palmeras",
    ]):
        return "informacion"

    if any(x in t for x in [
        "precios y cuotas de palmeras san miguel",
        "precios y cuotas de palmeras",
    ]):
        return "precios_cuotas"

    if any(x in t for x in [
        "puedo agendar una visita al proyecto",
        "agendar una visita al proyecto",
        "quiero agendar una visita al proyecto",
    ]):
        return "visita"

    return None


def es_solicitud_info_general_psm(texto):
    """
    Detecta entradas explícitas de anuncio / consulta general de Palmeras.
    Estas frases REINICIAN el flujo comercial nuevo de PSM aunque el número
    ya tenga estado previo en PostgreSQL. Así nunca caen al paquete antiguo.
    """
    t = normalizar_texto_topografia(texto)

    # Si además viene una intención específica, respetamos esa intención.
    if es_intencion_reserva_psm(texto) or detectar_intencion_visita(texto):
        return False
    if pide_enlace_maps_psm(texto):
        return False
    if any(x in t for x in [
        "precio", "precios", "cuanto cuesta", "cuanto vale", "cuota",
        "financiamiento", "enganche", "requisitos", "documentos",
        "escritur", "mantenimiento", "gastos", "plano", "disponibilidad",
        "foto", "video", "donde queda", "ubicacion", "agua", "construir",
        "abono", "capital"
    ]):
        return False

    frases = [
        "deseo informacion de palmeras",
        "quiero informacion de palmeras",
        "quisiera informacion de palmeras",
        "informacion de palmeras",
        "info de palmeras",
        "deseo informacion sobre palmeras",
        "quiero informacion sobre palmeras",
        "mas informacion de palmeras",
        "me interesa palmeras",
        "estoy interesado en palmeras",
    ]
    return any(x in t for x in frases)


def reiniciar_flujo_psm_para_presentacion(numero):
    """Limpia solo el estado comercial de PSM; no toca CRM ni historial."""
    estado = estado_psm(numero)
    estado["psm_etapa"] = None
    estado["psm_fase"] = None
    estado["psm_plan"] = None
    estado["psm_plazo"] = None
    estado["psm_cotizacion_enviada"] = False
    estado["psm_video_amenidades_enviado"] = False
    estado["psm_pregunta_pendiente"] = None
    estado["psm_visita_ofrecida"] = False
    estado["psm_recordatorio_token"] = None
    persistir_cliente(numero)
    return estado


def saludo_actual_guatemala():
    """Devuelve un saludo natural según la hora real de Guatemala."""
    try:
        hora = datetime.now(ZoneInfo("America/Guatemala")).hour
    except Exception:
        # Fallback neutro si por alguna razón no se puede resolver la zona horaria.
        hora = 12

    # 05:00 a 11:59 -> Buenos días
    if 5 <= hora < 12:
        return "Buenos días"

    # 12:00 a 18:59 -> Buenas tardes
    if 12 <= hora < 19:
        return "Buenas tardes"

    # 19:00 a 04:59 -> Buenas noches
    return "Buenas noches"


def generar_bienvenida_psm(numero, texto_cliente):
    """
    Bienvenida controlada de Palmeras San Miguel.

    Se mantiene intencionalmente en texto fijo para conservar el estilo comercial
    aprobado y evitar que la IA vuelva a generar mensajes rígidos, repetitivos o
    con frases en mayúsculas. La conversación posterior sigue usando la lógica/IA
    normal del bot.
    """
    saludo = saludo_actual_guatemala()

    return formalizar_trato_usted(
        f"{saludo}! 👋 Le saluda *Gabriel Polero, asesor de ventas de Multiproyectos DIVE* 😊\n\n"
        "En *Palmeras San Miguel* actualmente contamos con *2 fases disponibles* 🏡✨\n"
        "En ambas fases tenemos terrenos de *8x16 m (128 m²)*.\n\n"
        "🏊 *Fase 1: Q67,200* — con piscina y área verde.\n"
        "🌳 *Fase 2: Q70,400* — con área verde.\n\n"
        "El proyecto está ubicado en *Zona 5 de Retalhuleu, camino a La Verde* 📍\n\n"
        "Además, son *terrenos con todos los servicios* ✅: agua potable, energía eléctrica, "
        "calles pavimentadas y drenajes con planta de tratamiento.\n"
        "También cuentan con *escritura registrada* 📄\n\n"
        "Le comparto los planos para que pueda comparar ambas opciones.\n\n"
        "¿Cuál de las dos fases le parece más atractiva? 😊"
    )


def enviar_planos_psm_sin_topografia(numero, fase=None):
    planos = PLANOS_PROYECTOS.get("palmeras", {})
    claves = []
    if fase in ("fase_1", "fase_2"):
        claves = [fase]
    else:
        claves = ["fase_1", "fase_2"]

    enviados = 0
    for clave in claves:
        plano = planos.get(clave)
        if not plano:
            continue
        if enviar_documento_url_whatsapp(
            numero, plano["url"], plano["archivo"], caption=plano["nombre"]
        ):
            enviados += 1

    if enviados:
        # Los documentos pueden tardar un poco más en renderizarse en WhatsApp que un texto.
        # Esperamos después de enviar AMBOS planos para que el mensaje de colores aparezca debajo.
        time.sleep(3.0)
        enviar_whatsapp(
            numero,
            "🟢 *Verde: disponible*\n"
            "🔴 *Rojo: vendido*\n\n"
            "Si alguna ubicación le llama la atención, indíqueme cuál y con gusto la revisamos 😊. "
            "Además, *todos los lotes tienen calle al frente*."
        )
    return enviados > 0


def texto_planes_pago_psm(fase):
    datos = PSM_FASES[fase]
    emoji_amenidad = "🏊🌳" if fase == "fase_1" else "🌳"
    return (
        "Excelente elección 😊\n\n"
        f"La *{datos['nombre']}* tiene un valor de *{datos['precio_texto']}* y cuenta con "
        f"{datos['amenidad']} {emoji_amenidad}\n\n"
        "Para facilitarle la compra, puede elegir la forma de pago que mejor se adapte a usted:\n\n"
        "💳 *Financiamiento propio* de 2 a 8 años\n"
        "✨ *Plan de 1 año sin intereses*\n"
        "💰 *Pago al contado*\n\n"
        "¿Cuál de estas opciones le gustaría revisar primero? 😊"
    )


def enviar_video_referencia_amenidades_psm(numero):
    for ruta in VIDEOS_GENERALES:
        if os.path.exists(ruta):
            enviar_video_whatsapp(
                numero,
                ruta,
                caption=(
                    "Le comparto también este pequeño video 🏡✨ para que pueda darse una idea "
                    "del tipo de espacios y amenidades que desarrollamos.\n\n"
                    "Son amenidades realizadas en otros proyectos de la empresa y se las comparto "
                    "únicamente como referencia 😊"
                )
            )
            return True
    return False


def cuota_sin_intereses_psm(fase):
    datos = PSM_FASES[fase]
    saldo = datos["precio"] - datos["enganche"]
    return round(saldo / 11, 2)


def precio_contado_psm(fase, descuento=0.03):
    return round(PSM_FASES[fase]["precio"] * (1 - descuento), 2)


def enviar_imagen_plan_psm(numero, fase, plan):
    """Envía la imagen visual del plan elegido. Mantiene un fallback seguro."""
    rutas = PSM_PLANES_IMAGEN.get(fase, {})
    ruta = rutas.get(plan)

    # Compatibilidad: si todavía no está la carpeta palmeras_nuevo en el deploy,
    # el financiamiento puede usar la cotización histórica de la fase.
    if (not ruta or not os.path.exists(ruta)) and plan == "financiamiento":
        ruta_fallback = PSM_FASES.get(fase, {}).get("imagen_cotizacion")
        if ruta_fallback and os.path.exists(ruta_fallback):
            ruta = ruta_fallback

    if not ruta or not os.path.exists(ruta):
        print("PSM IMAGEN DE PLAN NO ENCONTRADA:", fase, plan, ruta)
        return False

    nombres = {
        "financiamiento": "Financiamiento propio de 2 a 8 años",
        "sin_intereses": "Plan de 1 año sin intereses",
        "contado": "Pago al contado",
    }
    return enviar_imagen_whatsapp(
        numero,
        ruta,
        caption=f"Palmeras San Miguel · {nombres.get(plan, plan)}"
    )


def _texto_tabla_financiamiento_psm(fase):
    """Fallback textual completo si por alguna razón la imagen no existe en Render."""
    datos = PSM_FASES[fase]
    tabla = PSM_CUOTAS_FINANCIAMIENTO.get(fase, {})
    lineas = [
        f"💳 *Financiamiento propio — {datos['nombre']}*",
        f"🏡 Precio: *{datos['precio_texto']}*",
        "💰 Enganche: *Q6,000*",
        "",
    ]
    for plazo in range(2, 9):
        cuota = tabla.get(plazo)
        if cuota is not None:
            lineas.append(f"• {plazo} años: *{formatear_quetzales(cuota)}* mensuales")
    lineas.append("")
    lineas.append("Financiamiento propio y directo con la empresa, sin banco.")
    return "\n".join(lineas)


def enviar_financiamiento_psm(numero, fase, plazo=None):
    """
    Si el cliente elige financiamiento, muestra de una vez el CUADRO COMPLETO
    de 2 a 8 años. Si además mencionó un plazo, primero responde esa cuota y
    luego deja visible el mismo cuadro para comparar los demás plazos.
    """
    datos = PSM_FASES[fase]

    if plazo:
        cuota = PSM_CUOTAS_FINANCIAMIENTO.get(fase, {}).get(plazo)
        if cuota is None:
            return False
        enviar_whatsapp(
            numero,
            f"Claro 😊 En *{datos['nombre']}*, a *{plazo} años* la cuota es de "
            f"*{formatear_quetzales(cuota)} mensuales*, con enganche de *Q6,000*.\n\n"
            "Le comparto también el cuadro completo para que pueda comparar los demás plazos."
        )
    else:
        enviar_whatsapp(
            numero,
            f"Claro 😊 Le comparto el financiamiento de *{datos['nombre']}* para que pueda "
            "comparar todas las cuotas de *2 a 8 años* en un solo cuadro.\n\n"
            f"🏡 Precio: *{datos['precio_texto']}*\n"
            "💰 Enganche: *Q6,000*\n"
            "💳 Financiamiento propio y directo con la empresa."
        )

    enviado = enviar_imagen_plan_psm(numero, fase, "financiamiento")
    if not enviado:
        return enviar_whatsapp(numero, _texto_tabla_financiamiento_psm(fase))
    return True


def enviar_plan_sin_intereses_psm(numero, fase):
    datos = PSM_FASES[fase]
    cuota = cuota_sin_intereses_psm(fase)
    saldo = datos["precio"] - datos["enganche"]
    enviar_whatsapp(
        numero,
        f"Claro 😊 Para *{datos['nombre']}*, el plan de *1 año sin intereses* queda así:\n\n"
        f"🏡 Precio: *{datos['precio_texto']}*\n"
        "💰 Enganche: *Q6,000*\n"
        f"📌 Saldo: *{formatear_quetzales(saldo)}*\n"
        f"✨ 11 mensualidades de *{formatear_quetzales(cuota)}*\n\n"
        "No se agregan intereses a ese saldo."
    )
    enviar_imagen_plan_psm(numero, fase, "sin_intereses")
    return True


def enviar_contado_psm(numero, fase):
    datos = PSM_FASES[fase]
    precio_3 = precio_contado_psm(fase, 0.03)
    enviar_whatsapp(
        numero,
        f"Claro 😊 En *{datos['nombre']}* el precio regular es *{datos['precio_texto']}*.\n\n"
        f"💰 Con el *3% de descuento inicial por pago al contado* quedaría en "
        f"*{formatear_quetzales(precio_3)}*.\n\n"
        "Si ya está considerando realizar la compra, puedo revisar si es posible mejorar un poco más esa condición."
    )
    enviar_imagen_plan_psm(numero, fase, "contado")
    return True


def enviar_comparacion_planes_psm(numero, fase):
    """Envía las TRES imágenes del plan elegido, como hacía el flujo visual anterior."""
    datos = PSM_FASES[fase]
    enviar_whatsapp(
        numero,
        f"Claro 😊 Le comparto las *tres alternativas de {datos['nombre']}* para que pueda compararlas con calma."
    )

    resultados = {
        "financiamiento": enviar_imagen_plan_psm(numero, fase, "financiamiento"),
        "sin_intereses": enviar_imagen_plan_psm(numero, fase, "sin_intereses"),
        "contado": enviar_imagen_plan_psm(numero, fase, "contado"),
    }

    # Si alguna imagen no está disponible en el deploy, no dejamos al cliente sin respuesta.
    if not resultados["financiamiento"]:
        enviar_whatsapp(numero, _texto_tabla_financiamiento_psm(fase))
    if not resultados["sin_intereses"]:
        cuota_0 = cuota_sin_intereses_psm(fase)
        enviar_whatsapp(
            numero,
            f"✨ *1 año sin intereses:* enganche Q6,000 + 11 mensualidades de "
            f"*{formatear_quetzales(cuota_0)}*."
        )
    if not resultados["contado"]:
        contado = precio_contado_psm(fase, 0.03)
        enviar_whatsapp(
            numero,
            f"💰 *Pago al contado:* con el 3% de descuento inicial queda en "
            f"*{formatear_quetzales(contado)}*."
        )

    return enviar_whatsapp(
        numero,
        "¿Cuál siente que se adapta mejor a lo que usted busca? 😊"
    )


def invitar_visita_despues_propuesta_psm(numero):
    estado = estado_psm(numero)
    if estado.get("psm_visita_ofrecida") or cita_ya_cerrada(numero):
        return
    estado["psm_visita_ofrecida"] = True
    estado["psm_etapa"] = "esperando_visita"
    estado["psm_pregunta_pendiente"] = "visita"
    persistir_cliente(numero)
    enviar_whatsapp(
        numero,
        "Si esta opción está dentro de lo que busca, lo ideal sería que conozca Palmeras San Miguel personalmente 🏡. "
        "Así puede ver el avance, las ubicaciones y escoger con más seguridad. ¿Qué día le quedaría bien visitarlo? 📆"
    )


def respuesta_reserva_psm(numero):
    estado = estado_psm(numero)
    estado["psm_etapa"] = "reserva"
    estado["psm_pregunta_pendiente"] = "lote_para_reservar"
    persistir_cliente(numero)
    return (
        "Claro 🙌 Para reservar en Palmeras San Miguel se depositan Q3,000 a la cuenta de la empresa. "
        "Ese monto forma parte del enganche y sirve para apartar exclusivamente el lote que usted escoja. "
        "Se emite la factura correspondiente y dispone de un máximo de 15 días para completar el enganche, "
        "reunir los requisitos y definir la modalidad de pago.\n\n"
        "¿Ya tiene alguna ubicación vista en el plano o desea que le comparta los planos actualizados?"
    )


def respuesta_ubicacion_psm(texto):
    base = (
        "Palmeras San Miguel está en Zona 5 de Retalhuleu, camino a La Verde / carretera hacia Las Pilas 📍. "
        "Para una visita normalmente nos reunimos en Centro Comercial La Trinidad y desde allí le acompaño al proyecto."
    )
    if pide_enlace_maps_psm(texto):
        return base + "\n\nGoogle Maps:\n" + UBICACIONES_PROYECTOS["palmeras"]["maps"]
    return base + "\n\nSi desea conocerlo, avíseme antes para coordinar y asegurarme de poder atenderle personalmente."


def _mensaje_es_pregunta_especifica_psm(texto):
    t = normalizar_texto_topografia(texto)
    return any(x in t for x in [
        "mantenimiento", "escritur", "titulo de agua", "agua", "requisitos", "documentos",
        "abono", "capital", "construir", "urbanizacion", "cuando entregan", "gastos",
        "donde queda", "ubicacion", "maps", "plano", "disponibilidad", "medida", "calle",
        "garita", "muro", "piscina", "servicios", "banco"
    ])


def manejar_flujo_palmeras_humano(numero, texto, proyecto, message_id):
    """Ruta progresiva de Palmeras. Devuelve True cuando consumió el mensaje."""
    if proyecto != "palmeras":
        return False

    estado = estado_psm(numero)
    # Cualquier respuesta real del cliente invalida el recordatorio de 10 minutos.
    invalidar_recordatorio_psm(numero)
    t = normalizar_texto_topografia(texto)

    # ========================================================
    # PREGUNTAS RÁPIDAS ACTUALES DEL ANUNCIO DE PALMERAS
    # ========================================================
    # 1) Información -> protocolo inicial completo.
    # 2) Precios y cuotas -> MISMO protocolo inicial completo.
    # 3) Agendar visita -> rompe el protocolo y coordina visita directamente.
    cta_palmeras = detectar_cta_palmeras(texto)

    if cta_palmeras == "visita":
        respuesta = respuesta_visita(numero, texto, "palmeras")
        estado["psm_etapa"] = "visita"
        estado["psm_pregunta_pendiente"] = "dia_hora_visita"
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    if cta_palmeras in {"informacion", "precios_cuotas"}:
        # Ambas preguntas comienzan exactamente por el mismo protocolo.
        # Reiniciamos SOLO el estado comercial de Palmeras para evitar que un
        # estado viejo mande al cliente a mitad de la conversación.
        estado = reiniciar_flujo_psm_para_presentacion(numero)
        bienvenida = generar_bienvenida_psm(numero, texto)
        estado["psm_etapa"] = "esperando_fase"
        estado["psm_pregunta_pendiente"] = "fase"
        marcar_cliente_presentado(numero)
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", bienvenida)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, bienvenida)
            enviar_planos_psm_sin_topografia(numero)
        return True

    # Detectores rápidos + una capa de IA para respuestas humanas que no siguen
    # exactamente las palabras del menú. La IA interpreta la DECISIÓN; las cifras
    # y acciones siguen saliendo únicamente de los datos oficiales del código.
    fase_en_mensaje = detectar_fase_psm(texto)
    plan_mencionado = detectar_plan_psm(texto)
    plazo_mencionado = extraer_plazo_cuota(texto)
    decision_ia = None

    if (
        not _mensaje_es_pregunta_especifica_psm(texto)
        and not es_intencion_reserva_psm(texto)
        and not detectar_intencion_visita(texto)
        and (
            estado.get("psm_etapa") in {
                "esperando_fase", "esperando_plan", "esperando_plazo",
                "propuesta_enviada", "esperando_reaccion_propuesta"
            }
            or estado.get("psm_pregunta_pendiente") in {
                "fase", "plan_pago", "plazo_financiamiento", "reaccion_propuesta"
            }
        )
    ):
        necesita_ia = (
            (estado.get("psm_etapa") == "esperando_fase" and fase_en_mensaje is None)
            or (estado.get("psm_etapa") == "esperando_plan" and plan_mencionado is None and not es_reaccion_video_psm(texto))
            or (estado.get("psm_etapa") == "esperando_plazo" and plazo_mencionado is None)
            or (estado.get("psm_etapa") in {"propuesta_enviada", "esperando_reaccion_propuesta"}
                and plan_mencionado is None and not es_reaccion_positiva_propuesta_psm(texto))
        )
        if necesita_ia:
            decision_ia = interpretar_decision_psm_ia(numero, texto, estado)

    if fase_en_mensaje is None and decision_ia in {"fase_1", "fase_2", "ambas"}:
        fase_en_mensaje = decision_ia
    if plan_mencionado is None and decision_ia in {"financiamiento", "sin_intereses", "contado", "todos"}:
        plan_mencionado = decision_ia
    if plazo_mencionado is None and isinstance(decision_ia, str) and decision_ia.startswith("plazo_"):
        try:
            plazo_mencionado = int(decision_ia.split("_", 1)[1])
        except Exception:
            plazo_mencionado = None

    # Multi-intención común: precio + ubicación. Respondemos ambas sin disparar el paquete completo.
    pide_precio_multi = any(x in t for x in [
        "precio", "precios", "cuanto cuesta", "cuanto vale", "cuanto cuestan", "valor", "costo"
    ])
    if pide_precio_multi and pide_ubicacion(texto) and not estado.get("psm_fase"):
        ubicacion = respuesta_ubicacion_psm(texto)
        respuesta = (
            "Claro 😊 Actualmente los lotes son de 8x16 (128 m²):\n"
            "• Fase 1: Q67,200 — piscina y área verde.\n"
            "• Fase 2: Q70,400 — área verde.\n\n"
            + ubicacion + "\n\n¿De las dos fases, cuál le parece más atractiva?"
        )
        estado["psm_etapa"] = "esperando_fase"
        estado["psm_pregunta_pendiente"] = "fase"
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
            enviar_planos_psm_sin_topografia(numero)
        return True

    # Intención alta rompe el protocolo.
    if es_intencion_reserva_psm(texto):
        respuesta = respuesta_reserva_psm(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    if detectar_intencion_visita(texto):
        respuesta = respuesta_visita(numero, texto, "palmeras")
        estado["psm_etapa"] = "visita"
        estado["psm_pregunta_pendiente"] = "dia_hora_visita"
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    # Si ya se ofreció visita y el cliente responde afirmativamente, seguimos a agenda.
    if estado.get("psm_pregunta_pendiente") == "visita":
        t = normalizar_texto_topografia(texto)
        if t in {"si", "si por favor", "claro", "de acuerdo", "esta bien", "bueno", "dale"}:
            estado["psm_etapa"] = "visita"
            estado["psm_pregunta_pendiente"] = "dia_hora_visita"
            persistir_cliente(numero)
            respuesta = respuesta_visita(numero, "quiero visitar", "palmeras")
            guardar_mensaje(numero, "user", texto)
            guardar_mensaje(numero, "assistant", respuesta)
            if procesamiento_sigue_vigente(numero, message_id):
                enviar_whatsapp(numero, respuesta)
            return True

    # Ubicación: jamás mandamos Maps salvo solicitud explícita.
    if pide_ubicacion(texto):
        respuesta = respuesta_ubicacion_psm(texto)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    # Plano / disponibilidad: enviamos plano actualizado, colores y nada de topografía.
    if pide_plano(texto):
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", "Se compartió el plano actualizado de Palmeras San Miguel.")
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_planos_psm_sin_topografia(numero, estado.get("psm_fase"))
        return True

    # Inicio genérico de la conversación.
    # Si llega desde la FAQ del anuncio (p. ej. "Deseo información de Palmeras"),
    # reiniciamos SOLO el flujo comercial PSM aunque este número tenga estado viejo.
    # Esto impide que caiga al algoritmo antiguo de "información completa".
    inicio_nuevo = es_inicio_general_psm(texto)
    reinicio_explicito = es_solicitud_info_general_psm(texto)
    if (not estado.get("psm_etapa") and inicio_nuevo) or reinicio_explicito:
        if reinicio_explicito:
            estado = reiniciar_flujo_psm_para_presentacion(numero)
        bienvenida = generar_bienvenida_psm(numero, texto)
        estado["psm_etapa"] = "esperando_fase"
        estado["psm_pregunta_pendiente"] = "fase"
        marcar_cliente_presentado(numero)
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", bienvenida)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, bienvenida)
            enviar_planos_psm_sin_topografia(numero)
        return True

    # Si pide cuotas/cotización/financiamiento antes de elegir fase, no mandamos todas las imágenes.
    pide_pago_general = any(x in t for x in [
        "cotizacion", "cuota", "cuotas", "mensualidad", "mensualidades",
        "financiamiento", "plan de pago", "planes de pago"
    ])
    if pide_pago_general and not estado.get("psm_fase"):
        respuesta = (
            "Con gusto 😊 Para darle el plan correcto primero necesito saber cuál fase desea tomar como referencia. "
            "La Fase 1 está en Q67,200 y contará con piscina y área verde; la Fase 2 está en Q70,400 y contará con área verde. "
            "¿Cuál le interesa más?"
        )
        estado["psm_etapa"] = "esperando_fase"
        estado["psm_pregunta_pendiente"] = "fase"
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
            enviar_planos_psm_sin_topografia(numero)
        return True

    # Si ya existe una fase y el cliente pregunta DE FORMA GENERAL por pagos,
    # mostramos las modalidades. Pero si ya eligió una modalidad concreta
    # (por ejemplo: "Financiamiento", "contado" o "1 año sin intereses"),
    # NO debemos interceptarla aquí: debe continuar al bloque de selección de plan
    # que está más abajo para avanzar correctamente en el algoritmo.
    if (
        pide_pago_general
        and estado.get("psm_fase")
        and plan_mencionado is None
        and estado.get("psm_etapa") not in ("esperando_plazo", "propuesta_enviada")
    ):
        estado["psm_etapa"] = "esperando_plan"
        estado["psm_pregunta_pendiente"] = "plan_pago"
        persistir_cliente(numero)
        respuesta = texto_planes_pago_psm(estado["psm_fase"])
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
            if enviar_video_referencia_amenidades_psm(numero):
                estado["psm_video_amenidades_enviado"] = True
                persistir_cliente(numero)
            programar_recordatorio_plan_psm(numero)
        return True

    # Consulta de precio antes de escoger fase: responder sin soltar todo el catálogo.
    pide_precio = any(x in t for x in [
        "precio", "precios", "cuanto cuesta", "cuanto vale", "cuanto cuestan", "valor", "costo"
    ])
    if pide_precio and not estado.get("psm_fase") and fase_en_mensaje not in ("fase_1", "fase_2"):
        respuesta = (
            "Claro 😊 Actualmente los lotes son de 8x16 (128 m²):\n\n"
            "🏊 Fase 1: Q67,200, con piscina y área verde.\n"
            "🌳 Fase 2: Q70,400, con área verde.\n\n"
            "¿Cuál de las dos fases le parece más atractiva?"
        )
        estado["psm_etapa"] = "esperando_fase"
        estado["psm_pregunta_pendiente"] = "fase"
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
            enviar_planos_psm_sin_topografia(numero)
        return True

    # Elección de fase, tanto durante el protocolo como si la menciona directamente.
    if fase_en_mensaje in ("fase_1", "fase_2") and (
        estado.get("psm_etapa") in (None, "esperando_fase") or
        estado.get("psm_pregunta_pendiente") == "fase" or
        pide_precio
    ):
        estado["psm_fase"] = fase_en_mensaje
        estado["psm_etapa"] = "esperando_plan"
        estado["psm_pregunta_pendiente"] = "plan_pago"
        persistir_cliente(numero)
        respuesta = texto_planes_pago_psm(fase_en_mensaje)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
            if enviar_video_referencia_amenidades_psm(numero):
                estado["psm_video_amenidades_enviado"] = True
                persistir_cliente(numero)
            programar_recordatorio_plan_psm(numero)
        return True

    if fase_en_mensaje == "ambas" and estado.get("psm_etapa") == "esperando_fase":
        respuesta = (
            "Con gusto podemos comparar ambas 😊. La Fase 1 está en Q67,200 y contará con piscina y área verde; "
            "la Fase 2 está en Q70,400 y contará con área verde. Ambas tienen lotes de 8x16 y están en proceso de urbanización. "
            "Para revisar pagos sin revolverle los números, ¿cuál desea tomar primero como referencia: Fase 1 o Fase 2?"
        )
        estado["psm_pregunta_pendiente"] = "fase"
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    # Si comenta el video sin contestar el plan, reconocemos el comentario y retomamos la pregunta pendiente.
    if estado.get("psm_etapa") == "esperando_plan" and es_reaccion_video_psm(texto):
        respuesta = (
            "Sí 😊 esos espacios ayudan mucho a visualizar cómo puede quedar el proyecto terminado. "
            "Y sobre las formas de pago, ¿cuál desea que revisemos primero: financiamiento de 2 a 8 años, "
            "1 año sin intereses o contado?"
        )
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
            programar_recordatorio_plan_psm(numero)
        return True

    # Después de una propuesta concreta, dejamos que el cliente decida.
    # Si demuestra interés, recién entonces avanzamos hacia visita; si pregunta
    # otra cosa, el flujo general/IA la responde sin perder el estado.
    if estado.get("psm_etapa") in {"propuesta_enviada", "esperando_reaccion_propuesta"}:
        if es_reaccion_positiva_propuesta_psm(texto) or decision_ia == "positivo":
            guardar_mensaje(numero, "user", texto)
            guardar_mensaje(numero, "assistant", "Cliente mostró interés en la propuesta; se avanzó a coordinar visita.")
            if procesamiento_sigue_vigente(numero, message_id):
                invitar_visita_despues_propuesta_psm(numero)
            return True
        if decision_ia == "comparar":
            fase = estado.get("psm_fase")
            if fase:
                estado["psm_etapa"] = "esperando_reaccion_propuesta"
                estado["psm_plan"] = "todos"
                estado["psm_cotizacion_enviada"] = True
                estado["psm_pregunta_pendiente"] = "reaccion_propuesta"
                persistir_cliente(numero)
                guardar_mensaje(numero, "user", texto)
                if procesamiento_sigue_vigente(numero, message_id):
                    enviar_comparacion_planes_psm(numero, fase)
                return True
        if decision_ia == "visita":
            respuesta = respuesta_visita(numero, texto, "palmeras")
            estado["psm_etapa"] = "visita"
            estado["psm_pregunta_pendiente"] = "dia_hora_visita"
            persistir_cliente(numero)
            guardar_mensaje(numero, "user", texto)
            guardar_mensaje(numero, "assistant", respuesta)
            if procesamiento_sigue_vigente(numero, message_id):
                enviar_whatsapp(numero, respuesta)
            return True
        if decision_ia == "reserva":
            respuesta = respuesta_reserva_psm(numero)
            guardar_mensaje(numero, "user", texto)
            guardar_mensaje(numero, "assistant", respuesta)
            if procesamiento_sigue_vigente(numero, message_id):
                enviar_whatsapp(numero, respuesta)
            return True

    # Elección de modalidad de pago.
    # Reutilizamos la detección anterior para que una respuesta como "Financiamiento"
    # avance a pedir el plazo en vez de volver a mostrar las tres modalidades.
    plan = plan_mencionado
    if estado.get("psm_fase") and plan:
        fase = estado["psm_fase"]
        estado["psm_plan"] = plan

        if plan == "financiamiento":
            plazo = plazo_mencionado or extraer_plazo_cuota(texto)
            if plazo and 2 <= plazo <= 8:
                estado["psm_plazo"] = plazo
            else:
                estado["psm_plazo"] = None

            # Al elegir financiamiento NO volvemos a preguntar un plazo.
            # Mostramos inmediatamente el cuadro completo de 2 a 8 años, tal como
            # funcionaba el flujo visual anterior. Si el cliente ya indicó un plazo,
            # además se resalta esa cuota antes de mostrar el cuadro.
            estado["psm_etapa"] = "esperando_reaccion_propuesta"
            estado["psm_cotizacion_enviada"] = True
            estado["psm_pregunta_pendiente"] = "reaccion_propuesta"
            persistir_cliente(numero)
            guardar_mensaje(numero, "user", texto)
            if procesamiento_sigue_vigente(numero, message_id):
                enviar_financiamiento_psm(numero, fase, plazo if plazo and 2 <= plazo <= 8 else None)
            return True

        if plan == "sin_intereses":
            estado["psm_etapa"] = "esperando_reaccion_propuesta"
            estado["psm_cotizacion_enviada"] = True
            estado["psm_pregunta_pendiente"] = "reaccion_propuesta"
            persistir_cliente(numero)
            guardar_mensaje(numero, "user", texto)
            if procesamiento_sigue_vigente(numero, message_id):
                enviar_plan_sin_intereses_psm(numero, fase)
            return True

        if plan == "contado":
            estado["psm_etapa"] = "esperando_reaccion_propuesta"
            estado["psm_cotizacion_enviada"] = True
            estado["psm_pregunta_pendiente"] = "reaccion_propuesta"
            persistir_cliente(numero)
            guardar_mensaje(numero, "user", texto)
            if procesamiento_sigue_vigente(numero, message_id):
                enviar_contado_psm(numero, fase)
            return True

        if plan == "todos":
            # Ya resolvimos la petición mostrando las tres alternativas. No regresamos
            # al mismo menú ni dejamos como pendiente la misma pregunta.
            estado["psm_etapa"] = "esperando_reaccion_propuesta"
            estado["psm_plan"] = "todos"
            estado["psm_cotizacion_enviada"] = True
            estado["psm_pregunta_pendiente"] = "reaccion_propuesta"
            persistir_cliente(numero)
            guardar_mensaje(numero, "user", texto)
            if procesamiento_sigue_vigente(numero, message_id):
                enviar_comparacion_planes_psm(numero, fase)
            return True

    # Compatibilidad con contactos que quedaron guardados en la antigua etapa
    # "esperando_plazo". Si contestan con un plazo, damos la cuota y el cuadro;
    # si contestan otra cosa, no repetimos la pregunta: el resto del motor/IA la atiende.
    if estado.get("psm_etapa") == "esperando_plazo" and estado.get("psm_fase"):
        plazo = plazo_mencionado or extraer_plazo_cuota(texto)
        if plazo and 2 <= plazo <= 8:
            estado["psm_plazo"] = plazo
            estado["psm_etapa"] = "esperando_reaccion_propuesta"
            estado["psm_cotizacion_enviada"] = True
            estado["psm_pregunta_pendiente"] = "reaccion_propuesta"
            persistir_cliente(numero)
            guardar_mensaje(numero, "user", texto)
            if procesamiento_sigue_vigente(numero, message_id):
                enviar_financiamiento_psm(numero, estado["psm_fase"], plazo)
            return True

    # Pregunta directa por fraccionar enganche: facilidad REACTIVA, nunca de primera.
    if pregunta_enganche(texto) and any(x in t for x in [
        "dividir", "fraccionar", "dos pagos", "2 pagos", "no tengo completo", "medio enganche",
        "pagar despues", "pagar después"
    ]):
        respuesta = (
            "Sí 😊 si lo necesita podemos facilitar el enganche de Q6,000 en dos pagos de Q3,000. "
            "En ese esquema puede realizar la primera parte el primer mes, completar el enganche el segundo mes "
            "y comenzar su primera cuota en el tercer mes. Esta facilidad aplica en ambas fases."
        )
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    # Si pregunta directamente por 1 año sin intereses y aún no eligió fase, primero necesitamos la fase.
    if plan == "sin_intereses" and not estado.get("psm_fase"):
        respuesta = (
            "Sí 😊 contamos con un plan de 1 año sin intereses. Para darle la cuota exacta necesito saber cuál fase desea tomar como referencia: "
            "Fase 1 en Q67,200 o Fase 2 en Q70,400."
        )
        estado["psm_etapa"] = "esperando_fase"
        estado["psm_pregunta_pendiente"] = "fase"
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    # Una pregunta puntual durante el protocolo debe contestarse libremente por el resto del bot/IA.
    # Conservamos el estado para que luego pueda retomar la pregunta pendiente.
    if _mensaje_es_pregunta_especifica_psm(texto):
        persistir_cliente(numero)
        return False

    return False


# ============================================================
# VISTA HERMOSA - FLUJO COMERCIAL HUMANO / PROGRESIVO
# ============================================================

VH_FASES = {
    "fase_f": {
        "nombre": "Fase F",
        "precio": 83200,
        "precio_texto": "Q83,200",
        "enganche": 6000,
        "reserva": 1500,
        "amenidad": "piscina y área verde",
        "imagen_financiamiento": "media/cotizaciones/vista_hermosa/8x16_fase_f.jpeg",
    },
    "fase_g": {
        "nombre": "Fase G",
        "precio": 89600,
        "precio_texto": "Q89,600",
        "enganche": 6000,
        "reserva": 1500,
        "amenidad": "área verde",
        "imagen_financiamiento": "media/cotizaciones/vista_hermosa/8x16_fase_g.jpeg",
    },
}

# Se conservan las cuotas oficiales que ya estaban cargadas para Vista Hermosa.
# El plan de 1 año SIN intereses se calcula aparte y NO usa la fila antigua de 1 año.
VH_CUOTAS_FINANCIAMIENTO = {
    "fase_f": {2: 3817, 3: 2752, 4: 2228, 5: 1919, 6: 1717, 7: 1578, 8: 1476},
    "fase_g": {2: 4133, 3: 2981, 4: 2412, 5: 2078, 6: 1860, 7: 1708, 8: 1599},
}

VH_FICHA_OFICIAL = """
PROYECTO: Vista Hermosa.
UBICACIÓN: CA-2 km 188, Retalhuleu.
MEDIDA DISPONIBLE ACTUAL: únicamente 8x16 m (128 m²) en Fase F y Fase G.

FASE F:
- Precio Q83,200.
- Piscina y área verde.

FASE G:
- Precio Q89,600.
- Área verde.

COMPRA:
- Reserva Q1,500; forma parte del enganche.
- Enganche total Q6,000.
- Financiamiento propio de 2 a 8 años.
- Plan de 1 año sin intereses: (precio - Q6,000) / 11.
- Pago al contado: ofrecer primero 3% de descuento; máximo 5% sujeto a la operación.
- Se permiten abonos a capital conforme a las reglas comerciales cargadas.

SERVICIOS Y PROYECTO:
- Agua potable.
- Energía eléctrica.
- Calles pavimentadas.
- Drenajes con planta de tratamiento.
- Garita.
- Muro perimetral.
- El proyecto sigue en proceso de urbanización.
- Aún no se puede construir.

GASTOS ADICIONALES (solo si preguntan):
- Escrituración Q3,500.
- Título de agua Q3,500.
- Mantenimiento Q50 al mes.
- Agua Q50 por 30,000 litros.

VISITAS:
- El punto normal de encuentro es directamente en Vista Hermosa.
- NO enviar Google Maps al inicio.
- Cuando la cita ya tenga día y hora confirmados, enviar el enlace de Google Maps.

LEGAL:
- La escritura es registrada.
- Finca, folio y libro NO están cargados actualmente. Si preguntan cualquiera de esos datos, pausar la IA y avisar a Gabriel; jamás inventarlos.
""".strip()


def _inicializar_estado_vh(estado):
    estado.setdefault("vh_etapa", None)
    estado.setdefault("vh_fase", None)
    estado.setdefault("vh_plan", None)
    estado.setdefault("vh_plazo", None)
    estado.setdefault("vh_cotizacion_enviada", False)
    estado.setdefault("vh_video_amenidades_enviado", False)
    estado.setdefault("vh_pregunta_pendiente", None)
    estado.setdefault("vh_visita_ofrecida", False)
    return estado


def estado_vh(numero):
    return _inicializar_estado_vh(obtener_estado_conversacion(numero))


def reiniciar_flujo_vh_para_presentacion(numero):
    estado = estado_vh(numero)
    estado["vh_etapa"] = None
    estado["vh_fase"] = None
    estado["vh_plan"] = None
    estado["vh_plazo"] = None
    estado["vh_cotizacion_enviada"] = False
    estado["vh_video_amenidades_enviado"] = False
    estado["vh_pregunta_pendiente"] = None
    estado["vh_visita_ofrecida"] = False
    persistir_cliente(numero)
    return estado


def detectar_fase_vh(texto):
    t = normalizar_texto_topografia(texto)
    if any(x in t for x in ["las dos", "ambas", "las 2", "cualquiera", "comparar las dos"]):
        return "ambas"
    if any(x in t for x in [
        "fase f", "fasef", "la f", "83200", "83,200", "la mas barata",
        "la de piscina", "con piscina"
    ]):
        return "fase_f"
    if any(x in t for x in [
        "fase g", "faseg", "la g", "89600", "89,600", "la segunda",
        "la de area verde", "solo area verde"
    ]):
        return "fase_g"
    return None


def detectar_plan_vh(texto):
    t = normalizar_texto_topografia(texto)
    if any(x in t for x in ["las tres", "los tres", "las 3", "todos", "todas", "ver las tres", "comparar las tres"]):
        return "todos"
    if any(x in t for x in [
        "sin intereses", "sin interes", "1 ano", "un ano", "11 cuotas",
        "semicontado", "semi contado"
    ]):
        return "sin_intereses"
    if any(x in t for x in ["contado", "de contado", "un solo pago", "pago completo"]):
        return "contado"
    if any(x in t for x in [
        "financiamiento", "financiado", "cuotas", "mensualidades", "credito",
        "2 anos", "3 anos", "4 anos", "5 anos", "6 anos", "7 anos", "8 anos"
    ]):
        return "financiamiento"
    return None


def detectar_cta_vista_hermosa(texto):
    """Las 2 primeras FAQs siguen protocolo; únicamente visita lo rompe."""
    t = normalizar_texto_topografia(texto)
    if any(x in t for x in [
        "quiero mas informacion de vista hermosa",
        "quiero informacion de vista hermosa",
        "mas informacion de vista hermosa",
    ]):
        return "informacion"
    if any(x in t for x in [
        "precios y cuotas de vista hermosa",
        "precio y cuotas de vista hermosa",
    ]):
        return "precios_cuotas"
    if any(x in t for x in [
        "puedo agendar una visita al proyecto",
        "agendar una visita al proyecto",
        "quiero agendar una visita al proyecto",
    ]):
        return "visita"
    return None


def es_inicio_general_vh(texto):
    t = normalizar_texto_topografia(texto)
    if detectar_intencion_visita(texto) or es_intencion_reserva_psm(texto):
        return False
    if any(x in t for x in [
        "finca", "folio", "libro", "escritura", "requisitos", "documentos",
        "mantenimiento", "gastos", "plano", "disponibilidad", "foto", "video",
        "construir", "abono", "capital"
    ]):
        return False
    if es_solo_saludo(texto):
        return True
    return any(x in t for x in [
        "quiero informacion", "quisiera informacion", "mas informacion", "deseo informacion",
        "me interesa", "estoy interesado", "vista hermosa", "vi el anuncio", "vengo del anuncio",
        "precio", "precios", "cuanto cuesta", "cuanto vale", "cuotas"
    ])


def es_solicitud_info_general_vh(texto):
    t = normalizar_texto_topografia(texto)
    if detectar_intencion_visita(texto) or es_intencion_reserva_psm(texto):
        return False
    return any(x in t for x in [
        "deseo informacion de vista hermosa", "quiero informacion de vista hermosa",
        "quisiera informacion de vista hermosa", "informacion de vista hermosa",
        "mas informacion de vista hermosa", "me interesa vista hermosa"
    ])


def interpretar_decision_vh_ia(numero, texto, estado):
    texto = str(texto or "").strip()
    if not texto:
        return None
    etapa = str((estado or {}).get("vh_etapa") or "")
    pendiente = str((estado or {}).get("vh_pregunta_pendiente") or "")
    if etapa not in {"esperando_fase", "esperando_plan", "esperando_reaccion_propuesta"} and pendiente not in {"fase", "plan_pago", "reaccion_propuesta"}:
        return None
    opciones = {
        "esperando_fase": "fase_f, fase_g, ambas, ninguna",
        "esperando_plan": "financiamiento, sin_intereses, contado, todos, ninguna",
        "esperando_reaccion_propuesta": "positivo, comparar, visita, reserva, ninguna",
    }.get(etapa, "ninguna")
    prompt = f"""
Clasifique UNA respuesta de un cliente inmobiliario de Vista Hermosa.
Estado actual: {etapa or 'sin etapa'}
Pregunta pendiente: {pendiente or 'ninguna'}
Fase guardada: {(estado or {}).get('vh_fase') or 'ninguna'}
Plan guardado: {(estado or {}).get('vh_plan') or 'ninguno'}
Mensaje del cliente: {texto}

Responda SOLO con una etiqueta: {opciones}
Reglas:
- No invente una decisión si el mensaje es una pregunta distinta.
- "la más económica" / "la de piscina" = fase_f.
- Si pide comparar las formas de pago = todos.
- Si quiere pagar poco a poco = financiamiento.
- Si después de propuesta dice que le gusta, le sirve o le interesa = positivo.
- Si quiere conocer/ver/ir al proyecto = visita.
- Si quiere apartar/comprar/reservar = reserva.
- Ante duda = ninguna.
"""
    try:
        r = client.responses.create(
            model="gpt-5-mini",
            instructions="Clasifique intención. Devuelva únicamente una etiqueta permitida.",
            input=[{"role": "user", "content": prompt}]
        )
        etiqueta = (r.output_text or "").strip().lower()
        permitidas = {"fase_f", "fase_g", "ambas", "financiamiento", "sin_intereses", "contado", "todos", "positivo", "comparar", "visita", "reserva", "ninguna"}
        return etiqueta if etiqueta in permitidas else None
    except Exception as exc:
        print("ERROR INTERPRETANDO DECISION VISTA HERMOSA:", exc)
        return None


def generar_bienvenida_vh(numero, texto_cliente):
    saludo = saludo_actual_guatemala()
    return formalizar_trato_usted(
        f"{saludo}! 👋 Le saluda *Gabriel Polero, asesor de ventas de Multiproyectos DIVE* 😊\n\n"
        "En *Vista Hermosa* actualmente contamos con *2 fases disponibles* 🏡✨\n"
        "En ambas fases tenemos terrenos de *8x16 m (128 m²)*.\n\n"
        "🏊 *Fase F: Q83,200* — con piscina y área verde.\n"
        "🌳 *Fase G: Q89,600* — con área verde.\n\n"
        "El proyecto está ubicado sobre la *CA-2 km 188, Retalhuleu* 📍\n\n"
        "Son *terrenos con todos los servicios* ✅: agua potable, energía eléctrica, calles pavimentadas y drenajes con planta de tratamiento.\n"
        "Además, Vista Hermosa cuenta con *garita y muro perimetral* 🛡️\n"
        "El proyecto continúa en proceso de urbanización y todavía no se puede construir.\n\n"
        "Le comparto los dos planos para que pueda comparar ambas opciones 😊"
    )


def enviar_planos_vh(numero, fase=None):
    planos = PLANOS_PROYECTOS.get("vista_hermosa", {})
    claves = [fase] if fase in {"fase_f", "fase_g"} else ["fase_f", "fase_g"]
    enviados = 0
    for clave in claves:
        plano = planos.get(clave)
        if not plano:
            continue
        if enviar_documento_url_whatsapp(numero, plano["url"], plano["archivo"], caption=plano["nombre"]):
            enviados += 1
    if enviados:
        time.sleep(3.0)
    if fase in {"fase_f", "fase_g"}:
        mensaje_final = (
            "🟢 *Verde: disponible*\n"
            "🔴 *Rojo: vendido*\n\n"
            "¿Hay alguna ubicación de esta fase que le llame la atención? 😊"
        )
    else:
        mensaje_final = (
            "🟢 *Verde: disponible*\n"
            "🔴 *Rojo: vendido*\n\n"
            "Revise ambas fases con calma 😊. ¿Cuál le interesa más: *Fase F* o *Fase G*?"
        )
    enviar_whatsapp(numero, mensaje_final)
    return enviados > 0


def texto_planes_pago_vh(fase):
    datos = VH_FASES[fase]
    emoji = "🏊🌳" if fase == "fase_f" else "🌳"
    return (
        "Excelente elección 😊\n\n"
        f"La *{datos['nombre']}* tiene un valor de *{datos['precio_texto']}* y cuenta con {datos['amenidad']} {emoji}\n\n"
        "Para facilitarle la compra, puede elegir la forma de pago que mejor se adapte a usted:\n\n"
        "💳 *Financiamiento propio* de 2 a 8 años\n"
        "✨ *Plan de 1 año sin intereses*\n"
        "💰 *Pago al contado*\n\n"
        "¿Cuál de estas opciones le gustaría revisar primero? 😊"
    )


def enviar_video_vh(numero):
    rutas = VIDEOS_PROYECTOS.get("vista_hermosa", [])
    for ruta in rutas:
        if os.path.exists(ruta):
            return enviar_video_whatsapp(
                numero,
                ruta,
                caption=(
                    "Le comparto también un video de *Vista Hermosa* 🏡✨ para que pueda conocer mejor el proyecto."
                )
            )
    return False


def cuota_sin_intereses_vh(fase):
    datos = VH_FASES[fase]
    return round((datos["precio"] - datos["enganche"]) / 11, 2)


def precio_contado_vh(fase, descuento=0.03):
    return round(VH_FASES[fase]["precio"] * (1 - descuento), 2)


def _texto_tabla_financiamiento_vh(fase):
    datos = VH_FASES[fase]
    tabla = VH_CUOTAS_FINANCIAMIENTO.get(fase, {})
    lineas = [
        f"💳 *Financiamiento propio — {datos['nombre']}*",
        f"🏡 Precio: *{datos['precio_texto']}*",
        "💰 Enganche: *Q6,000*",
        "",
    ]
    for plazo in range(2, 9):
        cuota = tabla.get(plazo)
        if cuota is not None:
            lineas.append(f"• {plazo} años: *{formatear_quetzales(cuota)}* mensuales")
    lineas += ["", "Financiamiento propio y directo con la empresa, sin banco."]
    return "\n".join(lineas)


def enviar_financiamiento_vh(numero, fase, plazo=None):
    datos = VH_FASES[fase]
    if plazo:
        cuota = VH_CUOTAS_FINANCIAMIENTO.get(fase, {}).get(plazo)
        if cuota is not None:
            enviar_whatsapp(
                numero,
                f"Claro 😊 En *{datos['nombre']}*, a *{plazo} años* la cuota es de aproximadamente "
                f"*{formatear_quetzales(cuota)} mensuales*, con enganche de *Q6,000*."
            )
    else:
        enviar_whatsapp(
            numero,
            f"Claro 😊 Le comparto el financiamiento de *{datos['nombre']}* para que pueda comparar las cuotas de *2 a 8 años*."
        )

    ruta = datos.get("imagen_financiamiento")
    if ruta and os.path.exists(ruta):
        enviar_imagen_whatsapp(
            numero,
            ruta,
            caption=(
                f"Vista Hermosa · {datos['nombre']} · financiamiento propio de 2 a 8 años. "
                "El plan de 1 año sin intereses se calcula aparte."
            )
        )
    else:
        enviar_whatsapp(numero, _texto_tabla_financiamiento_vh(fase))

    return enviar_whatsapp(
        numero,
        "¿Hay alguna cuota de ese cuadro que se acerque a lo que usted desea pagar mensualmente? 😊"
    )


def enviar_plan_sin_intereses_vh(numero, fase):
    datos = VH_FASES[fase]
    saldo = datos["precio"] - datos["enganche"]
    cuota = cuota_sin_intereses_vh(fase)
    return enviar_whatsapp(
        numero,
        f"Claro 😊 Para *{datos['nombre']}*, el plan de *1 año sin intereses* queda así:\n\n"
        f"🏡 Precio: *{datos['precio_texto']}*\n"
        "💰 Enganche: *Q6,000*\n"
        f"📌 Saldo: *{formatear_quetzales(saldo)}*\n"
        f"✨ 11 mensualidades de *{formatear_quetzales(cuota)}*\n\n"
        "No se agregan intereses a ese saldo. ¿Qué le parece esta modalidad? 😊"
    )


def enviar_contado_vh(numero, fase):
    datos = VH_FASES[fase]
    precio_3 = precio_contado_vh(fase, 0.03)
    return enviar_whatsapp(
        numero,
        f"Claro 😊 En *{datos['nombre']}* el precio regular es *{datos['precio_texto']}*.\n\n"
        f"💰 Con el *3% de descuento inicial por pago al contado* quedaría en *{formatear_quetzales(precio_3)}*.\n\n"
        "Si ya está considerando realizar la compra, puedo revisar si es posible mejorar un poco más esa condición, hasta un máximo autorizado del 5%. "
        "¿Desea que revisemos esta opción o prefiere comparar otra modalidad?"
    )


def enviar_comparacion_vh(numero, fase):
    datos = VH_FASES[fase]
    enviar_whatsapp(numero, f"Claro 😊 Le comparto las *tres alternativas de {datos['nombre']}* para que pueda compararlas con calma.")
    # Financiamiento: cuadro existente del proyecto.
    ruta = datos.get("imagen_financiamiento")
    if ruta and os.path.exists(ruta):
        enviar_imagen_whatsapp(numero, ruta, caption=f"Vista Hermosa · {datos['nombre']} · financiamiento de 2 a 8 años")
    else:
        enviar_whatsapp(numero, _texto_tabla_financiamiento_vh(fase))
    cuota_0 = cuota_sin_intereses_vh(fase)
    contado = precio_contado_vh(fase, 0.03)
    enviar_whatsapp(
        numero,
        f"✨ *1 año sin intereses:* enganche Q6,000 + 11 mensualidades de *{formatear_quetzales(cuota_0)}*."
    )
    enviar_whatsapp(
        numero,
        f"💰 *Pago al contado:* con el 3% de descuento inicial queda en *{formatear_quetzales(contado)}*."
    )
    return enviar_whatsapp(numero, "¿Cuál de las tres formas de pago siente que se adapta mejor a usted? 😊")


def respuesta_reserva_vh(numero):
    estado = estado_vh(numero)
    estado["vh_etapa"] = "reserva"
    estado["vh_pregunta_pendiente"] = "lote_para_reservar"
    persistir_cliente(numero)
    return (
        "Claro 🙌 En *Vista Hermosa* puede reservar el lote con *Q1,500*. "
        "Ese monto forma parte del enganche total de Q6,000 y sirve para apartar la ubicación escogida mientras completa el proceso. "
        "¿Ya vio alguna ubicación que le interese en los planos o desea que le comparta ambas fases?"
    )


def respuesta_ubicacion_vh(numero):
    datos = UBICACIONES_PROYECTOS["vista_hermosa"]
    if cita_ya_cerrada(numero):
        return (
            f"Vista Hermosa está ubicado en *{datos['texto']}* 📍. Como su visita ya está coordinada, le comparto el enlace para llegar directamente:\n"
            f"{datos['maps']}\n\n¿Necesita que le indique algo más antes de llegar?"
        )
    return (
        f"Vista Hermosa está ubicado en *{datos['texto']}* 📍. Para las visitas normalmente nos reunimos directamente en el residencial. "
        "El enlace de Maps se lo envío cuando dejemos confirmados el día y la hora, así llega directamente al punto correcto. "
        "¿Qué día le quedaría bien conocerlo?"
    )


def pregunta_datos_registrales_vh(texto):
    t = normalizar_texto_topografia(texto)
    return any(x in t for x in [
        "numero de finca", "número de finca", "finca", "folio", "libro registral",
        "numero de libro", "número de libro", "registro de la propiedad"
    ])


def es_reaccion_video_vh(texto):
    return es_reaccion_video_psm(texto)


def es_reaccion_positiva_vh(texto):
    return es_reaccion_positiva_propuesta_psm(texto)


def _mensaje_es_pregunta_especifica_vh(texto):
    t = normalizar_texto_topografia(texto)
    return any(x in t for x in [
        "mantenimiento", "escritur", "titulo de agua", "agua", "requisitos", "documentos",
        "abono", "capital", "construir", "urbanizacion", "cuando entregan", "gastos",
        "donde queda", "ubicacion", "maps", "plano", "disponibilidad", "medida",
        "garita", "muro", "piscina", "servicios", "banco", "finca", "folio", "libro"
    ])


def manejar_flujo_vista_hermosa_humano(numero, texto, proyecto, message_id):
    """Mismo recorrido comercial de Palmeras, adaptado a Vista Hermosa."""
    if proyecto != "vista_hermosa":
        return False

    estado = estado_vh(numero)
    t = normalizar_texto_topografia(texto)
    cta = detectar_cta_vista_hermosa(texto)

    # La FAQ de visita es la única de las tres que salta el protocolo.
    if cta == "visita":
        respuesta = respuesta_visita(numero, texto, "vista_hermosa")
        estado["vh_etapa"] = "visita"
        estado["vh_pregunta_pendiente"] = "dia_hora_visita"
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    if cta in {"informacion", "precios_cuotas"}:
        estado = reiniciar_flujo_vh_para_presentacion(numero)
        bienvenida = generar_bienvenida_vh(numero, texto)
        estado["vh_etapa"] = "esperando_fase"
        estado["vh_pregunta_pendiente"] = "fase"
        marcar_cliente_presentado(numero)
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", bienvenida)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, bienvenida)
            enviar_planos_vh(numero)
        return True

    # Dato legal expresamente no cargado: pausa + alerta a Gabriel.
    if pregunta_datos_registrales_vh(texto):
        respuesta = (
            "La escritura de Vista Hermosa es registrada 📄✅. El número exacto de *finca, folio y libro* no lo tengo cargado en este momento y prefiero no inventárselo. "
            "¿Me permite confirmarle ese dato correctamente?"
        )
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
            marcar_intervencion_automatica(numero, texto, motivo="dato registral Vista Hermosa no cargado")
        return True

    # Fecha exacta de finalización: sabemos que sigue en urbanización, pero no hay fecha oficial cargada.
    if pregunta_plazo_entrega_urbanizacion(texto):
        respuesta = (
            "Vista Hermosa sigue en proceso de urbanización y *todavía no se puede construir* 🏗️. "
            "No tengo una fecha exacta de finalización cargada y prefiero confirmarla antes de darle un dato incorrecto. "
            "¿Me permite verificarle el avance y plazo actualizado?"
        )
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
            marcar_intervencion_automatica(numero, texto, motivo="plazo exacto de urbanización Vista Hermosa")
        return True

    fase = detectar_fase_vh(texto)
    plan = detectar_plan_vh(texto)
    plazo = extraer_plazo_cuota(texto)
    decision_ia = None

    if (
        not _mensaje_es_pregunta_especifica_vh(texto)
        and not es_intencion_reserva_psm(texto)
        and not detectar_intencion_visita(texto)
        and estado.get("vh_etapa") in {"esperando_fase", "esperando_plan", "esperando_reaccion_propuesta"}
    ):
        necesita_ia = (
            (estado.get("vh_etapa") == "esperando_fase" and fase is None)
            or (estado.get("vh_etapa") == "esperando_plan" and plan is None and not es_reaccion_video_vh(texto))
            or (estado.get("vh_etapa") == "esperando_reaccion_propuesta" and plan is None and not es_reaccion_positiva_vh(texto))
        )
        if necesita_ia:
            decision_ia = interpretar_decision_vh_ia(numero, texto, estado)

    if fase is None and decision_ia in {"fase_f", "fase_g", "ambas"}:
        fase = decision_ia
    if plan is None and decision_ia in {"financiamiento", "sin_intereses", "contado", "todos"}:
        plan = decision_ia

    # Pregunta informativa sobre reserva: responder el monto sin asumir que ya comprará.
    if any(x in t for x in [
        "cuanto es la reserva", "cuanto para reservar", "con cuanto reservo",
        "de cuanto es la reserva", "valor de la reserva"
    ]):
        respuesta = (
            "En *Vista Hermosa* puede reservar con *Q1,500* 😊. Ese monto forma parte del enganche total de Q6,000. "
            "¿Desea que le muestre los planos para escoger la ubicación que más le interese?"
        )
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    # Intención alta: reserva/compra o visita rompe el protocolo.
    if es_intencion_reserva_psm(texto):
        respuesta = respuesta_reserva_vh(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    if detectar_intencion_visita(texto):
        respuesta = respuesta_visita(numero, texto, "vista_hermosa")
        estado["vh_etapa"] = "visita"
        estado["vh_pregunta_pendiente"] = "dia_hora_visita"
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    # Ubicación no manda Maps antes de tener cita cerrada.
    if pide_ubicacion(texto):
        respuesta = respuesta_ubicacion_vh(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    # Planos/disponibilidad: siempre F y G si aún no eligió fase.
    if pide_plano(texto):
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", "Se compartieron los planos actualizados de Vista Hermosa.")
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_planos_vh(numero, estado.get("vh_fase"))
        return True

    # Inicio general u orgánico de precio/cuotas: mismo protocolo de bienvenida.
    if not estado.get("vh_etapa") and es_inicio_general_vh(texto):
        estado = reiniciar_flujo_vh_para_presentacion(numero)
        bienvenida = generar_bienvenida_vh(numero, texto)
        estado["vh_etapa"] = "esperando_fase"
        estado["vh_pregunta_pendiente"] = "fase"
        marcar_cliente_presentado(numero)
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", bienvenida)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, bienvenida)
            enviar_planos_vh(numero)
        return True

    if es_solicitud_info_general_vh(texto):
        estado = reiniciar_flujo_vh_para_presentacion(numero)
        bienvenida = generar_bienvenida_vh(numero, texto)
        estado["vh_etapa"] = "esperando_fase"
        estado["vh_pregunta_pendiente"] = "fase"
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", bienvenida)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, bienvenida)
            enviar_planos_vh(numero)
        return True

    # Pregunta de pago antes de seleccionar fase: no soltar las dos cotizaciones.
    pide_pago_general = any(x in t for x in [
        "precio", "precios", "cuanto cuesta", "cuanto vale", "valor", "costo",
        "cotizacion", "cuota", "cuotas", "mensualidad", "mensualidades",
        "financiamiento", "plan de pago", "planes de pago", "sin intereses", "contado"
    ])
    if pide_pago_general and not estado.get("vh_fase") and fase not in {"fase_f", "fase_g"}:
        respuesta = (
            "Con gusto 😊 Para darle el plan correcto primero elijamos la fase que desea tomar como referencia:\n\n"
            "🏊 *Fase F: Q83,200* — piscina y área verde.\n"
            "🌳 *Fase G: Q89,600* — área verde.\n\n"
            "¿Cuál le interesa más: *Fase F* o *Fase G*?"
        )
        estado["vh_etapa"] = "esperando_fase"
        estado["vh_pregunta_pendiente"] = "fase"
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
            enviar_planos_vh(numero)
        return True

    # Elección de fase.
    if fase in {"fase_f", "fase_g"} and (
        estado.get("vh_etapa") in {None, "esperando_fase"}
        or estado.get("vh_pregunta_pendiente") == "fase"
        or "precio" in t
    ):
        estado["vh_fase"] = fase
        estado["vh_etapa"] = "esperando_plan"
        estado["vh_pregunta_pendiente"] = "plan_pago"
        persistir_cliente(numero)
        respuesta = texto_planes_pago_vh(fase)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
            if not estado.get("vh_video_amenidades_enviado") and enviar_video_vh(numero):
                estado["vh_video_amenidades_enviado"] = True
                persistir_cliente(numero)
        return True

    if fase == "ambas" and estado.get("vh_etapa") == "esperando_fase":
        respuesta = (
            "Claro 😊 Podemos comparar ambas. *Fase F* está en Q83,200 con piscina y área verde; "
            "*Fase G* está en Q89,600 con área verde. Ambas son de 8x16. "
            "¿Cuál desea tomar primero como referencia para revisar las formas de pago?"
        )
        estado["vh_pregunta_pendiente"] = "fase"
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    if estado.get("vh_etapa") == "esperando_plan" and es_reaccion_video_vh(texto):
        respuesta = (
            "Me alegra que le haya gustado 😊. Sobre la forma de pago, podemos revisar *financiamiento de 2 a 8 años*, "
            "*1 año sin intereses* o *pago al contado*. ¿Cuál desea que revisemos primero?"
        )
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    # Reacción a propuesta: no repetir el menú; avanzar a visita si hay interés real.
    if estado.get("vh_etapa") == "esperando_reaccion_propuesta":
        if es_reaccion_positiva_vh(texto) or decision_ia == "positivo":
            estado["vh_etapa"] = "visita"
            estado["vh_pregunta_pendiente"] = "dia_hora_visita"
            persistir_cliente(numero)
            respuesta = (
                "Me alegra que la opción le interese 😊🏡. Lo ideal ahora es que pueda conocer Vista Hermosa personalmente y ver el avance del proyecto. "
                "¿Qué día le quedaría bien visitarlo?"
            )
            guardar_mensaje(numero, "user", texto)
            guardar_mensaje(numero, "assistant", respuesta)
            if procesamiento_sigue_vigente(numero, message_id):
                enviar_whatsapp(numero, respuesta)
            return True
        if decision_ia == "visita":
            respuesta = respuesta_visita(numero, texto, "vista_hermosa")
            estado["vh_etapa"] = "visita"
            estado["vh_pregunta_pendiente"] = "dia_hora_visita"
            persistir_cliente(numero)
            guardar_mensaje(numero, "user", texto)
            guardar_mensaje(numero, "assistant", respuesta)
            if procesamiento_sigue_vigente(numero, message_id):
                enviar_whatsapp(numero, respuesta)
            return True
        if decision_ia == "reserva":
            respuesta = respuesta_reserva_vh(numero)
            guardar_mensaje(numero, "user", texto)
            guardar_mensaje(numero, "assistant", respuesta)
            if procesamiento_sigue_vigente(numero, message_id):
                enviar_whatsapp(numero, respuesta)
            return True
        if decision_ia == "comparar":
            plan = "todos"

    # Elección/cambio de modalidad. La fase se conserva.
    if estado.get("vh_fase") and plan:
        fase_actual = estado["vh_fase"]
        estado["vh_plan"] = plan
        estado["vh_plazo"] = plazo if plazo and 2 <= plazo <= 8 else None
        estado["vh_etapa"] = "esperando_reaccion_propuesta"
        estado["vh_cotizacion_enviada"] = True
        estado["vh_pregunta_pendiente"] = "reaccion_propuesta"
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        if procesamiento_sigue_vigente(numero, message_id):
            if plan == "financiamiento":
                enviar_financiamiento_vh(numero, fase_actual, estado.get("vh_plazo"))
            elif plan == "sin_intereses":
                enviar_plan_sin_intereses_vh(numero, fase_actual)
            elif plan == "contado":
                enviar_contado_vh(numero, fase_actual)
            elif plan == "todos":
                enviar_comparacion_vh(numero, fase_actual)
        return True

    # Si ya eligió fase y pregunta específicamente por un plazo, conservar contexto.
    if estado.get("vh_fase") and plazo and 2 <= plazo <= 8:
        estado["vh_plan"] = "financiamiento"
        estado["vh_plazo"] = plazo
        estado["vh_etapa"] = "esperando_reaccion_propuesta"
        estado["vh_cotizacion_enviada"] = True
        estado["vh_pregunta_pendiente"] = "reaccion_propuesta"
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_financiamiento_vh(numero, estado["vh_fase"], plazo)
        return True

    # Pregunta concreta sobre construcción: responder sin inventar fecha.
    if any(x in t for x in ["ya puedo construir", "se puede construir", "puedo construir", "construir ahorita", "construir ahora"]):
        respuesta = (
            "Todavía no 😊 Vista Hermosa continúa en proceso de urbanización. Primero deben quedar habilitadas las obras y servicios necesarios; después podrá construirse. "
            "¿Desea que le explique qué servicios tendrá el residencial?"
        )
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    # Preguntas puntuales restantes las resuelve el motor general/IA con la ficha ya corregida.
    if _mensaje_es_pregunta_especifica_vh(texto):
        persistir_cliente(numero)
        return False

    return False


# ============================================================
# BUENAVENTURA CUYOTENANGO - FLUJO COMERCIAL HUMANO / PROGRESIVO
# ============================================================
# Replica la misma filosofía comercial de Palmeras/Vista Hermosa:
# presentación -> plano -> calificación por uso -> producto -> forma de pago
# -> conversación abierta -> visita. El cliente puede romper el protocolo
# cuando pregunta algo concreto y el bot debe responder esa pregunta primero.

BNV_PRODUCTOS = {
    "res_8x16": {
        "nombre": "8x16 residencial / inversión",
        "medida": "8x16",
        "precio": 83200,
        "precio_texto": "Q83,200",
        "enganche": 6000,
        "enganche_texto": "Q6,000",
        "imagen_financiamiento": "media/cotizaciones/buenaventura/8x16.jpeg",
        "sector": "residencial",
    },
    "res_8x18": {
        "nombre": "8x18 residencial / inversión",
        "medida": "8x18",
        "precio": 93600,
        "precio_texto": "Q93,600",
        "enganche": 8000,
        "enganche_texto": "Q8,000",
        "imagen_financiamiento": "media/cotizaciones/buenaventura/8x18.jpeg",
        "sector": "residencial",
    },
    "com_8x16": {
        "nombre": "8x16 comercial",
        "medida": "8x16",
        "precio": 128000,
        "precio_texto": "Q128,000",
        "enganche": 6000,
        "enganche_texto": "Q6,000",
        "imagen_financiamiento": "media/cotizaciones/buenaventura/8x16_comercial.jpeg",
        "sector": "comercial",
    },
}

BNV_CUOTAS_FINANCIAMIENTO = {
    "res_8x16": {2: 3817, 3: 2752, 4: 2228, 5: 1919, 6: 1717, 7: 1578, 8: 1476},
    "res_8x18": {2: 4232, 3: 3052, 4: 2470, 5: 2127, 6: 1904, 7: 1749, 8: 1637},
    "com_8x16": {2: 6032, 3: 4350, 4: 3520, 5: 3032, 6: 2714, 7: 2493, 8: 2333},
}

BNV_FICHA_OFICIAL = """
PROYECTO: Buenaventura Cuyotenango.
UBICACIÓN: km 168 de la carretera hacia la playa de Tulate, Cuyotenango.
PLANO: existe un solo plano general grande para todo el proyecto.

CALIFICACIÓN OBLIGATORIA:
- Preguntar si el terreno lo busca para vivir, invertir o para negocio.
- Para vivir o invertir se usan las opciones residenciales.
- Para negocio se usa el lote comercial.

VIVIR / INVERTIR:
- 8x16: Q83,200. Enganche Q6,000.
- 8x18: Q93,600. Enganche Q8,000.
- El sector residencial mantiene los servicios y amenidades del proyecto, además de garita y muro perimetral.

NEGOCIO / COMERCIAL:
- Únicamente 8x16 comercial: Q128,000.
- Enganche Q6,000.
- El área comercial NO tiene garita y NO tiene muro perimetral.
- Conserva los servicios cargados del proyecto.

FORMAS DE PAGO:
- Financiamiento propio de 2 a 8 años.
- Plan de 1 año sin intereses: precio menos enganche, dividido entre 11 mensualidades.
- Pago al contado: ofrecer primero 3% de descuento; se puede negociar hasta un máximo de 5% según la operación.
- Abonos extraordinarios a capital conforme a las reglas comerciales ya cargadas; no inventar condiciones nuevas.

SERVICIOS:
- Agua potable.
- Energía eléctrica.
- Calles pavimentadas.
- Drenajes con planta de tratamiento.

AMENIDADES:
- Casa club.
- Piscinas.
- Áreas verdes.
- Juegos para niños.
- Caminamientos.

GASTOS ADICIONALES (son los mismos para vivir, invertir o negocio; solo si preguntan):
- Escrituración 1 lote: Q6,000.
- Cada lote adicional suma Q2,400 (2 lotes Q8,400; 3 lotes Q10,800).
- Título de agua: Q4,000.
- Mantenimiento: Q100 al mes.
- Agua: Q100 al mes por 30,000 litros.

RESERVA:
- El monto exacto de reserva NO fue definido en esta actualización. Si el cliente pregunta el monto exacto para reservar, no inventarlo: pausar la IA y avisar a Gabriel.

REGLAS:
- No ofrecer 9x20: ya no forma parte de las opciones cargadas en este flujo.
- No mezclar el precio residencial 8x16 con el comercial 8x16.
- Si el cliente pide fotos o videos, enviarlos inmediatamente desde las carpetas ya cargadas.
""".strip()


def _inicializar_estado_bnv(estado):
    estado.setdefault("bnv_etapa", None)
    estado.setdefault("bnv_uso", None)
    estado.setdefault("bnv_producto", None)
    estado.setdefault("bnv_plan", None)
    estado.setdefault("bnv_plazo", None)
    estado.setdefault("bnv_cotizacion_enviada", False)
    estado.setdefault("bnv_video_enviado", False)
    estado.setdefault("bnv_pregunta_pendiente", None)
    estado.setdefault("bnv_visita_ofrecida", False)
    return estado


def estado_bnv(numero):
    return _inicializar_estado_bnv(obtener_estado_conversacion(numero))


def reiniciar_flujo_bnv_para_presentacion(numero):
    estado = estado_bnv(numero)
    for clave, valor in {
        "bnv_etapa": None,
        "bnv_uso": None,
        "bnv_producto": None,
        "bnv_plan": None,
        "bnv_plazo": None,
        "bnv_cotizacion_enviada": False,
        "bnv_video_enviado": False,
        "bnv_pregunta_pendiente": None,
        "bnv_visita_ofrecida": False,
    }.items():
        estado[clave] = valor
    persistir_cliente(numero)
    return estado


def detectar_cta_bnv_nuevo(texto):
    # Conserva compatibilidad con las preguntas que ya existen en Meta Ads.
    accion_vieja = detectar_cta_buenaventura(texto)
    if accion_vieja == "agendar_visita":
        return "visita"
    if accion_vieja == "ubicacion":
        return "ubicacion"
    if accion_vieja in {"precios_cuotas", "lotes_disponibles"}:
        return "inicio"

    t = normalizar_texto_topografia(texto)
    if any(x in t for x in [
        "quiero mas informacion de buenaventura", "quiero informacion de buenaventura",
        "mas informacion de buenaventura", "informacion de buenaventura cuyo",
        "informacion de buenaventura cuyotenango",
    ]):
        return "inicio"
    if any(x in t for x in [
        "precios y cuotas de buenaventura", "precio y cuotas de buenaventura",
        "precios y cuotas de buenaventura cuyo",
    ]):
        return "inicio"
    if any(x in t for x in [
        "puedo agendar una visita al proyecto", "agendar una visita al proyecto",
        "quiero agendar una visita al proyecto",
    ]):
        return "visita"
    return None


def es_inicio_general_bnv(texto):
    t = normalizar_texto_topografia(texto)
    if detectar_intencion_visita(texto) or pide_fotos(texto) or pide_videos(texto):
        return False
    if any(x in t for x in [
        "gastos", "mantenimiento", "escritur", "titulo de agua", "finca", "folio", "libro",
        "reserva", "reservar", "abono", "capital", "plano", "ubicacion", "maps"
    ]):
        return False
    if es_solo_saludo(texto):
        return True
    return any(x in t for x in [
        "buenaventura", "cuyo", "cuyotenango", "quiero informacion", "mas informacion",
        "me interesa", "vi el anuncio", "vengo del anuncio", "precios y cuotas"
    ])


def detectar_uso_bnv(texto):
    t = normalizar_texto_topografia(texto)
    if any(x in t for x in [
        "negocio", "local", "locales", "comercial", "comercio", "emprendimiento",
        "poner mi negocio", "para negocio"
    ]):
        return "negocio"
    if any(x in t for x in [
        "invertir", "inversion", "inversionista", "plusvalia", "patrimonio",
        "revender", "reventa", "para inversion"
    ]):
        return "inversion"
    if any(x in t for x in [
        "vivir", "casa", "vivienda", "mi familia", "para mi familia", "construir mi casa",
        "para vivir"
    ]):
        return "vivir"
    return None


def detectar_producto_bnv(texto, estado=None):
    t = normalizar_texto_topografia(texto)
    estado = estado or {}
    uso = estado.get("bnv_uso")
    if "9x20" in t or "9×20" in t:
        return "no_disponible_9x20"
    if "8x18" in t or "8×18" in t:
        return "res_8x18"
    if "8x16" in t or "8×16" in t:
        if uso == "negocio" or any(x in t for x in ["comercial", "negocio", "local", "locales"]):
            return "com_8x16"
        if uso in {"vivir", "inversion"}:
            return "res_8x16"
        return "8x16_sin_uso"
    return None


def detectar_plan_bnv(texto):
    t = normalizar_texto_topografia(texto)
    if any(x in t for x in ["las tres", "las 3", "todas", "todos", "comparar las tres", "ver las tres"]):
        return "todos"
    if any(x in t for x in ["1 ano sin intereses", "un ano sin intereses", "sin intereses", "11 pagos", "11 cuotas", "semicontado", "semi contado"]):
        return "sin_intereses"
    if any(x in t for x in ["contado", "de contado", "un solo pago", "pagar todo", "pago completo"]):
        return "contado"
    if any(x in t for x in ["financiamiento", "financiado", "cuotas", "mensualidades", "credito", "a plazos"]):
        return "financiamiento"
    if extraer_plazo_cuota(texto):
        return "financiamiento"
    return None


def generar_bienvenida_bnv(numero, texto_cliente):
    saludo = saludo_actual_guatemala()
    return formalizar_trato_usted(
        f"{saludo}! 👋 Le saluda *Gabriel Polero, asesor de ventas de Multiproyectos DIVE* 😊\n\n"
        "En *Buenaventura Cuyotenango* contamos con opciones para vivienda, inversión y también un área comercial 🏡✨\n\n"
        "📍 El proyecto está ubicado en el *km 168 de la carretera hacia la playa de Tulate, Cuyotenango*.\n\n"
        "Cuenta con *todos los servicios*: agua potable, energía eléctrica, calles pavimentadas y drenajes con planta de tratamiento ✅\n"
        "Además, contempla casa club, piscinas, áreas verdes, juegos para niños y caminamientos 🏊🌳\n\n"
        "Le comparto el *plano general* para que pueda conocer la distribución del proyecto."
    )


def enviar_plano_inicio_bnv(numero):
    plano = PLANOS_PROYECTOS.get("buenaventura", {}).get("general")
    if plano:
        enviar_documento_url_whatsapp(numero, plano["url"], plano["archivo"], caption=plano["nombre"])
    time.sleep(1.5)
    enviar_whatsapp(
        numero,
        "Para que pueda identificar mejor el plano 😊\n\n"
        "🟢 *Verde: disponible*\n"
        "🔴 *Rojo: vendido*\n"
        "🟡 *Reservado: actualmente apartado*\n\n"
        "Para orientarle con el precio correcto, ¿el terreno lo busca *para vivir*, *para invertir* o *para negocio*?"
    )
    return True


def texto_opciones_residenciales_bnv(uso):
    motivo = "vivir" if uso == "vivir" else "invertir"
    return (
        f"Perfecto 😊 Si lo busca para *{motivo}*, tenemos estas dos opciones:\n\n"
        "🏡 *8x16 — Q83,200* | enganche *Q6,000*\n"
        "🏡 *8x18 — Q93,600* | enganche *Q8,000*\n\n"
        "En el sector residencial el proyecto cuenta con sus servicios y amenidades, además de garita y muro perimetral.\n\n"
        "¿Cuál medida le interesa más: *8x16* o *8x18*?"
    )


def texto_producto_comercial_bnv():
    return (
        "Perfecto 😊 Para *negocio* contamos con el lote *8x16 comercial*:\n\n"
        "🏪 Precio: *Q128,000*\n"
        "💰 Enganche: *Q6,000*\n\n"
        "El área comercial cuenta con los servicios del proyecto, pero *no tiene garita ni muro perimetral*.\n\n"
        + texto_planes_pago_bnv("com_8x16")
    )


def texto_planes_pago_bnv(producto):
    datos = BNV_PRODUCTOS[producto]
    return (
        f"Para el lote *{datos['nombre']}* puede elegir la forma de pago que mejor se adapte a usted:\n\n"
        "💳 *Financiamiento propio* de 2 a 8 años\n"
        "✨ *Plan de 1 año sin intereses*\n"
        "💰 *Pago al contado*\n\n"
        "¿Cuál de estas opciones le gustaría revisar primero? 😊"
    )


def enviar_video_bnv(numero):
    rutas = VIDEOS_PROYECTOS.get("buenaventura", [])
    for ruta in rutas:
        if os.path.exists(ruta):
            return enviar_video_whatsapp(
                numero,
                ruta,
                caption="Buenaventura Cuyotenango 🏡🎥"
            )
    for ruta in VIDEOS_GENERALES:
        if os.path.exists(ruta):
            return enviar_video_whatsapp(
                numero,
                ruta,
                caption="Video de referencia de amenidades 🏡✨"
            )
    return False


def _texto_tabla_financiamiento_bnv(producto):
    datos = BNV_PRODUCTOS[producto]
    tabla = BNV_CUOTAS_FINANCIAMIENTO.get(producto, {})
    lineas = [
        f"💳 *Financiamiento propio — {datos['nombre']}*",
        f"🏡 Precio: *{datos['precio_texto']}*",
        f"💰 Enganche: *{datos['enganche_texto']}*",
        "",
    ]
    for plazo in range(2, 9):
        cuota = tabla.get(plazo)
        if cuota is not None:
            lineas.append(f"• {plazo} años: *{formatear_quetzales(cuota)}* mensuales")
    return "\n".join(lineas)


def enviar_financiamiento_bnv(numero, producto, plazo=None):
    datos = BNV_PRODUCTOS[producto]
    tabla = BNV_CUOTAS_FINANCIAMIENTO.get(producto, {})
    if plazo and plazo in tabla:
        enviar_whatsapp(
            numero,
            f"Claro 😊 Para *{datos['nombre']}*, a *{plazo} años* la cuota es de aproximadamente "
            f"*{formatear_quetzales(tabla[plazo])} mensuales*, con enganche de *{datos['enganche_texto']}*.\n\n"
            "Le comparto también el cuadro completo para que pueda comparar los demás plazos."
        )
    else:
        enviar_whatsapp(
            numero,
            f"Claro 😊 Le comparto el cuadro completo de *{datos['nombre']}* para que pueda comparar las cuotas de *2 a 8 años*."
        )
    ruta = datos.get("imagen_financiamiento")
    enviado = False
    if ruta and os.path.exists(ruta):
        enviado = enviar_imagen_whatsapp(numero, ruta, caption=f"Buenaventura · {datos['nombre']} · Financiamiento")
    if not enviado:
        enviar_whatsapp(numero, _texto_tabla_financiamiento_bnv(producto))
    return enviar_whatsapp(numero, "¿Qué plazo siente que se adapta mejor a su presupuesto? 😊")


def cuota_sin_intereses_bnv(producto):
    datos = BNV_PRODUCTOS[producto]
    return round((datos["precio"] - datos["enganche"]) / 11, 2)


def precio_contado_bnv(producto, descuento=0.03):
    return round(BNV_PRODUCTOS[producto]["precio"] * (1 - descuento), 2)


def enviar_plan_sin_intereses_bnv(numero, producto):
    datos = BNV_PRODUCTOS[producto]
    saldo = datos["precio"] - datos["enganche"]
    cuota = cuota_sin_intereses_bnv(producto)
    return enviar_whatsapp(
        numero,
        f"Claro 😊 Para *{datos['nombre']}*, el plan de *1 año sin intereses* queda así:\n\n"
        f"🏡 Precio: *{datos['precio_texto']}*\n"
        f"💰 Enganche: *{datos['enganche_texto']}*\n"
        f"📌 Saldo: *{formatear_quetzales(saldo)}*\n"
        f"✨ *11 pagos de {formatear_quetzales(cuota)}*\n\n"
        "No se agregan intereses a ese saldo. ¿Qué le parece esta modalidad? 😊"
    )


def enviar_contado_bnv(numero, producto):
    datos = BNV_PRODUCTOS[producto]
    precio_3 = precio_contado_bnv(producto, 0.03)
    return enviar_whatsapp(
        numero,
        f"Claro 😊 Para *{datos['nombre']}* el precio regular es *{datos['precio_texto']}*.\n\n"
        f"💰 Con el *3% de descuento inicial por pago al contado* quedaría en *{formatear_quetzales(precio_3)}*.\n\n"
        "Si existe una negociación real, puedo revisar una mejora hasta un máximo de 5%. "
        "¿Desea que revisemos esta opción al contado? 😊"
    )


def enviar_comparacion_bnv(numero, producto):
    datos = BNV_PRODUCTOS[producto]
    enviar_whatsapp(numero, f"Claro 😊 Le comparto las tres alternativas para *{datos['nombre']}*.")
    ruta = datos.get("imagen_financiamiento")
    if ruta and os.path.exists(ruta):
        enviar_imagen_whatsapp(numero, ruta, caption=f"Buenaventura · {datos['nombre']} · Financiamiento 2 a 8 años")
    else:
        enviar_whatsapp(numero, _texto_tabla_financiamiento_bnv(producto))
    cuota = cuota_sin_intereses_bnv(producto)
    contado = precio_contado_bnv(producto, 0.03)
    return enviar_whatsapp(
        numero,
        f"✨ *1 año sin intereses:* enganche {datos['enganche_texto']} + 11 pagos de *{formatear_quetzales(cuota)}*.\n"
        f"💰 *Contado:* con 3% de descuento inicial queda en *{formatear_quetzales(contado)}*.\n\n"
        "¿Cuál de las tres formas de pago se adapta mejor a lo que usted busca? 😊"
    )


def respuesta_enganche_bnv(estado):
    producto = estado.get("bnv_producto")
    if producto in BNV_PRODUCTOS:
        datos = BNV_PRODUCTOS[producto]
        return (
            f"Para *{datos['nombre']}* el enganche es de *{datos['enganche_texto']}* 😊. "
            "¿Qué forma de pago le gustaría revisar: financiamiento, 1 año sin intereses o contado?"
        )
    return (
        "En Buenaventura el enganche depende de la opción 😊:\n\n"
        "• 8x16 para vivir/invertir: *Q6,000*\n"
        "• 8x18 para vivir/invertir: *Q8,000*\n"
        "• 8x16 comercial: *Q6,000*\n\n"
        "¿El terreno lo busca para vivir, invertir o para negocio?"
    )


def _es_pregunta_reserva_bnv(texto):
    t = normalizar_texto_topografia(texto)
    return any(x in t for x in ["reserva", "reservar", "apartar", "apartado", "cuanto para reservar", "cuanto para apartar"])


def _es_pregunta_registral_bnv(texto):
    t = normalizar_texto_topografia(texto)
    return any(x in t for x in ["finca", "folio", "libro"])


def _mensaje_es_pregunta_especifica_bnv(texto):
    t = normalizar_texto_topografia(texto)
    return any(x in t for x in [
        "mantenimiento", "escritur", "titulo de agua", "gastos", "agua", "servicios",
        "amenidades", "piscina", "garita", "muro", "enganche", "abono", "capital",
        "ubicacion", "donde queda", "maps", "plano", "requisitos", "documentos",
        "construir", "urbanizacion", "disponibilidad"
    ])


def manejar_flujo_buenaventura_humano(numero, texto, proyecto, message_id):
    """Flujo progresivo de Buenaventura. Devuelve True cuando consume el mensaje."""
    if proyecto != "buenaventura":
        return False

    estado = estado_bnv(numero)
    t = normalizar_texto_topografia(texto)
    cta = detectar_cta_bnv_nuevo(texto)

    # Visita siempre rompe el protocolo comercial.
    if cta == "visita" or detectar_intencion_visita(texto):
        respuesta = respuesta_visita(numero, texto, "buenaventura")
        estado["bnv_etapa"] = "visita"
        estado["bnv_pregunta_pendiente"] = "dia_hora_visita"
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    if cta == "ubicacion":
        guardar_mensaje(numero, "user", texto)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_ubicacion_proyecto(numero, "buenaventura")
        return True

    # Datos no definidos: mejor detenerse que inventar.
    if _es_pregunta_reserva_bnv(texto):
        respuesta = (
            "Con gusto le ayudo a reservar 😊. El monto exacto de reserva de Buenaventura no lo tengo cargado en esta versión, "
            "así que prefiero confirmarlo antes de darle un dato incorrecto. ¿Me permite revisarlo?"
        )
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
            marcar_intervencion_automatica(numero, texto, motivo="monto de reserva de Buenaventura no cargado")
        return True

    if _es_pregunta_registral_bnv(texto):
        respuesta = (
            "Ese dato registral prefiero confirmarlo antes de indicárselo para no darle información incorrecta 😊. "
            "¿Me permite revisarlo?"
        )
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
            marcar_intervencion_automatica(numero, texto, motivo="dato registral Buenaventura no cargado")
        return True

    # FAQs de información/precios/lotes disponibles: todas inician el protocolo.
    if cta == "inicio" or (not estado.get("bnv_etapa") and es_inicio_general_bnv(texto)):
        estado = reiniciar_flujo_bnv_para_presentacion(numero)
        bienvenida = generar_bienvenida_bnv(numero, texto)
        estado["bnv_etapa"] = "esperando_uso"
        estado["bnv_pregunta_pendiente"] = "uso"
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", bienvenida)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, bienvenida)
            enviar_plano_inicio_bnv(numero)
        return True

    uso = detectar_uso_bnv(texto)
    producto = detectar_producto_bnv(texto, estado)
    plan = detectar_plan_bnv(texto)
    plazo = extraer_plazo_cuota(texto)

    # Si pide precio/cuotas antes de explicar el uso, calificamos primero.
    if estado.get("bnv_etapa") in {None, "esperando_uso"} and not uso:
        if any(x in t for x in ["precio", "precios", "cuota", "cuotas", "financiamiento", "medida", "medidas", "cuanto cuesta", "cuanto vale"]):
            respuesta = (
                "Claro 😊 En Buenaventura el precio cambia según el uso del terreno. "
                "¿Lo busca *para vivir*, *para invertir* o *para negocio*?"
            )
            estado["bnv_etapa"] = "esperando_uso"
            estado["bnv_pregunta_pendiente"] = "uso"
            persistir_cliente(numero)
            guardar_mensaje(numero, "user", texto)
            guardar_mensaje(numero, "assistant", respuesta)
            if procesamiento_sigue_vigente(numero, message_id):
                enviar_whatsapp(numero, respuesta)
            return True

    # Elección de uso.
    if uso:
        estado["bnv_uso"] = uso
        if uso == "negocio":
            estado["bnv_producto"] = "com_8x16"
            estado["bnv_etapa"] = "esperando_plan"
            estado["bnv_pregunta_pendiente"] = "plan_pago"
            respuesta = texto_producto_comercial_bnv()
        else:
            estado["bnv_producto"] = None
            estado["bnv_etapa"] = "esperando_medida"
            estado["bnv_pregunta_pendiente"] = "medida"
            respuesta = texto_opciones_residenciales_bnv(uso)
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
            if uso == "negocio" and not estado.get("bnv_video_enviado") and enviar_video_bnv(numero):
                estado["bnv_video_enviado"] = True
                persistir_cliente(numero)
        return True

    # Si menciona 8x16 antes de decir uso, no adivinamos si es residencial o comercial.
    if producto == "8x16_sin_uso":
        respuesta = (
            "Sí 😊 Tenemos 8x16, pero existe una opción residencial/inversión y otra comercial con precios distintos. "
            "¿Lo busca para vivir, invertir o para negocio?"
        )
        estado["bnv_etapa"] = "esperando_uso"
        estado["bnv_pregunta_pendiente"] = "uso"
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    if producto == "no_disponible_9x20":
        respuesta = (
            "Actualmente en este flujo de Buenaventura estamos manejando *8x16 y 8x18* para vivir/invertir, "
            "y *8x16 comercial* para negocio 😊. ¿Cuál de esas opciones le interesa revisar?"
        )
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    # Selección de medida residencial.
    if producto in {"res_8x16", "res_8x18"} and estado.get("bnv_uso") in {"vivir", "inversion"}:
        estado["bnv_producto"] = producto
        estado["bnv_etapa"] = "esperando_plan"
        estado["bnv_pregunta_pendiente"] = "plan_pago"
        datos = BNV_PRODUCTOS[producto]
        respuesta = (
            f"Excelente 😊 El *{datos['medida']}* tiene un valor de *{datos['precio_texto']}* y enganche de *{datos['enganche_texto']}*.\n\n"
            + texto_planes_pago_bnv(producto)
        )
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
            if not estado.get("bnv_video_enviado") and enviar_video_bnv(numero):
                estado["bnv_video_enviado"] = True
                persistir_cliente(numero)
        return True

    # Pregunta directa de enganche: responder según contexto, sin reiniciar.
    if "enganche" in t:
        respuesta = respuesta_enganche_bnv(estado)
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    # Gastos fijos para cualquier uso.
    if pide_gastos_adicionales(texto) or any(x in t for x in ["escrituracion", "titulo de agua", "mantenimiento"]):
        respuesta = respuesta_gastos_adicionales("buenaventura")
        if "?" not in respuesta[-30:]:
            respuesta += "\n\n¿Desea que le explique también cuándo se paga cada uno?"
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    # Garita / muro depende del sector.
    if any(x in t for x in ["garita", "muro perimetral", "muro"]):
        if estado.get("bnv_uso") == "negocio" or estado.get("bnv_producto") == "com_8x16":
            respuesta = (
                "En el *área comercial* de Buenaventura no hay garita ni muro perimetral. "
                "Sí mantiene los servicios cargados del proyecto 😊. ¿Desea que le muestre el financiamiento del 8x16 comercial?"
            )
        else:
            respuesta = (
                "En el sector residencial de Buenaventura sí se contemplan garita y muro perimetral, además de los servicios y amenidades del proyecto 😊. "
                "¿Lo está considerando para vivir o para invertir?"
            )
        guardar_mensaje(numero, "user", texto)
        guardar_mensaje(numero, "assistant", respuesta)
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)
        return True

    # Formas de pago. Requieren producto definido para no mezclar precios.
    if plan or (plazo and 2 <= plazo <= 8):
        producto_actual = estado.get("bnv_producto")
        if producto_actual not in BNV_PRODUCTOS:
            if estado.get("bnv_uso") in {"vivir", "inversion"}:
                respuesta = "Con gusto 😊 Antes necesito saber qué medida desea tomar como referencia: *8x16* o *8x18*. ¿Cuál le interesa?"
                estado["bnv_etapa"] = "esperando_medida"
                estado["bnv_pregunta_pendiente"] = "medida"
            else:
                respuesta = "Con gusto 😊 Para darle el plan correcto, ¿el terreno lo busca para vivir, invertir o para negocio?"
                estado["bnv_etapa"] = "esperando_uso"
                estado["bnv_pregunta_pendiente"] = "uso"
            persistir_cliente(numero)
            guardar_mensaje(numero, "user", texto)
            guardar_mensaje(numero, "assistant", respuesta)
            if procesamiento_sigue_vigente(numero, message_id):
                enviar_whatsapp(numero, respuesta)
            return True

        plan = plan or "financiamiento"
        estado["bnv_plan"] = plan
        estado["bnv_plazo"] = plazo if plazo and 2 <= plazo <= 8 else None
        estado["bnv_etapa"] = "esperando_reaccion_propuesta"
        estado["bnv_cotizacion_enviada"] = True
        estado["bnv_pregunta_pendiente"] = "reaccion_propuesta"
        persistir_cliente(numero)
        guardar_mensaje(numero, "user", texto)
        if procesamiento_sigue_vigente(numero, message_id):
            if plan == "financiamiento":
                enviar_financiamiento_bnv(numero, producto_actual, estado.get("bnv_plazo"))
            elif plan == "sin_intereses":
                enviar_plan_sin_intereses_bnv(numero, producto_actual)
            elif plan == "contado":
                enviar_contado_bnv(numero, producto_actual)
            elif plan == "todos":
                enviar_comparacion_bnv(numero, producto_actual)
        return True

    # Una reacción positiva después de la propuesta avanza a visita en vez de repetir menús.
    if estado.get("bnv_etapa") == "esperando_reaccion_propuesta":
        if es_reaccion_positiva_vh(texto):
            respuesta = (
                "Me alegra que la opción le interese 😊🏡. Lo ideal ahora sería que conozca Buenaventura personalmente y vea el proyecto. "
                "¿Qué día le quedaría bien visitarlo?"
            )
            estado["bnv_etapa"] = "visita"
            estado["bnv_pregunta_pendiente"] = "dia_hora_visita"
            persistir_cliente(numero)
            guardar_mensaje(numero, "user", texto)
            guardar_mensaje(numero, "assistant", respuesta)
            if procesamiento_sigue_vigente(numero, message_id):
                enviar_whatsapp(numero, respuesta)
            return True

    # Si la conversación sigue abierta y es una pregunta puntual, dejamos que la IA
    # general responda usando BNV_FICHA_OFICIAL y el estado persistente.
    if _mensaje_es_pregunta_especifica_bnv(texto):
        persistir_cliente(numero)
        return False

    return False

# ============================================================
# CONSULTAS MULTIPLES EN UN MISMO BLOQUE
# ============================================================

def _pide_ubicacion_directa_multi(texto):
    """
    Para el coordinador multi-intencion evitamos confundir "mapa/plano del
    proyecto" con una solicitud de Google Maps.
    """
    t = normalizar_ventas(texto)
    frases = [
        "ubicacion", "donde queda", "como llego", "direccion",
        "google maps", "maps", "mandame ubicacion", "manda ubicacion"
    ]
    return any(x in t for x in frases)


def manejar_intenciones_multiples(numero, texto, proyecto, message_id):
    """
    Atiende varias solicitudes que llegaron juntas durante la ventana de 8 s.

    Antes, el procesador usaba una cadena de `if ... return`: al encontrar por
    ejemplo "ubicacion", respondia eso y ya no alcanzaba a procesar "precios".
    Este coordinador detecta varias intenciones independientes y las ejecuta en
    la misma tanda sin alterar el comportamiento normal cuando solo hay una.
    """
    texto = str(texto or "").strip()
    if not texto:
        return False

    # Intenciones especializadas de dinero. Evitamos contar dos veces la misma
    # pregunta (por ejemplo, "enganche" tambien puede coincidir con cotizacion).
    quiere_enganche = pregunta_enganche(texto)
    quiere_cuota = pregunta_cuota_especifica(texto)
    quiere_medidas = pregunta_medidas_disponibles(texto)

    quiere_precio = False
    if not quiere_enganche and not quiere_cuota:
        quiere_precio = (
            es_consulta_general_de_precio(texto)
            or debe_enviar_cotizacion_directa(numero, texto)
        )

    quiere_plano = pide_plano(texto)
    quiere_ubicacion = _pide_ubicacion_directa_multi(texto)
    quiere_multimedia = pide_fotos(texto) or pide_videos(texto)
    quiere_requisitos = cliente_en_extranjero(texto) or pide_requisitos_compra(texto)
    quiere_gastos = pide_gastos_adicionales(texto)
    quiere_visita = detectar_intencion_visita(texto)

    intenciones = [
        nombre for nombre, activa in [
            ("enganche", quiere_enganche),
            ("cuota", quiere_cuota),
            ("medidas", quiere_medidas),
            ("precio", quiere_precio),
            ("ubicacion", quiere_ubicacion),
            ("plano", quiere_plano),
            ("multimedia", quiere_multimedia),
            ("requisitos", quiere_requisitos),
            ("gastos", quiere_gastos),
            ("visita", quiere_visita),
        ] if activa
    ]

    # Con una sola intención dejamos trabajar exactamente al flujo anterior.
    if len(intenciones) < 2:
        return False

    print("\n========================================")
    print("CONSULTA MULTI-INTENCION")
    print("========================================")
    print("CLIENTE:", numero)
    print("INTENCIONES:", ", ".join(intenciones))

    # Calcular esto ANTES de guardar el bloque actual. De lo contrario el propio
    # bloque se contaría como una consulta comercial anterior.
    primera_consulta_comercial = es_primera_consulta_comercial(numero)

    guardar_mensaje(numero, "user", texto)

    # Si esta es la primera consulta comercial y pidió precio, usamos el paquete
    # completo existente. Ese paquete YA contiene ubicación, cotizaciones y
    # material visual, así que no los repetimos después.
    paquete_completo_enviado = False
    if (
        proyecto not in {"palmeras", "vista_hermosa"}
        and quiere_precio
        and es_consulta_general_de_precio(texto)
        and primera_consulta_comercial
    ):
        if procesamiento_sigue_vigente(numero, message_id):
            if proyecto:
                enviar_info_completa_proyecto(numero, proyecto, cierre=True)
                paquete_completo_enviado = True
            else:
                enviar_whatsapp(
                    numero,
                    "¡Claro! 😊 ¿De cuál proyecto desea conocer los precios y la información?"
                )
        # Si no sabemos el proyecto, no podemos ejecutar correctamente el resto.
        if not proyecto:
            guardar_mensaje(
                numero,
                "assistant",
                "Se pidió confirmar el proyecto para atender varias solicitudes."
            )
            return True

    # Dinero / cotizaciones cuando no se mandó ya el paquete completo.
    if not paquete_completo_enviado:
        if quiere_enganche:
            respuesta = respuesta_enganche(proyecto, texto)
            if respuesta and procesamiento_sigue_vigente(numero, message_id):
                enviar_whatsapp(numero, respuesta)

        if quiere_cuota:
            respuesta = respuesta_cuota_especifica(proyecto, texto)
            if respuesta and procesamiento_sigue_vigente(numero, message_id):
                enviar_whatsapp(numero, respuesta)

        if quiere_medidas:
            respuesta = respuesta_medidas_disponibles(proyecto)
            if respuesta and procesamiento_sigue_vigente(numero, message_id):
                enviar_whatsapp(numero, respuesta)

        if quiere_precio:
            if es_consulta_general_de_precio(texto):
                respuesta = respuesta_precio_breve_con_intencion(proyecto)
                if respuesta and procesamiento_sigue_vigente(numero, message_id):
                    enviar_whatsapp(numero, respuesta)
            else:
                if procesamiento_sigue_vigente(numero, message_id):
                    enviar_cotizacion_del_proyecto(
                        numero,
                        proyecto,
                        detectar_medida_en_texto(texto)
                    )

    # El paquete completo ya incluye ubicación y fotos/videos; no duplicarlos.
    if quiere_ubicacion and not paquete_completo_enviado:
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_ubicacion_proyecto(numero, proyecto)

    if quiere_plano:
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_planos_solicitados(numero, proyecto, texto)

    if quiere_multimedia and not paquete_completo_enviado:
        if procesamiento_sigue_vigente(numero, message_id):
            enviar_multimedia_del_proyecto(
                numero,
                proyecto,
                enviar_fotos=pide_fotos(texto),
                enviar_videos=pide_videos(texto)
            )

    if quiere_requisitos:
        respuesta = respuesta_requisitos_segun_contexto(numero, texto)
        if respuesta and procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)

    if quiere_gastos:
        respuesta = respuesta_gastos_adicionales(proyecto)
        if respuesta and procesamiento_sigue_vigente(numero, message_id):
            ultima_intencion[numero] = "gastos_adicionales"
            enviar_whatsapp(numero, respuesta)

    if quiere_visita and not cita_ya_cerrada(numero):
        respuesta = respuesta_visita(numero, texto, proyecto)
        if respuesta and procesamiento_sigue_vigente(numero, message_id):
            enviar_whatsapp(numero, respuesta)

    guardar_mensaje(
        numero,
        "assistant",
        "Atendí en la misma respuesta estas solicitudes: " + ", ".join(intenciones) + "."
    )
    return True


# ============================================================
# RECIBIR MENSAJES DE WHATSAPP
# ============================================================

def procesar_mensaje_en_segundo_plano(datos, message_id):
    """
    Procesa IA, cotizaciones, fotos y videos DESPUES de que el webhook
    ya respondió 200 a Meta. Así Meta no interpreta que tardamos y no
    reenvía el mismo mensaje una y otra vez.
    """
    try:
        value = datos["entry"][0]["changes"][0]["value"]

        if "messages" not in value:
            return

        mensaje = value["messages"][0]

        numero_cliente = mensaje["from"]
        tipo_mensaje = mensaje.get("type")

        # PRIMERO fijamos el proyecto del anuncio. Esto debe ocurrir incluso si
        # Gabriel tiene el chat en MANUAL o si el primer mensaje es solo un saludo.
        fijar_proyecto_desde_anuncio(numero_cliente, mensaje)

        if tipo_mensaje == "text":
            # Los textos llegan aquí YA agrupados por el worker de 8 segundos.
            # Si alguna ruta interna llama este procesador con un texto normal,
            # seguimos siendo compatibles y usamos el body tal cual.
            texto_agrupado = str(
                (mensaje.get("text") or {}).get("body") or ""
            ).strip()

            if not texto_agrupado:
                return

            if not procesamiento_sigue_vigente(numero_cliente, message_id):
                print("PROCESAMIENTO ANTIGUO CANCELADO:", message_id)
                return
        else:
            if not procesamiento_sigue_vigente(numero_cliente, message_id):
                print("PROCESAMIENTO ANTIGUO CANCELADO:", message_id)
                return

        print("\nNUMERO DEL CLIENTE:")
        print(numero_cliente)

        # Si Gabriel tomó el control desde el CRM, la IA no responde.
        # El mensaje ya quedó registrado por el webhook para verlo en el CRM.
        if crm_esta_manual(numero_cliente):
            print("CRM: conversación en modo MANUAL. IA pausada.")
            return

        if tipo_mensaje == "audio":
            # La nota de voz se convierte en texto y continúa por TODO el flujo normal.
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
                        "Recibí tu audio 🎙️😊, pero no pude transcribirlo "
                        "en este momento. Intenta enviarlo nuevamente."
                    )
                return

            print("\nAUDIO TRANSCRITO:")
            print(texto_cliente)
            crm_actualizar_contenido_por_evento(
                numero_cliente,
                message_id,
                f"🎙️ Audio recibido\n📝 {texto_cliente}"
            )

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

        # PRESENTACION INICIAL:
        # Palmeras tiene una bienvenida comercial propia y flexible. Si el proyecto
        # ya viene identificado como Palmeras y el mensaje es genérico, NO mandamos
        # antes el saludo corto porque duplicaría la presentación.
        proyecto_previo_presentacion = obtener_proyecto_actual(numero_cliente)
        proyecto_mencionado_presentacion = detectar_proyecto_en_texto(texto_cliente)
        proyecto_para_presentacion = proyecto_previo_presentacion or proyecto_mencionado_presentacion
        cta_palmeras_presentacion = detectar_cta_palmeras(texto_cliente)
        cta_vh_presentacion = detectar_cta_vista_hermosa(texto_cliente)
        cta_bnv_presentacion = detectar_cta_bnv_nuevo(texto_cliente)
        if proyecto_para_presentacion == "palmeras" and (
            es_inicio_general_psm(texto_cliente)
            or cta_palmeras_presentacion in {"informacion", "precios_cuotas", "visita"}
        ):
            presentacion_enviada = False
        elif proyecto_para_presentacion == "vista_hermosa" and (
            es_inicio_general_vh(texto_cliente)
            or cta_vh_presentacion in {"informacion", "precios_cuotas", "visita"}
        ):
            # Vista Hermosa también tiene su propia presentación comercial progresiva.
            presentacion_enviada = False
        elif proyecto_para_presentacion == "buenaventura" and (
            es_inicio_general_bnv(texto_cliente)
            or cta_bnv_presentacion in {"inicio", "visita", "ubicacion"}
        ):
            # Buenaventura usa su propia presentación y calificación por uso.
            presentacion_enviada = False
        else:
            presentacion_enviada = enviar_presentacion_si_corresponde(
                numero_cliente,
                message_id
            )

        # Si el PRIMER mensaje fue únicamente un saludo, ya respondimos con la
        # presentación. Terminamos aquí para que OpenAI no mande un segundo saludo.
        #
        # Si escribió algo como:
        # "Hola, ¿cuánto cuesta Buenaventura?"
        # NO entra aquí: se presenta y luego continúa para responder la consulta.
        if presentacion_enviada and es_solo_saludo(texto_cliente):
            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(
                numero_cliente,
                "assistant",
                mensaje_presentacion_inicial()
            )
            return

        # El proyecto del anuncio ya quedó fijado al inicio del procesamiento.
        # Si el cliente menciona explícitamente otro proyecto en el texto,
        # esa mención sí puede cambiar el proyecto activo a continuación.

        # Mantener proyecto fijo por número.
        proyecto = actualizar_proyecto_activo(
            numero_cliente,
            texto_cliente
        )

        # ========================================================
        # MULTIMEDIA CON PRIORIDAD GLOBAL
        # ========================================================
        # Si el cliente pide fotos o videos, se le envía exactamente el tipo
        # solicitado ANTES de cualquier protocolo comercial. Así Palmeras,
        # Vista Hermosa y Buenaventura obedecen la petición aunque la conversación
        # esté esperando fase, uso, medida o forma de pago.
        quiere_fotos_prioridad = pide_fotos(texto_cliente)
        quiere_videos_prioridad = pide_videos(texto_cliente)
        if quiere_fotos_prioridad or quiere_videos_prioridad:
            guardar_mensaje(numero_cliente, "user", texto_cliente)
            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_multimedia_del_proyecto(
                    numero_cliente,
                    proyecto,
                    enviar_fotos=quiere_fotos_prioridad,
                    enviar_videos=quiere_videos_prioridad
                )
            return

        # BUENAVENTURA CUYOTENANGO: flujo comercial progresivo con
        # calificación adicional por uso (vivir / invertir / negocio).
        if manejar_flujo_buenaventura_humano(
            numero_cliente,
            texto_cliente,
            proyecto,
            message_id
        ):
            return

        # VISTA HERMOSA: mismo cerebro comercial progresivo de Palmeras,
        # con sus precios, fases, reserva, garita, muro y reglas propias.
        if manejar_flujo_vista_hermosa_humano(
            numero_cliente,
            texto_cliente,
            proyecto,
            message_id
        ):
            return

        # PALMERAS SAN MIGUEL: conversación comercial progresiva.
        # Va ANTES del coordinador genérico para evitar que una consulta de precio
        # vuelva a disparar el paquete completo antiguo.
        if manejar_flujo_palmeras_humano(
            numero_cliente,
            texto_cliente,
            proyecto,
            message_id
        ):
            return

        # Si el cliente envió varias preguntas seguidas (o una sola frase con
        # varias solicitudes), las atendemos TODAS antes de entrar a los flujos
        # de una sola intención que terminan con `return`.
        if manejar_intenciones_multiples(
            numero_cliente,
            texto_cliente,
            proyecto,
            message_id
        ):
            return

        # ========================================================
        # BOTONES CONTROLADOS DE LA CAMPAÑA DE BUENAVENTURA
        # ========================================================
        # Tienen prioridad sobre todos los detectores generales y sobre OpenAI.
        # Así "precios y cuotas", "ubicación", "lotes disponibles" y "agendar visita"
        # siempre siguen el guion definido para esta campaña.
        if manejar_cta_buenaventura(
            numero_cliente,
            texto_cliente,
            proyecto,
            message_id
        ):
            return

        # Respuestas cortas a preguntas que hizo el flujo anterior:
        # "para mi casa", "locales", "fin de semana", "sábado", "por la tarde", etc.
        if manejar_seguimiento_cta_buenaventura(
            numero_cliente,
            texto_cliente,
            proyecto,
            message_id
        ):
            return

        # INFORMACIÓN DE LOS TRES PROYECTOS EN UNA SOLA CONSULTA
        # No obligamos al cliente a escoger antes si pidió explícitamente las 3 opciones.
        if pide_info_todos_proyectos(texto_cliente):
            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(
                numero_cliente,
                "assistant",
                "Se envió el resumen comparativo de los 3 proyectos con ubicación, servicios y fotos de amenidades."
            )
            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_info_todos_proyectos(numero_cliente)
            return

        # Si justo antes recibió la información de los 3 proyectos y ahora elige uno,
        # tratamos esa elección como si hubiera pedido información completa de ese proyecto
        # desde el inicio. A partir de ahí queda fijado como proyecto activo y sigue el
        # algoritmo normal de precios, planos, cuotas, fotos, ubicación, etc.
        if esperando_proyecto_despues_tres(numero_cliente):
            elegido = proyecto_elegido_despues_tres(texto_cliente)
            if elegido:
                estado = obtener_estado_conversacion(numero_cliente)
                estado["proyecto_actual"] = elegido
                proyecto_activo[numero_cliente] = elegido
                estado["esperando_proyecto_despues_tres"] = False
                persistir_cliente(numero_cliente)

                guardar_mensaje(numero_cliente, "user", texto_cliente)
                guardar_mensaje(
                    numero_cliente,
                    "assistant",
                    f"Se envió la información completa del proyecto {elegido}."
                )

                if procesamiento_sigue_vigente(numero_cliente, message_id):
                    if elegido == "palmeras":
                        estado_psm_actual = reiniciar_flujo_psm_para_presentacion(numero_cliente)
                        bienvenida = generar_bienvenida_psm(numero_cliente, texto_cliente)
                        estado_psm_actual["psm_etapa"] = "esperando_fase"
                        estado_psm_actual["psm_pregunta_pendiente"] = "fase"
                        persistir_cliente(numero_cliente)
                        enviar_whatsapp(numero_cliente, bienvenida)
                        enviar_planos_psm_sin_topografia(numero_cliente)
                    elif elegido == "vista_hermosa":
                        estado_vh_actual = reiniciar_flujo_vh_para_presentacion(numero_cliente)
                        bienvenida = generar_bienvenida_vh(numero_cliente, texto_cliente)
                        estado_vh_actual["vh_etapa"] = "esperando_fase"
                        estado_vh_actual["vh_pregunta_pendiente"] = "fase"
                        persistir_cliente(numero_cliente)
                        enviar_whatsapp(numero_cliente, bienvenida)
                        enviar_planos_vh(numero_cliente)
                    else:
                        enviar_info_completa_proyecto(numero_cliente, elegido, cierre=True)
                return

            # No reutilizar un proyecto viejo si el cliente todavía no eligió cuál de los 3.
            if any(x in normalizar_texto_topografia(texto_cliente) for x in [
                "cotizacion", "cotización", "plano", "precio", "precios", "cuota", "financiamiento"
            ]):
                respuesta = (
                    "¡Claro! 😊 Te lo envío. Solo dime de cuál de los 3 proyectos lo quieres: "
                    "Buenaventura Cuyotenango, Palmeras San Miguel o Vista Hermosa. 🏡"
                )
                guardar_mensaje(numero_cliente, "user", texto_cliente)
                guardar_mensaje(numero_cliente, "assistant", respuesta)
                if procesamiento_sigue_vigente(numero_cliente, message_id):
                    enviar_whatsapp(numero_cliente, respuesta)
                return

        # CONTINUACIÓN DE FOTOS/VIDEOS PENDIENTES
        # Ejemplo:
        # Cliente: "Me puede fotos"
        # Bot: "¿De cuál proyecto?"
        # Cliente: "Palmeras San Miguel"
        # => enviar el material inmediatamente, sin volver a preguntar qué desea.
        if multimedia_pendiente(numero_cliente) and proyecto:
            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(
                numero_cliente,
                "assistant",
                f"Se envió el material multimedia del proyecto {proyecto}."
            )

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_multimedia_del_proyecto(
                    numero_cliente,
                    proyecto,
                    enviar_fotos=True,
                    enviar_videos=True
                )
            return

        # SEGUIMIENTO DE TOPOGRAFÍA DESPUÉS DE ENVIAR PLANOS
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

        # Si ya estamos hablando de topografía y manda un número de lote.
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
            respuesta = respuesta_plazo_escritura(proyecto)

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
        # Debe resolverse antes de IA, cotización, cuotas o cualquier otra rama.
        # También conserva el tema para seguimientos como "¿cuánto es de cada uno?".
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

        # DESCUENTO POR PAGO DE CONTADO - REGLA EXACTA
        respuesta_desc_pendiente = respuesta_cantidad_descuento_pendiente(
            numero_cliente,
            texto_cliente
        )
        if respuesta_desc_pendiente:
            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta_desc_pendiente)
            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta_desc_pendiente)
            return

        if pregunta_descuento_contado(texto_cliente):
            respuesta = respuesta_descuento_contado(numero_cliente, texto_cliente)
            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)
            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)
            return

        # DISEÑO DE CONSTRUCCION LIBRE
        if pregunta_diseno_construccion(texto_cliente):
            respuesta = respuesta_diseno_construccion()
            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)
            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)
            return

        # PALMERAS: explicar POR QUÉ no hay garita únicamente si el cliente lo pregunta.
        if pregunta_por_que_sin_garita_palmeras(texto_cliente, proyecto):
            respuesta = respuesta_por_que_sin_garita_palmeras()
            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)
            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)
            return

        # ESTADO REAL DE GARITA / AMENIDADES SEGUN PROYECTO
        if pregunta_estado_amenidades_o_garita(texto_cliente):
            respuesta = respuesta_estado_amenidades(numero_cliente, proyecto)
            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)
            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)
            return

        # CONFIRMACION AL CTA "QUIERE QUE LE MUESTRE CUALES TENEMOS DISPONIBLES"
        # Envia directamente el/los planos, leyenda de colores y seguimiento de topografia.
        if confirmacion_para_mostrar_disponibilidad(numero_cliente, texto_cliente):
            if not proyecto:
                respuesta = (
                    "Claro 😊 ¿De qué proyecto deseas que te muestre la disponibilidad: "
                    "Palmeras San Miguel, Vista Hermosa o Buenaventura Cuyotenango?"
                )
                guardar_mensaje(numero_cliente, "user", texto_cliente)
                guardar_mensaje(numero_cliente, "assistant", respuesta)
                if procesamiento_sigue_vigente(numero_cliente, message_id):
                    enviar_whatsapp(numero_cliente, respuesta)
                return

            limpiar_confirmacion_disponibilidad(numero_cliente)
            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(
                numero_cliente,
                "assistant",
                f"Se enviaron los planos de {nombre_proyecto_plano(proyecto)}, la leyenda de colores y la pregunta sobre topografía."
            )
            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_planos_solicitados(numero_cliente, proyecto, "disponibilidad")
            return

        # TOPOGRAFÍA DEL TERRENO - RESPUESTA INTELIGENTE
        # "lote plano" significa terreno llano; NO debe enviar el PDF/croquis.
        if pregunta_topografia_terreno(texto_cliente):
            respuesta = generar_respuesta(
                numero_cliente,
                texto_cliente
            )

            if not respuesta or not respuesta.strip():
                respuesta = (
                    "Claro 😊 Déjame revisar exactamente lo que me solicitas "
                    "y te lo envío en un momento."
                )

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)

            return

        # PLANOS / MAPA DE LOTES - PRIORIDAD ALTA
        # Usa los PDF públicos de GitHub Pages. Si el archivo se actualiza
        # conservando el mismo nombre, el bot seguirá enviando la versión nueva.
        if pide_plano(texto_cliente):
            # Si el mensaje trae un proyecto explícito, actualizar_proyecto_activo
            # ya lo habrá fijado. Si no, usamos el proyecto de la conversación.
            if not proyecto:
                respuesta = (
                    "Claro 😊 ¿De qué proyecto deseas que te envíe el plano: "
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
                f"Se enviaron los planos de {nombre_proyecto_plano(proyecto)}, la leyenda de colores y la pregunta sobre topografía."
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
        # Si el cliente pregunta dónde nos podemos juntar, sugerimos primero
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
        # Nunca volvemos a ofrecer otra visita ni preguntamos otro día/hora
        # a menos que el cliente pida explícitamente cambiar/reprogramar.
        if cita_ya_cerrada(numero_cliente) and pregunta_sobre_cita_existente(texto_cliente):
            respuesta = resumen_cita_cerrada(numero_cliente)

            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_whatsapp(numero_cliente, respuesta)

            return

        # VISITA / CITA:
        # Si el cliente ya quiere conocer los lotes, dejamos de repetir información
        # y avanzamos directamente a coordinar día y hora.
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
        # Si el cliente dice que está fuera de Guatemala, o pide requisitos,
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
            # Si pide explícitamente una cotización, esa intención se atiende más abajo
            # para poder enviar la imagen correspondiente. Para consultas naturales como
            # "¿lotes de 8x18?" o "¿cuánto vale 8x16?", respondemos con el monto exacto.
            if not any(x in texto_cliente.lower() for x in ["cotizacion", "cotización", "cotizaciones"]):
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
        # Si por el proyecto activo la mejor recomendación es Xochi,
        # responde la ruta y envía automáticamente el tarifario.
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
        # Recuperamos también el proyecto persistente por si el mensaje actual es muy corto
        # y no vuelve a mencionar "Vista Hermosa" o "Palmeras".
        proyecto_diferencia = proyecto or obtener_proyecto_actual(numero_cliente)
        if pregunta_por_diferencia_de_fases(texto_cliente, proyecto_diferencia):
            respuesta = respuesta_diferencia_fases(numero_cliente)

            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(numero_cliente, "assistant", respuesta)

            enviar_whatsapp(numero_cliente, respuesta)
            return

        # CUOTA ESPECIFICA POR PLAZO:
        # Si pregunta "¿cuánto es la cuota a 7 años?", responder el monto.
        # NO volver a enviar las imágenes de cotización.
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

        # PRECIO GENERAL: EVITAR REPETIR TODO EL PAQUETE
        # Si "¿cuánto valen los terrenos?" es la primera consulta comercial,
        # mantenemos el comportamiento completo. Si la conversación ya venía
        # avanzando, respondemos solo precios + una pregunta de calificación.
        if proyecto != "palmeras" and es_consulta_general_de_precio(texto_cliente):
            if es_primera_consulta_comercial(numero_cliente):
                guardar_mensaje(numero_cliente, "user", texto_cliente)
                guardar_mensaje(
                    numero_cliente,
                    "assistant",
                    f"Se envió la información completa de {proyecto or 'el proyecto'} por ser la primera consulta comercial."
                )
                if procesamiento_sigue_vigente(numero_cliente, message_id):
                    if proyecto:
                        enviar_info_completa_proyecto(numero_cliente, proyecto, cierre=True)
                    else:
                        enviar_whatsapp(
                            numero_cliente,
                            "¡Claro! 😊 ¿De cuál proyecto desea conocer los precios?"
                        )
                return

            respuesta_precio = respuesta_precio_breve_con_intencion(proyecto)
            if respuesta_precio:
                guardar_mensaje(numero_cliente, "user", texto_cliente)
                guardar_mensaje(numero_cliente, "assistant", respuesta_precio)
                if procesamiento_sigue_vigente(numero_cliente, message_id):
                    enviar_whatsapp(numero_cliente, respuesta_precio)
                return

        # PRECIOS / CUOTAS / COTIZACIONES
        # Cotización explícita, cuotas, plazos o confirmaciones conservan el flujo
        # de imágenes y planes de pago existente.
        if proyecto != "palmeras" and debe_enviar_cotizacion_directa(
            numero_cliente,
            texto_cliente
        ):
            enviar_cotizacion_del_proyecto(
                numero_cliente,
                proyecto,
                detectar_medida_en_texto(texto_cliente)
            )
            return

        # MULTIMEDIA CONTROLADA (fallback; la prioridad global está arriba).
        quiere_fotos = pide_fotos(texto_cliente)
        quiere_videos = pide_videos(texto_cliente)

        if quiere_fotos or quiere_videos:
            enviar_multimedia_del_proyecto(
                numero_cliente,
                proyecto,
                enviar_fotos=quiere_fotos,
                enviar_videos=quiere_videos
            )
            return

        # SELECCIÓN SIMPLE DE PROYECTO -> INFORMACIÓN COMPLETA DIRECTA
        # Si el cliente únicamente responde con el nombre del proyecto (por ejemplo
        # "De Buenaventura"), no lo hacemos elegir entre cotización, ubicación,
        # requisitos o visita. Enviamos de una vez el paquete completo que ya existe
        # en este app.py: resumen, ubicación, cotizaciones, fotos/videos y amenidades.
        # Este bloque está justo antes de la IA para NO alterar ningún flujo específico
        # que ya se trabajó anteriormente.
        if proyecto and proyecto != "palmeras" and es_seleccion_simple_de_proyecto(texto_cliente):
            guardar_mensaje(numero_cliente, "user", texto_cliente)
            guardar_mensaje(
                numero_cliente,
                "assistant",
                f"Se envió la información completa del proyecto {proyecto}."
            )

            if procesamiento_sigue_vigente(numero_cliente, message_id):
                enviar_info_completa_proyecto(
                    numero_cliente,
                    proyecto,
                    cierre=True
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

            # Si la IA recomendó Xochi al responder una consulta de ruta,
            # adjuntamos el tarifario automáticamente.
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
        # El tiempo de inactividad empieza DESPUÉS de que el bot termina
        # de responder, incluso si era el primer mensaje de la conversación.
        # Si el cliente mandó otro mensaje mientras procesábamos, este proceso
        # viejo no programa ningún seguimiento.
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
    Meta puede incluir MÁS DE UN mensaje dentro de value["messages"].
    Procesamos cada elemento por separado para que cada mensaje:
    - aparezca en el CRM;
    - genere su propia notificación Push;
    - sea procesado por el bot.
    """
    datos = request.get_json()

    print("\n========================================")
    print("WEBHOOK RECIBIDO")
    print("========================================")

    try:
        value = datos["entry"][0]["changes"][0]["value"]

        # Estados de enviado / entregado / leído.
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

                # Detectar y guardar el proyecto DEL ANUNCIO antes de registrar el
                # mensaje en CRM. Así se muestra "Palmeras San Miguel" de inmediato
                # aunque la conversación esté en modo MANUAL y la IA esté pausada.
                fijar_proyecto_desde_anuncio(numero_cliente, mensaje)

                # 1) Guardar en CRM y disparar UNA notificación propia.
                # Si es una foto, también la conservamos de forma persistente
                # para poder verla luego dentro del CRM.
                media_url_crm = None
                media_tipo_crm = None
                if mensaje.get("type") in {"image", "audio", "video", "document"}:
                    media_url_crm, media_tipo_crm = guardar_media_whatsapp_crm(
                        numero_cliente,
                        mensaje
                    )

                crm_registrar_mensaje(
                    numero_cliente,
                    "in",
                    crm_resumen_entrante(mensaje),
                    event_id=message_id,
                    media_url=media_url_crm,
                    media_tipo=media_tipo_crm
                )

                # 2) Cancelar seguimiento pendiente.
                cancelar_seguimiento(numero_cliente)

                # 3) Los mensajes de TEXTO pasan al agrupador de 8 segundos.
                # No arrancamos un Thread por cada texto: un solo worker por
                # cliente espera el silencio, agrupa la tanda y la procesa.
                if mensaje.get("type") == "text":
                    acumular_mensaje_texto(
                        numero_cliente,
                        message_id,
                        mensaje
                    )
                else:
                    # Audio, imagen, video u otro tipo conservan el flujo inmediato.
                    iniciar_procesamiento(
                        numero_cliente,
                        message_id
                    )

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

        # Meta recibe 200 inmediatamente después de despachar todos.
        return "EVENT_RECEIVED", 200

    except Exception as error:
        print("\nERROR DEL WEBHOOK:")
        print(error)

        # Siempre respondemos 200 para evitar reintentos infinitos.
        return "EVENT_RECEIVED", 200


# ============================================================
# CRM WEB - GABRIEL
# ============================================================

# ============================================================
# RESUMENES DE LEADS PARA SEGUIMIENTO TELEFONICO
# ============================================================

lock_resumen_seguimiento = Lock()
ultimo_resultado_resumen = {"enviados": 0, "fallidos": 0, "fecha": None}


def _texto_conversacion_para_resumen(numero):
    """Construye un transcript factual del CRM; no agrega ni interpreta datos."""
    with lock_crm:
        lista = list(crm_mensajes.get(numero, []))

    lineas = []
    for m in lista[-120:]:
        contenido = str(m.get("contenido") or "").strip()
        if not contenido:
            continue
        # Los marcadores de fotos sirven como contexto, pero no intentamos inferir su contenido.
        rol = "CLIENTE" if m.get("direccion") == "in" else "ASESOR/BOT"
        lineas.append(f"{rol}: {contenido}")

    return "\n".join(lineas)


def generar_resumen_lead(numero):
    """Resume únicamente datos explícitos del historial. Si no existe un dato, lo omite."""
    transcript = _texto_conversacion_para_resumen(numero)
    proyecto = crm_nombre_proyecto(numero)

    if not transcript:
        return None

    instrucciones = """
Eres un asistente que prepara un resumen factual para una persona que llamará a un prospecto inmobiliario.

REGLAS OBLIGATORIAS:
- Usa ÚNICAMENTE información explícita del transcript que se te entrega.
- NO inventes ni deduzcas nombre, edad, profesión, presupuesto, motivo de compra, cantidad de lotes,
  forma de pago, país, disponibilidad, intención, parentescos ni ningún otro dato.
- NO conviertas una respuesta del asesor/bot en un dato afirmado por el cliente.
- Sí puedes indicar hechos de la conversación como: "se le envió el plano", "preguntó por precios",
  "consultó por financiamiento" o "dejó de responder después de...", solo si eso se observa en el transcript.
- Si no hay nombre, NO escribas un campo de nombre.
- Si no hay suficiente información para un campo, omítelo por completo. No escribas "No proporcionado".
- No agregues recomendaciones inventadas ni opiniones sobre qué tan interesado está.
- Sé MUY breve: el resumen debe poder leerse rápidamente antes de una llamada.
- Prioriza únicamente lo que el CLIENTE preguntó, pidió, confirmó o mostró interés en conocer.
- No repitas listas largas de amenidades, servicios, precios o explicaciones que haya dado el asesor/bot, salvo que el cliente haya reaccionado específicamente a ese dato.
- Resume Datos relevantes en 1 o 2 frases cortas.
- El Último punto debe ser una sola frase corta.
- Agrega un Seguimiento sugerido breve, basado SOLO en el punto donde quedó la conversación; no inventes necesidades ni interés.
- No menciones que eres IA ni expliques estas reglas.

FORMATO:
📞 Teléfono: +[número]
🏡 Proyecto: [solo si hay proyecto identificado]
📌 Datos relevantes: [1-2 frases cortas con lo más importante que expresó/preguntó el cliente]
📝 Último punto: [1 frase corta]
☎️ Seguimiento: [1 frase corta y práctica para retomar la conversación]

No añadas otros campos.
"""

    entrada = f"""NUMERO: +{numero}\nPROYECTO REGISTRADO EN CRM: {proyecto}\n\nTRANSCRIPT:\n{transcript}"""

    try:
        respuesta = client.responses.create(
            model="gpt-5-mini",
            instructions=instrucciones,
            input=entrada
        )
        texto = str(respuesta.output_text or "").strip()
        return texto or None
    except Exception as exc:
        print("ERROR GENERANDO RESUMEN LEAD:", numero, exc)
        # Fallback 100% factual si OpenAI falla.
        ultimos_cliente = []
        with lock_crm:
            for m in crm_mensajes.get(numero, [])[-30:]:
                if m.get("direccion") == "in" and str(m.get("contenido") or "").strip():
                    ultimos_cliente.append(str(m.get("contenido")).strip())
        if not ultimos_cliente:
            return f"📞 Teléfono: +{numero}\n🏡 Proyecto: {proyecto}"
        return (
            f"📞 Teléfono: +{numero}\n"
            + (f"🏡 Proyecto: {proyecto}\n" if proyecto != "Sin proyecto" else "")
            + "📌 Mensajes recientes del cliente: " + " | ".join(ultimos_cliente[-5:])
        )


def _fallback_resumen_corto(numero):
    """Fallback breve y 100% factual si una llamada de IA falla."""
    proyecto = crm_nombre_proyecto(numero)
    with lock_crm:
        mensajes = list(crm_mensajes.get(numero, []))

    entrantes = [
        str(m.get("contenido") or "").strip()
        for m in mensajes[-40:]
        if m.get("direccion") == "in" and str(m.get("contenido") or "").strip()
    ]

    if not entrantes:
        return None

    # No interpreta ni inventa: usa únicamente frases reales del cliente.
    recientes = entrantes[-3:]
    resumen_cliente = " / ".join(recientes)
    if len(resumen_cliente) > 320:
        resumen_cliente = resumen_cliente[:317].rstrip() + "..."

    lineas = [f"📞 +{numero}"]
    if proyecto and proyecto != "Sin proyecto":
        lineas.append(f"🏡 {proyecto}")
    lineas.append(f"📝 Resumen: {resumen_cliente}")
    lineas.append("☎️ Seguimiento: Retomar desde la última consulta del cliente.")
    return "\n".join(lineas)


def _generar_resumenes_chunk(numeros_chunk):
    """Genera un grupo pequeño de resúmenes en una sola llamada a OpenAI."""
    numeros_chunk = [str(n) for n in numeros_chunk]
    bloques = []

    for numero in numeros_chunk:
        transcript = _texto_conversacion_para_resumen(numero)
        proyecto = crm_nombre_proyecto(numero)
        if not transcript:
            continue
        # Limitamos contexto por lead para poder procesar muchos clientes sin saturar la petición.
        if len(transcript) > 5500:
            transcript = transcript[-5500:]
        bloques.append(
            f"=== CLIENTE {numero} ===\n"
            f"PROYECTO REGISTRADO EN CRM: {proyecto}\n"
            f"TRANSCRIPT:\n{transcript}\n"
        )

    if not bloques:
        return {}

    instrucciones = """
Eres un asistente que prepara resúmenes MUY CORTOS para una persona que llamará a prospectos inmobiliarios.
Redacta cada resumen con tus propias palabras, de forma natural, clara y útil para una llamada.

REGLAS OBLIGATORIAS:
- Usa ÚNICAMENTE información explícita del transcript de CADA cliente.
- NO inventes ni deduzcas datos que el cliente no haya dicho o que no estén registrados.
- NO mezcles información entre clientes.
- NO conviertas una respuesta del asesor/bot en una afirmación hecha por el cliente.
- Prioriza lo que el CLIENTE preguntó, pidió, confirmó, eligió o mostró interés en conocer.
- Omite listas largas de amenidades, servicios, precios y explicaciones del bot.
- Si un dato del asesor es necesario para entender dónde quedó la conversación, resúmelo en pocas palabras.
- No escribas 'No proporcionado'. Si un dato no existe, omítelo.
- NO opines sobre qué tan interesado está el cliente.
- El resumen debe ser rápido de leer antes de marcarle por teléfono.
- "Resumen" debe tener máximo 2 frases y aproximadamente 45 palabras.
- "Último punto" debe ser 1 frase muy corta.
- "Seguimiento" debe ser 1 frase práctica para retomar exactamente desde donde quedó.
- Usa tus propias palabras; NO copies párrafos completos del chat.

FORMATO EXACTO DE CADA MENSAJE:
📞 +[número]
🏡 [proyecto, solo si existe]
📝 Resumen: [máximo 2 frases]
📌 Último punto: [1 frase]
☎️ Seguimiento: [1 frase]

Devuelve SOLAMENTE JSON válido, sin markdown ni texto adicional, con esta forma:
[{"numero":"50200000000","resumen":"📞 +50200000000\n🏡 Vista Hermosa\n📝 Resumen: ...\n📌 Último punto: ...\n☎️ Seguimiento: ..."}]
"""

    entrada = "\n\n".join(bloques)
    try:
        respuesta = client.responses.create(
            model="gpt-5-mini",
            instructions=instrucciones,
            input=entrada
        )
        bruto = str(respuesta.output_text or "").strip()
        if bruto.startswith("```"):
            bruto = re.sub(r"^```(?:json)?\s*", "", bruto, flags=re.I)
            bruto = re.sub(r"\s*```$", "", bruto)

        data = json.loads(bruto)
        resultado = {}
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                numero = str(item.get("numero") or "").strip().lstrip("+")
                resumen = str(item.get("resumen") or "").strip()
                if numero in numeros_chunk and resumen:
                    resultado[numero] = resumen

        # Completa únicamente los faltantes con fallback factual.
        for numero in numeros_chunk:
            if numero not in resultado:
                fallback = _fallback_resumen_corto(numero)
                if fallback:
                    resultado[numero] = fallback
        return resultado

    except Exception as exc:
        print("ERROR GENERANDO CHUNK DE RESUMENES:", numeros_chunk, exc)
        resultado = {}
        for numero in numeros_chunk:
            fallback = _fallback_resumen_corto(numero)
            if fallback:
                resultado[numero] = fallback
        return resultado


def generar_resumenes_leads_en_lote(numeros):
    """
    Genera todos los resúmenes seleccionados sin obligar al usuario a hacerlo uno por uno.
    Internamente divide los leads en grupos pequeños y procesa hasta 4 grupos en paralelo,
    evitando una sola petición gigantesca que pueda provocar timeout en Render.
    """
    numeros = [str(n) for n in numeros]
    if not numeros:
        return {}

    # 6 leads por llamada. Con 24 chats son 4 llamadas en paralelo.
    tamano_chunk = 6
    chunks = [numeros[i:i + tamano_chunk] for i in range(0, len(numeros), tamano_chunk)]
    resultado = {}

    max_workers = min(4, len(chunks)) or 1
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futuros = {executor.submit(_generar_resumenes_chunk, chunk): chunk for chunk in chunks}
            for futuro in as_completed(futuros):
                chunk = futuros[futuro]
                try:
                    resultado.update(futuro.result())
                except Exception as exc:
                    print("ERROR EN GRUPO DE RESUMENES:", chunk, exc)
                    for numero in chunk:
                        fallback = _fallback_resumen_corto(numero)
                        if fallback:
                            resultado[numero] = fallback
    except Exception as exc:
        print("ERROR GENERAL RESUMENES PARALELOS:", exc)
        for numero in numeros:
            fallback = _fallback_resumen_corto(numero)
            if fallback:
                resultado[numero] = fallback

    return resultado

def enviar_texto_whatsapp_con_estado(numero, texto):
    """Envía texto y devuelve (ok, detalle). Registra en CRM únicamente si Meta lo acepta."""
    url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": numero,
        "type": "text",
        "text": {"preview_url": False, "body": texto}
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=25)
        if 200 <= r.status_code < 300:
            crm_registrar_mensaje(numero, "out", texto)
            return True, "ok"
        print("RESUMEN META ERROR:", r.status_code, r.text)
        return False, f"Meta {r.status_code}: {r.text[:300]}"
    except Exception as exc:
        print("RESUMEN ENVIO ERROR:", exc)
        return False, str(exc)


def _numeros_para_resumen():
    cargar_memoria_persistente()
    with lock_crm:
        numeros = [n for n in crm_mensajes.keys() if str(n) != str(CRM_SEGUIMIENTO_NUMERO)]
        numeros.sort(key=lambda n: crm_ultima_actividad.get(n, 0), reverse=True)
    return numeros


# Jobs temporales para generar vistas previas sin bloquear la petición web.
# Así Render no devuelve 502 aunque se seleccionen muchos clientes.
resumen_preview_jobs = {}
lock_resumen_preview_jobs = Lock()


def _limpiar_jobs_resumen_preview():
    ahora = time.time()
    with lock_resumen_preview_jobs:
        viejos = [
            job_id for job_id, job in resumen_preview_jobs.items()
            if ahora - float(job.get("created_at", ahora)) > 3600
        ]
        for job_id in viejos:
            resumen_preview_jobs.pop(job_id, None)


def _iniciar_job_preview_resumenes(seleccionados):
    _limpiar_jobs_resumen_preview()
    job_id = f"preview-{time.time_ns()}"
    with lock_resumen_preview_jobs:
        resumen_preview_jobs[job_id] = {
            "estado": "procesando",
            "created_at": time.time(),
            "total": len(seleccionados),
            "seleccionados": list(seleccionados),
            "resumenes": {},
            "error": "",
        }

    def trabajar():
        try:
            resumenes = generar_resumenes_leads_en_lote(seleccionados)
            with lock_resumen_preview_jobs:
                job = resumen_preview_jobs.get(job_id)
                if job is not None:
                    job["resumenes"] = resumenes
                    job["estado"] = "listo"
        except Exception as exc:
            print("ERROR JOB PREVIEW RESUMENES:", exc)
            with lock_resumen_preview_jobs:
                job = resumen_preview_jobs.get(job_id)
                if job is not None:
                    job["estado"] = "error"
                    job["error"] = str(exc)

    Thread(target=trabajar, daemon=True).start()
    return job_id


@app.route("/crm/resumen-seguimiento/estado/<job_id>", methods=["GET"])
def crm_resumen_seguimiento_estado(job_id):
    if not crm_autorizado():
        return jsonify({"ok": False, "error": "no_autorizado"}), 401
    with lock_resumen_preview_jobs:
        job = resumen_preview_jobs.get(job_id)
        if not job:
            return jsonify({"ok": False, "estado": "no_encontrado"}), 404
        return jsonify({
            "ok": True,
            "estado": job.get("estado"),
            "total": job.get("total", 0),
            "error": job.get("error", ""),
        })


@app.route("/crm/resumen-seguimiento", methods=["GET", "POST"])
def crm_resumen_seguimiento():
    global ultimo_resultado_resumen
    if not crm_autorizado():
        return crm_pedir_login()

    numeros = _numeros_para_resumen()

    def tarjeta_cliente(numero, checked=True):
        proyecto = crm_nombre_proyecto(numero) or "Sin proyecto"
        with lock_crm:
            mensajes = list(crm_mensajes.get(numero, []))
        ultimos = []
        for m in mensajes[-12:]:
            contenido = str(m.get("contenido") or "").strip()
            if not contenido:
                continue
            prefijo = "Cliente" if m.get("direccion") == "in" else "Bot"
            ultimos.append(f"{prefijo}: {contenido}")
        preview = " | ".join(ultimos[-4:]) or "Sin mensajes de texto para mostrar."
        return f"""
        <label class='card'>
          <div class='check'><input type='checkbox' name='numeros' value='{html.escape(str(numero))}' {'checked' if checked else ''}></div>
          <div class='contenido'>
            <div class='numero'>📞 +{html.escape(str(numero))}</div>
            <div class='proyecto'>🏡 {html.escape(str(proyecto))}</div>
            <div class='preview'>{html.escape(preview)}</div>
          </div>
        </label>
        """

    def pagina_espera(job_id, total):
        job_js = json.dumps(job_id)
        return Response(f"""
        <!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
        <title>Generando resúmenes</title>
        <style>
          body{{font-family:Arial,sans-serif;background:#f4f6f8;color:#17212b;margin:0}}
          .box{{max-width:650px;margin:80px auto;background:white;border-radius:16px;padding:28px;box-shadow:0 4px 18px rgba(0,0,0,.08)}}
          .spinner{{width:42px;height:42px;border:5px solid #dbe4ea;border-top-color:#047857;border-radius:50%;animation:g 1s linear infinite;margin:22px auto}}
          @keyframes g{{to{{transform:rotate(360deg)}}}}
          .small{{color:#64748b}}
        </style></head><body><div class='box'>
          <h1>🧠 Preparando {total} resúmenes</h1>
          <div class='spinner'></div>
          <p>La IA está resumiendo todos los clientes en segundo plano.</p>
          <p class='small'>Puedes esperar aquí. Esta página ya no mantiene una petición larga abierta, por lo que Render no debería devolver 502.</p>
          <p id='estado'>Procesando…</p>
          <p><a href='/crm'>Volver al CRM</a></p>
        </div>
        <script>
        const job = {job_js};
        async function revisar() {{
          try {{
            const r = await fetch('/crm/resumen-seguimiento/estado/' + encodeURIComponent(job), {{cache:'no-store'}});
            const d = await r.json();
            if (d.estado === 'listo') {{
              location.href = '/crm/resumen-seguimiento?job=' + encodeURIComponent(job);
              return;
            }}
            if (d.estado === 'error') {{
              document.getElementById('estado').textContent = 'Ocurrió un error: ' + (d.error || 'desconocido');
              return;
            }}
            document.getElementById('estado').textContent = 'Procesando ' + (d.total || {total}) + ' clientes…';
          }} catch(e) {{
            document.getElementById('estado').textContent = 'El servidor sigue trabajando. Reintentando…';
          }}
          setTimeout(revisar, 1500);
        }}
        revisar();
        </script></body></html>
        """, content_type="text/html; charset=utf-8")

    def render_preview(previews):
        cards = []
        for numero, proyecto, resumen in previews:
            n = html.escape(str(numero))
            r = html.escape(resumen)
            p = html.escape(str(proyecto))
            cards.append(f"""
            <label class='card resumen-card'>
              <div class='check'><input type='checkbox' name='seleccion' value='{n}' checked></div>
              <div class='contenido'>
                <div class='numero'>📞 +{n}</div>
                <div class='proyecto'>🏡 {p}</div>
                <pre>{r}</pre>
                <textarea name='resumen_{n}' hidden>{r}</textarea>
              </div>
            </label>
            """)

        return Response(f"""
        <!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Vista previa de resúmenes</title>
        <style>
          body{{font-family:Arial,sans-serif;background:#f4f6f8;margin:0;color:#17212b}}
          .wrap{{max-width:980px;margin:28px auto;padding:0 18px 60px}}
          .card{{display:flex;gap:14px;background:white;border:1px solid #dfe5eb;border-radius:14px;padding:16px;margin:12px 0;box-shadow:0 2px 8px rgba(0,0,0,.04)}}
          .check input{{width:22px;height:22px;margin-top:3px}}
          .contenido{{flex:1;min-width:0}}
          .numero{{font-weight:800;font-size:18px}}
          .proyecto{{color:#52606d;margin-top:4px}}
          pre{{white-space:pre-wrap;font-family:Arial,sans-serif;background:#f8fafc;border-radius:10px;padding:12px;margin:12px 0 0;line-height:1.45}}
          .acciones{{position:sticky;bottom:0;background:rgba(244,246,248,.96);padding:14px 0;display:flex;gap:10px;flex-wrap:wrap}}
          button,.btn{{border:0;border-radius:9px;padding:12px 16px;font-weight:700;cursor:pointer;text-decoration:none;display:inline-block}}
          .send{{background:#065f46;color:white}} .back{{background:#e5e7eb;color:#111827}}
        </style></head><body><div class='wrap'>
          <div class='topbar'><div><h1>👀 Vista previa de resúmenes</h1><p>Desmarca cualquier cliente que <strong>NO</strong> quieras enviar. Puedes enviar todos los seleccionados de una sola vez.</p></div></div>
          <form method='post' onsubmit="return confirm('¿Enviar TODOS los resúmenes que dejaste seleccionados? El envío continuará en segundo plano.');">
            <input type='hidden' name='accion' value='enviar_seleccionados'>
            {''.join(cards)}
            <div class='acciones'>
              <button class='send' type='submit'>📤 Enviar todos los seleccionados</button>
              <a class='btn back' href='/crm/resumen-seguimiento'>← Cambiar selección</a>
              <a class='btn back' href='/crm'>Volver al CRM</a>
            </div>
          </form>
        </div></body></html>
        """, content_type="text/html; charset=utf-8")

    # Al volver desde la página de espera, mostrar el resultado ya calculado.
    job_id_get = request.args.get("job", "").strip() if request.method == "GET" else ""
    if job_id_get:
        with lock_resumen_preview_jobs:
            job = resumen_preview_jobs.get(job_id_get)
            if job:
                estado = job.get("estado")
                seleccionados_job = list(job.get("seleccionados") or [])
                resumenes_job = dict(job.get("resumenes") or {})
                error_job = job.get("error", "")
            else:
                estado = None
                seleccionados_job = []
                resumenes_job = {}
                error_job = ""
        if estado == "procesando":
            return pagina_espera(job_id_get, len(seleccionados_job))
        if estado == "error":
            return Response(f"<h2>Error generando resúmenes</h2><p>{html.escape(error_job)}</p><p><a href='/crm/resumen-seguimiento'>Volver</a></p>", status=500, content_type="text/html; charset=utf-8")
        if estado == "listo":
            previews = []
            for numero in seleccionados_job:
                resumen = resumenes_job.get(str(numero))
                if not resumen:
                    continue
                proyecto = crm_nombre_proyecto(numero) or "Sin proyecto"
                previews.append((numero, proyecto, resumen))
            return render_preview(previews)

    if request.method == "POST":
        accion = request.form.get("accion", "").strip()

        if accion == "previsualizar":
            seleccionados = [n for n in request.form.getlist("numeros") if n in numeros]
            if not seleccionados:
                return Response("<h2>No seleccionaste ningún cliente.</h2><p><a href='/crm/resumen-seguimiento'>Volver</a></p>", status=400, content_type="text/html; charset=utf-8")

            # La generación masiva ya no ocurre dentro de esta petición HTTP.
            # Se lanza en un hilo y el navegador consulta el estado cada 1.5 s.
            job_id = _iniciar_job_preview_resumenes(seleccionados)
            return pagina_espera(job_id, len(seleccionados))

        if accion == "enviar_seleccionados":
            seleccionados = request.form.getlist("seleccion")
            if not seleccionados:
                return Response("<h2>No dejaste ningún resumen seleccionado.</h2><p><a href='/crm/resumen-seguimiento'>Volver</a></p>", status=400, content_type="text/html; charset=utf-8")

            paquetes = []
            for numero in seleccionados:
                if numero not in numeros:
                    continue
                resumen = request.form.get(f"resumen_{numero}", "").strip()
                if resumen:
                    paquetes.append((str(numero), resumen))

            if not paquetes:
                return Response("<h2>No había resúmenes válidos para enviar.</h2><p><a href='/crm/resumen-seguimiento'>Volver</a></p>", status=400, content_type="text/html; charset=utf-8")

            if lock_resumen_seguimiento.locked():
                return Response("<h2>Ya hay un envío de resúmenes en proceso.</h2><p>Espera a que termine antes de iniciar otro.</p><p><a href='/crm'>Volver al CRM</a></p>", status=409, content_type="text/html; charset=utf-8")

            def enviar_lote_background(paquetes_copia):
                global ultimo_resultado_resumen
                if not lock_resumen_seguimiento.acquire(blocking=False):
                    return
                enviados = 0
                fallidos = 0
                errores = []
                try:
                    for numero_origen, resumen in paquetes_copia:
                        ok, detalle = enviar_texto_whatsapp_con_estado(CRM_SEGUIMIENTO_NUMERO, resumen)
                        if ok:
                            enviados += 1
                        else:
                            fallidos += 1
                            errores.append(f"+{numero_origen}: {detalle}")
                        time.sleep(0.20)
                finally:
                    ultimo_resultado_resumen = {
                        "enviados": enviados,
                        "fallidos": fallidos,
                        "errores": errores[:20],
                        "total": len(paquetes_copia),
                        "fecha": datetime.now(ZoneInfo("America/Guatemala")).strftime("%d/%m/%Y %I:%M %p")
                    }
                    lock_resumen_seguimiento.release()

            Thread(target=enviar_lote_background, args=(list(paquetes),), daemon=True).start()

            return Response(f"""
            <!doctype html><html lang='es'><head><meta charset='utf-8'><title>Envío iniciado</title></head>
            <body style='font-family:Arial,sans-serif;max-width:760px;margin:40px auto;padding:0 20px'>
              <h1>📤 Envío iniciado</h1>
              <p>Se están enviando <strong>{len(paquetes)}</strong> resúmenes a <strong>+{CRM_SEGUIMIENTO_NUMERO}</strong>.</p>
              <p>El proceso continúa en segundo plano. Puedes volver al CRM inmediatamente.</p>
              <p><a href='/crm'>Volver al CRM</a> · <a href='/crm/resumen-seguimiento'>Preparar otro envío</a></p>
            </body></html>
            """, content_type="text/html; charset=utf-8")

    tarjetas = "".join(tarjeta_cliente(n) for n in numeros)
    return Response(f"""
    <!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Resumen de leads</title>
    <style>
      body{{font-family:Arial,sans-serif;background:#f4f6f8;margin:0;color:#17212b}}
      .wrap{{max-width:980px;margin:28px auto;padding:0 18px 60px}}
      .card{{display:flex;gap:14px;background:white;border:1px solid #dfe5eb;border-radius:14px;padding:15px;margin:10px 0;cursor:pointer}}
      .card:hover{{border-color:#9ca3af}}
      .check input{{width:22px;height:22px;margin-top:3px}}
      .contenido{{min-width:0;flex:1}}
      .numero{{font-weight:800;font-size:17px}}
      .proyecto{{color:#52606d;margin-top:3px}}
      .preview{{color:#475569;margin-top:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
      .acciones{{position:sticky;bottom:0;background:rgba(244,246,248,.96);padding:14px 0;display:flex;gap:10px;flex-wrap:wrap}}
      button,.btn{{border:0;border-radius:9px;padding:12px 16px;font-weight:700;cursor:pointer;text-decoration:none;display:inline-block}}
      .previewbtn{{background:#065f46;color:white}} .secondary{{background:#e5e7eb;color:#111827}}
    </style></head><body><div class='wrap'>
      <h1>📞 Preparar resumen de leads</h1>
      <p>Se encontraron <strong>{len(numeros)}</strong> conversaciones. Puedes seleccionar todas las que quieras.</p>
      <p>La vista previa se genera en segundo plano para evitar errores 502 aunque haya muchos chats.</p>
      <form method='post'>
        <input type='hidden' name='accion' value='previsualizar'>
        {tarjetas}
        <div class='acciones'>
          <button class='previewbtn' type='submit'>👀 Generar vista previa</button>
          <button class='secondary' type='button' onclick="document.querySelectorAll('input[name=numeros]').forEach(x=>x.checked=true)">Seleccionar todos</button>
          <button class='secondary' type='button' onclick="document.querySelectorAll('input[name=numeros]').forEach(x=>x.checked=false)">Quitar todos</button>
          <a class='btn secondary' href='/crm'>← Volver al CRM</a>
        </div>
      </form>
    </div></body></html>
    """, content_type="text/html; charset=utf-8")


def guardar_media_crm_bytes(numero, contenido, mime_type):
    """Guarda un archivo enviado manualmente desde el CRM para poder volver a verlo."""
    if not contenido or not inicializar_media_db():
        return None
    media_key = f"manual-{uuid.uuid4().hex}"
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO crm_media (media_key, numero, mime_type, contenido, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    """,
                    (media_key, str(numero), mime_type or "application/octet-stream", psycopg2.Binary(contenido))
                )
            conn.commit()
        finally:
            conn.close()
        return f"/crm/media/{media_key}"
    except Exception as exc:
        print("MEDIA MANUAL DB SAVE ERROR:", exc)
        return None


def subir_media_bytes_a_meta(contenido, nombre_archivo, mime_type):
    """Sube bytes recibidos desde el navegador del CRM a WhatsApp Cloud API."""
    url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/media"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    data = {"messaging_product": "whatsapp", "type": mime_type}
    try:
        respuesta = requests.post(
            url, headers=headers, data=data,
            files={"file": (nombre_archivo, contenido, mime_type)}, timeout=120
        )
        print("CRM MEDIA UPLOAD STATUS:", respuesta.status_code)
        print("CRM MEDIA UPLOAD RESPONSE:", respuesta.text)
        if 200 <= respuesta.status_code < 300:
            return respuesta.json().get("id")
    except Exception as exc:
        print("CRM MEDIA UPLOAD ERROR:", exc)
    return None


def enviar_media_id_whatsapp(numero, media_id, tipo, nombre_archivo, caption=""):
    """Envía una imagen, video o PDF ya subido a Meta."""
    url = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    objeto = {"id": media_id}
    if caption:
        objeto["caption"] = caption[:1024]
    if tipo == "document":
        objeto["filename"] = nombre_archivo
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": numero,
        "type": tipo,
        tipo: objeto
    }
    try:
        respuesta = requests.post(url, headers=headers, json=payload, timeout=60)
        print("CRM MEDIA SEND STATUS:", respuesta.status_code)
        print("CRM MEDIA SEND RESPONSE:", respuesta.text)
        return 200 <= respuesta.status_code < 300
    except Exception as exc:
        print("CRM MEDIA SEND ERROR:", exc)
        return False


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
        .sidebar-search {
            padding: 10px 12px;
            border-bottom: 1px solid #edf0f2;
            position: sticky;
            top: 0;
            background: white;
            z-index: 2;
        }
        .sidebar-search input {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid #cfd6dd;
            border-radius: 9px;
            font: inherit;
            outline: none;
        }
        .sidebar-search input:focus { border-color: #2563eb; }
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
        .channel-badge {
            display:inline-block; margin-right:5px; padding:3px 7px; border-radius:999px;
            font-size:10px; font-weight:800; vertical-align:middle;
        }
        .channel-badge.whatsapp { background:#dcfce7; color:#166534; }
        .channel-badge.facebook { background:#dbeafe; color:#1d4ed8; }
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
        .quick-action {
            border: 0;
            border-radius: 9px;
            padding: 10px 13px;
            cursor: pointer;
            font-weight: 700;
            background: #2563eb;
            color: white;
        }
        .head-actions { display:flex; gap:8px; align-items:center; flex-wrap:wrap; justify-content:flex-end; }
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
        .crm-photo-link { display:block; margin-bottom:7px; }
        .crm-photo {
            display:block; max-width:100%; width:min(340px, 70vw); max-height:420px;
            object-fit:contain; border-radius:9px; cursor:zoom-in; background:#f3f4f6;
        }
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
        .composer-stack { display:flex; flex-direction:column; gap:8px; }
        .media-form { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
        .media-form input[type=file] {
            flex:1; min-width:220px; border:1px solid #cfd6dd; border-radius:9px; padding:9px; background:white;
        }
        .media-send {
            border:0; background:#2563eb; color:white; font-weight:bold; border-radius:9px; padding:11px 16px; cursor:pointer;
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
        .stage-badge {
            display:inline-block; margin-top:6px; padding:3px 7px; border-radius:999px;
            font-size:10px; font-weight:700; background:#eef2ff; color:#4338ca;
        }
        .sidebar-search { display:grid; gap:7px; }
        .sidebar-search select {
            width:100%; padding:9px 10px; border:1px solid #cfd6dd; border-radius:9px;
            background:white; font:inherit; color:#344054;
        }
        .lead-management {
            background:#ffffff; border-bottom:1px solid #dbe1e7; padding:12px 18px;
            display:grid; gap:10px;
        }
        .lead-management-title { font-weight:800; font-size:13px; color:#344054; }
        .lead-form {
            display:grid; grid-template-columns:minmax(150px,1fr) minmax(210px,2fr) minmax(190px,1fr) auto;
            gap:8px; align-items:end;
        }
        .lead-field { display:flex; flex-direction:column; gap:5px; min-width:0; }
        .lead-field label { font-size:11px; font-weight:700; color:#667085; }
        .lead-field input, .lead-field select {
            width:100%; padding:9px 10px; border:1px solid #cfd6dd; border-radius:9px;
            font:inherit; background:white; min-height:39px;
        }
        .save-lead {
            border:0; border-radius:9px; padding:10px 14px; background:#111827; color:white;
            font-weight:800; cursor:pointer; min-height:39px;
        }
        .quick-tools {
            background:#f8fafc; border-bottom:1px solid #dbe1e7; padding:10px 18px;
        }
        .quick-tools-title { font-size:11px; font-weight:800; color:#667085; margin-bottom:8px; }
        .quick-grid { display:flex; flex-wrap:wrap; gap:7px; }
        .quick-grid form { margin:0; }
        .quick-chip {
            border:1px solid #c7d2fe; background:#eef2ff; color:#3730a3; border-radius:9px;
            padding:8px 10px; font-size:12px; font-weight:800; cursor:pointer;
        }
        .quick-chip:hover { background:#e0e7ff; }
        .quick-chip.secondary { border-color:#d1d5db; background:white; color:#374151; }
        .quick-chip:disabled { opacity:.42; cursor:not-allowed; }
        .next-mini { margin-top:5px; font-size:11px; color:#b45309; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        @media (max-width: 980px) {
            .lead-form { grid-template-columns:1fr 1fr; }
            .save-lead { width:100%; }
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
        <strong>🏡 CRM Gabriel <span style="font-size:12px;color:#86efac;">● En vivo</span></strong>
        <div style="display:flex;gap:8px;align-items:center;">
            <button id="btn-notificaciones"
                    type="button"
                    style="background:#1f2937;color:white;border:1px solid #64748b;border-radius:8px;padding:7px 10px;cursor:pointer;">
                📱 Activar notificaciones
            </button>
            <button id="btn-probar-push"
                    type="button"
                    style="background:#065f46;color:white;border:1px solid #047857;border-radius:8px;padding:7px 10px;cursor:pointer;">
                🧪 Probar móvil
            </button>
            <a href="{{ url_for('crm_resumen_seguimiento') }}" style="background:#1d4ed8;border-color:#2563eb;">📞 Resumen leads</a>
            <a href="{{ url_for('crm') }}">Actualizar</a>
        </div>
    </div>

    <div class="layout">
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-title">Conversaciones (<span id="client-count">{{ clientes|length }}</span>)</div>
            <div class="sidebar-search">
                <input id="crm-search-number" type="search" placeholder="🔎 Buscar cliente..." autocomplete="off">
                <select id="crm-filter-stage" aria-label="Filtrar por etapa">
                    <option value="">Todas las etapas</option>
                    {% for etapa in etapas %}
                        <option value="{{ etapa }}">{{ etapa }}</option>
                    {% endfor %}
                </select>
            </div>
            {% if not clientes %}
                <div style="padding:20px;color:#667085;">
                    Todavía no han entrado mensajes desde que se inició esta versión.
                </div>
            {% endif %}

            {% for c in clientes %}
                <a class="chat-link {% if seleccionado == c.numero %}active{% endif %}"
                   data-number="{{ c.numero }}"
                   data-channel="{{ c.canal }}"
                   data-label="{{ (c.nombre_manual ~ ' ' ~ c.identificador) if c.nombre_manual else c.identificador }}"
                   data-stage="{{ c.etapa }}"
                   href="{{ url_for('crm', numero=c.numero) }}">
                    <div>
                        {% if c.canal == 'facebook' %}
                            <span class="channel-badge facebook">🔵 Facebook</span>
                        {% else %}
                            <span class="channel-badge whatsapp">🟢 WhatsApp</span>
                        {% endif %}
                        <span class="phone">{{ c.nombre_manual if c.nombre_manual else c.identificador }}</span>
                        {% if c.manual %}
                            <span class="status manual">MANUAL</span>
                        {% else %}
                            <span class="status ai">IA</span>
                        {% endif %}
                    </div>
                    {% if c.nombre_manual %}<div class="small">{{ c.identificador }}</div>{% endif %}
                    <div class="preview">{{ c.preview }}</div>
                    <div class="small">{{ c.proyecto }}</div>
                    <span class="stage-badge">{{ c.etapa }}</span>
                    {% if c.proxima_accion %}
                        <div class="next-mini">⏰ {{ c.proxima_accion }}{% if c.proxima_accion_fecha %} · {{ c.proxima_accion_fecha|replace('T',' ') }}{% endif %}</div>
                    {% endif %}
                </a>
            {% endfor %}
        </aside>

        <main class="main">
        {% if seleccionado %}
            <div class="chat-head">
                <div>
                    <h2>
                        {% if canal_seleccionado == 'facebook' %}
                            <span class="channel-badge facebook">🔵 Facebook</span>
                        {% else %}
                            <span class="channel-badge whatsapp">🟢 WhatsApp</span>
                        {% endif %}
                        {{ nombre_manual_seleccionado if nombre_manual_seleccionado else identificador_seleccionado }}
                    </h2>
                    <p>{% if nombre_manual_seleccionado %}{{ identificador_seleccionado }} · {% endif %}{{ proyecto_seleccionado }}</p>
                </div>

                <div class="head-actions">
                    <form method="post" action="{{ url_for('crm_accion_info_tres_proyectos', numero=seleccionado) }}"
                          onsubmit="return confirm('¿Enviar al cliente el resumen oficial de los 3 proyectos?');">
                        <button class="quick-action" type="submit">🤖 Info 3 proyectos</button>
                    </form>
                    <form method="post" action="{{ url_for('crm_toggle', numero=seleccionado) }}">
                        {% if manual %}
                            <button class="toggle resume" type="submit">▶ Activar IA</button>
                        {% else %}
                            <button class="toggle pause" type="submit">⏸ Pausar IA</button>
                        {% endif %}
                    </form>
                </div>
            </div>

            <div class="lead-management">
                <div class="lead-management-title">📌 Gestión del lead</div>
                <form class="lead-form" method="post" action="{{ url_for('crm_guardar_gestion', numero=seleccionado) }}">
                    <div class="lead-field">
                        <label>Nombre / etiqueta del contacto</label>
                        <input type="text" name="nombre_contacto" maxlength="100" value="{{ nombre_manual_seleccionado }}" placeholder="Ej. Juan Pérez | Palmeras San Miguel">
                    </div>
                    <div class="lead-field">
                        <label>Etapa del embudo</label>
                        <select name="etapa">
                            {% for etapa in etapas %}
                                <option value="{{ etapa }}" {% if meta_seleccionada.etapa == etapa %}selected{% endif %}>{{ etapa }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="lead-field">
                        <label>Próxima acción</label>
                        <input type="text" name="proxima_accion" maxlength="180" value="{{ meta_seleccionada.proxima_accion }}" placeholder="Ej. Llamar, enviar plano, confirmar visita...">
                    </div>
                    <div class="lead-field">
                        <label>Fecha y hora</label>
                        <input type="datetime-local" name="proxima_accion_fecha" value="{{ meta_seleccionada.proxima_accion_fecha }}">
                    </div>
                    <button class="save-lead" type="submit">💾 Guardar</button>
                </form>
            </div>

            <div class="quick-tools">
                <div class="quick-tools-title">⚡ MENSAJES Y ENVÍOS RÁPIDOS · usan el proyecto activo: {{ proyecto_seleccionado }}</div>
                <div class="quick-grid">
                    <form method="post" action="{{ url_for('crm_accion_rapida', numero=seleccionado, accion='palmeras-completa') }}"><button class="quick-chip" type="submit" title="Fija Palmeras San Miguel como proyecto activo y envía toda la información">🌴 Info Palmeras</button></form>
                    <form method="post" action="{{ url_for('crm_accion_rapida', numero=seleccionado, accion='info-completa') }}"><button class="quick-chip" type="submit" {% if not proyecto_clave_seleccionado %}disabled title="Primero debe existir un proyecto activo"{% endif %}>🏡 Info completa</button></form>
                    <form method="post" action="{{ url_for('crm_accion_rapida', numero=seleccionado, accion='cotizaciones') }}"><button class="quick-chip" type="submit" {% if not proyecto_clave_seleccionado %}disabled{% endif %}>💰 Cotizaciones</button></form>
                    <form method="post" action="{{ url_for('crm_accion_rapida', numero=seleccionado, accion='ubicacion') }}"><button class="quick-chip" type="submit" {% if not proyecto_clave_seleccionado %}disabled{% endif %}>📍 Ubicación</button></form>
                    <form method="post" action="{{ url_for('crm_accion_rapida', numero=seleccionado, accion='plano') }}"><button class="quick-chip" type="submit" {% if not proyecto_clave_seleccionado %}disabled{% endif %}>🗺️ Plano</button></form>
                    <form method="post" action="{{ url_for('crm_accion_rapida', numero=seleccionado, accion='fotos') }}"><button class="quick-chip" type="submit" {% if not proyecto_clave_seleccionado %}disabled{% endif %}>📸 Fotos</button></form>
                    <form method="post" action="{{ url_for('crm_accion_rapida', numero=seleccionado, accion='videos') }}"><button class="quick-chip" type="submit" {% if not proyecto_clave_seleccionado %}disabled{% endif %}>🎥 Videos</button></form>
                    <form method="post" action="{{ url_for('crm_accion_rapida', numero=seleccionado, accion='requisitos') }}"><button class="quick-chip secondary" type="submit">📋 Requisitos</button></form>
                    <form method="post" action="{{ url_for('crm_accion_rapida', numero=seleccionado, accion='gastos') }}"><button class="quick-chip secondary" type="submit" {% if not proyecto_clave_seleccionado %}disabled{% endif %}>💧 Gastos</button></form>
                    <form method="post" action="{{ url_for('crm_accion_rapida', numero=seleccionado, accion='visita') }}"><button class="quick-chip secondary" type="submit">📅 Proponer visita</button></form>
                    <form method="post" action="{{ url_for('crm_accion_rapida', numero=seleccionado, accion='seguimiento') }}"><button class="quick-chip secondary" type="submit">☎️ Seguimiento</button></form>
                </div>
            </div>

            {% if requiere_intervencion_seleccionado %}
            <div style="margin:12px 0;padding:14px 16px;border-radius:12px;background:#fff7ed;border:1px solid #fb923c;color:#9a3412;font-weight:700;">
                ⚠️ La IA se pausó automáticamente porque necesita una respuesta suya.
                {% if intervencion_pregunta_seleccionado %}<div style="font-weight:500;margin-top:6px;">{{ intervencion_pregunta_seleccionado }}</div>{% endif %}
                <div style="font-weight:500;margin-top:6px;">Responda desde este CRM. Al enviarlo, la IA se reanudará automáticamente.</div>
            </div>
            {% endif %}

            {% if canal_seleccionado == 'facebook' %}
            <div class="notice" style="background:#eff6ff;border-color:#bfdbfe;color:#1d4ed8;">
                🔵 Messenger usa la misma lógica automática de WhatsApp. Puede alternar entre IA y MANUAL cuando quiera.
            </div>
            {% endif %}

            {% if manual %}
                <div class="notice">
                    ✋ Estás atendiendo esta conversación manualmente. La IA y el seguimiento automático están pausados.
                </div>
            {% endif %}

            <div class="messages" id="messages" data-numero="{{ seleccionado or '' }}">
                {% for m in mensajes %}
                    <div class="row {{ m.direccion }}">
                        <div class="bubble">
                            {% if m.media_tipo == 'image' and m.media_url %}
                                <a class="crm-photo-link" href="{{ m.media_url }}" target="_blank" rel="noopener">
                                    <img class="crm-photo" src="{{ m.media_url }}" alt="Imagen del chat" loading="lazy">
                                </a>
                            {% elif m.media_tipo == 'video' and m.media_url %}
                                <video controls preload="metadata" style="display:block;max-width:100%;width:min(420px,70vw);max-height:420px;border-radius:9px;margin-bottom:7px;">
                                    <source src="{{ m.media_url }}">
                                </video>
                            {% elif m.media_tipo == 'audio' and m.media_url %}
                                <audio controls preload="metadata" style="display:block;width:min(420px,70vw);max-width:100%;margin-bottom:7px;">
                                    <source src="{{ m.media_url }}">
                                </audio>
                            {% elif m.media_tipo == 'document' and m.media_url %}
                                <a href="{{ m.media_url }}" target="_blank" rel="noopener" style="display:inline-block;margin-bottom:7px;font-weight:700;">📄 Abrir PDF</a><br>
                            {% endif %}
                            {{ m.contenido }}
                            <span class="time">{{ m.hora }}</span>
                        </div>
                    </div>
                {% endfor %}
            </div>

            <div class="composer">
                <div class="composer-stack">
                    <form method="post" action="{{ url_for('crm_enviar', numero=seleccionado) }}">
                        <textarea id="composer-text" name="mensaje" placeholder="Escribe tu respuesta manual..." required></textarea>
                        <button class="send" type="submit">Enviar</button>
                    </form>
                    {% if canal_seleccionado != 'facebook' %}
                    <form class="media-form" method="post" enctype="multipart/form-data" action="{{ url_for('crm_enviar_archivo', numero=seleccionado) }}">
                        <input type="file" name="archivo" accept="image/jpeg,image/png,video/mp4,application/pdf" required>
                        <input type="text" name="caption" placeholder="Texto opcional para acompañar el archivo" style="flex:1;min-width:220px;padding:10px;border:1px solid #cfd6dd;border-radius:9px;">
                        <button class="media-send" type="submit">📎 Enviar archivo</button>
                    </form>
                    {% else %}
                    <div style="font-size:12px;color:#667085;padding:2px 4px;">
                        🔵 El envío manual de archivos se mantiene separado. Los envíos automáticos del bot sí usan la misma lógica de WhatsApp.
                    </div>
                    {% endif %}
                </div>
            </div>
        {% else %}
            <div class="empty">
                <h2>Selecciona una conversación</h2>
                <p>Aquí podrás pausar la IA y responder tú mismo.</p>
            </div>
        {% endif %}
        </main>
    </div>

    <script>
        const box = document.getElementById("messages");
        const composer = document.getElementById("composer-text");
        if (box) box.scrollTop = box.scrollHeight;

        const crmSearchNumber = document.getElementById("crm-search-number");
        const crmFilterStage = document.getElementById("crm-filter-stage");
        function filtrarConversacionesPorNumero() {
            const q = crmSearchNumber ? (crmSearchNumber.value || "").trim().toLowerCase() : "";
            const etapa = crmFilterStage ? (crmFilterStage.value || "") : "";
            document.querySelectorAll("#sidebar .chat-link").forEach(link => {
                const buscable = [
                    link.dataset.number || "",
                    link.dataset.channel || "",
                    link.dataset.label || "",
                    link.textContent || ""
                ].join(" ").toLowerCase();
                const etapaLink = link.dataset.stage || "";
                const coincideNumero = !q || buscable.includes(q);
                const coincideEtapa = !etapa || etapaLink === etapa;
                link.style.display = (coincideNumero && coincideEtapa) ? "block" : "none";
            });
        }
        if (crmSearchNumber) crmSearchNumber.addEventListener("input", filtrarConversacionesPorNumero);
        if (crmFilterStage) crmFilterStage.addEventListener("change", filtrarConversacionesPorNumero);

        let lastSignature = "";
        let ultimoEventoEntrante = null;
        const btnNotificaciones = document.getElementById("btn-notificaciones");

        let pushRegistradoServidor = false;
        let pushDevices = 0;

        function actualizarBotonNotificaciones() {
            if (!btnNotificaciones) return;

            if (!("Notification" in window)) {
                btnNotificaciones.textContent = "🔕 No compatible";
                btnNotificaciones.disabled = true;
                return;
            }

            if (Notification.permission === "denied") {
                btnNotificaciones.textContent = "🔕 Notificaciones bloqueadas";
                return;
            }

            if (Notification.permission === "granted" && pushRegistradoServidor) {
                btnNotificaciones.textContent = `🔔 Activo en este teléfono (${pushDevices})`;
                return;
            }

            if (Notification.permission === "granted") {
                btnNotificaciones.textContent = "📱 Registrar este teléfono";
                return;
            }

            btnNotificaciones.textContent = "🔔 Activar notificaciones";
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
                throw new Error("No pude obtener la configuración Push del servidor.");
            }

            const config = await configResp.json();

            if (!config.publicKey) {
                throw new Error("Falta VAPID_PUBLIC_KEY en Render.");
            }

            // Registrar SW y esperar hasta que realmente esté activo.
            await navigator.serviceWorker.register("/crm-sw.js", {
                scope: "/"
            });

            const registro = await navigator.serviceWorker.ready;

            // Recuperar una suscripción anterior si existe.
            let sub = await registro.pushManager.getSubscription();

            // Si no existe, crearla usando la llave pública VAPID.
            if (!sub) {
                sub = await registro.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: urlBase64ToUint8Array(config.publicKey)
                });
            }

            if (!sub || !sub.endpoint) {
                throw new Error("Chrome no devolvió una suscripción Push válida.");
            }

            // IMPORTANTE:
            // Aunque Chrome ya estuviera suscrito, SIEMPRE mandamos esa
            // suscripción otra vez al servidor. Esto recupera el registro
            // después de un deploy/reinicio de Render.
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
                    data.error || "No se pudo guardar el teléfono en el servidor."
                );
            }

            pushRegistradoServidor = true;
            pushDevices = Number(data.devices || 1);
            actualizarBotonNotificaciones();

            if (mostrarMensaje) {
                alert(
                    `✅ Teléfono registrado correctamente.\n\n` +
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
                    btnProbarPush.textContent = "⏳ Probando...";

                    // Primero garantizamos que ESTE teléfono esté registrado
                    // en el servidor antes de intentar el push.
                    const sync = await sincronizarPush({
                        pedirPermiso: true,
                        mostrarMensaje: false
                    });

                    if (!sync.ok) {
                        throw new Error(
                            "No se pudo registrar este teléfono para recibir Push."
                        );
                    }

                    const resp = await fetch("/crm/push/test", {
                        method: "POST",
                        headers: {"Content-Type": "application/json"}
                    });

                    const data = await resp.json();

                    if (data.ok) {
                        alert(
                            "✅ El servidor envió la notificación.\n\n" +
                            "Dispositivos suscritos: " + (data.devices ?? sync.devices) +
                            "\n\nAhora revisa la barra de notificaciones del teléfono."
                        );
                    } else {
                        alert(
                            "❌ No se pudo enviar.\n\n" +
                            (data.error || "Error desconocido") +
                            "\n\nDispositivos suscritos: " +
                            (data.devices ?? 0)
                        );
                    }
                } catch (err) {
                    alert("❌ Error probando push: " + err.message);
                } finally {
                    btnProbarPush.disabled = false;
                    btnProbarPush.textContent = "🧪 Probar móvil";
                }
            });
        }

        actualizarBotonNotificaciones();

        // Si este teléfono YA dio permiso anteriormente, al abrir el CRM
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

            // Primera carga: establecemos la línea base.
            // Así no recibes 30 alertas de mensajes que ya estaban antes de abrir el CRM.
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
                        ? ` · ${e.proyecto}`
                        : "";

                    const ident = e.nombre_manual || e.identificador || (e.canal === "facebook" ? "Facebook" : `+${e.numero}`);
                    const n = new Notification("🏡 Nuevo mensaje de cliente", {
                        body: `${ident}${proyecto}\n${e.contenido}`,
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
                        ${m.media_tipo === "image" && m.media_url ? `
                            <a class="crm-photo-link" href="${escapeHtml(m.media_url)}" target="_blank" rel="noopener">
                                <img class="crm-photo" src="${escapeHtml(m.media_url)}" alt="Imagen del chat" loading="lazy">
                            </a>
                        ` : ""}
                        ${m.media_tipo === "video" && m.media_url ? `
                            <video controls preload="metadata" style="display:block;max-width:100%;width:min(420px,70vw);max-height:420px;border-radius:9px;margin-bottom:7px;">
                                <source src="${escapeHtml(m.media_url)}">
                            </video>
                        ` : ""}
                        ${m.media_tipo === "audio" && m.media_url ? `
                            <audio controls preload="metadata" style="display:block;width:min(420px,70vw);max-width:100%;margin-bottom:7px;">
                                <source src="${escapeHtml(m.media_url)}">
                            </audio>
                        ` : ""}
                        ${m.media_tipo === "document" && m.media_url ? `
                            <a href="${escapeHtml(m.media_url)}" target="_blank" rel="noopener" style="display:inline-block;margin-bottom:7px;font-weight:700;">📄 Abrir PDF</a><br>
                        ` : ""}
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
                div.textContent = "Todavía no han entrado mensajes desde que se inició esta versión.";
                sidebar.appendChild(div);
                return;
            }

            clientes.forEach(c => {
                const a = document.createElement("a");
                a.className = "chat-link" + (seleccionado === c.numero ? " active" : "");
                a.dataset.number = c.numero || "";
                a.dataset.channel = c.canal || "";
                a.dataset.label = ((c.nombre_manual || "") + " " + (c.identificador || "")).trim();
                a.dataset.stage = c.etapa || "Nuevo lead";
                a.href = "/crm?numero=" + encodeURIComponent(c.numero);
                const prox = c.proxima_accion
                    ? `<div class="next-mini">⏰ ${escapeHtml(c.proxima_accion)}${c.proxima_accion_fecha ? " · " + escapeHtml(String(c.proxima_accion_fecha).replace("T", " ")) : ""}</div>`
                    : "";
                const canalBadge = c.canal === "facebook"
                    ? '<span class="channel-badge facebook">🔵 Facebook</span>'
                    : '<span class="channel-badge whatsapp">🟢 WhatsApp</span>';
                a.innerHTML = `
                    <div>
                        ${canalBadge}
                        <span class="phone">${escapeHtml(c.nombre_manual || c.identificador || c.numero)}</span>
                        <span class="status ${c.manual ? "manual" : "ai"}">
                            ${c.manual ? "MANUAL" : "IA"}
                        </span>
                    </div>
                    ${c.nombre_manual ? `<div class="small">${escapeHtml(c.identificador || c.numero)}</div>` : ""}
                    <div class="preview">${escapeHtml(c.preview)}</div>
                    <div class="small">${escapeHtml(c.proyecto)}</div>
                    <span class="stage-badge">${escapeHtml(c.etapa || "Nuevo lead")}</span>
                    ${prox}
                `;
                sidebar.appendChild(a);
            });
            filtrarConversacionesPorNumero();
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
                        toggle.textContent = "▶ Activar IA";
                        toggle.classList.remove("pause");
                        toggle.classList.add("resume");
                        if (notice) notice.style.display = "";
                    } else {
                        toggle.textContent = "⏸ Pausar IA";
                        toggle.classList.remove("resume");
                        toggle.classList.add("pause");
                        if (notice) notice.style.display = "none";
                    }
                }
            } catch (err) {
                console.log("CRM polling:", err);
            }
        }

        // Actualiza automáticamente sin interrumpir lo que estás escribiendo.
        // No recarga la página completa.
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

    const title = data.title || '🏡 Nuevo mensaje de cliente';

    const options = {
        body: data.body || 'Tienes un mensaje nuevo.',
        // TAG ÚNICO POR MENSAJE: no reemplazar alertas anteriores.
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
        return jsonify({"ok": False, "error": "Suscripción inválida"}), 400

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
        "Prueba de ntfy: las notificaciones del CRM ya están conectadas ✅",
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
        "Esta es una prueba de notificación móvil del CRM Gabriel ✅"
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
    cargar_crm_lead_meta()

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
            meta = crm_obtener_meta(numero)
            clientes.append({
                "numero": numero,
                "identificador": crm_identificador_visible(numero),
                "nombre_manual": crm_nombre_manual(numero),
                "canal": crm_canal_contacto(numero),
                "preview": ultimo[:70],
                "manual": numero in crm_modo_manual,
                "proyecto": crm_nombre_proyecto(numero),
                "etapa": meta["etapa"],
                "proxima_accion": meta["proxima_accion"],
                "proxima_accion_fecha": meta["proxima_accion_fecha"],
            })

        mensajes_seleccionados = list(
            crm_mensajes.get(seleccionado, [])
        ) if seleccionado else []

        manual = seleccionado in crm_modo_manual if seleccionado else False

    meta_seleccionada = crm_obtener_meta(seleccionado) if seleccionado else crm_obtener_meta(None)
    proyecto_clave_seleccionado = proyecto_activo.get(seleccionado) if seleccionado else None

    return render_template_string(
        CRM_HTML,
        clientes=clientes,
        seleccionado=seleccionado,
        mensajes=mensajes_seleccionados,
        manual=manual,
        proyecto_seleccionado=crm_nombre_proyecto(seleccionado) if seleccionado else "",
        proyecto_clave_seleccionado=proyecto_clave_seleccionado,
        canal_seleccionado=crm_canal_contacto(seleccionado) if seleccionado else "",
        identificador_seleccionado=crm_identificador_visible(seleccionado) if seleccionado else "",
        nombre_manual_seleccionado=crm_nombre_manual(seleccionado) if seleccionado else "",
        requiere_intervencion_seleccionado=es_intervencion_activa(seleccionado) if seleccionado else False,
        intervencion_pregunta_seleccionado=(obtener_estado_conversacion(seleccionado).get("intervencion_pregunta") if seleccionado else ""),
        etapas=CRM_ETAPAS,
        meta_seleccionada=meta_seleccionada,
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
            meta = crm_obtener_meta(numero)
            clientes.append({
                "numero": numero,
                "identificador": crm_identificador_visible(numero),
                "nombre_manual": crm_nombre_manual(numero),
                "canal": crm_canal_contacto(numero),
                "preview": ultimo[:70],
                "manual": numero in crm_modo_manual,
                "proyecto": crm_nombre_proyecto(numero),
                "etapa": meta["etapa"],
                "proxima_accion": meta["proxima_accion"],
                "proxima_accion_fecha": meta["proxima_accion_fecha"],
            })

        mensajes = list(
            crm_mensajes.get(seleccionado, [])
        ) if seleccionado else []

        manual = seleccionado in crm_modo_manual if seleccionado else False

        # Últimos mensajes entrantes de TODAS las conversaciones.
        # El navegador usa el ID para avisar una sola vez por cada mensaje.
        eventos_entrantes = []
        for numero, lista in crm_mensajes.items():
            for m in lista:
                if m.get("direccion") == "in":
                    eventos_entrantes.append({
                        "id": m.get("id", 0),
                        "numero": numero,
                        "identificador": crm_identificador_visible(numero),
                        "nombre_manual": crm_nombre_manual(numero),
                        "canal": crm_canal_contacto(numero),
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


@app.route("/crm/gestion/<numero>", methods=["POST"])
def crm_guardar_gestion(numero):
    if not crm_autorizado():
        return crm_pedir_login()

    nombre_contacto = request.form.get("nombre_contacto", "").strip()[:100]
    etapa = request.form.get("etapa", "Nuevo lead").strip()
    proxima_accion = request.form.get("proxima_accion", "").strip()
    proxima_accion_fecha = request.form.get("proxima_accion_fecha", "").strip()

    # Se guarda dentro del snapshot JSON existente: NO cambia la estructura de PostgreSQL.
    estado = obtener_estado_conversacion(numero)
    estado["crm_nombre_manual"] = nombre_contacto
    persistir_cliente(numero)

    crm_guardar_meta(numero, etapa, proxima_accion, proxima_accion_fecha)
    return redirect(url_for("crm", numero=numero))


def _crm_worker_accion_rapida(numero, accion):
    proyecto = proyecto_activo.get(numero)
    try:
        if accion == "palmeras-completa":
            # Botón independiente del proyecto activo: siempre trabaja con Palmeras San Miguel.
            proyecto = "palmeras"
            estado = obtener_estado_conversacion(numero)
            estado["proyecto_actual"] = proyecto
            proyecto_activo[numero] = proyecto
            persistir_cliente(numero)
            enviar_info_completa_proyecto(numero, proyecto, cierre=True)
        elif accion == "info-completa":
            if proyecto:
                enviar_info_completa_proyecto(numero, proyecto, cierre=True)
        elif accion == "cotizaciones":
            if proyecto:
                enviar_cotizacion_del_proyecto(numero, proyecto)
        elif accion == "ubicacion":
            if proyecto:
                enviar_ubicacion_proyecto(numero, proyecto)
        elif accion == "plano":
            if proyecto:
                enviar_planos_solicitados(numero, proyecto, "plano")
        elif accion == "fotos":
            if proyecto:
                enviar_multimedia_del_proyecto(numero, proyecto, enviar_fotos=True, enviar_videos=False)
        elif accion == "videos":
            if proyecto:
                enviar_multimedia_del_proyecto(numero, proyecto, enviar_fotos=False, enviar_videos=True)
        elif accion == "requisitos":
            texto = respuesta_requisitos_segun_contexto(numero, "")
            enviar_whatsapp(numero, texto)
            guardar_mensaje(numero, "assistant", texto)
        elif accion == "gastos":
            if proyecto:
                texto = respuesta_gastos_adicionales(proyecto)
                enviar_whatsapp(numero, texto)
                guardar_mensaje(numero, "assistant", texto)
        elif accion == "visita":
            texto = (
                "Si gustas, podemos coordinar una visita para que conozcas el proyecto "
                "personalmente 🏡📍 ¿Qué día te quedaría cómodo?"
            )
            enviar_whatsapp(numero, texto)
            guardar_mensaje(numero, "assistant", texto)
        elif accion == "seguimiento":
            texto = (
                "Hola 👋 Solo quería saber si pudiste revisar la información que te envié 😊 "
                "¿Hubo alguna opción que te llamara más la atención?"
            )
            enviar_whatsapp(numero, texto)
            guardar_mensaje(numero, "assistant", texto)
    except Exception as exc:
        print("ERROR ACCION RAPIDA CRM:", accion, numero, exc)


@app.route("/crm/accion/rapida/<numero>/<accion>", methods=["POST"])
def crm_accion_rapida(numero, accion):
    if not crm_autorizado():
        return crm_pedir_login()

    permitidas = {
        "palmeras-completa", "info-completa", "cotizaciones", "ubicacion", "plano", "fotos",
        "videos", "requisitos", "gastos", "visita", "seguimiento"
    }
    if accion not in permitidas:
        return Response("Acción no válida", status=400)

    if accion == "palmeras-completa":
        estado = obtener_estado_conversacion(numero)
        estado["proyecto_actual"] = "palmeras"
        proyecto_activo[numero] = "palmeras"
        persistir_cliente(numero)

    cancelar_seguimiento(numero)
    iniciar_procesamiento(numero, f"crm-accion-rapida-{accion}-{time.time()}")

    Thread(
        target=_crm_worker_accion_rapida,
        args=(numero, accion),
        daemon=True
    ).start()

    return redirect(url_for("crm", numero=numero))


@app.route("/crm/toggle/<numero>", methods=["POST"])
def crm_toggle(numero):
    if not crm_autorizado():
        return crm_pedir_login()

    if crm_esta_manual(numero):
        # Si Gabriel decide reactivar la IA manualmente, también limpiamos
        # cualquier bandera de intervención pendiente.
        limpiar_intervencion_automatica(numero, reanudar_ia=True)
    else:
        # Pausar inmediatamente cualquier respuesta IA que esté en proceso.
        crm_poner_manual(numero)
        cancelar_seguimiento(numero)
        iniciar_procesamiento(
            numero,
            f"crm-manual-{time.time()}"
        )

    return redirect(url_for("crm", numero=numero))


def _crm_worker_info_tres_proyectos(numero):
    """Envía el resumen de los 3 proyectos y las fotos de amenidades fuera de la petición HTTP del CRM.
    Así el navegador no queda esperando mientras se suben las imágenes.
    """
    try:
        enviar_info_todos_proyectos(numero)
        guardar_mensaje(
            numero,
            "assistant",
            "Se envió desde el CRM el resumen comparativo de los 3 proyectos y las fotos de amenidades."
        )
    except Exception as exc:
        print("ERROR ACCION INFO 3 PROYECTOS:", exc)
        try:
            crm_registrar_mensaje(
                numero,
                "out",
                "⚠️ No pude completar el envío de la información de los 3 proyectos."
            )
        except Exception as exc2:
            print("ERROR REGISTRANDO FALLO INFO 3 PROYECTOS:", exc2)


@app.route("/crm/accion/info-3-proyectos/<numero>", methods=["POST"])
def crm_accion_info_tres_proyectos(numero):
    """Dispara el envío completo en segundo plano y vuelve al CRM de inmediato."""
    if not crm_autorizado():
        return crm_pedir_login()

    cancelar_seguimiento(numero)
    iniciar_procesamiento(numero, f"crm-accion-3-proyectos-{time.time()}")

    Thread(
        target=_crm_worker_info_tres_proyectos,
        args=(numero,),
        daemon=True
    ).start()

    return redirect(url_for("crm", numero=numero))


@app.route("/crm/enviar/<numero>", methods=["POST"])
def crm_enviar(numero):
    if not crm_autorizado():
        return crm_pedir_login()

    mensaje = request.form.get("mensaje", "").strip()

    if not mensaje:
        return redirect(url_for("crm", numero=numero))

    # Si la IA se pausó sola por una duda, esta respuesta de Gabriel resuelve
    # la intervención y la IA debe reanudarse automáticamente. En una respuesta
    # manual normal, conservamos el comportamiento anterior: queda en MANUAL.
    era_intervencion = es_intervencion_activa(numero)

    crm_poner_manual(numero)
    cancelar_seguimiento(numero)

    # Invalida cualquier respuesta automática que todavía estuviera procesándose.
    iniciar_procesamiento(
        numero,
        f"crm-manual-{time.time()}"
    )

    ok = False
    if crm_es_facebook(numero):
        ok = enviar_messenger_texto(numero, mensaje, formalizar=False)
        if ok:
            guardar_mensaje(numero, "assistant", mensaje, formalizar=False)
        else:
            crm_registrar_mensaje(
                numero,
                "out",
                "⚠️ Messenger no pudo enviar este mensaje. Revise el token de la Página en Render."
            )
    else:
        ok = enviar_whatsapp(numero, mensaje, formalizar=False)
        if ok:
            guardar_mensaje(numero, "assistant", mensaje, formalizar=False)

    if ok and era_intervencion:
        limpiar_intervencion_automatica(numero, reanudar_ia=True)
        meta_actual = crm_obtener_meta(numero)
        crm_guardar_meta(
            numero,
            meta_actual.get("etapa") or "Interesado",
            "Respuesta de Gabriel enviada; IA reanudada",
            meta_actual.get("proxima_accion_fecha") or ""
        )
        # La respuesta manual también puede quedar pendiente de contestación.
        programar_seguimiento_inactividad(numero)

    return redirect(url_for("crm", numero=numero))


@app.route("/crm/enviar-archivo/<numero>", methods=["POST"])
def crm_enviar_archivo(numero):
    if not crm_autorizado():
        return crm_pedir_login()

    if crm_es_facebook(numero):
        crm_registrar_mensaje(
            numero,
            "out",
            "ℹ️ El envío manual de archivos por Messenger se mantiene separado; los envíos automáticos del bot sí están activos."
        )
        return redirect(url_for("crm", numero=numero))

    archivo = request.files.get("archivo")
    caption = request.form.get("caption", "").strip()
    if not archivo or not archivo.filename:
        return redirect(url_for("crm", numero=numero))

    nombre = os.path.basename(archivo.filename)
    mime = (archivo.mimetype or mimetypes.guess_type(nombre)[0] or "").lower()
    permitidos = {
        "image/jpeg": "image",
        "image/png": "image",
        "video/mp4": "video",
        "application/pdf": "document"
    }
    tipo = permitidos.get(mime)
    if not tipo:
        crm_registrar_mensaje(numero, "out", "⚠️ No se envió el archivo: formato no permitido.")
        return redirect(url_for("crm", numero=numero))

    contenido = archivo.read()
    if not contenido:
        return redirect(url_for("crm", numero=numero))

    # Al enviar manualmente cualquier archivo, Gabriel toma control de la conversación.
    # Si venía de una intervención automática, al enviarse correctamente se reanuda la IA.
    era_intervencion = es_intervencion_activa(numero)
    crm_poner_manual(numero)
    cancelar_seguimiento(numero)
    iniciar_procesamiento(numero, f"crm-manual-media-{time.time()}")

    media_id = subir_media_bytes_a_meta(contenido, nombre, mime)
    if not media_id:
        crm_registrar_mensaje(numero, "out", f"⚠️ No pude subir {nombre} a WhatsApp.")
        return redirect(url_for("crm", numero=numero))

    ok = enviar_media_id_whatsapp(numero, media_id, tipo, nombre, caption)
    if ok:
        media_url = guardar_media_crm_bytes(numero, contenido, mime)
        etiqueta = {"image": "🖼️ Imagen enviada", "video": "🎥 Video enviado", "document": "📄 PDF enviado"}[tipo]
        texto_crm = f"{etiqueta}: {nombre}" + (f"\n{caption}" if caption else "")
        crm_registrar_mensaje(numero, "out", texto_crm, media_url=media_url, media_tipo=tipo)
        guardar_mensaje(numero, "assistant", texto_crm, formalizar=False)
        if era_intervencion:
            limpiar_intervencion_automatica(numero, reanudar_ia=True)
            programar_seguimiento_inactividad(numero)
    else:
        crm_registrar_mensaje(numero, "out", f"⚠️ WhatsApp rechazó el envío de {nombre}.")

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
