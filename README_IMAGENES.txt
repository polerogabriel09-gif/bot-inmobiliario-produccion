BOT INMOBILIARIO - ENVIO DE IMAGENES

Archivos preparados:
- app.py actualizado
- 6 imágenes de Palmeras San Miguel
- 9 imágenes de Buenaventura Cuyotenango
- carpeta Vista Hermosa preparada (todavía sin fotos)

IMPORTANTE:
1. Conserva tu archivo .env actual. NO lo reemplaces.
2. Copia app.py y la carpeta media dentro de BOT_INMOBILIARIA.
3. Debe quedar:
   BOT_INMOBILIARIA/
       app.py
       contexto.txt
       .env
       media/
           palmeras/
           buenaventura/
           vista_hermosa/

4. Reinicia:
   Ctrl + C
   python app.py

PRUEBAS:
- "Me interesa Palmeras San Miguel"
- "Mándame fotos"

o:
- "Quiero información de Buenaventura"
- "¿Tienes imágenes?"

El bot recuerda el proyecto por número y manda máximo 2 imágenes por solicitud.

NOTA:
Meta recibe la imagen local mediante /media, devuelve un media_id,
y luego el bot envía ese media_id por /messages.
