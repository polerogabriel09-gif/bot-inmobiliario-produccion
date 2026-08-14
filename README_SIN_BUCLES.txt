CORRECCION CRITICA: BUCLE DE RESPUESTAS

CAUSA PROBABLE:
El webhook estaba subiendo fotos/videos y consultando OpenAI ANTES de
responder 200 a Meta. Eso puede tardar. Meta interpreta que el webhook
no respondió a tiempo y vuelve a enviar EL MISMO mensaje.

Resultado:
El bot procesa otra vez el mismo mensaje y parece entrar en bucle.

SOLUCION IMPLEMENTADA:

1. Cada mensaje entrante tiene un message_id de WhatsApp.
2. El bot guarda temporalmente los message_id ya procesados.
3. Si Meta manda otra vez el mismo message_id, se ignora.
4. El webhook responde 200 inmediatamente.
5. OpenAI, cotizaciones, fotos y videos se procesan en un hilo separado.

EN TERMINAL PODRAS VER:
MENSAJE DUPLICADO IGNORADO: wamid....

Eso es normal y significa que la protección está funcionando.

IMPORTANTE:
- Mantiene la memoria de proyecto por número.
- Ubicación sigue usando el proyecto fijo.
- Fotos siguen limitadas.
- Videos siguen limitados.
- Cotizaciones siguen funcionando.

INSTALACION:
1. Conserva tu .env.
2. Reemplaza app.py.
3. Conserva/reemplaza la carpeta media.
4. Ctrl + C
5. python app.py

PRUEBA:
Envía UN solo mensaje:
"Me interesa Palmeras San Miguel"

Espera la respuesta completa antes de mandar el siguiente.

Luego:
"¿Dónde queda?"

Debe responder UNA sola vez.
