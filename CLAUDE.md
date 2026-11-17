# AuditaGlosas HUEM — contexto del proyecto para Claude

## Qué es
Sistema de auditoría y control de glosas para el **Hospital Universitario Erasmo Meoz (HUEM)**, Cúcuta.
Valida cada factura **antes de radicarla** ante la EPS, comparándola con su **RIPS en JSON** (Res. 2275 de 2023),
sus **soportes** y las **tarifas pactadas con cada EPS**, según las causales del Manual Único de
Devoluciones, Glosas y Respuestas (**Res. 2284 de 2023**).

Proyecto Integrador AR (167410) · Ingeniería de Sistemas · Universidad de Pamplona.
Equipo: Yarly Guerrero (Product Owner), Einer Alvear (Scrum Master), Brayan Amado (líder técnico y calidad).
Docente: Harvey Michael Gamboa Peña.

## Estado actual (Sprint 1: sistema completo en pull requests #9 a #17, pendientes de revisión)
- `backend/`: FastAPI + SQLAlchemy (SQLite por defecto, PostgreSQL con `DATABASE_URL`). Se ejecuta desde `backend/`:
  `python -m scripts.carga_inicial` · `uvicorn main:app --reload` · `python -m pytest` (359 pruebas).
  - `app/reglas/`: motor de reglas. Cada regla es una clase con `@registrar`; no consulta la base de datos.
  - `app/servicios/`: lotes, validación, reportes, indicadores y prueba z. `app/rutas/`: endpoints de `/api`.
  - `scripts/generar_lote.py`: lotes sintéticos con errores conocidos (semilla fija).
- `frontend/`: 8 páginas en HTML + CSS + JavaScript sin librerías externas, servidas por FastAPI. Los datos nunca se
  escriben con `innerHTML` (función `h()` de `js/comun.js`) y el servidor envía una CSP estricta: nada de estilos ni
  scripts en línea.
- `docs/arquitectura.md` (diseño y diagramas) y `docs/manual_usuario.md`.
- El documento del paciente que viene en el RIPS **no se guarda**: los esquemas de entrada lo descartan.
- `index.html` de la raíz: prototipo del Sprint 0 (demo en GitHub Pages; no se modifica). Tiene 8 reglas:
  - FA-01 RIPS corresponde a la factura · FA-02 total = suma del RIPS · FA-03 códigos factura↔RIPS · FA-04 formato de código
  - TA-01 valor = tarifa pactada · TA-02 servicio con tarifa pactada
  - SO-01 soporte obligatorio según tipo de servicio · AU-01 autorización cuando la EPS la exige
- `data/lote_demo.json`: 12 facturas sintéticas con estructura RIPS. `data/contratos_tarifas.json`: tarifas de 3 EPS de prueba.
- `docs/plan_de_trabajo.md` (EDT, hitos H1–H6) y `docs/bitacora.md`.
- Issues HU-01 a HU-08 con milestones H1–H6 y tablero Kanban en GitHub Projects.

## Stack objetivo (versión final)
- Backend: **Python** (FastAPI) · Base de datos: **PostgreSQL** · Frontend web sencillo.
- Software libre. Datos de pacientes **nunca** se guardan (Ley 1581 de 2012): solo datos sintéticos o agregados.

## Incrementos (ciclo de vida iterativo e incremental, sprints de 1 semana)
1. Incremento 1 (sem. 6–7): carga de facturas y RIPS (HU-01) + validador de soportes y autorizaciones (HU-02).
2. Incremento 2 (sem. 7–8): validador de codificación factura↔RIPS (HU-03).
3. Incremento 3 (sem. 8–10): validador de tarifas (HU-04) + reportes por causal y por EPS (HU-05).
- Catálogo de reglas configurable (HU-06). Línea base y piloto (HU-07). Manual (HU-08).

## Forma de trabajar
- Una rama por historia: `feature/HU-0X-descripcion`. Commits en español: `HU-0X: qué se hizo`.
- Pull request revisado por otro integrante antes de unir a `main`.
- Definición de terminado: código en GitHub con PR revisado, pruebas pasan, criterio de aceptación verificado, README/manual actualizado, bitácora al día.
- Explica el código en español sencillo: el equipo debe poder sustentarlo.
