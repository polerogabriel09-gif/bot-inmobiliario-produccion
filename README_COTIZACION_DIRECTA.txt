CORRECCION: COTIZACION DIRECTA SIN PREGUNTAS REDUNDANTES

Problema corregido:
El bot decía que enviaría la cotización, luego preguntaba plazo,
luego volvía a preguntar y no mandaba las imágenes.

Ahora:
- "quiero la cotización" -> envía cotización inmediatamente.
- "sí porfa" después de una oferta de cotización -> envía cotización.
- "el de 8" después de hablar de planes de pago -> envía cotización.
- No vuelve a preguntar plazo ni si desea que se la mande.
- Usa el proyecto activo guardado en memoria.

El envío mantiene todas las cotizaciones/fases disponibles del proyecto,
según la lógica ya cargada en el bot.

INSTALACION:
1. Conserva .env
2. Conserva media
3. Reemplaza app.py
4. Ctrl + C
5. python app.py
