# -*- coding: utf-8 -*-
"""
GENERADOR DE YOUTUBE SHORTS (v3 - modo inteligente)

MODO INTELIGENTE (recomendado): usa la API de Claude con búsqueda web para
entender la pregunta, buscar datos ACTUALES y escribir un guion con sentido,
dividido en escenas con una imagen distinta para cada parte.

  1) Crea una clave en https://console.anthropic.com
  2) En PowerShell:   $env:ANTHROPIC_API_KEY="sk-ant-..."
     o guarda la clave en un archivo "clave_anthropic.txt" junto a este script.

MODO BÁSICO (sin clave): usa Wikipedia. Funciona bien con temas concretos
("Roblox", "Francisco Franco") pero NO con preguntas sobre datos actuales.

Requisitos:
    py -m pip install -U requests edge-tts aiohttp pyttsx3
    FFmpeg instalado y en el PATH (ffmpeg -version)
"""

import asyncio
import datetime
import html
import json
import os
import random
import re
import shutil
import subprocess
import tempfile
import textwrap
import time
import unicodedata
from pathlib import Path

import edge_tts
import requests

# ------------------------------------------------------------
# CONFIGURACIÓN
# ------------------------------------------------------------

API_URL = "https://api.anthropic.com/v1/messages"
MODELO = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")

WIKI_API = "https://es.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "GeneradorShortsEducativos/3.0 (uso personal educativo)"

ANCHO = 1080
ALTO = 1920
FPS = 30
PALABRAS_POR_SEGUNDO = 2.4

VOCES = [
    "es-ES-AlvaroNeural",
    "es-MX-JorgeNeural",
    "es-ES-ArnauNeural",
]
VELOCIDADES = ["+4%", "+0%"]

MIME_A_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

PREFIJOS = [
    "cuéntame sobre", "cuentame sobre", "háblame de", "hablame de",
    "quién fue", "quien fue", "quién es", "quien es",
    "quién creó", "quien creó", "quien creo", "quién creo",
    "qué es", "que es", "historia de", "sobre",
]


# ------------------------------------------------------------
# UTILIDADES
# ------------------------------------------------------------

def encabezado(texto):
    print("\n" + "=" * 68)
    print(texto.center(68))
    print("=" * 68)


def ejecutar(comando):
    subprocess.run(comando, check=True)


def comprobar_programas():
    for programa in ("ffmpeg", "ffprobe"):
        if shutil.which(programa) is None:
            raise RuntimeError(
                f"No encuentro {programa}. Instala FFmpeg y añádelo al PATH."
            )


def sin_tildes(texto):
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def limpiar_html(texto):
    texto = re.sub(r"<[^>]+>", "", texto or "")
    return html.unescape(texto).strip()


def limpiar_texto(texto):
    texto = limpiar_html(texto)
    texto = re.sub(r"\[[^\]]*\]", "", texto)
    texto = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def preparar_narracion(frase):
    frase = re.sub(r"\([^)]*\)", "", frase)
    frase = re.sub(r"\[[^\]]*\]", "", frase)
    frase = re.sub(r"\s+([,.;:])", r"\1", frase)
    frase = re.sub(r"\s+", " ", frase)
    return frase.strip(" ,;")


ABREV = re.compile(
    r"(?:\b[A-ZÁÉÍÓÚÑ]|\b(?:Sr|Sra|Dr|Dra|Gral|Ud|Uds|Avda|Prof|Lic|Ing"
    r"|vol|pp|núm|aprox|cap|Cía))\.$"
)


def dividir_frases(texto):
    partes = re.split(r"(?<=[.!?])\s+", texto)
    frases = []
    for p in partes:
        if frases and ABREV.search(frases[-1]):
            frases[-1] += " " + p
        else:
            frases.append(p)
    return [f for f in frases if f.strip()]


def normalizar_busqueda(texto):
    texto = texto.strip().strip("¿?¡! ")
    cambio = True
    while cambio:
        cambio = False
        for prefijo in PREFIJOS:
            if texto.lower().startswith(prefijo + " "):
                texto = texto[len(prefijo):].strip()
                cambio = True
    return texto.strip("¿?¡! ")


def nombre_limpio(titulo):
    return re.sub(r"\s*\([^)]*\)\s*$", "", titulo).strip()


def palabras_importantes(texto):
    ignorar = {
        "quien", "sobre", "para", "como", "fue", "del", "los", "las",
        "una", "por", "que", "mas", "muy", "menos", "con", "son", "ser",
        "esta", "este", "hay",
    }
    palabras = re.findall(r"[a-z0-9ñü]+", sin_tildes(texto.lower()))
    return [p for p in palabras if len(p) > 2 and p not in ignorar]


PATRON_ACTUALIDAD = re.compile(
    r"\b(mas|menos)\s+(rico|pobre|alto|grande|famoso|popular|caro|vendido|"
    r"visto|seguido|poderoso|joven|viejo)\b"
    r"|\b(actual|actualmente|hoy|ahora|ultimo|ultima|ultimos|ultimas|"
    r"reciente|recientes|ranking|top|precio|cotizacion|gana|ganador|campeon)\b"
    r"|\bpresidente de\b|\b20[2-9]\d\b"
)


def requiere_actualidad(prompt):
    return bool(PATRON_ACTUALIDAD.search(sin_tildes(prompt.lower())))


# ------------------------------------------------------------
# MODO INTELIGENTE: CLAUDE + BÚSQUEDA WEB
# ------------------------------------------------------------

def cargar_clave():
    clave = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if clave:
        return clave
    for base in (Path.cwd(), Path(__file__).resolve().parent):
        ruta = base / "clave_anthropic.txt"
        if ruta.exists():
            return ruta.read_text(encoding="utf-8").strip()
    return ""


def llamar_claude(clave, sistema, mensaje, usar_web=True):
    herramientas = []
    if usar_web:
        herramientas = [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5,
        }]

    mensajes = [{"role": "user", "content": mensaje}]
    bloques = []

    for _ in range(4):
        cuerpo = {
            "model": MODELO,
            "max_tokens": 3000,
            "system": sistema,
            "messages": mensajes,
        }
        if herramientas:
            cuerpo["tools"] = herramientas

        r = requests.post(
            API_URL,
            headers={
                "x-api-key": clave,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=cuerpo,
            timeout=180,
        )

        if r.status_code != 200:
            raise RuntimeError(f"API {r.status_code}: {r.text[:400]}")

        datos = r.json()
        contenido = datos.get("content", [])
        bloques += contenido

        if datos.get("stop_reason") == "pause_turn":
            mensajes.append({"role": "assistant", "content": contenido})
            continue
        break

    return bloques


def extraer_json(bloques):
    textos = [b.get("text", "") for b in bloques if b.get("type") == "text"]
    candidatos = [t for t in textos if '"segmentos"' in t] or textos
    if not candidatos:
        raise ValueError("La respuesta no contiene texto.")

    texto = candidatos[-1]
    ini, fin = texto.find("{"), texto.rfind("}")
    if ini < 0 or fin <= ini:
        raise ValueError("La respuesta no contiene JSON.")
    return json.loads(texto[ini:fin + 1])


def extraer_fuentes(bloques):
    citadas, otras = [], []
    vistos = set()

    for b in bloques:
        for c in (b.get("citations") or []):
            url = c.get("url")
            if url and url not in vistos:
                vistos.add(url)
                citadas.append({"titulo": c.get("title", url), "url": url})

        if b.get("type") == "web_search_tool_result":
            contenido = b.get("content")
            if isinstance(contenido, list):
                for r in contenido:
                    url = r.get("url")
                    if url and url not in vistos:
                        vistos.add(url)
                        otras.append({"titulo": r.get("title", url), "url": url})

    return (citadas + otras)[:8]


def plan_con_claude(clave, prompt, duracion):
    palabras = int(duracion * PALABRAS_POR_SEGUNDO)
    hoy = datetime.date.today().strftime("%d/%m/%Y")

    sistema = f"""Eres guionista de YouTube Shorts educativos en español de España.
Hoy es {hoy}.

REGLAS:
- Interpreta lo que la persona quiere saber realmente. Si la pregunta depende
  de datos actuales (rankings, cargos, cifras, noticias), usa la búsqueda web
  y da datos verificados indicando la fuente y la fecha ("según Forbes, a
  fecha de ...").
- No inventes nada. Si las fuentes discrepan o no hay datos claros, dilo.
- En política e historia usa un tono neutral y factual, sin opiniones propias.
- Estructura: gancho potente en la primera frase, 3 a 5 datos concretos y
  cierre breve que invite a comentar.
- Frases cortas y naturales para narrar en voz alta: sin paréntesis, sin
  listas, sin URLs, sin emojis, sin abreviaturas raras.
- Extensión total: unas {palabras} palabras (±10%).
- Divide el guion en 5 a 8 segmentos de 1 o 2 frases. Para cada segmento
  indica "imagen": un término para buscar en Wikimedia Commons (nombre propio
  concreto: persona, lugar, empresa u objeto; 1 a 4 palabras), distinto en
  cada segmento cuando sea posible.

Responde SOLO con JSON válido, sin texto antes ni después:
{{"titulo": "tema principal en pocas palabras",
  "segmentos": [{{"texto": "...", "imagen": "..."}}]}}"""

    mensaje = (
        f'Tema o pregunta: "{prompt}"\n'
        f"Duración objetivo: {duracion} segundos (unas {palabras} palabras)."
    )

    try:
        bloques = llamar_claude(clave, sistema, mensaje, usar_web=True)
    except RuntimeError as e:
        if "API 400" in str(e):
            print(f"⚠️ La búsqueda web no está disponible ({e}).")
            print("   Continúo sin búsqueda web (puede haber datos desactualizados).")
            bloques = llamar_claude(clave, sistema, mensaje, usar_web=False)
        else:
            raise

    datos = extraer_json(bloques)

    segmentos = []
    for s in datos.get("segmentos", []):
        texto = limpiar_texto(s.get("texto", ""))
        if len(texto) >= 10:
            segmentos.append({
                "texto": texto,
                "imagen": limpiar_texto(s.get("imagen", "")) or "",
            })

    if len(segmentos) < 3:
        raise ValueError("El guion devuelto es demasiado corto.")

    return {
        "titulo": limpiar_texto(datos.get("titulo", "")) or normalizar_busqueda(prompt),
        "segmentos": segmentos,
        "fuentes": extraer_fuentes(bloques),
        "modo": "Claude + búsqueda web",
    }


# ------------------------------------------------------------
# MODO BÁSICO: WIKIPEDIA
# ------------------------------------------------------------

def wiki_request(params):
    r = requests.get(
        WIKI_API, params=params,
        headers={"User-Agent": USER_AGENT}, timeout=20,
    )
    r.raise_for_status()
    return r.json()


def buscar_wikipedia(consulta, limite=8):
    datos = wiki_request({
        "action": "query", "list": "search", "srsearch": consulta,
        "srlimit": limite, "format": "json", "utf8": 1,
    })
    return [x["title"] for x in datos.get("query", {}).get("search", [])]


def obtener_articulo(titulo):
    datos = wiki_request({
        "action": "query",
        "prop": "extracts|info|pageprops",
        "ppprop": "disambiguation",
        "explaintext": 1,
        "inprop": "url",
        "titles": titulo,
        "format": "json",
        "formatversion": 2,
        "redirects": 1,
    })

    for pagina in datos.get("query", {}).get("pages", []):
        if pagina.get("missing"):
            continue
        if "disambiguation" in (pagina.get("pageprops") or {}):
            continue

        crudo = pagina.get("extract", "") or ""
        crudo = re.sub(r"^=+.*?=+\s*$", "", crudo, flags=re.M)
        texto = limpiar_texto(crudo)

        if len(texto) > 120:
            return {
                "titulo": pagina.get("title", titulo),
                "texto": texto,
                "url": pagina.get("fullurl", ""),
            }
    return None


def relevancia(articulo, claves):
    if not claves:
        return 1.0
    base = sin_tildes(
        (articulo["titulo"] + " " + articulo["texto"][:800]).lower()
    )
    tokens = set(re.findall(r"[a-z0-9ñü]+", base))
    return sum(1 for c in claves if c in tokens) / len(claves)


def investigar(prompt):
    encabezado("🔎 INVESTIGANDO EN WIKIPEDIA")

    tema = normalizar_busqueda(prompt)
    claves = palabras_importantes(tema)

    articulos, usados = [], set()

    def agregar(titulo, directo=False):
        try:
            a = obtener_articulo(titulo)
        except Exception as e:
            print(f"⚠️ Error leyendo '{titulo}': {e}")
            return
        if not a or a["titulo"].lower() in usados:
            return
        usados.add(a["titulo"].lower())
        a["directo"] = directo
        a["relevancia"] = 1.0 if directo else relevancia(a, claves)
        articulos.append(a)
        print(f"📖 {a['titulo']}  (relevancia {a['relevancia']:.0%})")

    print(f"\n🎯 Título directo: {tema}")
    agregar(tema, directo=True)

    for consulta in (tema, f"{tema} historia"):
        if len(articulos) >= 5:
            break
        print(f"\n🔍 Búsqueda: {consulta}")
        try:
            resultados = buscar_wikipedia(consulta)
        except Exception as e:
            print(f"⚠️ Error buscando: {e}")
            continue
        for titulo in resultados:
            agregar(titulo)
            if len(articulos) >= 5:
                break

    # Descarta lo poco relevante
    articulos = [a for a in articulos if a["relevancia"] >= 0.6]

    if not articulos:
        raise RuntimeError(
            f"No encontré ningún artículo claramente relacionado con '{tema}'. "
            "Prueba con un tema más concreto o usa el modo inteligente (clave de API)."
        )

    t = tema.lower()

    def puntuacion(a):
        titulo = nombre_limpio(a["titulo"]).lower()
        puntos = a["relevancia"] * 100
        if a.get("directo"):
            puntos += 20000
        if titulo == t:
            puntos += 10000
        elif titulo.startswith(t):
            puntos += 3000
        elif t in titulo:
            puntos += 1000
        return puntos - len(titulo)

    articulos.sort(key=puntuacion, reverse=True)
    return articulos


def plan_con_wikipedia(prompt, duracion, articulos):
    principal = articulos[0]
    nombre = nombre_limpio(principal["titulo"])
    claves = palabras_importantes(prompt)

    candidatos = []
    for idx, art in enumerate(articulos):
        if idx > 0 and not all(c in sin_tildes(art["titulo"].lower()) for c in claves):
            continue
        for pos, frase in enumerate(dividir_frases(art["texto"])):
            frase = preparar_narracion(frase)
            if len(frase) < 40 or len(frase) > 240 or frase.count(",") > 6:
                continue
            f = sin_tildes(frase.lower())
            puntos = (200 if idx == 0 else -100) + max(0, 120 - pos * 6)
            puntos += sum(25 for c in claves if c in f)
            candidatos.append({"texto": frase, "idx": idx, "pos": pos, "puntos": puntos})

    if not candidatos:
        raise RuntimeError("No encontré suficiente información para crear el guion.")

    hook = random.choice([
        f"Esto es lo esencial que debes saber sobre {nombre}.",
        f"{nombre}: lo que debes saber en menos de un minuto.",
    ])
    cierre = random.choice([
        "¿Ya conocías estos datos? Te leo en los comentarios.",
        "Si quieres más vídeos como este, sígueme.",
    ])

    objetivo = int(duracion * PALABRAS_POR_SEGUNDO)
    presupuesto = objetivo - len(hook.split()) - len(cierre.split())

    candidatos.sort(key=lambda x: x["puntos"], reverse=True)
    elegidos, vistos, usadas = [], set(), 0
    for c in candidatos:
        n = len(c["texto"].split())
        if c["texto"].lower() in vistos or usadas + n > presupuesto:
            continue
        vistos.add(c["texto"].lower())
        elegidos.append(c)
        usadas += n
        if usadas >= presupuesto - 8:
            break
    elegidos.sort(key=lambda x: (x["idx"], x["pos"]))

    textos = [hook] + [c["texto"] for c in elegidos] + [cierre]
    return {
        "titulo": nombre,
        "segmentos": [{"texto": t, "imagen": nombre} for t in textos],
        "fuentes": [{"titulo": a["titulo"], "url": a["url"]} for a in articulos],
        "modo": "Wikipedia (modo básico)",
    }


def segmentar_texto(texto, consultas):
    """Convierte un texto editado a mano en segmentos de ~2 frases."""
    frases = dividir_frases(texto)
    segmentos, actual = [], []
    for f in frases:
        actual.append(f)
        if len(" ".join(actual).split()) >= 22:
            segmentos.append(" ".join(actual))
            actual = []
    if actual:
        segmentos.append(" ".join(actual))
    return [
        {"texto": s, "imagen": consultas[i % len(consultas)]}
        for i, s in enumerate(segmentos)
    ]


# ------------------------------------------------------------
# VOZ + TIMESTAMPS
# ------------------------------------------------------------

def expandir_frase_a_palabras(texto, inicio, fin):
    palabras = texto.split()
    if not palabras:
        return []
    pesos = [len(p) + 2 for p in palabras]
    total = sum(pesos)
    duracion = max(fin - inicio, 0.1)
    resultado, t = [], inicio
    for p, w in zip(palabras, pesos):
        d = duracion * w / total
        resultado.append({"texto": p, "inicio": t, "fin": t + d})
        t += d
    return resultado


def estimar_palabras(texto, duracion):
    palabras = texto.split()
    if not palabras:
        return []
    pesos = []
    for p in palabras:
        w = len(p) + 2
        if p.endswith((".", "!", "?")):
            w += 6
        elif p.endswith((",", ";", ":")):
            w += 3
        pesos.append(w)
    total = sum(pesos)
    util = max(duracion - 0.3, 0.5)
    t, resultado = 0.1, []
    for p, w in zip(palabras, pesos):
        d = util * w / total
        resultado.append({"texto": p, "inicio": t, "fin": t + d})
        t += d
    return resultado


async def generar_voz(texto, voz, destino, velocidad):
    try:
        com = edge_tts.Communicate(
            texto, voice=voz, rate=velocidad, boundary="WordBoundary"
        )
    except TypeError:
        com = edge_tts.Communicate(texto, voice=voz, rate=velocidad)

    palabras, frases = [], []
    recibio_audio = False

    with open(destino, "wb") as archivo:
        async for m in com.stream():
            tipo = m.get("type")
            if tipo == "audio":
                datos = m.get("data")
                if datos:
                    archivo.write(datos)
                    recibio_audio = True
            elif tipo in ("WordBoundary", "SentenceBoundary"):
                txt, off, dur = m.get("text"), m.get("offset"), m.get("duration")
                if txt and off is not None:
                    ini = float(off) / 10_000_000
                    fin = ini + float(dur or 0) / 10_000_000
                    (palabras if tipo == "WordBoundary" else frases).append(
                        {"texto": txt, "inicio": ini, "fin": fin}
                    )

    if not recibio_audio or destino.stat().st_size < 1000:
        raise RuntimeError("No se recibió audio.")

    if not palabras and frases:
        for f in frases:
            palabras += expandir_frase_a_palabras(f["texto"], f["inicio"], f["fin"])
    return palabras


def voz_offline(texto, destino):
    import pyttsx3

    motor = pyttsx3.init()
    elegida = None
    for v in motor.getProperty("voices"):
        datos = f"{v.id} {v.name}".lower()
        if any(x in datos for x in (
            "spanish", "español", "es-es", "es-mx",
            "helena", "pablo", "sabina", "laura", "raul",
        )):
            elegida = v
            break
    if elegida is None:
        raise RuntimeError("No hay ninguna voz en español instalada en Windows.")

    motor.setProperty("voice", elegida.id)
    motor.setProperty("rate", 175)
    motor.save_to_file(texto, str(destino))
    motor.runAndWait()
    motor.stop()

    if not destino.exists() or destino.stat().st_size < 1000:
        raise RuntimeError("La voz offline no generó audio.")
    return f"offline: {elegida.name}"


def crear_audio(texto, trabajo):
    errores = []
    destino = trabajo / "narracion.mp3"

    for voz in VOCES:
        for velocidad in VELOCIDADES:
            try:
                print(f"🎙️ Probando voz: {voz} ({velocidad})")
                if destino.exists():
                    destino.unlink()
                palabras = asyncio.run(generar_voz(texto, voz, destino, velocidad))
                print(f"✅ Voz funcionando: {voz}")
                return voz, palabras, destino
            except Exception as e:
                msg = f"{voz} ({velocidad}): {type(e).__name__}: {e}"
                print(f"⚠️ {msg}")
                errores.append(msg)
                time.sleep(1)

    print("\n🔁 Edge TTS no responde. Probando voz offline de Windows...")
    try:
        wav = trabajo / "narracion.wav"
        voz = voz_offline(texto, wav)
        print(f"✅ Voz funcionando: {voz}")
        return voz, [], wav
    except Exception as e:
        errores.append(f"offline: {type(e).__name__}: {e}")

    raise RuntimeError(
        "No se pudo crear ninguna voz.\n\n" + "\n".join(errores)
        + "\n\nPrueba: py -m pip install -U edge-tts pyttsx3"
    )


def duracion_audio(archivo):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(archivo)],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


# ------------------------------------------------------------
# IMÁGENES (Wikimedia Commons), UNA POR ESCENA
# ------------------------------------------------------------

_cache_commons = {}


def candidatos_commons(consulta):
    if consulta in _cache_commons:
        return _cache_commons[consulta]

    lista = []
    try:
        r = requests.get(
            COMMONS_API,
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": f"{consulta} filetype:bitmap",
                "gsrnamespace": 6,
                "gsrlimit": 20,
                "prop": "imageinfo",
                "iiprop": "url|size|mime",
                "iiurlwidth": 1400,
                "format": "json",
                "formatversion": 2,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        r.raise_for_status()
        paginas = r.json().get("query", {}).get("pages", [])
        paginas.sort(key=lambda p: p.get("index", 0))

        for p in paginas:
            info = (p.get("imageinfo") or [{}])[0]
            ext = MIME_A_EXT.get(info.get("mime", ""))
            if not ext:
                continue
            if info.get("width", 0) < 500 or info.get("height", 0) < 500:
                continue
            url = info.get("thumburl") or info.get("url")
            if url:
                lista.append({
                    "url": url,
                    "ext": ext,
                    "pagina": info.get("descriptionurl", ""),
                })
    except Exception as e:
        print(f"⚠️ Error buscando imágenes de '{consulta}': {e}")

    _cache_commons[consulta] = lista
    return lista


def obtener_imagen(consultas, destino_base, usadas):
    for consulta in consultas:
        if not consulta:
            continue
        for c in candidatos_commons(consulta):
            if c["url"] in usadas:
                continue
            try:
                d = requests.get(c["url"], headers={"User-Agent": USER_AGENT}, timeout=30)
                d.raise_for_status()
                destino = destino_base.with_suffix(c["ext"])
                destino.write_bytes(d.content)
                if destino.stat().st_size > 5000:
                    usadas.add(c["url"])
                    return {"ruta": destino, "pagina": c["pagina"]}
            except Exception:
                continue
    return None


def crear_fondo(destino):
    ejecutar([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"color=c=0x16213e:s={ANCHO}x{ALTO}",
        "-frames:v", "1", str(destino),
    ])
    return destino


# ------------------------------------------------------------
# VÍDEO VERTICAL
# ------------------------------------------------------------

def crear_escena(imagen, salida, segundos, indice):
    ancho_g, alto_g = int(ANCHO * 1.5), int(ALTO * 1.5)

    if indice % 2 == 0:
        zoom = "min(zoom+0.0009,1.15)"
    else:
        zoom = "if(eq(on,1),1.15,max(zoom-0.0009,1.0))"

    filtro = (
        f"scale={ancho_g}:{alto_g}:force_original_aspect_ratio=increase,"
        f"crop={ancho_g}:{alto_g},"
        f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d=1:s={ANCHO}x{ALTO}:fps={FPS},format=yuv420p"
    )

    ejecutar([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-framerate", str(FPS), "-i", str(imagen),
        "-t", f"{segundos:.3f}", "-vf", filtro, "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-pix_fmt", "yuv420p", str(salida),
    ])


def unir_videos(clips, lista, salida):
    lista.write_text(
        "\n".join(f"file '{str(c.resolve()).replace(chr(92), '/')}'" for c in clips),
        encoding="utf-8",
    )
    ejecutar([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(lista),
        "-c", "copy", str(salida),
    ])


# ------------------------------------------------------------
# SUBTÍTULOS
# ------------------------------------------------------------

def escapar_ass(texto):
    return texto.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def tiempo_ass(s):
    return f"{int(s // 3600)}:{int((s % 3600) // 60):02d}:{s % 60:05.2f}"


def crear_subtitulos_ass(palabras, destino):
    cabecera = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {ANCHO}
PlayResY: {ALTO}

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Arial,76,&H00FFFFFF,&H000000FF,&H00101010,&H99000000,1,0,0,0,100,100,0,0,1,5,2,2,60,60,240,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    grupos, actual = [], []
    for p in palabras:
        actual.append(p)
        if len(actual) >= 3 or p["texto"].endswith((".", "!", "?")):
            grupos.append(actual)
            actual = []
    if actual:
        grupos.append(actual)

    lineas = [cabecera]
    for i, g in enumerate(grupos):
        ini, fin = g[0]["inicio"], g[-1]["fin"]
        if i + 1 < len(grupos):
            fin = min(max(fin, ini + 0.2), grupos[i + 1][0]["inicio"])
        else:
            fin = max(fin, ini + 0.2)
        texto = r"{\fad(60,60)}" + " ".join(escapar_ass(p["texto"].upper()) for p in g)
        lineas.append(
            f"Dialogue: 0,{tiempo_ass(ini)},{tiempo_ass(fin)},Default,,0,0,0,,{texto}"
        )

    destino.write_text("\n".join(lineas), encoding="utf-8-sig")


# ------------------------------------------------------------
# PLAN DE VÍDEO (guion + escenas)
# ------------------------------------------------------------

def generar_plan(prompt, duracion, clave, contexto):
    """Devuelve el plan usando Claude si hay clave; si no, Wikipedia."""
    if clave:
        try:
            print("\n🧠 Claude está investigando y escribiendo el guion...")
            return plan_con_claude(clave, prompt, duracion)
        except Exception as e:
            print(f"\n⚠️ El modo inteligente falló: {e}")
            print("   Paso al modo básico (Wikipedia).")

    if requiere_actualidad(prompt):
        print("\n⚠️ Tu pregunta parece depender de datos ACTUALES (rankings,")
        print("   cargos, cifras...). Wikipedia no es fiable para eso y el")
        print("   guion podría salir sin sentido o desactualizado.")
        print("   Solución: configura ANTHROPIC_API_KEY (ver cabecera del script)")
        print("   o indica un tema concreto, por ejemplo: Elon Musk")
        nuevo = input("\nTema concreto (ENTER para continuar igualmente): ").strip()
        if nuevo:
            prompt = nuevo
            contexto.pop("articulos", None)
        contexto["prompt"] = prompt

    if "articulos" not in contexto:
        contexto["articulos"] = investigar(contexto.get("prompt", prompt))

    return plan_con_wikipedia(contexto.get("prompt", prompt), duracion, contexto["articulos"])


def mostrar_plan(plan):
    encabezado("📝 GUION")
    print(f"\nModo: {plan['modo']}   |   Tema: {plan['titulo']}\n")
    texto = " ".join(s["texto"] for s in plan["segmentos"])
    print(textwrap.fill(texto, width=70))
    print(f"\n({len(texto.split())} palabras, {len(plan['segmentos'])} escenas)")
    if plan["fuentes"]:
        print("\n📚 Fuentes:")
        for f in plan["fuentes"][:6]:
            print(f"  - {f['titulo']}\n    {f['url']}")


# ------------------------------------------------------------
# PROGRAMA PRINCIPAL
# ------------------------------------------------------------

def main():
    encabezado("🤖 GENERADOR DE YOUTUBE SHORTS v3")

    clave = cargar_clave()
    if clave:
        print("\n✅ Modo inteligente activado (Claude + búsqueda web).")
    else:
        print("\nℹ️ Modo básico (Wikipedia). Para respuestas inteligentes y datos")
        print("   actuales, configura ANTHROPIC_API_KEY (ver cabecera del script).")

    prompt = input("\n💡 ¿Sobre qué quieres hacer el Short?\n> ").strip()
    if not prompt:
        print("No escribiste ningún tema.")
        return

    entrada = input("\n⏱️ Duración aproximada [30 segundos]: ").strip()
    try:
        duracion_objetivo = max(15, min(60, int(entrada or "30")))
    except ValueError:
        duracion_objetivo = 30

    nombre = input("\n💾 Nombre del archivo [short_final.mp4]: ").strip() or "short_final.mp4"
    if not nombre.lower().endswith(".mp4"):
        nombre += ".mp4"
    salida = Path(nombre).resolve()

    comprobar_programas()

    contexto = {"prompt": prompt}
    plan = generar_plan(prompt, duracion_objetivo, clave, contexto)

    while True:
        mostrar_plan(plan)
        opcion = input(
            "\n¿Crear el vídeo? [S]í / [R]egenerar / [E]ditar / [N]o: "
        ).strip().lower()

        if opcion in ("s", "si", "sí", ""):
            break

        if opcion == "r":
            plan = generar_plan(prompt, duracion_objetivo, clave, contexto)
            continue

        if opcion == "e":
            print("\nEscribe el nuevo guion. Termina con una línea vacía:")
            lineas = []
            while True:
                linea = input()
                if not linea.strip():
                    break
                lineas.append(linea)
            nuevo = " ".join(lineas).strip()
            if nuevo:
                plan["segmentos"] = segmentar_texto(
                    nuevo, [plan["titulo"], normalizar_busqueda(prompt)]
                )
            continue

        if opcion in ("n", "no"):
            print("Cancelado.")
            return

        print("⚠️ Opción no válida. Escribe S, R, E o N.")

    encabezado("🎬 CREANDO SHORT")

    salida.parent.mkdir(parents=True, exist_ok=True)
    trabajo = Path(tempfile.mkdtemp(prefix="short_", dir=str(salida.parent)))
    creditos_imagenes = []

    try:
        segmentos = plan["segmentos"]
        guion = " ".join(s["texto"] for s in segmentos)

        print("\n🎙️ Generando voz y sincronización...")
        voz, palabras, audio = crear_audio(guion, trabajo)
        duracion_real = duracion_audio(audio)
        print(f"⏱️ Duración real: {duracion_real:.1f} segundos")

        if not palabras:
            print("ℹ️ Sin marcas de tiempo del motor: se estiman a partir del audio.")
            palabras = estimar_palabras(guion, duracion_real)

        # Una imagen por escena, relacionada con lo que se dice
        print(f"\n🖼️ Buscando imágenes para {len(segmentos)} escenas...")
        tema_general = [plan["titulo"], normalizar_busqueda(prompt)]
        usadas = set()
        rutas = []
        fondo = None

        for i, seg in enumerate(segmentos):
            consultas = [seg.get("imagen", "")] + tema_general
            img = obtener_imagen(consultas, trabajo / f"imagen_{i:02d}", usadas)

            if img:
                print(f"  ✅ Escena {i + 1}: {seg.get('imagen') or plan['titulo']}")
                rutas.append(img["ruta"])
                if img["pagina"]:
                    creditos_imagenes.append(img["pagina"])
            elif rutas:
                print(f"  ♻️ Escena {i + 1}: sin imagen nueva, reutilizo una anterior")
                rutas.append(rutas[-1])
            else:
                print(f"  ⚠️ Escena {i + 1}: sin imagen, uso fondo liso")
                fondo = fondo or crear_fondo(trabajo / "fondo.png")
                rutas.append(fondo)

        # Cada escena dura según la cantidad de texto que narra
        total_chars = sum(len(s["texto"]) for s in segmentos)
        total_seg = duracion_real + 0.5
        clips = []

        print("\n🎬 Creando escenas...")
        for i, (seg, ruta) in enumerate(zip(segmentos, rutas)):
            dur = max(1.0, total_seg * len(seg["texto"]) / total_chars)
            print(f"  Escena {i + 1}/{len(segmentos)} ({dur:.1f}s)")
            clip = trabajo / f"clip_{i:03d}.mp4"
            crear_escena(ruta, clip, dur, i)
            clips.append(clip)

        video = trabajo / "video.mp4"
        print("\n🔗 Uniendo escenas...")
        unir_videos(clips, trabajo / "lista.txt", video)

        subtitulos = trabajo / "subtitulos.ass"
        print("💬 Creando subtítulos...")
        crear_subtitulos_ass(palabras, subtitulos)

        encabezado("✨ CREANDO SHORT FINAL")
        ass = str(subtitulos.resolve()).replace("\\", "/").replace(":", r"\:")

        ejecutar([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(video), "-i", str(audio),
            "-vf", f"ass='{ass}'",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "medium", "-crf", "21",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart",
            str(salida),
        ])
    finally:
        shutil.rmtree(trabajo, ignore_errors=True)

    fuentes = salida.with_suffix(".fuentes.txt")
    fuentes.write_text(
        f"GUION ({plan['modo']})\n\n{guion}\n\n"
        "FUENTES DE INFORMACIÓN\n"
        + "\n".join(f"- {f['titulo']}\n  {f['url']}" for f in plan["fuentes"])
        + "\n\nIMÁGENES (Wikimedia Commons, revisa la licencia de cada una)\n"
        + "\n".join(f"- {u}" for u in creditos_imagenes),
        encoding="utf-8",
    )

    encabezado("✅ SHORT CREADO CORRECTAMENTE")
    print(f"\n🎬 Archivo:\n{salida}")
    print(f"\n📚 Guion, fuentes y créditos:\n{fuentes}")
    print(f"\n🎙️ Voz usada: {voz}")
    print("\nNota: verifica los datos y las licencias de las imágenes antes de publicar.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelado por el usuario.")
    except Exception as e:
        encabezado("❌ ERROR")
        print(f"\n{type(e).__name__}: {e}")
        print("\nEl programa se ha detenido.")
