# Comparación de dos fuentes

Orquestación independiente entre scraper, Clean&Process y presentación. Abrir
`http://127.0.0.1:8787/compare/` después de iniciar:

```powershell
npm run build --prefix src/web
.\.venv\Scripts\python.exe -m uvicorn src.server.main:app --host 127.0.0.1 --port 8787
```

La UI permite capturas consecutivas, importación de dos JSON, historial,
comparación de las cuatro preguntas, fichas con imágenes/reseñas, evidencia y
exportaciones. El botón «Ver ejemplo» usa datos sintéticos identificados; no
captura sitios ni llama a Jev.

## Contrato de llamada

`POST /api/comparisons` devuelve HTTP 202 con identidad y estado versionado:

```json
{
  "contract_version": "1.0",
  "sources": [
    {"url": "https://fuente-a.example/catalogo", "label": "Fuente A"},
    {"url": "https://fuente-b.example/catalogo", "label": "Fuente B"}
  ],
  "limits": {
    "max_pages": 5,
    "max_hops": 2,
    "capture_seconds": 180,
    "processing_seconds": 120
  },
  "interpreter": "declared"
}
```

Orden con dos fuentes: captura A, captura B, procesamiento A, procesamiento B.
También acepta una sola fuente: captura A y procesamiento A, con la misma
presentación, evidencia, historial y exportaciones. El modo «Analizar una URL»
inicia por defecto una visita, cero saltos y 120 segundos por etapa. Las
importaciones siguen requiriendo dos archivos. Límites por fuente/etapa. Captura limitada al host de cada semilla por defecto,
un thread y cero reintentos automáticos. El host no restringe a una categoría.

`POST /api/comparisons/import` acepta `sources: [{label, payload}, {label, payload}]`
y los mismos límites e intérprete. Acepta exportaciones completas del scraper,
entradas contractuales y outputs de Clean&Process. Valida antes de crear el
trabajo. Outputs ya procesados se validan y presentan sin reinterpretación.

`declared` no utiliza modelos. `jev` requiere credenciales en el entorno del
servicio. La captura desactiva la interpretación de campos del scraper y la
delega a Clean&Process; las rutas antiguas mantienen su comportamiento.

## Consulta y control

El estado incluye `stage_timer` con acción (`capture` / `process`), índice de
fuente, instante de inicio y límite en segundos de la etapa actual, junto con
`server_time` para sincronizar la cuenta. El indicador circular cambia de acción
y reinicia su cuenta en cada etapa, incluso entre fuentes. Muestra el tiempo
restante hasta el límite confirmado, no una estimación de trabajo pendiente;
una etapa puede terminar antes. Recargar recupera el inicio guardado. Al finalizar
o cancelar, el contador se detiene. Los análisis históricos sin timer siguen
siendo compatibles y no reciben tiempos inventados.

La interfaz muestra un aviso y reproduce un sonido al alcanzar el primer límite
de tiempo o terminar la ejecución, lo que suceda primero. El aviso se emite una
sola vez por ejecución en la pestaña y no se repite por polling, cambio de etapa
o recarga. Abrir un resultado histórico terminado no dispara avisos. El audio se
habilita con la interacción del usuario al iniciar; si el navegador lo bloquea,
el aviso sigue visible y ofrece «Reproducir aviso sonoro». No solicita permisos
de notificaciones del sistema.

Todas las rutas siguientes están bajo `/api/comparisons`:

| Método / ruta | Función |
|---|---|
| `GET /contract` | Esquemas de solicitud, importación, estado y presentación |
| `GET` | Últimas 50 comparaciones |
| `GET /{id}` | Estado, eventos, archivos y progreso por fuente |
| `POST /{id}/cancel` | Cancelar la etapa activa y evitar las siguientes |
| `GET /{id}/sources/{index}` | Presentación de la fuente 0 o 1 |
| `POST /{id}/sources/{index}/evidence` | Evidencia de hasta 100 `assertion_ids` |
| `GET /{id}/sources/{index}/download/{kind}` | Descargar archivo disponible |

Tipos de descarga: `capture`, `import`, `input`, `output`, `presentation`, `usage`.
No se admiten rutas arbitrarias. El enlace `?comparison=<id>` recupera resultados
guardados después de recargar o reiniciar la API.

## Persistencia y cancelación

Cada comparación tiene su directorio en `data/comparisons/<id>/`. Las capturas
usan auditoría SQLite aislada; no agregan URLs a la cola persistente. Se guardan
originales, entrada, output, presentación, manifiesto y eventos mediante reemplazo
atómico. Los archivos ya disponibles se pueden descargar aunque falle otra etapa.

Cada etapa corre en un proceso aislado. La cancelación/timeout detiene su árbol
de procesos, no la API ni otros trabajos. El worker tiene además un límite de
seguridad si se pierde el supervisor. El cierre normal cancela trabajos activos.
Tras un reinicio, las ejecuciones sin supervisión se marcan interrumpidas y no se
reanudan automáticamente.

Una captura con timeout que conservó contenido puede procesarse como parcial.
Una fuente fallida no impide terminar la otra. Jev conserva un registro por
llamada; si se interrumpe en vuelo, su uso se marca incompleto sin inventar coste.

Ejecutar un solo worker de Uvicorn: el supervisor es local al proceso de API.
No hay cola distribuida ni reanudación automática de etapas interrumpidas.

## Frontera con la presentación

`clean_process.presentation.present()` genera filas de productos y gráficos.
La UI filtra y dibuja; no clasifica opiniones, deduplica productos ni convierte
monedas. No presupone equivalencia de productos entre fuentes. Reseñas textuales
y cantidades publicadas son conjuntos distintos. Puntuaciones sin límites de
escala conocidos no se normalizan.

Los datos ausentes o ambiguos se muestran explícitamente. El intérprete de
Clean&Process sigue siendo textual: no analiza píxeles ni fabrica funciones de
imágenes. El contrato de presentación se exporta con:

```powershell
.\.venv\Scripts\python.exe -m clean_process --write-schemas clean_process/schemas
```

## Verificar

```powershell
$env:TYPESAFE_TEST_MODE='1'
.\.venv\Scripts\python.exe -m pytest tests/test_comparison.py tests/test_clean_process.py tests/test_clean_process_integration.py tests/test_semantic_fields.py tests/test_semantic_strategy.py tests/test_extract_api.py tests/test_scrape_api.py -q
npm run build --prefix src/web
```

Se comprueban orden A/B, cancelación, timeout y fallos parciales, workers reales
de procesamiento, contratos, importaciones, evidencias, descargas y regresiones.

## Recorrido limitado solo por tiempo

En Límites y procesamiento, los cambios permanecen como borrador hasta pulsar
«Confirmar parámetros». Cancelar o cerrar descarta el borrador. El formulario
principal muestra los valores aplicados a la próxima ejecución; las ejecuciones
guardadas o activas no cambian. Cada modo conserva sus límites en la sesión.
Las opciones rápidas permiten una sola página o explorar durante 2 o 5 minutos.
Estas últimas fijan `max_pages: null`, `max_hops: null` y 120 o 300 segundos
de captura, restringida al mismo sitio. El procesamiento tiene un tiempo separado.
No hay corte por líneas de JSON. La captura puede terminar antes
si agota las URLs y expansiones reconocidas. Los límites internos de muestreo
del extractor siguen registrándose en la evidencia de cobertura.

## Reconocimiento de reseñas

Las solicitudes de comparación e importación aceptan `review_recognition`: `e5`
(predeterminado), `lexical` u `off`. El worker de Clean&Process utiliza vocabulario
multilingüe y E5 local, conserva candidatos ambiguos y registra cobertura/fallos.
La pestaña Opiniones muestra sus decisiones. Preparar el modelo según
`clean_process/README.md` antes de ejecutar; la inferencia no descarga pesos.
