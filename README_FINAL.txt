VERSIÓN FINAL - SIN MENSAJES TARDÍOS + GASTOS ADICIONALES

CAMBIO 1: NO ESCRIBIR SI EL CLIENTE NO ESCRIBE
------------------------------------------------
- El bot NO tiene seguimientos automáticos.
- Cada mensaje del cliente crea un procesamiento identificado por message_id.
- Si llega un mensaje nuevo, cualquier respuesta vieja que todavía estuviera
  procesándose queda invalidada.
- Los duplicados de Meta siguen bloqueados por message_id.
- No se programan mensajes para minutos después.

CAMBIO 2: GASTOS ADICIONALES
-----------------------------
Los gastos adicionales SOLO se muestran si el cliente pregunta:
- gastos adicionales
- otros pagos
- mantenimiento
- agua / título de agua
- escrituración

PALMERAS SAN MIGUEL
- Escrituración: Q3,500
- Título de agua: Q3,500
- Mantenimiento: Q50 al mes
- Agua: Q50 por 30,000 litros
- Mantenimiento y agua se cobran cuando el proyecto ya esté urbanizado.

CIUDAD VISTA HERMOSA
- Escrituración: Q3,500
- Título de agua: Q3,500
- Mantenimiento: Q50 al mes
- Agua: Q50 por 30,000 litros
- Mantenimiento y agua se cobran cuando el proyecto ya esté urbanizado.

BUENAVENTURA CUYOTENANGO
- Escrituración 1 lote: Q6,000
- 2 lotes: Q8,400
- 3 lotes: Q10,800
- Cada lote adicional: +Q2,400
- Título de agua: Q4,000
- Mantenimiento: Q100 al mes
- Agua: Q100 por 30,000 litros al mes

INSTALACIÓN
-----------
1. Conserva tu .env.
2. Reemplaza app.py.
3. Mantén la carpeta media.
4. Ctrl + C
5. python app.py
