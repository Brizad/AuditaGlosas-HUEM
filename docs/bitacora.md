# Bitácora de sprints

| Sprint | Fechas | Objetivo | Resultado | Impedimentos | Responsable |
|---|---|---|---|---|---|
| Sprint 0 | 2 – 8 nov. 2026 | Plan de trabajo y prueba de concepto del motor de reglas | EDT, hitos, cronograma con ruta crítica, metodología y roles en el documento de trabajo de grado; prototipo con 8 reglas validado con lote sintético de 12 facturas (5 aptas, 7 con inconsistencias, $260.000 en riesgo); derecho de petición enviado al HUEM (7 nov. 2026); repositorio y tablero creados (8 nov. 2026) | Sin datos reales del HUEM todavía (en término de respuesta, 10 días hábiles) | Equipo |
| Sprint 1 | 9 – 16 nov. 2026 *(fechas por confirmar)* | Pasar del prototipo al sistema completo: backend en Python, base de datos, motor de reglas, API, interfaz web, indicadores y pruebas (HU-01 a HU-08) | Arquitectura documentada con diagramas (`docs/arquitectura.md`); base de datos con SQLAlchemy (SQLite, y PostgreSQL por `DATABASE_URL`); motor con las 8 reglas como clases que se activan o desactivan desde la base de datos; API en FastAPI documentada en `/docs`; interfaz web de 8 pantallas; indicador de facturas glosadas y prueba z (alfa = 0,05); generador de lotes sintéticos (línea base de 200 facturas con 40 % de error y piloto con 15 %); 329 pruebas automáticas aprobadas; el lote demo da lo mismo que el prototipo (12 facturas, 5 aptas, 7 con inconsistencias, $260.000 en riesgo); README y manual de usuario. Código en 9 ramas con pull requests #9 a #17 **abiertos, pendientes de revisión** (nada unido a `main` todavía) | Sin datos reales del HUEM: todo se probó con datos sintéticos y «factura glosada» se mide como factura con inconsistencias detectadas. PostgreSQL configurado pero sin probar en un servidor real. Faltan la revisión de los PR por otro integrante y la verificación de los criterios de aceptación por la Product Owner *(impedimentos por confirmar con el equipo)* | Brayan Amado (desarrollo, con apoyo de Claude Code) · revisión de PR: pendiente |

## Retrospectiva Sprint 0
- **Qué funcionó:** prototipo temprano para reducir el riesgo técnico (lectura del RIPS en JSON).
- **Qué mejorar:** repartir mejor la carga entre integrantes (se niveló en la Tabla XIX del documento).
- **Acción:** dailies asíncronas por chat dos veces por semana.

## Retrospectiva Sprint 1
*(Pendiente: la escribe el equipo en la revisión del sprint. Abajo quedan solo los hechos verificables en el repositorio.)*

- **Hechos:** el lote demo produce el mismo resultado que el prototipo; el motor detecta exactamente los errores
  sembrados por el generador en 5 lotes de 300 facturas (sin falsos positivos ni negativos); la prueba z se comprobó
  contra un ejemplo calculado a mano (45/100 contra 30/100 → z = 2,19).
- **Pendiente para cumplir la definición de terminado:** revisión de los pull requests #9 a #17 por otro integrante,
  verificación de criterios de aceptación por la Product Owner y prueba sobre PostgreSQL.
- **Qué funcionó / qué mejorar / acción:** *(por completar)*
