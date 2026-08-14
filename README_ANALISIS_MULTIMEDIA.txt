ANALISIS INTELIGENTE DE FOTOS Y VIDEOS RECIBIDOS

NUEVO:
- Si el CLIENTE envía una foto, el bot la descarga desde WhatsApp Cloud API
  y la analiza con visión.
- Si es una cotización, mapa, terreno, proyecto, documento o contenido relacionado,
  responde de forma útil dentro del contexto del proyecto activo.
- Si la imagen es ambigua, pregunta qué desea revisar.
- Si no tiene relación con terrenos (meme, comida, selfie, etc.), no se desvía:
  redirige la conversación a terrenos.

VIDEOS:
- Descarga el video.
- Extrae 3 fotogramas representativos.
- Analiza esos fotogramas juntos.
- No intenta analizar cada segundo del video.

IMPORTANTE PARA VIDEOS:
Instala OpenCV una sola vez en tu computadora:

    pip install opencv-python

Sin OpenCV las fotos sí funcionan, pero el bot no podrá extraer fotogramas de videos.

SEGURIDAD:
- No certifica autenticidad/legalidad de documentos solo por una imagen.
- No inventa cifras/textos no visibles.
- No repite datos sensibles innecesariamente.

INSTALACION:
1. Conserva tu .env.
2. Conserva tu carpeta media.
3. Reemplaza app.py.
4. En la terminal ejecuta una sola vez:
       pip install opencv-python
5. Reinicia:
       Ctrl + C
       python app.py

PRUEBAS:
A) Envía una captura de una cotización.
B) Envía una foto de un terreno.
C) Envía una imagen no relacionada.
D) Envía un video corto de un proyecto.
