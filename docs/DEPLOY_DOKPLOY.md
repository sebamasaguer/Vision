# Deploy en Dokploy (Docker Compose)

Este proyecto es multi-servicio (Redis, MinIO, backend API, 3 workers y
frontend, más una base **Postgres remota externa** — no corre en este
compose) con dependencias y healthchecks entre ellos. La forma correcta de
llevarlo a Dokploy es como **una sola app de tipo "Compose"**, no como
Dockerfiles sueltos — así se conservan los `depends_on`/`healthcheck` tal como
están pensados.

Archivo de compose para producción: **`compose.dokploy.yaml`** (en la raíz del
repo). No es el mismo que `compose.yaml` (ese queda para desarrollo local) —
las diferencias están comentadas al principio del archivo y resumidas más
abajo en "Qué se cambió y por qué".

## 0. Antes de nada: subir el código a GitHub

El repo ya tiene el remoto configurado:

```
git remote -v
# origin  https://github.com/sebamasaguer/Vision.git
```

Pero todavía no hay ningún commit. Con `.gitignore` y `.env.example` ya
creados (nunca se commitea el `.env` real):

```bash
git add -A
git commit -m "Initial commit: HYS Vision v1.1.0"
git push -u origin main
```

Confirmame si querés que yo corra este `git add/commit/push`, o lo hacés vos.
Es la única parte que toca un servicio externo (GitHub), por eso prefiero que
lo decidas explícitamente — sobre todo revisá antes si el repo en GitHub es
privado o público.

## 1. Crear el proyecto en Dokploy

1. Dokploy → **Create Project** → dentro del proyecto, **Create Service** →
   **Compose**.
2. En **General**, conectá el repo de GitHub (`sebamasaguer/Vision`), rama
   `main`, y en **Compose Path** poné `compose.dokploy.yaml` (no el default
   `docker-compose.yml`).
3. Activá **Auto Deploy** si querés que cada push a `main` redeploye solo
   (Dokploy te da un webhook para esto).

## 2. Variables de entorno

En la pestaña **Environment** de la app, pegá el contenido de `.env.example`
con los valores reales (dominios reales, contraseñas fuertes generadas, no las
de ejemplo). Dokploy guarda esto como el `.env` que `env_file: .env` lee en
`compose.dokploy.yaml`.

Puntos que **tenés que cambiar sí o sí** antes de deployar (no dejar el valor
de ejemplo):

- `DATABASE_URL` → string de conexión completo a tu Postgres de **producción,
  remota** (no corre en este compose). Formato psycopg:
  `postgresql+psycopg://usuario:password@host:5432/nombre_db?sslmode=require`
  (sacá `?sslmode=require` solo si tu proveedor no lo exige). El servidor
  donde corre Dokploy tiene que poder alcanzar ese host:puerto — revisá
  firewall/allowlist de IP del lado del proveedor de la base **antes** de
  deployar, o el backend no va a levantar.
- `MINIO_SECRET_KEY`, `JWT_SECRET`, `BOOTSTRAP_ADMIN_PASSWORD` → generar
  valores random fuertes.
- `BOOTSTRAP_ADMIN_EMAIL` → el mail real del admin inicial (el bootstrap es
  idempotente: si esa base ya tiene datos de producción, no duplica nada, solo
  crea lo que falte).
- `CORS_ORIGINS` → el dominio público del frontend, en formato JSON:
  `["https://app.tudominio.com"]`. El backend usa `allow_credentials=True`,
  así que no acepta `"*"` como origen.
- `VITE_API_BASE_URL` → dominio público del backend + `/api/v1`, por ejemplo
  `https://api.tudominio.com/api/v1`. **Ojo**: esto se hornea en el build del
  frontend (es Vite, corre en el navegador del usuario), así que si cambiás el
  dominio del backend después, hay que rebuildear el frontend, no solo
  reiniciarlo.

`REDIS_URL` y `MINIO_ENDPOINT` **no van en el `.env`**: ya están fijados en
`compose.dokploy.yaml` apuntando a los nombres de servicio internos (`redis`,
`minio`). No los agregues en Dokploy o vas a pisar el valor correcto.

> **Antes del primer deploy**: hacé un backup de esa base remota. El backend
> corre `alembic upgrade head` al arrancar (ver paso 4), y eso va a aplicar
> sobre esa base todas las migraciones que le falten. Si la base no está en
> la revisión que este código espera, conviene probar primero contra una
> copia/staging antes de apuntar el `.env` de Dokploy a la base real.

## 3. Dominios (Domains)

Este stack necesita **dos dominios públicos**, cada uno con HTTPS (Dokploy te
da Let's Encrypt automático):

| Servicio   | Puerto interno | Dominio sugerido           |
|------------|-----------------|-----------------------------|
| `frontend` | 80              | `app.tudominio.com`        |
| `backend`  | 8000            | `api.tudominio.com`        |

Redis, MinIO y los 3 workers **no necesitan dominio ni puerto público** (la
base Postgres tampoco corre acá, es remota y externa) — el backend sirve la
evidencia (fotos/video de eventos) proxificada
desde MinIO a través de su propia API (`/events/evidence/{id}/content`), así
que MinIO nunca se expone a Internet.

Pasos (Dokploy ≥ 0.7, [docs oficiales](https://docs.dokploy.com/docs/core/docker-compose/domains)):
en la app → pestaña **Domains** → **Add Domain** → elegís el servicio
(`frontend` o `backend`), el puerto interno (80 u 8000) y el dominio. Dokploy
agrega las labels de Traefik solo, no hace falta tocar el compose.

Antes de esto, apuntá los DNS de `app.tudominio.com` y `api.tudominio.com` al
IP del servidor.

## 4. Deploy

Con env vars y dominios listos: botón **Deploy**. Dokploy clona el repo, hace
`docker compose build` + `up -d` sobre `compose.dokploy.yaml`. El backend corre
`alembic upgrade head` y `python -m app.bootstrap` antes de levantar uvicorn,
así que la primera vez deja la base de datos migrada y el usuario admin creado
con `BOOTSTRAP_ADMIN_EMAIL`/`BOOTSTRAP_ADMIN_PASSWORD`.

Mirá los logs de cada servicio desde la pestaña **Logs**; los healthchecks
deberían ponerse en verde en orden: `redis`/`minio` → `backend` →
`camera-worker` → `vision-engine` → `alert-worker` → `frontend`. Si `backend`
no levanta, lo primero a revisar en sus logs es la conexión a `DATABASE_URL`
(host/puerto alcanzable, credenciales, SSL).

## 5. (Opcional) Cargar el modelo bootstrap y datasets existentes

`compose.dokploy.yaml` usa **volúmenes nombrados** para `models`, `datasets` y
`reports` (en vez de bind mounts al repo clonado) — es necesario porque
Dokploy re-clona el repo en cada deploy y borraría cualquier bind mount a esas
carpetas, perdiendo lo que la app haya escrito ahí en producción (datasets
subidos, modelos entrenados/promovidos, reportes generados).

Efecto práctico: arrancan **vacíos** en el primer deploy. Si querés que el
modelo bootstrap Intel (`models/bootstrap/intel-worker-safety/`, ~20MB, hoy en
tu repo local) esté disponible desde el día uno para SHADOW, subilo una vez
por SSH al volumen ya creado:

```bash
# server donde corre Dokploy
docker cp models/bootstrap <container_id_o_nombre_backend>:/opt/hys-models/bootstrap
```

(reemplazá `models/bootstrap` por la ruta local si corrés esto desde tu
máquina vía `scp` + `docker cp` en el server, o copialo directo si tenés el
repo clonado ahí). Los `datasets/` de trabajo que tenés localmente
(`HYS-PPE-20260904`, `HYS-PPE-REAL`) no se migran automáticamente — decidí si
los necesitás en producción o si arrancás con datasets nuevos.

## Qué se cambió respecto al compose.yaml local, y por qué

- **Sin `ports:` en ningún servicio**: la exposición pública la maneja Dokploy
  vía Traefik + la pestaña Domains, no bindeos de puerto en el host. Evita
  choques de puertos con otras apps en el mismo VPS y exposición sin HTTPS.
- **Sin servicio `postgres`**: la base es remota y externa (ya tiene datos de
  producción), no corre como contenedor acá. El backend y los 3 workers se
  conectan directo con `DATABASE_URL` desde el `.env`. `compose.yaml` (uso
  local) sí sigue trayendo Postgres en contenedor, para no depender de la base
  remota en desarrollo.
- **`datasets/`, `reports/`, `models/` → volúmenes nombrados** en vez de bind
  mounts `./datasets`, `./reports`, `./models`: sobreviven a los redeploys
  (ver punto 5).
- **`demo/` sigue como bind mount** del repo: es contenido de referencia
  estático (videos de demo), no algo que la app escriba en runtime, así que
  no hay pérdida de datos al redeployar.
- **`REDIS_URL`/`MINIO_ENDPOINT` fijos en el compose**, no en `.env`: son
  internos a la topología de servicios (Redis y MinIO sí corren acá) y no
  deberían poder desincronizarse por un typo en las env vars de Dokploy.
  `DATABASE_URL` en cambio sí va en el `.env`, porque apunta a un host externo
  que solo vos conocés.
- **Se quitó `container_name`** en cada servicio: nombres fijos pueden chocar
  si alguna vez corrés dos deploys de este proyecto en el mismo Docker host;
  Dokploy nombra los contenedores solo.
- **Se quitó el servicio `trainer`**: necesita GPU y corre solo bajo el
  profile `training`; no aplica a un deploy web en un VPS de Dokploy.

Fuentes: [Dokploy — Docker Compose](https://docs.dokploy.com/docs/core/docker-compose),
[Dokploy — Domains](https://docs.dokploy.com/docs/core/docker-compose/domains),
[Dokploy — Environment Variables](https://docs.dokploy.com/docs/core/variables).
