# AuditaGlosas HUEM — Prototipo (Sprint 0)

Prueba de concepto del proyecto **«Sistema de auditoría y control de glosas para el Hospital Universitario Erasmo Meoz en Cúcuta, 2026»** — Proyecto Integrador AR (167410), Ingeniería de Sistemas, Universidad de Pamplona (sede Villa del Rosario).

**Equipo:** Yarly Melitza Guerrero Berbesi · Einer Arlex Alvear Jaimes · Brayan David Amado Ramírez
**Docente:** Harvey Michael Gamboa Peña

## Enlaces
- **Demo en línea:** https://brizad.github.io/AuditaGlosas-HUEM/
- **Tablero del proyecto (GitHub Projects):** ver la pestaña *Projects* del repositorio
- **Hitos H1–H6:** ver *Issues → Milestones*

## Equipo y roles (Scrum adaptado + Kanban)
| Rol | Integrante |
|---|---|
| Product Owner y documentación | Yarly Melitza Guerrero Berbesi |
| Scrum Master | Einer Arlex Alvear Jaimes |
| Líder técnico y calidad | Brayan David Amado Ramírez |
| Developers | Los tres integrantes |

## ¿Qué hace?
Valida cada factura **antes de radicarla** ante la EPS, comparándola con su RIPS (estructura en JSON de la Resolución 2275 de 2023) y con el contrato de tarifas de la EPS. Aplica un catálogo de reglas configurable, agrupado según los grupos de causales del Manual Único de Devoluciones, Glosas y Respuestas (Resolución 2284 de 2023):

| Regla | Grupo | Verifica |
|---|---|---|
| FA-01 | Facturación | El RIPS corresponde a la factura |
| FA-02 | Facturación | Total de la factura = suma de servicios del RIPS |
| FA-03 | Facturación / codificación | Cada código facturado está en el RIPS y viceversa |
| FA-04 | Facturación / codificación | Formato válido de códigos (6 caracteres) |
| TA-01 | Tarifas | Valor unitario = tarifa pactada con la EPS |
| TA-02 | Tarifas | El servicio tiene tarifa pactada |
| SO-01 | Soportes | Soportes obligatorios según el tipo de servicio |
| AU-01 | Autorizaciones | Número de autorización cuando la EPS lo exige |

## Cómo usarlo
1. Abrir `index.html` en el navegador (funciona sin internet).
2. **Cargar lote de demostración** → **Validar antes de radicar**.
3. Hacer clic en una factura para ver sus hallazgos. En *Catálogo de reglas* se pueden activar o desactivar reglas.
4. *Cargar archivo JSON* permite probar con otro lote (ver `data/lote_demo.json`).

## Datos
Todos los datos son **sintéticos** (`data/`): EPS, tarifas, códigos y usuarios ilustrativos. No contiene información de pacientes reales (Ley 1581 de 2012).

## Mapeo con la EDT
- 4.1 Incremento 1 (soportes): SO-01, AU-01 y carga de facturas/RIPS.
- 4.2 Incremento 2 (codificación): FA-01 a FA-04.
- 4.3 Incremento 3 (tarifas y reportes): TA-01, TA-02 y reporte CSV.

## Flujo de trabajo
- Sprints de **una semana**; revisión del incremento en la clase semanal.
- Tablero Kanban: **Backlog → Por hacer → En progreso (máx. 3) → En revisión → Hecho**.
- Cada paquete de trabajo de la EDT es un *issue* (historia de usuario o entregable) con su milestone H1–H6.
- **Definición de terminado:** código en GitHub con pull request revisado por otro integrante, casos de prueba aprobados, criterios de aceptación verificados por el Product Owner, documentación actualizada y bitácora al día.

## Estructura
```
index.html            Prototipo (una sola página, funciona sin conexión)
data/                 Lote de facturas y contratos de tarifas sintéticos
docs/bitacora.md      Bitácora de sprints
docs/plan_de_trabajo.md  EDT, hitos y cronograma resumidos
```

## Estado
Prototipo del Sprint 0 (prueba de concepto). Próximos sprints: backend en Python, base de datos PostgreSQL, carga de soportes y reglas parametrizables por contrato.
