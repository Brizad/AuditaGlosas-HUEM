# Arquitectura de AuditaGlosas HUEM

Documento de diseño (hito **H3**). Explica cómo está organizado el sistema, qué hace cada parte y por qué se
tomó cada decisión, en lenguaje sencillo para que cualquier integrante del equipo lo pueda sustentar.

## 1. Idea general

El facturador sube un **lote de facturas** (cada una con su RIPS en JSON). El sistema guarda el lote, le aplica un
**catálogo de reglas** y devuelve, para cada factura, si está **apta para radicar** o qué **hallazgos** tiene, con el
**valor en riesgo de glosa**. Con esos resultados se arman reportes e indicadores.

El sistema tiene tres capas, cada una con una sola responsabilidad:

| Capa | Qué hace | Tecnología |
|---|---|---|
| Frontend | Lo que ve el facturador: páginas, tarjetas, gráficas | HTML + CSS + JavaScript (sin frameworks) |
| Backend | Recibe las peticiones, aplica las reglas, arma los reportes | Python + FastAPI |
| Base de datos | Guarda lotes, facturas, hallazgos, reglas y contratos | SQLite (desarrollo) o PostgreSQL (producción), con SQLAlchemy |

## 2. Estructura de carpetas

```
AuditaGlosas-HUEM/
├── index.html                  Prototipo del Sprint 0 (demo en GitHub Pages; no se modifica)
├── data/                       Datos sintéticos de prueba
│   ├── contratos_tarifas.json      Tarifas pactadas y autorizaciones de 3 EPS
│   ├── catalogo_servicios.json     Descripción y tipo de cada servicio; soportes obligatorios por tipo
│   └── lote_demo.json              12 facturas con su RIPS
├── docs/                       Documentación (plan, bitácora, arquitectura, manual)
├── frontend/                   Páginas web que sirve FastAPI
│   ├── *.html                      Una página por pantalla
│   ├── css/estilos.css             Un solo archivo de estilos
│   └── js/                         comun.js (funciones compartidas) + un archivo por página
└── backend/
    ├── main.py                 Punto de entrada: `uvicorn main:app`
    ├── requirements.txt        Librerías necesarias
    ├── app/
    │   ├── principal.py            Crea la aplicación y conecta todas las piezas
    │   ├── configuracion.py        Rutas de carpetas y variable DATABASE_URL
    │   ├── base_datos.py           Conexión a la base de datos y sesiones
    │   ├── modelos.py              Las tablas (una clase por tabla)
    │   ├── esquemas.py             Forma de los datos que entran y salen por la API
    │   ├── reglas/                 MOTOR DE REGLAS (no conoce la base de datos)
    │   │   ├── base.py                 Clase base de una regla, contexto y hallazgo
    │   │   ├── registro.py             Lista de reglas disponibles
    │   │   ├── facturacion.py          FA-01, FA-02, FA-03, FA-04
    │   │   ├── tarifas.py              TA-01, TA-02
    │   │   ├── soportes.py             SO-01
    │   │   ├── autorizaciones.py       AU-01
    │   │   └── motor.py                Aplica las reglas activas a una factura
    │   ├── servicios/              LÓGICA DE NEGOCIO (une el motor con la base de datos)
    │   │   ├── lotes.py                Guardar un lote
    │   │   ├── carga_inicial.py        Cargar contratos, catálogo y lote demo
    │   │   ├── validacion.py           Validar un lote y guardar los hallazgos
    │   │   ├── catalogo_reglas.py      Activar y desactivar reglas
    │   │   ├── reportes.py             Reportes por causal, por EPS y CSV
    │   │   ├── indicadores.py          Porcentaje de facturas glosadas
    │   │   └── estadistica.py          Prueba z de diferencia de proporciones
    │   └── rutas/                  ENDPOINTS de la API (uno por tema)
    ├── scripts/                Utilidades de consola (carga inicial, generador de lotes)
    └── tests/                  Pruebas automáticas con pytest
```

**Regla de dependencias:** las flechas van en un solo sentido. Las `rutas` llaman a los `servicios`; los
`servicios` usan los `modelos` y el motor de `reglas`; el motor de `reglas` no llama a nadie. Así cada parte se puede
probar por separado.

## 3. Diagrama de componentes

```mermaid
flowchart LR
    U([Facturador]) --> FE

    subgraph FE [Frontend · navegador]
        P[Páginas HTML]
        JS[JavaScript · fetch]
        P --- JS
    end

    JS -- "JSON por HTTP" --> R

    subgraph BE [Backend · FastAPI]
        R[Rutas /api]
        E[Esquemas Pydantic<br/>validan la estructura]
        S[Servicios<br/>lotes · validación · reportes · indicadores]
        M[Motor de reglas<br/>FA · TA · SO · AU]
        O[Modelos SQLAlchemy]
        R --> E
        R --> S
        S --> M
        S --> O
    end

    O --> BD[(Base de datos<br/>SQLite o PostgreSQL)]
    D[/data/*.json<br/>datos sintéticos/] -. carga inicial .-> S
```

**Recorrido de una validación:**

1. El facturador elige un archivo JSON en la página *Cargar lote*.
2. La ruta `POST /api/lotes` recibe el JSON. Los **esquemas** revisan que tenga la estructura correcta; si no, se
   responde con la lista de errores en español.
3. El servicio de **lotes** guarda el lote, sus facturas, ítems, servicios del RIPS y soportes.
4. Con `POST /api/lotes/{id}/validar`, el servicio de **validación** arma un *contexto* por cada factura
   (factura + contrato de su EPS + catálogo) y se lo entrega al **motor**.
5. El motor ejecuta cada regla **activa** y devuelve los hallazgos. El servicio los guarda y marca la factura como
   *apta* o *con inconsistencias*.
6. Las páginas de resultados y reportes consultan lo guardado.

## 4. Modelo entidad-relación

```mermaid
erDiagram
    EPS ||--o{ TARIFAS : pacta
    EPS ||--o{ AUTORIZACIONES_REQUERIDAS : exige
    EPS ||--o{ FACTURAS : recibe
    LOTES ||--o{ FACTURAS : agrupa
    FACTURAS ||--o{ ITEMS_FACTURA : cobra
    FACTURAS ||--o{ SERVICIOS_RIPS : reporta
    FACTURAS ||--o{ SOPORTES_FACTURA : adjunta
    FACTURAS ||--o{ HALLAZGOS : tiene
    REGLAS ||--o{ HALLAZGOS : genera

    EPS {
        int id PK
        string codigo UK "EPS-ALFA"
        string nombre
        bool activa
    }
    TARIFAS {
        int id PK
        int eps_id FK
        string codigo_servicio "CUPS o medicamento"
        decimal valor "tarifa pactada"
    }
    AUTORIZACIONES_REQUERIDAS {
        int id PK
        int eps_id FK
        string codigo_servicio
    }
    SERVICIOS_CATALOGO {
        string codigo PK
        string descripcion
        string tipo "consulta, laboratorio, imagen, medicamento"
    }
    SOPORTES_REQUERIDOS {
        int id PK
        string tipo_servicio
        string nombre_soporte
    }
    REGLAS {
        string codigo PK "FA-01"
        string nombre
        string grupo "FA, TA, SO, AU"
        string descripcion
        bool activa
    }
    LOTES {
        int id PK
        string nombre
        string tipo "general, linea_base, piloto"
        string periodo "AAAA-MM"
        string estado "cargado, validado"
        datetime fecha_carga
        datetime fecha_validacion
    }
    FACTURAS {
        int id PK
        int lote_id FK
        int eps_id FK
        string num_factura
        date fecha_expedicion
        decimal valor_total
        string rips_num_factura "numero que trae el RIPS"
        string estado "sin_validar, apta, con_inconsistencias"
        decimal valor_en_riesgo
    }
    ITEMS_FACTURA {
        int id PK
        int factura_id FK
        string codigo
        decimal cantidad
        decimal valor_unitario
    }
    SERVICIOS_RIPS {
        int id PK
        int factura_id FK
        string clase "consulta, procedimiento, medicamento"
        string codigo
        decimal cantidad
        decimal valor_unitario
        decimal valor_servicio
        string num_autorizacion
        int indice_usuario "posicion del usuario en el RIPS"
    }
    SOPORTES_FACTURA {
        int id PK
        int factura_id FK
        string nombre
    }
    HALLAZGOS {
        int id PK
        int factura_id FK
        string regla_codigo FK
        string grupo
        string titulo
        string detalle
        decimal valor_en_riesgo
    }
```

**Notas del modelo**

- **No hay tabla de pacientes.** El RIPS trae el documento del usuario, pero el sistema lo **descarta al cargar**
  (Ley 1581 de 2012). Solo se guarda `indice_usuario`: "este servicio es del primer usuario del RIPS".
- **Servicios del RIPS en una sola tabla.** Consultas, procedimientos y medicamentos comparten casi todas las
  columnas; la columna `clase` dice cuál es. Así las reglas recorren una sola lista.
- `SERVICIOS_CATALOGO` y `SOPORTES_REQUERIDOS` no tienen llaves foráneas a propósito: una factura puede traer un
  código que no existe en el catálogo, y eso no debe impedir cargarla (lo debe detectar una regla).
- Una misma factura puede estar en dos lotes distintos (por ejemplo, antes y después de corregirla), pero no dos
  veces en el mismo lote.
- El dinero se guarda con dos decimales (`Numeric(14,2)`).

## 5. Diseño del motor de reglas

### 5.1 Cada regla es una clase

Todas las reglas heredan de `ReglaBase` y tienen los mismos cuatro datos y un método:

```python
@registrar
class ReglaSoporteObligatorio(ReglaBase):
    codigo = "SO-01"
    nombre = "Soporte obligatorio faltante"
    grupo = "SO"                      # grupo de causal de la Res. 2284 de 2023
    descripcion = "La factura incluye los soportes obligatorios según el tipo de servicio."

    def evaluar(self, contexto):      # devuelve una lista de hallazgos (vacía si todo está bien)
        ...
```

### 5.2 El contexto

Una regla **no consulta la base de datos**. Recibe un `ContextoFactura` con todo lo que necesita ya listo:

| Dato del contexto | De dónde sale |
|---|---|
| Número, valor total, ítems y soportes de la factura | Tablas `facturas`, `items_factura`, `soportes_factura` |
| Número de factura que trae el RIPS y servicios prestados | `facturas.rips_num_factura`, `servicios_rips` |
| Tarifas pactadas y códigos que exigen autorización | `tarifas`, `autorizaciones_requeridas` de la EPS de la factura |
| Descripción y tipo de cada servicio, soportes por tipo | `servicios_catalogo`, `soportes_requeridos` |

Ventaja: para probar una regla basta con armar un contexto a mano; no hace falta base de datos.

### 5.3 El hallazgo y el valor en riesgo

Cada regla devuelve hallazgos con: código de la regla, grupo, título, detalle en español y **valor en riesgo**.

| Regla | Grupo | Cuándo genera hallazgo | Valor en riesgo |
|---|---|---|---|
| FA-01 | Facturación | El número de factura del RIPS es distinto al de la factura | Valor total de la factura (causa devolución) |
| FA-02 | Facturación | El total de la factura no es igual a la suma de servicios del RIPS | La diferencia |
| FA-03 | Facturación | Un código está en la factura y no en el RIPS, o al revés | Valor del ítem o del servicio |
| FA-04 | Facturación | Una consulta o procedimiento no tiene código de 6 caracteres válidos | Valor del servicio |
| TA-01 | Tarifas | El valor unitario es distinto a la tarifa pactada | Diferencia × cantidad |
| TA-02 | Tarifas | El servicio no tiene tarifa pactada con la EPS | Valor del servicio |
| SO-01 | Soportes | Falta un soporte obligatorio para el tipo de servicio | Valor del servicio |
| AU-01 | Autorizaciones | La EPS exige autorización y el servicio no la trae | Valor del servicio |

El **valor en riesgo de la factura** es la suma de sus hallazgos, pero nunca mayor al valor total de la factura
(no se puede glosar más de lo facturado). Las comparaciones de dinero aceptan una diferencia de hasta $0,50 por
redondeos.

### 5.4 El registro

`registro.py` guarda un diccionario `codigo → regla`. El decorador `@registrar` mete la regla ahí cuando Python
carga el archivo. **Para agregar una regla nueva** basta con:

1. Escribir una clase nueva que herede de `ReglaBase` y ponerle `@registrar`.
2. Reiniciar el servidor: al arrancar, `sincronizar_reglas()` la crea en la tabla `reglas` como activa.

No hay que tocar el motor ni la API.

### 5.5 Activar y desactivar

La tabla `reglas` tiene la columna `activa`. Antes de validar un lote, el servicio lee qué códigos están activos y
se los pasa al motor; el motor salta las demás. Como cada validación borra los hallazgos anteriores del lote y los
vuelve a calcular, basta desactivar una regla y **validar de nuevo** para ver el efecto.

```mermaid
flowchart TD
    A[validar_lote] --> B[Leer reglas activas de la tabla]
    A --> C[Por cada factura: armar ContextoFactura]
    B --> D
    C --> D[motor.validar_factura]
    D --> E{Por cada regla registrada}
    E -- inactiva --> E
    E -- activa --> F[regla.evaluar]
    F --> G[Lista de hallazgos]
    G --> H[Valor en riesgo = menor entre suma y total]
    H --> I[Guardar hallazgos y estado de la factura]
```

## 6. Endpoints de la API

Todos empiezan por `/api`. La documentación interactiva se genera sola en **`/docs`**.

| Método | Ruta | Qué hace | Historia |
|---|---|---|---|
| GET | `/api/salud` | Confirma que el servidor está vivo | — |
| POST | `/api/lotes` | Carga un lote en JSON (valida la estructura) | HU-01 |
| GET | `/api/lotes` | Lista los lotes cargados | HU-01 |
| GET | `/api/lotes/{id}` | Datos de un lote | HU-01 |
| DELETE | `/api/lotes/{id}` | Elimina un lote con sus facturas y hallazgos | HU-01 |
| POST | `/api/lotes/{id}/validar` | Aplica las reglas activas al lote | HU-02, 03, 04 |
| GET | `/api/lotes/{id}/resultados` | Resumen del lote y estado de cada factura | HU-05 |
| GET | `/api/facturas/{id}` | Detalle de una factura con sus hallazgos | HU-05 |
| GET | `/api/reportes/por-causal` | Hallazgos y valor en riesgo por grupo de causal y por regla | HU-05 |
| GET | `/api/reportes/por-eps` | Facturas, inconsistencias y valor en riesgo por EPS | HU-05 |
| GET | `/api/reportes/exportar.csv` | Descarga el reporte de hallazgos en CSV | HU-05 |
| GET | `/api/reglas` | Catálogo de reglas | HU-06 |
| POST | `/api/reglas/{codigo}/activar` | Activa una regla | HU-06 |
| POST | `/api/reglas/{codigo}/desactivar` | Desactiva una regla | HU-06 |
| GET, POST | `/api/eps` | Lista o crea EPS | HU-04 |
| GET, PUT, DELETE | `/api/eps/{codigo}` | Consulta, edita o elimina una EPS | HU-04 |
| GET, POST | `/api/eps/{codigo}/tarifas` | Lista o crea tarifas pactadas | HU-04 |
| PUT, DELETE | `/api/eps/{codigo}/tarifas/{codigo_servicio}` | Edita o elimina una tarifa | HU-04 |
| GET, POST | `/api/eps/{codigo}/autorizaciones` | Lista o agrega servicios que exigen autorización | HU-02 |
| DELETE | `/api/eps/{codigo}/autorizaciones/{codigo_servicio}` | Quita la exigencia de autorización | HU-02 |
| GET | `/api/indicadores` | Indicadores generales para la página de inicio | HU-05 |
| GET | `/api/indicadores/glosas` | Porcentaje de facturas glosadas por periodo y por causal | HU-07 |
| POST | `/api/indicadores/prueba-z` | Prueba z de diferencia de proporciones (línea base vs. piloto) | HU-07 |

Los reportes aceptan filtros opcionales por lote (`lote_id`) y por periodo (`periodo=AAAA-MM`).

## 7. Decisiones de diseño y por qué

| Decisión | Motivo |
|---|---|
| Reglas como clases independientes con registro | Cumple HU-06: agregar o apagar una regla sin tocar el resto |
| El motor no conoce la base de datos | Se prueba con datos armados a mano; las pruebas son rápidas y claras |
| SQLAlchemy con `DATABASE_URL` | El mismo código corre en SQLite (desarrollo) y PostgreSQL (producción) |
| No guardar el documento del paciente | Ley 1581 de 2012: el sistema no necesita identificar al paciente para validar |
| Frontend sin frameworks ni librerías externas | Funciona sin internet en el hospital y el equipo puede explicar cada línea |
| Errores de estructura vs. hallazgos | Un archivo mal formado se **rechaza** al cargar; una factura con un dato incorrecto se **carga** y la regla lo reporta |
| Revalidar borra y recalcula los hallazgos | El resultado siempre corresponde a las reglas activas en ese momento |

## 8. Limitaciones conocidas y trabajo futuro

- Del RIPS se leen **consultas, procedimientos y medicamentos**. Urgencias, hospitalización, recién nacidos y otros
  servicios (Res. 2275 de 2023) quedan para una siguiente versión.
- No hay inicio de sesión ni roles todavía.
- Las tablas se crean automáticamente al arrancar. Cuando el modelo cambie con datos reales en producción convendrá
  usar migraciones (Alembic).
- "Factura glosada" se mide como *factura con inconsistencias detectadas por el sistema*, porque aún no se reciben
  las respuestas reales de las EPS.
