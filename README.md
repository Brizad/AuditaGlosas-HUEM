# AuditaGlosas HUEM

**Sistema de auditoría y control de glosas para el Hospital Universitario Erasmo Meoz en Cúcuta, 2026.**
Proyecto Integrador AR (167410) · Ingeniería de Sistemas · Universidad de Pamplona (sede Villa del Rosario).

**Equipo:** Yarly Melitza Guerrero Berbesi · Einer Arlex Alvear Jaimes · Brayan David Amado Ramírez
**Docente:** Harvey Michael Gamboa Peña

## ¿Qué es?

Una glosa es una objeción que hace la EPS a una factura del hospital: mientras no se resuelva, ese dinero no se paga.
AuditaGlosas revisa cada factura **antes de radicarla** ante la EPS y avisa qué hay que corregir. Para eso compara:

- la **factura** con su **RIPS** en JSON (Resolución 2275 de 2023),
- los **soportes** que la acompañan,
- las **tarifas pactadas** y las **autorizaciones** que exige el contrato con cada EPS,

usando un catálogo de reglas agrupado según las causales del Manual Único de Devoluciones, Glosas y Respuestas
(Resolución 2284 de 2023).

| Regla | Grupo | Qué verifica |
|---|---|---|
| FA-01 | Facturación | El RIPS corresponde a la factura (mismo número) |
| FA-02 | Facturación | El total de la factura es igual a la suma de servicios del RIPS |
| FA-03 | Facturación / codificación | Cada código facturado está en el RIPS y viceversa |
| FA-04 | Facturación / codificación | Los códigos de consultas y procedimientos tienen 6 caracteres válidos |
| TA-01 | Tarifas | El valor unitario es igual a la tarifa pactada con la EPS |
| TA-02 | Tarifas | El servicio tiene tarifa pactada |
| SO-01 | Soportes | Están los soportes obligatorios según el tipo de servicio |
| AU-01 | Autorizaciones | Hay número de autorización cuando la EPS lo exige |

## ¿Qué trae el sistema?

- **Carga de lotes** de facturas con su RIPS, con revisión de la estructura y errores claros en español.
- **Validación antes de radicar**: cada factura queda *apta* o *con inconsistencias*, con su valor en riesgo de glosa.
- **Resultados y detalle** por factura: qué regla se incumple, por qué y cuánto dinero está en riesgo.
- **Reportes** por causal y por EPS, con exportación a CSV (se abre en Excel).
- **Catálogo de reglas** que se activan o desactivan con un interruptor.
- **Contratos y tarifas** de cada EPS editables desde la pantalla.
- **Línea base y piloto**: porcentaje de facturas glosadas por periodo y por causal, y prueba z de diferencia de
  proporciones (alfa = 0,05) para saber si la reducción es estadísticamente significativa.
- **Generador de lotes sintéticos** con errores conocidos, para probar sin datos reales.

![Resultados de un lote](docs/img/03-resultados.png)

## Requisitos

- **Python 3.11 o superior** (se desarrolló y probó con Python 3.12).
- Un navegador actualizado (Edge, Chrome o Firefox).
- No se necesita instalar una base de datos para probarlo: por defecto usa **SQLite** (un archivo local).

## Instalar

En Windows (PowerShell):

```powershell
git clone https://github.com/Brizad/AuditaGlosas-HUEM.git
cd AuditaGlosas-HUEM\backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

En Linux o macOS cambia la activación del entorno: `source .venv/bin/activate`.

## Ejecutar

Siempre desde la carpeta `backend/`, con el entorno virtual activado:

```powershell
python -m scripts.carga_inicial     # solo la primera vez: carga las 3 EPS, el catálogo y el lote demo
uvicorn main:app --reload           # enciende el servidor
```

Abre **http://127.0.0.1:8000** en el navegador. La documentación interactiva de la API está en
**http://127.0.0.1:8000/docs**.

Para empezar de cero (borra todo y vuelve a cargar los datos de ejemplo): `python -m scripts.carga_inicial --reiniciar`.

### Recorrido de demostración (5 minutos)

1. **Resultados** → elegir «Lote de demostración (Sprint 0)» → **Validar antes de radicar**.
   Debe dar **12 facturas, 5 aptas, 7 con inconsistencias y $260.000 en riesgo** (lo mismo que el prototipo).
2. Clic en la factura `FV-1003` para ver qué corregir.
3. **Cargar lote** → subir `data/lote_linea_base_200.json` y después `data/lote_piloto_200.json`.
4. **Línea base** → 40 % contra 15 % de facturas glosadas; la prueba z rechaza H0 (z = 5,60; valor p < 0,001).
5. **Reglas** → apagar SO-01 → volver a Resultados → **Validar de nuevo** para ver el efecto.

El paso a paso para el facturador está en el **[manual de usuario](docs/manual_usuario.md)**.

## Probar

```powershell
cd backend
python -m pytest
```

Son **329 pruebas** automáticas (tardan unos 15 segundos). Usan una base de datos en memoria: no tocan los datos
del sistema. Cubren:

| Archivos | Qué prueban |
|---|---|
| `test_regla_*.py`, `test_reglas_*.py` | Cada regla con casos que pasan y casos que fallan, y sus casos límite |
| `test_motor.py`, `test_catalogo_reglas.py` | El motor, el registro de reglas y el encendido/apagado desde la base de datos |
| `test_lote_demo.py` | El lote demo completo: 12 facturas, 5 aptas, 7 con inconsistencias, $260.000 |
| `test_api_*.py` | Todos los endpoints, incluidos los errores |
| `test_estadistica.py`, `test_api_linea_base.py` | La prueba z contra valores calculados a mano y el indicador de glosas |
| `test_generador.py` | Que el motor detecta exactamente los errores sembrados por el generador |
| `test_paginas.py` | Las páginas web y las cabeceras de seguridad |
| `test_base_datos.py`, `test_errores.py`, `test_arranque_y_scripts.py` | Base de datos, mensajes de error, arranque y scripts |

## Usar PostgreSQL (opcional)

El sistema lee la variable de entorno `DATABASE_URL`. Si no existe, usa SQLite en `backend/auditaglosas.db`.

```powershell
pip install "psycopg[binary]"
$env:DATABASE_URL = "postgresql://usuario:clave@localhost:5432/auditaglosas"
python -m scripts.carga_inicial
uvicorn main:app
```

> El código es el mismo para las dos bases de datos (SQLAlchemy). Hasta ahora las pruebas se han corrido con SQLite;
> la verificación sobre un servidor PostgreSQL real está pendiente.

## Generar lotes sintéticos

```powershell
python -m scripts.generar_lote      # vuelve a crear la línea base y el piloto de data/
python -m scripts.generar_lote --facturas 500 --porcentaje-error 25 --tipo general --periodo 2026-09 --prefijo SEP --semilla 7 --salida ../data/lote_sep.json
```

Cada lote sale con un archivo `..._esperado.json` que dice qué reglas debe disparar cada factura.
La misma semilla produce siempre el mismo lote.

## Datos y privacidad

Todos los datos de `data/` son **sintéticos**: EPS, tarifas, códigos y usuarios inventados. No hay información de
pacientes reales (Ley 1581 de 2012). Además, el sistema **nunca guarda el documento del usuario** que viene en el
RIPS: lo descarta al leer el archivo.

| Archivo | Contenido |
|---|---|
| `data/contratos_tarifas.json` | Tarifas pactadas y autorizaciones de 3 EPS de prueba |
| `data/catalogo_servicios.json` | Descripción y tipo de cada servicio; soportes obligatorios por tipo |
| `data/lote_demo.json` | 12 facturas del Sprint 0 |
| `data/lote_linea_base_200.json` | 200 facturas, 80 con errores sembrados (40 %) |
| `data/lote_piloto_200.json` | 200 facturas, 30 con errores sembrados (15 %) |

## Estructura del repositorio

```
index.html      Prototipo del Sprint 0 (demo en GitHub Pages)
backend/        Servidor en Python: API (FastAPI), motor de reglas, base de datos y pruebas
frontend/       Páginas web (HTML, CSS y JavaScript sin librerías externas)
data/           Datos sintéticos
docs/           Arquitectura, manual de usuario, plan de trabajo y bitácora
```

- **[docs/arquitectura.md](docs/arquitectura.md)**: cómo está hecho el sistema y por qué (con diagramas).
- **[docs/manual_usuario.md](docs/manual_usuario.md)**: paso a paso para quien factura.
- **[docs/plan_de_trabajo.md](docs/plan_de_trabajo.md)** y **[docs/bitacora.md](docs/bitacora.md)**: EDT, hitos y sprints.

## Enlaces

- **Demo del prototipo (Sprint 0):** https://brizad.github.io/AuditaGlosas-HUEM/
- **Tablero del proyecto:** pestaña *Projects* del repositorio · **Hitos H1–H6:** *Issues → Milestones*

## Equipo y forma de trabajo

| Rol | Integrante |
|---|---|
| Product Owner y documentación | Yarly Melitza Guerrero Berbesi |
| Scrum Master | Einer Arlex Alvear Jaimes |
| Líder técnico y calidad | Brayan David Amado Ramírez |
| Developers | Los tres integrantes |

- Sprints de **una semana**; revisión del incremento en la clase semanal.
- Tablero Kanban: **Backlog → Por hacer → En progreso (máx. 3) → En revisión → Hecho**.
- Una rama por historia (`feature/HU-0X-descripcion`) y commits en español (`HU-0X: qué se hizo`).
- **Definición de terminado:** código en GitHub con pull request revisado por otro integrante, pruebas aprobadas,
  criterios de aceptación verificados por el Product Owner, documentación actualizada y bitácora al día.

## Limitaciones conocidas

- Del RIPS se leen consultas, procedimientos y medicamentos (no urgencias, hospitalización ni otros servicios).
- No hay inicio de sesión ni roles: está pensado para usarse en la red interna durante el piloto.
- «Factura glosada» se mide como factura con inconsistencias detectadas, porque aún no se tienen las respuestas
  reales de las EPS. Las cifras reales se pueden digitar en la pantalla de línea base.
- Los resultados son una ayuda para el facturador; no reemplazan la auditoría oficial de cuentas médicas.
