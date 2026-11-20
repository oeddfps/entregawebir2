# Frontend

## Inicio rápido desde un clon nuevo

Requiere Git, Python 3.11+ y Node.js 22+. Esta instalación utiliza el repositorio
independiente de pruebas. Desde PowerShell:

```powershell
git clone https://github.com/oeddfps/entregawebir2.git
cd entregawebir2
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium
npm.cmd ci --prefix src/web
$env:PYTHON = (Resolve-Path .\.venv\Scripts\python.exe).Path
npm.cmd run dev --prefix src/web
```

Abrir `http://localhost:3000/compare/` o el puerto que indique Next.js.
Mantener la terminal abierta: el comando inicia frontend, API y motor.
Los puertos 3000 y 8787 deben estar disponibles. Si ya existe una API,
consultar la opción `dev:next` en **Desarrollo y build**.

Pulsar **Ver ejemplo** para comprobar la interfaz con datos de demostración:
no captura sitios externos ni necesita Jev. Para probar la captura real,
introducir dos URL públicas y elegir **Configuración avanzada → Solo esta
página**, con interpretación **Datos estructurados**. Revisar estados y
diagnósticos de ambas fuentes; no todas las páginas publican los mismos campos.
Para interpretar texto con Jev, seguir **Configurar Jev desde la interfaz**.

No hace falta copiar un `.env` para esta comprobación inicial. Credenciales,
historial y datos de otra instalación no se incluyen en el clon. En Linux/macOS,
crear el entorno con `python3 -m venv .venv`, usar `.venv/bin/python` y `npm`
en lugar de `npm.cmd`, y exportar `PYTHON` con la ruta absoluta del entorno.
Los pasos posteriores de build y pruebas se describen más abajo.

## Stack y estructura

El frontend vive en `src/web` y usa Next.js 16, React 19 y CSS global. No usa Tailwind.
Las versiones fijadas son Next.js **16.3.8**, React/React DOM **19.3.0** y Geist
`^1.9.2`; `package-lock.json` conserva la resolución reproducible. El código es
JavaScript/JSX: no hay `tsconfig.json`, tipos TypeScript ni un comando de
typecheck independiente. La validación HTTP se realiza con Pydantic en Python.

- `app/page.jsx`: portal Scrapper.
- `app/compare/page.jsx`: aplicación Clean&Process para análisis y comparación.
- `app/layout.jsx`: layout raíz, fuentes Geist y tema inicial.
- `app/globals.css`: marco visual del Scrapper y tema global.
- `app/compare/comparison.css`: estilos de la comparación.
- `app/compare/brand-intelligence.css`: estilos de inteligencia de marcas.
- `components/control-room.jsx`: navegación, extracción y monitor del motor.
- `components/comparison.jsx`: orquestación de análisis y comparación.
- `components/theme-toggle.jsx`: alternancia persistente de tema.
- `components/jev-credentials.jsx`: control de credencial dentro del modal; la clave se comparte entre los servicios del servidor.
- `components/processing-settings.jsx`: límites y modo de interpretación.
- `components/comparison-charts.jsx`, `brand-competitiveness.jsx`, `contract-results.jsx`: presentaciones derivadas de los resultados contractuales.
- `components/brand-gallery.jsx`: agrupación de productos por marca, conservando fuente, variantes y moneda.
- `components/stage-timer.jsx`, `completion-notification.jsx`, `completion-alerts.mjs`: tiempo por etapa y aviso de finalización.
- `lib/contract-view.mjs`, `brand-competitiveness.mjs`: lectura de respuestas contractuales y métricas de marcas.
- `scripts/dev.mjs`: procesos locales de Next.js, API y worker persistente.
- `next.config.mjs`: exportación estática y proxy `/api` exclusivo de desarrollo.

`lib/api.js`, `lib/commercial.js`, `lib/schema.js`, `components/shared.jsx` y
`components/page-result.jsx` no forman parte del grafo de importaciones de las
dos rutas actuales. Se conservan por compatibilidad; no son la fuente de verdad
del transporte HTTP activo. `ControlRoom` y `Comparison` tienen sus propios
clientes `fetch`.

El backend está en `src/server/main.py`, `src/persistent/api.py` y
`src/comparison/api.py`. La captura vive en `src/common/scrapper`, la cola en
`src/persistent`, el adaptador en `src/integrations/clean_process.py` y los
contratos/proyecciones de interpretación en `clean_process`. Los datos locales
se guardan bajo `data/`, fuera de Git.

## Rutas

- `/`: centro de operaciones Scrapper.
- `/?view=...`: navegación interna del portal mediante el parámetro `view`.
- `/compare/`: comparación de dos fuentes o análisis de una URL.
- `/compare/?mode=single`: modo de una sola fuente.
- `/compare/?comparison=<id>`: reabre una comparación persistida.

Las rutas siguen el estado con URL/`popstate`; no requieren una navegación SPA externa.

### Parámetros de navegación

| Ruta/contexto | Parámetro | Significado |
| --- | --- | --- |
| `/` | `view` | `dashboard` (predeterminado), `extract`, `active`, `seeds`, `settings`, `activities`, `failures` o `suspects`. |
| `/` | `activity` | ID de actividad; abre su detalle en lugar de la sección. |
| Detalle de actividad | `visit` | ID de captura seleccionado dentro de sus resultados. |
| `/?view=extract` | `extract_job`, `extract_run` | Job temporal y recorrido persistido; guardar `extract_run` permite recuperar resultados tras reiniciar la API. |
| `/?view=activities` o `failures` | `page`, `status` | Página desde 1 y filtro de estado; `failures` usa `error` por defecto. |
| `/?view=seeds` | `page`, `edit`, `origin` | Página del listado; `edit=new` crea un origen, `edit=<id>` lo edita y `origin=<id>` muestra sus páginas. Evitar combinar `edit` y `origin`. |
| Páginas de un origen/dominio | `q`, `page_status`, `items_page` | Búsqueda, estado y paginación desde 1 de las páginas. |
| `/?view=suspects` | `domain` | Dominio seleccionado para mostrar sus páginas. |
| `/compare/` | `mode=single` | Formulario de una fuente; sin ese valor se abre la comparación de dos fuentes. |
| `/compare/` | `comparison` | ID persistido. Sus fuentes y su origen importado determinan el modo mostrado al cargarlo. |

Ejemplos: `/?view=seeds&edit=new`, `/?view=activities&page=2&status=error`
y `/compare/?comparison=<id>`. Los ID pertenecen a la instalación que sirve
la página: copiar el enlace no copia los resultados a otro servidor.
Pestañas, búsqueda de productos, archivos JSON elegidos y borradores de
parámetros de comparación viven en React, no se restauran mediante la URL.
El portal usa `pushState`; la comparación usa `replaceState` para cambiar
modo/ID. Ambos escuchan `popstate` para sincronizarse con el historial.

## Tema

El tema activo se guarda en `html.dataset.theme` y en `html.classList.dark`.

- `light`: tema claro.
- `dark`: tema oscuro.
- Preferencia inicial: `localStorage["scrapper-theme"]`; si no existe, `prefers-color-scheme`.

`layout.jsx` aplica el tema antes de pintar para evitar flash claro. `ThemeToggle` persiste la selección, actualiza ambos indicadores y escucha cambios del sistema, almacenamiento y preferencia mientras no exista una elección guardada.

Los tokens compartidos están definidos en `globals.css`: `--background`, `--foreground`, `--card`, `--input`, `--border`, `--muted`, `--primary`, `--surface`, `--control-border` y `--line`. Los bloques claros usan fondos neutros `#f2f4f7` / `#ffffff`; los oscuros usan `#09090b` / `#18181b`.

## Scrapper

`ControlRoom` refresca datos de `/api/service/dashboard` cada dos segundos y mantiene las secciones:

- **Análisis:** métricas generales y actividad reciente.
- **Extraer:** inicia una captura aislada.
- **Actividad:** slots, tareas activas, páginas/hora, cola, RAM y CPU.
- **Dominios y páginas:** alta y configuración de orígenes.
- **Configuración:** límites globales y por actividad.
- **Historial:** todas las extracciones.
- **Fallidas:** reintentos y errores.
- **Dominios marcados:** revisiones por comportamiento sospechoso.

La tabla móvil reemplaza la tabla de slots según el breakpoint. Los estados de carga y error deben conservar el botón de reintento disponible.

## Comparación

`Comparison` admite tres modos:

1. Captura de dos URLs.
2. Análisis de una URL.
3. Importación de dos JSON compatibles.

El estado inicial no muestra gráficos ni paneles vacíos. Presenta una orientación compacta hasta que exista una comparación o resultado.

La pantalla inicia operaciones con POST y consulta el estado cada **1300 ms**
hasta un estado terminal. Solo pide cada presentación cuando
`sources[index].result_available` es verdadero:

- `POST /api/comparisons`
- `POST /api/comparisons/import`
- `POST /api/comparisons/example`
- `GET /api/comparisons` (historial, hasta 50 operaciones)
- `GET /api/comparisons/contract` (esquemas JSON)
- `GET /api/comparisons/<id>`
- `GET /api/comparisons/<id>/sources/<index>`
- `POST /api/comparisons/<id>/sources/<index>/evidence`
- `GET /api/comparisons/<id>/sources/<index>/download/<kind>`
- `POST /api/comparisons/<id>/cancel`

Las pestañas de resultados son:

- Resumen
- Marcas
- Precios
- Imágenes
- Términos
- Opiniones

Los resultados contractuales se muestran sin inferir equivalencias no respaldadas. La evidencia abre en un panel lateral y las exportaciones siguen disponibles desde “Fuentes, diagnósticos y exportaciones”.

## Estados e interacción

- Los cuadros vacíos deben explicar la acción necesaria, no parecer errores.
- Las operaciones largas muestran progreso por fuente y permiten cancelar.
- Los errores HTTP preservan el detalle informado por la API cuando existe.
- Los diálogos bloquean el fondo, cierran con Escape y devuelven el foco al abrir/cerrar.
- Los botones y campos deben usar tokens semánticos, no blancos fijos en modo oscuro.
- Las respuestas pequeñas usan controles sin desbordamiento horizontal.

### Timer y avisos de finalización

`StageTimer` muestra el presupuesto de la **etapa y fuente actuales**, no una
estimación de duración total. Lee `stage_timer.action`, `source_index`,
`started_at` y `limit_seconds`; cada captura y procesamiento tiene su contador.
Los tiempos se fijan al iniciar la operación: editar el borrador del modal no
cambia un trabajo en ejecución.

El reloj visual se actualiza cada 250 ms y se ancla a `server_time` para
compensar la diferencia con el reloj local. Los estados llegan por polling.
Llegar a cero indica límite alcanzado; el servidor cierra la etapa, conserva
la evidencia y puede continuar con otra fuente o con el procesamiento. No
significa que toda la comparación haya terminado. Un estado terminal muestra
cero restante; los trabajos históricos sin timer siguen siendo legibles sin
mostrar un contador final.

`CompletionWatcher` entrega como máximo un aviso automático por comparación:
el primer timeout observado o su finalización. Un aviso por timeout impide
repetirlo al terminar otras etapas. Abrir un resultado histórico ya terminado
no avisa; una operación nueva se registra explícitamente, incluso si termina
antes del primer polling. Los ID avisados se guardan en
`sessionStorage["clean-process:completion-notifications"]` para evitar duplicados
al recargar esa sesión. No existe coordinación entre pestañas y bloquear ese
almacenamiento impide garantizar la persistencia de esta deduplicación.

El aviso visible permite **Ver resultados**, cerrarlo y, si no sonó,
**Reproducir aviso sonoro**. Web Audio requiere interacción del usuario y está
sujeto a las restricciones del navegador. No son notificaciones del sistema:
cerrar la página impide recibir avisos y una pestaña suspendida puede
retrasarlos. El estado del backend y los resultados guardados son la referencia
para confirmar la finalización.

## Desarrollo y build

Requiere Python **3.11+**, Node.js **22+**, las dependencias de
`requirements.txt` y Chromium de Playwright **1.63.0**. Desde la raíz en Windows:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium
npm.cmd ci --prefix src/web
$env:PYTHON = (Resolve-Path .\.venv\Scripts\python.exe).Path
npm.cmd run dev --prefix src/web
```

Si el lanzador `py` no detecta Python, ejecutar el `python.exe` instalado por su
ruta absoluta para crear el entorno. Después usar el ejecutable de `.venv`
explícitamente como en los comandos anteriores.

`scripts/dev.mjs` inicia Next.js (normalmente puerto 3000), FastAPI en
`http://127.0.0.1:8787` y el worker persistente. Usa `PYTHON` o, por defecto,
`py` en Windows y `python3` en otros sistemas. No instala dependencias.
El motor conserva `/proc`, PSS y grupos de procesos en Linux. En Windows usa
`psutil>=7.2,<8` para identificar procesos, pausar/reanudar, cancelar árboles y
medir USS (memoria privada residente). Las pruebas de cola y navegadores pueden
ejecutarse en Windows con stores aislados. Los límites de CPU mediante systemd
y las unidades de despliegue siguen siendo específicos de Linux.

Para usar una API que ya está ejecutándose, iniciar **solo Next.js**:

```powershell
$env:BACKEND_URL = 'http://127.0.0.1:8788'
npm.cmd run dev:next --prefix src/web
```

`npm run dev` siempre arranca además su propia API local en 8787; cambiar
`BACKEND_URL` solo cambia el destino del proxy, no ese puerto de escucha.

Build de producción, desde la raíz:

```powershell
npm.cmd run build --prefix src/web
```

Next.js exporta `/` y `/compare/` a `src/web/out`; FastAPI sirve ese directorio,
`/_next` y `/compare-assets` en el mismo origen que `/api`. El build estático no
contiene rewrites ni requiere `next start`. Para servirlo localmente:

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.server.main:app --host 127.0.0.1 --port 8787
```

En producción `python -m src.server` exige una IPv4 de Tailscale y escucha en
8787. El worker se ejecuta por separado con `python -m src.persistent.worker`;
las unidades Linux están en `deploy/`. Sin exportar el portal, sus rutas HTML
responden 503 con instrucciones de compilación.

## Configuración del entorno

El ejemplo versionado es [`.env.example`](../.env.example). No hay secretos
necesarios en el navegador ni variables `NEXT_PUBLIC_*` obligatorias.

| Variable | Consumidor y origen |
| --- | --- |
| `TYPESAFE_API_KEY` | Solo servidor. Prioridad: ambiente, clave guardada por interfaz y `.env` raíz. Sin clave, la extracción estructural sigue funcionando; una comparación con `interpreter: "jev"` se rechaza con 422 y solicita configurar el panel Jev. |
| `TYPESAFE_TEST_MODE`, `TYPESAFE_TEST_API_KEY` | Pruebas: el modo `1` usa únicamente la clave de pruebas, sin recurrir a la de producción. `tests/conftest.py` activa ese modo y puede leer `.env.test`. |
| `BACKEND_URL` | Proxy de Next.js en desarrollo; predeterminado `http://127.0.0.1:8787`. Se configura en el ambiente o en los archivos de entorno de `src/web`. |
| `PYTHON` | Ejecutable de `scripts/dev.mjs`; configurar en el ambiente antes de arrancarlo. |
| `PLAYWRIGHT_BROWSERS_PATH` | Ubicación de los navegadores. El lanzador de desarrollo reconoce también `E:\playwright-browsers` en Windows. |
| `SCRAPER_DATABASE_URL` | Conexión PostgreSQL del backend; ambiente o `/etc/scraper/database.env`. En desarrollo sin DSN, stores locales SQLite. |
| `SCRAPER_TEST_DSN` | Exclusivo de pruebas PostgreSQL, contra una base desechable: las pruebas vacían tablas. |
| `SCRAPER_BROWSER_ENDPOINT`, `SCRAPER_BROWSER_TOKEN`, `SCRAPER_DIRECT_PLAYWRIGHT` | Transporte privado del pool de navegadores; lo asigna el motor. No se envía al frontend. |
| `SCRAPER_DESKTOP_PROFILE`, `SCRAPER_BROWSER_STORAGE_STATE` | Opciones del capturador para perfil y estado de navegador. El estado puede contener datos privados; no se versiona. |

El `.env` raíz no es un cargador genérico para Python ni para el script Node:
su lector Python solo resuelve `TYPESAFE_API_KEY`. Exportar explícitamente las
demás variables. No introducir claves reales en `.env.example`, Git o bundles.

### Configurar Jev desde la interfaz

En `/compare/`, abrir **Configuración avanzada** y elegir **Jev · interpretar
texto libre**. El panel muestra el campo **Clave API de Jev**: pegar la clave y
pulsar **Guardar clave Jev** o Enter. El campo es de contraseña y se vacía después
de guardar. El modal permanece abierto y conserva los límites y la interpretación;
solo **Confirmar parámetros** aplica el borrador. Las siguientes extracciones
del Scrapper leen la misma clave del servidor.

El editor de credencial usa un grupo sin `<form>` propio ni un campo `required`
que interfiera con el formulario externo. Enter se limita a guardar una clave
no vacía; no confirma ni cierra el modal. Los límites numéricos conservan su
validación HTML, incluso después de guardar la credencial.

La API guarda la credencial en `data/secrets/jev.json`, fuera de Git, mediante
reemplazo atómico. El archivo tiene permisos 0600 al crearse en Unix; en Windows
se aplican los permisos del directorio del servicio. No se almacena en
`localStorage`/`sessionStorage` ni se devuelve desde la API. Es una configuración
de la instalación privada, compartida por sus usuarios y procesos. La lectura
es dinámica: no hace falta reiniciar API o workers. Las operaciones ya iniciadas
conservan el modo que eligieron al comenzar.

`GET /api/service/credentials/jev` devuelve solo `{configured, source, editable}`.
`PUT` en la misma ruta recibe `{"api_key": "..."}`, `Content-Type:
application/json` y `X-Jev-Configuration: 1`. Rechaza solicitudes cross-site,
cuerpos mayores a 8192 bytes y claves vacías, con espacios/controles o mayores
a 4096 caracteres, sin reflejar el valor enviado en errores. La credencial
administrada mediante el entorno tiene prioridad y no se reemplaza por esta UI
(409). En modo de pruebas sigue aislada de cualquier clave de producción.

Guardar no hace una llamada facturable ni certifica la validez ante TypeSafe:
esa validez se comprueba al usar Jev. Una clave inválida se puede reemplazar
abriendo el mismo panel. Errores de almacenamiento se presentan como 503.

## Contratos y flujos HTTP

Todas las peticiones de UI son relativas al mismo origen. La API valida entradas
y responde JSON; los archivos de evidencia y descarga usan su tipo de contenido.
OpenAPI está en `/openapi.json` y Swagger en `/api/docs`.

### Comparación y análisis

`POST /api/comparisons` acepta una o dos fuentes y responde **202** con el
estado completo; no devuelve `job_id`. Ejemplo de análisis de una fuente:

```json
{
  "contract_version": "1.0",
  "sources": [{"url": "https://example.org/catalog", "label": "Fuente A"}],
  "limits": {
    "max_pages": 1,
    "max_hops": 0,
    "same_host_only": true,
    "capture_seconds": 120,
    "processing_seconds": 120
  },
  "interpreter": "declared",
  "review_recognition": "e5"
}
```

`max_pages`: 1–100 o `null`; `max_hops`: 0–8 o `null`; ambos tiempos: enteros
5–600 segundos. `null` significa sin límite de visitas/saltos, manteniendo el
límite de tiempo. `label` admite hasta 120 caracteres. Las URL deben ser HTTP(S),
sin credenciales. Campos desconocidos se rechazan. `interpreter` es `declared`
o `jev`; `review_recognition` es `off`, `lexical` o `e5` (predeterminado).
La UI utiliza E5 por defecto y no envía una opción distinta; E5 solo busca su
modelo local, con reconocimiento léxico si no está disponible.

La captura A precede a B; después se procesa cada fuente. Una sola fuente no
crea una fuente B. La importación exige exactamente dos objetos `{label,
payload}` compatibles con Input, Output o JSON del scraper. La UI limita cada
archivo importado a 20 MiB; no es una cuota HTTP aplicada por el backend.

El estado incluye `comparison_id`, `contract_version`, `status`, `phase`,
`sources`, `events`, `stage_timer` y `server_time`. Estados terminales: `done`,
`partial`, `failed`, `cancelled`, `interrupted`; estados de trabajo: `queued`,
`running`. Cada fuente conserva sus estados de captura y procesamiento,
`result_available`, `artifacts`, progreso y `diagnostics`. Cada diagnóstico de
etapa incluye `stage` (`capture`/`process`), `code`, `message` y un `http_status`
opcional. La cancelación conserva resultados
disponibles. Un reinicio marca las operaciones desprendidas como `interrupted`.

#### Ejemplo de respuesta de estado

Ejemplo ilustrativo completo de `GET /api/comparisons/<id>` durante una captura.
El POST devuelve el mismo contrato, aunque puede haber avanzado al responder.
ID, fechas y progreso varían; los campos opcionales pueden ser `null`.

```json
{
  "contract_version": "1.0",
  "comparison_id": "0123456789abcdef0123456789abcdef",
  "status": "running",
  "phase": "capture_0",
  "created_at": "2026-11-20T12:00:00+00:00",
  "finished_at": null,
  "imported": false,
  "synthetic": false,
  "stage_timer": {
    "action": "capture",
    "source_index": 0,
    "started_at": "2026-11-20T12:00:01+00:00",
    "limit_seconds": 120
  },
  "server_time": "2026-11-20T12:00:02+00:00",
  "sources": [{
    "url": "https://example.org/catalog",
    "label": "Fuente A",
    "status": "capturing",
    "capture_status": "running",
    "processing_status": "queued",
    "stop_reason": null,
    "processing_stop_reason": null,
    "started_at": "2026-11-20T12:00:01+00:00",
    "capture_finished_at": null,
    "finished_at": null,
    "progress": {},
    "result_available": false,
    "diagnostics": [],
    "artifacts": []
  }],
  "events": [{"at": "2026-11-20T12:00:00+00:00", "message": "Análisis creado."}]
}
```

Ejemplo de un elemento de `sources[].diagnostics` para una fuente fallida
(no es una respuesta completa):

```json
{
  "stage": "capture",
  "code": "http_error",
  "message": "La fuente respondió HTTP 404. Comprueba que sea pública y esté disponible.",
  "http_status": 404
}
```

`synthetic: true` identifica el ejemplo de demostración. El historial responde
`{"items": [...]}`; `/api/comparisons/contract` publica los esquemas de solicitud
de comparación, importación, estado y presentación (`request`, `import`,
`state`, `presentation`).

`GET /<id>/sources/<index>` devuelve `Presentation`, definido en
`clean_process/presentation.py`: `questions`, `products`, `charts`, `issues`,
`summary`, `findings`, etc. El Output completo descargable usa `data.question_results`.
Los lectores contractuales admiten ambas envolturas; los gráficos no deben
inventar una escala, equivalencia de productos o mezcla de monedas.
Los importes contractuales son cadenas decimales. Ver el
[contrato detallado de las consultas](contratos/CONTRATO_BACKEND_FRONTEND_ITER1.md)
y [la operación de comparación](../src/comparison/README.md).

La evidencia se solicita por **POST** con `{"assertion_ids": ["..."]}` (máximo
100 IDs) y devuelve `{assertions, evidence}`. Las descargas admiten `capture`,
`import`, `input`, `output`, `presentation`, `usage`, únicamente si existen.

### Extracción puntual e historial

`POST /api/extract` recibe solo `{"url": "https://example.org/page"}` y devuelve
202 con `{job_id}`. El servidor fija una visita, cero saltos y un thread.
La UI consulta `GET /api/scrapes/jobs/<job_id>` cada 1500 ms, recupera su `run_id`
y lee `GET /api/scrapes/<run_id>` y `/visits/<visit_id>`. `extract_run` en la URL
permite recuperar el resultado persistido aunque el job en memoria ya responda
404. `GET /api/scrapes` devuelve una lista directa, sin envoltura `items`.

Por ejemplo, el POST responde:

```json
{"job_id": "abcdef0123456789abcdef0123456789"}
```

Y `GET /api/scrapes/jobs/<job_id>` puede responder inicialmente:

```json
{
  "status": "running",
  "message": "Preparando recorrido",
  "run_id": null,
  "scheduled": 0,
  "succeeded": 0,
  "failed": 0,
  "doubtful": 0,
  "content_events": 0
}
```

Al avanzar aparece `run_id`; al terminar se añade `summary`. El estado `done`
del job significa recorrido terminado, no éxito de todas las visitas: comprobar
también `failed`, el resumen y `visit.error`. Los errores de visita permanecen
en la auditoría al reabrir un resultado histórico.

Las capturas están en `/api/scrapes/<run_id>/visits/<visit_id>/screenshot`,
`/html?clean=true` y `/actions/<index>/<before|after>/<html|screenshot>`.
`POST /api/scrapes` sigue disponible para recorridos con `url`/`urls`, límites
y reglas, aunque la pantalla Extraer utiliza el endpoint aislado. Los endpoints
retirados de análisis/clasificación responden 410.

### Motor persistente

Prefijo `/api/service`. La paginación usa `page` desde 1, 20 filas y una
envoltura con `items`, `page`, `page_size`, `total` en los listados paginados.

| Métodos y rutas | Uso/contrato |
| --- | --- |
| `GET /dashboard`, `GET/PUT /settings` | Estado agregado y modelo `Settings` de `src/persistent/store.py`. |
| `GET/POST /seeds`, `GET/PUT/DELETE /seeds/<id>` | Listado, alta (201), detalle, edición y eliminación de un origen. Modelo `Seed`. |
| `POST /seeds/<id>/pause`, `/start` | Pausa o inicio (202); iniciar puede dejar trabajo en cola si el motor global está desactivado. |
| `DELETE /seeds/<id>/history` | Elimina historial exclusivo y conserva datos compartidos; puede devolver `file_errors`. |
| `GET /seeds/<id>/pages`, `/urls`, `/checks` | Páginas paginadas, URL conocidas y controles del origen. |
| `POST /rules/validate`, `/rules/test` | `{kind: "domain"|"regex", value}` y `{pattern, urls}`; el test devuelve `{results}`. |
| `GET /activities`, `/activities/<id>` | Historial paginado y actividad con visitas, costos y referencias. Filtros `status`, `domain`. |
| `POST /activities/<id>/retry`, `/pages/<id>/rescrape` | Responde 202 con `{activity_id}`. Reintento inválido: 409. |
| `GET /domains`, `GET /pages?domain=...` | Dominios y páginas filtrables por `query`, `page`, `status`. |
| `POST /domains/action` | `{domain, approved_limit}`; `approved_limit` es 2–1000000 o `null`. |
| `POST /engine/restart` | Solicita iniciar el worker y devuelve `{started, message}`. |
| `GET/POST /subscribers`, `GET /contents`, `GET /subscribers/<id>/contents` | API adicional sin pantalla dedicada; requiere PostgreSQL (503 sin DSN). |

`Settings` rechaza campos extra: `enabled`, `threads` (1–50), `attempts` (1–10),
`freshness_hours` (1–8760), `retry_delay` (1–86400), `memory_mb` (256–262144),
`activity_memory_mb` (128–262144), `cpu_percent` (1–10000), `suspicious_pages`
(2–1000000) y `strategy: "semantic"`. La UI envía números, no cadenas.

`Seed` contiene `url`, `enabled`, `rule_mode` (`white`/`black`), `max_pages`
(entero positivo o `null`), `max_urls_per_minute` (1–60000 o `null`) y las listas
`allowed_domains`, `blocked_domains`, `allowed_url_patterns`,
`blocked_url_patterns` (hasta 100 reglas por lista). Los dominios delimitan el
alcance; la UI conserva `allowed_domains` también en modo negro y envía solo
las regex del modo elegido. No convertir un campo opcional vacío a cero.

### Errores

FastAPI usa `{detail: string}` o `detail: [{loc, msg, type, ...}]` para 422.
Las pantallas convierten estos detalles en mensajes legibles; respuestas no JSON
también deben producir un error visible. Códigos relevantes: 400 para una acción
inválida, 404 para identidades/evidencias ausentes, 409 para conflictos de estado
o dos comparaciones activas, 422 para validación y 503 para indisponibilidad.
La extracción puntual limita a dos recorridos simultáneos y usa 503 al excederlos.

Las fallas asíncronas de captura/procesamiento aparecen en `sources[].diagnostics`,
visibles por fuente en la pantalla y en el panel de diagnósticos. Incluyen acceso
de red denegado, DNS, certificados HTTPS, conexión, navegación agotada, navegador
no disponible y HTTP 4xx/5xx. Los mensajes públicos no contienen el traceback,
rutas locales ni parámetros de la URL. Las comparaciones históricas fallidas
pueden recuperar la causa desde su auditoría guardada.

Si todas las URL fallan con `ERR_NETWORK_ACCESS_DENIED`, comprobar el entorno
desde el que se inició el servicio: puede permitir localhost y restringir la red
externa. Iniciar API y worker desde un entorno con acceso de red autorizado. No
es un problema de selectores del dominio; no requiere desactivar validación TLS
ni reglas del extractor. Una URL con login, HTTP de error o fuente inaccesible
conserva su error explícito; el resultado de otra fuente disponible se mantiene.

## Pruebas

Desde la raíz, después de compilar:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_next_portal.py tests/test_comparison.py tests/test_comparison_portal.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_jev_credentials.py tests/test_comparison_capture.py tests/test_process_control.py -q
node --test tests/test_contract_view.mjs tests/test_brand_competitiveness.mjs tests/test_completion_alerts.mjs
npm.cmd run build --prefix src/web
```

`test_next_portal.py` usa Chromium con FastAPI y SQLite aislados para navegación,
formularios, errores y extracción. `test_comparison_portal.py` comprueba la UI
exportada contra la API real aislada, con captura/procesamiento sustituidos por
fixtures: una/dos fuentes, evidencia POST, recarga, sincronización `popstate` e
importación JSON válida/inválida con el mensaje 422 del backend.
`test_comparison.py` valida contratos, límites, cancelación, persistencia e
importación mediante workers. Los `.mjs` usan el runner nativo de Node.

`test_jev_credentials.py` verifica guardado y reemplazo con claves ficticias,
precedencia, aislamiento y errores que no revelan secretos, sin llamar al
proveedor. `test_comparison_portal.py` incluye guardar por clic/Enter sin cerrar
el modal ni perder parámetros, validación y diagnósticos por fuente.
`test_comparison_capture.py` ejecuta workers, Chromium, servidor HTTP local y
procesamiento reales: dos URL correctas y un HTTP 404 que conserva la otra
fuente, además de privacidad de los diagnósticos y recuperación de auditoría.
`test_process_control.py` usa procesos reales para verificar el aislamiento
por actividad/store y la terminación de descendientes. Estos casos no necesitan
tráfico hacia sitios públicos ni consumo de Jev. Los avisos y su deduplicación
se verifican en `test_completion_alerts.mjs`.

Si pytest falla al preparar temporales con `PermissionError`, repetir con
`--basetemp` apuntando a una **carpeta nueva y exclusiva** en almacenamiento
local rápido y escribible. Pytest puede borrar el contenido de ese directorio;
no utilizar una carpeta con datos que deban conservarse. No modificar los
límites de los tests para compensar problemas de permisos o disco.

La suite general es `python -m pytest -q`. Las pruebas PostgreSQL se omiten sin
`SCRAPER_TEST_DSN`; no sustituirlo por el DSN de producción. Las pruebas de pool,
memoria y terminación del motor usan controles nativos de cada plataforma,
manteniendo los mismos criterios de aislamiento y concurrencia. Usar temporales
del sistema para la suite: un `--basetemp` en almacenamiento lento puede agotar
los plazos de sincronización sin indicar un defecto del extractor. Las pruebas vivas en
`tests/live_*.py` son recorridos independientes, con acceso externo y posible
consumo Jev; no son parte de la validación aislada descrita aquí.

`package.json` solo define `dev`, `dev:next` y `build`: **no hay comandos lint ni
typecheck dedicados**. `next build` comprueba la compilación de imports y JSX,
pero no equivale a ESLint ni a tipado estático de los payloads JavaScript.
No declarar esos checks como aprobados si no existen.
