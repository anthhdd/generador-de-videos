# 🤖 Generador Automático de YouTube Shorts

Un generador automático de YouTube Shorts educativos creado con Python.

El programa puede crear un vídeo vertical a partir de un tema o pregunta. Genera el guion, crea una narración con voz artificial, busca imágenes relacionadas, genera subtítulos y finalmente exporta un vídeo listo en formato MP4.

> ⚠️ Este proyecto todavía está en desarrollo. Actualmente no tiene un nivel de inteligencia muy avanzado y necesita muchas mejoras.

---

## ✨ ¿Qué hace?

El programa realiza automáticamente gran parte del proceso de creación de un YouTube Short:

- 🧠 Genera un guion sobre el tema indicado.
- 🔎 Puede buscar información actual usando Claude y búsqueda web.
- 📚 Tiene un modo básico que utiliza Wikipedia.
- 🎙️ Genera una narración con voz artificial.
- 🖼️ Busca imágenes relacionadas en Wikimedia Commons.
- 🎬 Crea escenas verticales en formato 1080x1920.
- 🔍 Añade un pequeño efecto de zoom a las imágenes.
- 💬 Genera subtítulos automáticamente.
- 🎵 Sincroniza el audio con el vídeo.
- 📁 Exporta el resultado final como un archivo `.mp4`.
- 📚 Genera un archivo adicional con el guion, las fuentes y los créditos de las imágenes.

---

# 🧠 Modos de funcionamiento

## 🚀 Modo inteligente

El modo inteligente utiliza la API de Claude y, cuando está disponible, búsqueda web.

Este modo permite:

- Entender mejor preguntas complejas.
- Buscar información actual.
- Crear guiones más naturales.
- Dividir el contenido en diferentes escenas.
- Buscar imágenes diferentes para cada parte del vídeo.

Para utilizar este modo necesitas una clave de API de Anthropic.

Puedes configurar la clave como variable de entorno:

```powershell
$env:ANTHROPIC_API_KEY="TU_CLAVE_AQUI"
```

También puedes crear un archivo llamado:

```text
clave_anthropic.txt
```

Y colocar tu clave dentro.

> ⚠️ Nunca subas tu clave de API a GitHub.

---

## 📚 Modo básico

Si no tienes una clave de API, el programa utiliza Wikipedia.

Este modo funciona mejor con temas concretos como:

```text
Roblox
Albert Einstein
La historia de España
Francisco Franco
```

Sin embargo, no es recomendable para preguntas que dependan de información actual, rankings, precios, noticias o cargos actuales.

---

# 📦 Requisitos

Necesitas tener instalado:

- Python 3
- FFmpeg
- Python pip

También debes instalar las librerías necesarias.

Ejecuta:

```powershell
py -m pip install -r requirements.txt
```

O manualmente:

```powershell
py -m pip install -U requests edge-tts aiohttp pyttsx3
```

---

# 🎥 Instalar FFmpeg

FFmpeg es necesario para crear y unir las escenas del vídeo.

Después de instalarlo, comprueba que funciona ejecutando:

```powershell
ffmpeg -version
```

Y también:

```powershell
ffprobe -version
```

Si ambos comandos funcionan correctamente, FFmpeg está instalado y configurado correctamente.

---

# 🚀 Cómo ejecutar el programa

Abre PowerShell o CMD dentro de la carpeta del proyecto.

Después ejecuta:

```powershell
py short_generator.py
```

El programa te preguntará:

### 1. El tema del Short

Por ejemplo:

```text
💡 ¿Sobre qué quieres hacer el Short?

> ¿Qué es Roblox?
```

### 2. La duración

Puedes elegir aproximadamente entre 15 y 60 segundos.

Por ejemplo:

```text
30
```

### 3. El nombre del vídeo

Por ejemplo:

```text
mi_short.mp4
```

---

# 📝 Antes de crear el vídeo

El programa mostrará el guion generado.

Después podrás elegir:

```text
[S] Sí
[R] Regenerar
[E] Editar
[N] No
```

## Opciones

### S — Crear

Genera el vídeo utilizando el guion actual.

### R — Regenerar

Intenta generar otro guion.

### E — Editar

Permite escribir manualmente un nuevo guion.

### N — Cancelar

Cancela el proceso.

---

# 🎬 Cómo se crea el vídeo

El proceso funciona aproximadamente así:

```text
Tema
  ↓
Investigación
  ↓
Generación del guion
  ↓
Generación de voz
  ↓
Búsqueda de imágenes
  ↓
Creación de escenas
  ↓
Generación de subtítulos
  ↓
Unión del vídeo y audio
  ↓
MP4 final
```

El resultado es un vídeo vertical de:

```text
1080x1920
```

Pensado principalmente para:

- YouTube Shorts
- TikTok
- Instagram Reels

---

# 📁 Archivos generados

Cuando el proceso termina correctamente se generan principalmente:

```text
mi_short.mp4
```

El vídeo final.

También se genera:

```text
mi_short.fuentes.txt
```

Este archivo contiene:

- El guion utilizado.
- Las fuentes de información.
- Los créditos o enlaces relacionados con las imágenes utilizadas.

---

# ⚠️ Limitaciones actuales

Este proyecto todavía necesita muchas mejoras.

Actualmente el sistema **no tiene una inteligencia extremadamente avanzada** y puede cometer errores.

Algunas de las mejoras necesarias son:

- 🧠 Mejorar la comprensión de preguntas.
- 🔎 Mejorar la verificación de información.
- 🖼️ Mejorar la selección de imágenes.
- 🎙️ Añadir más voces y opciones de configuración.
- 💬 Mejorar la sincronización de subtítulos.
- 🎬 Añadir transiciones y efectos más avanzados.
- 🎵 Añadir música de fondo opcional.
- 🤖 Mejorar la generación automática de guiones.
- 📊 Añadir una interfaz gráfica.
- ⚙️ Añadir un archivo de configuración.
- 🌐 Mejorar la compatibilidad con diferentes sistemas.
- 📱 Añadir opciones específicas para diferentes plataformas.
- 🔄 Mejorar el sistema de recuperación de errores.

---

# ⚠️ Importante sobre la información

Aunque el programa puede utilizar fuentes online, debes revisar la información antes de publicar un vídeo.

El sistema puede:

- Utilizar información desactualizada.
- Interpretar incorrectamente una pregunta.
- Seleccionar imágenes que no sean perfectas para el contexto.
- Generar un guion con errores.

No publiques automáticamente contenido sin revisar el resultado.

---

# ⚠️ Licencias de las imágenes

Las imágenes se buscan en Wikimedia Commons.

Cada imagen puede tener condiciones de licencia diferentes.

Antes de publicar un vídeo debes comprobar la licencia y los requisitos de atribución de las imágenes utilizadas.

El programa genera un archivo de fuentes para facilitar la revisión.

---

# 🔑 Seguridad

Nunca subas estos archivos a GitHub:

```text
clave_anthropic.txt
.env
```

Tampoco publiques:

- API keys.
- Contraseñas.
- Tokens.
- Información privada.

El archivo `.gitignore` está pensado para evitar subir accidentalmente algunos de estos archivos.

---

# 🛠️ Futuro del proyecto

Este proyecto es una base que puede convertirse en un sistema mucho más avanzado.

La idea es seguir mejorándolo para conseguir:

- Mejores guiones.
- Mejores vídeos.
- Mejor selección de imágenes.
- Más automatización.
- Más personalización.
- Una interfaz más fácil de utilizar.

Actualmente es un proyecto en desarrollo y todavía queda bastante trabajo para convertirlo en un generador de Shorts más potente y fiable.

---

# 📌 Tecnologías utilizadas

- Python
- FFmpeg
- Edge TTS
- pyttsx3
- Requests
- Wikipedia API
- Wikimedia Commons API
- Anthropic API

---

# 📄 Aviso

Este proyecto está pensado principalmente
