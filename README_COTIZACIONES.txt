ACTUALIZACION: COTIZACIONES + PROYECTO FIJO

Incluye:
- Cotizaciones en imagen de Palmeras San Miguel.
- Cotizaciones en imagen de Vista Hermosa.
- Cotizaciones en imagen de Buenaventura.
- El bot recuerda el proyecto por número.
- Si ya se habló de Palmeras, no vuelve a preguntar "¿qué proyecto?".
- Solo cambia el proyecto cuando el cliente menciona otro.

PRUEBAS:

1)
Cliente: Me interesa Palmeras San Miguel
Cliente: ¿Tienes la cotización?
Bot: pregunta SOLO 8x16 u 8x18, no vuelve a preguntar proyecto.

2)
Cliente: Quiero de San Miguel de 8x16
Bot: manda las 2 cotizaciones 8x16 de Palmeras.

3)
Cliente: Me interesa Vista Hermosa
Cliente: Mándame la cotización
Bot: manda automáticamente las cotizaciones 8x16 Fase F y Fase G.

4)
Cliente: Me interesa Buenaventura
Cliente: Cotización 8x18
Bot: manda la imagen 8x18 de Buenaventura.

INSTALACION:
Copia app.py y la carpeta media dentro de BOT_INMOBILIARIA.
Conserva tu .env actual.
Luego:
Ctrl + C
python app.py
