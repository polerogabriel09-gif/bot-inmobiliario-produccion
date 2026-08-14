MULTIMEDIA ENTRANTE COMPLETA

AUDIOS
- Descarga la nota de voz desde WhatsApp.
- La transcribe con OpenAI usando gpt-transcribe.
- El texto transcrito entra al mismo flujo normal.
- Si el audio dice "quiero precios de Palmeras", manda cotizaciones igual que texto.
- También funciona con ubicación, requisitos, gastos adicionales, etc.

FOTOS
- Descarga y analiza la imagen.
- Si es relevante al negocio, responde sobre ella.
- Si es ambigua, pregunta qué desea revisar.
- Si no tiene relación con terrenos, redirige al negocio.

VIDEOS
- Descarga el video.
- Extrae 3 fotogramas.
- Analiza esos fotogramas en conjunto.
- Requiere opencv-python.

INSTALACIÓN
1. Conserva .env
2. Conserva media
3. Reemplaza app.py
4. Para videos, una sola vez:
   pip install opencv-python
5. Reinicia:
   Ctrl + C
   python app.py

No necesitas otra API key para audio; usa OPENAI_API_KEY.
