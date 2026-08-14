PLANOS DESDE GITHUB PAGES
=========================

Se agregó envío automático de planos desde:
https://polerogabriel09-gif.github.io/planos-inmobiliaria/

Comportamiento:
- Buenaventura: envía plano general.
- Palmeras: sin fase envía Fase 1 + Fase 2; si especifican fase envía solo esa.
- Vista Hermosa: sin fase envía Fase F + Fase G; si especifican fase envía solo esa.
- Entiende: plano, planos, croquis, mapa de lotes, mapa del proyecto y distribución de lotes.
- Después de CADA solicitud de planos envía la leyenda:
  🟢 Disponible
  🔴 Vendido
  🟣 Reservado por área técnica (no disponible para venta)
  🔵 Apartado por área técnica (será tomado como área verde)
  🟡 Reservado

ACTUALIZACION DIARIA:
Puedes reemplazar los PDF en GitHub conservando exactamente los mismos nombres.
El bot agrega una marca de tiempo a la URL para solicitar la versión más reciente.

Rutas esperadas:
assets/planos/buenaventura.pdf
assets/planos/palmeras-fase-1.pdf
assets/planos/palmeras-fase-2.pdf
assets/planos/vista-hermosa-fase-f.pdf
assets/planos/vista-hermosa-fase-g.pdf
