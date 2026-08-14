VERSION: CUOTAS = TODAS LAS COTIZACIONES

NUEVO COMPORTAMIENTO:

Si el cliente ya está hablando de un proyecto y escribe:
- cuotas
- cotización
- cotizaciones
- mensualidades
- plan de pagos
- financiamiento

el bot NO pregunta la medida.

Envía automáticamente TODAS las imágenes de cotización disponibles
del proyecto activo.

PALMERAS SAN MIGUEL:
- 8x16 no esquina
- 8x16 segunda fase
- 8x18 primera fase
- 8x18 segunda fase

VISTA HERMOSA:
- 8x16 Fase F
- 8x16 Fase G

BUENAVENTURA:
- 8x16
- 8x18
- 9x20

EJEMPLO:

Cliente: Me interesa Palmeras San Miguel
Bot: responde sobre Palmeras

Cliente: ¿Cuáles son las cuotas?
Bot: envía TODAS las imágenes de cotización de Palmeras,
sin preguntar otra vez proyecto ni medida.

INSTALACION:
1. Conserva tu .env actual.
2. Reemplaza app.py.
3. Copia/reemplaza la carpeta media.
4. Ctrl + C
5. python app.py
