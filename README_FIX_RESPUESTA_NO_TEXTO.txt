FIX FINAL: respuesta_no_texto

Se eliminó cualquier referencia antigua a respuesta_no_texto.

Ahora:
- audio -> se descarga, transcribe y entra al flujo normal del bot;
- foto -> se analiza con visión;
- video -> se analiza por fotogramas;
- otros archivos -> respuesta controlada;
- ya no debe aparecer:
  name 'respuesta_no_texto' is not defined

INSTALACION:
1. Conserva tu .env.
2. Conserva tu carpeta media.
3. Reemplaza app.py.
4. Ctrl + C
5. python app.py
