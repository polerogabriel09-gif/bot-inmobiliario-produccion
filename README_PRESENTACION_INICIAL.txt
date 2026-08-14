PRESENTACION INICIAL AUTOMATICA

En la primera interacción de cada cliente, el bot envía primero:

¡Hola! 👋 Soy Gabriel Polero. 😊 ¿En qué le podemos servir?

Después:
- Si pidió precios, continúa y manda la cotización/fotos correspondiente.
- Si pidió ubicación, continúa con la ubicación.
- Si pidió gastos adicionales, continúa con los montos.
- Si pidió fotos/videos, continúa con multimedia.
- Si solo saludó, mantiene una respuesta breve y pregunta en qué le podemos servir.

La presentación NO se repite en cada mensaje del mismo cliente durante la sesión.

IMPORTANTE:
Este control se guarda en RAM. Si reinicias app.py, la sesión de presentación
empieza de nuevo, por lo que un cliente que escriba después del reinicio puede
recibir nuevamente la presentación. Esto es apropiado para el comportamiento
actual del bot y evita presentarse en cada mensaje.

INSTALACION:
1. Conserva tu archivo .env.
2. Conserva tu carpeta media.
3. Reemplaza app.py por el nuevo.
4. Ctrl+C al bot actual.
5. python app.py
