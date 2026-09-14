# Landing page en vision.saltia.com.ar (app movida a /admin) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que `vision.saltia.com.ar` sirva la landing de marketing (proyecto `VISION.IA`) en la raíz, y que la app actual (dashboard operativo) pase a `vision.saltia.com.ar/admin/`, todo desde el mismo servicio Docker `frontend` que ya está deployado y funcionando.

**Architecture:** Un Dockerfile multi-stage: build de `landing/` (nuevo, copiado de `VISION.IA`) → `nginx html root`; build de `frontend/` (la app existente, con `base: '/admin/'` agregado) → `nginx html root/admin`. nginx resuelve por path (`/admin/` vs `/`). El servicio `frontend` en `compose.dokploy.yaml` conserva nombre, posición, redes y `depends_on` — solo cambia su `build.context`/`dockerfile`/`args`. No se toca Dokploy Domains, DNS, `backend`, `apivision.saltia.com.ar`, CORS, ni las redes (`hysvision_internal`/`dokploy-network`).

**Tech Stack:** React 18 + Vite (ambos proyectos), Tailwind + Framer Motion + EmailJS (landing), TypeScript (app), nginx 1.27-alpine, Docker multi-stage build.

**Spec:** `docs/superpowers/specs/2026-09-14-landing-page-design.md`

## Global Constraints

- El servicio `frontend` en `compose.dokploy.yaml` mantiene exactamente su nombre, posición en `services:`, `networks: [hysvision_internal, dokploy-network]` y `depends_on` — no reordenar ni renombrar (riesgo conocido: Dokploy cruzó labels de Traefik entre servicios la última vez que cambió la forma del compose).
- No se toca `backend`, `apivision.saltia.com.ar`, `CORS_ORIGINS`, `VITE_API_BASE_URL`, ni ninguna entrada de Dokploy → Domains/DNS.
- La app (`frontend/`) no usa ningún router (`react-router` no está instalado) — mover su base a `/admin/` no requiere `basename` ni cambios de navegación, solo el `base` de Vite.
- `landing/vite.config.js` mantiene `base` por defecto (`/`) — la landing vive en la raíz.
- Credenciales reales de EmailJS quedan fuera de alcance (el usuario no las tiene todavía) — se dejan como placeholders vacíos en `.env.example`.

---

### Task 1: Copiar el código de la landing a `Vision/landing/`

**Files:**
- Create: `Vision/landing/` (árbol completo copiado de `/home/seba/Escritorio/workspace/VISION.IA`, sin `.git`, sin `node_modules`)

**Interfaces:**
- Produces: `Vision/landing/package.json` (scripts `dev`/`build`/`preview`, `npm run build` genera `Vision/landing/dist/index.html` + `Vision/landing/dist/assets/*.{js,css}`), `Vision/landing/src/App.jsx` como entry point, `Vision/landing/src/components/Navbar.jsx` (consumido por Task 4).

- [ ] **Step 1: Confirmar que `Vision/landing/` no existe todavía**

Run: `ls /home/seba/Escritorio/workspace/Vision/landing 2>&1`
Expected: `No such file or directory`

- [ ] **Step 2: Copiar el árbol de archivos, excluyendo `.git` y `node_modules`**

```bash
mkdir -p /home/seba/Escritorio/workspace/Vision/landing
rsync -a \
  --exclude='.git' \
  --exclude='node_modules' \
  /home/seba/Escritorio/workspace/VISION.IA/ \
  /home/seba/Escritorio/workspace/Vision/landing/
```

- [ ] **Step 3: Verificar que copió lo esperado**

Run: `ls /home/seba/Escritorio/workspace/Vision/landing`
Expected: salida incluye `package.json`, `index.html`, `src`, `vite.config.js`, `tailwind.config.js`, `postcss.config.js`, `.env.example`, `README.md` — **no** incluye `.git` ni `node_modules`.

- [ ] **Step 4: Build local de verificación**

```bash
cd /home/seba/Escritorio/workspace/Vision/landing
npm install --no-audit --no-fund
npm run build
```

Expected: termina sin error, y `ls dist/` muestra `index.html` y una carpeta `assets/` con archivos `.js`/`.css`.

- [ ] **Step 5: Commit**

```bash
cd /home/seba/Escritorio/workspace/Vision
git add landing/
git commit -m "$(cat <<'EOF'
Copiar proyecto landing (VISION.IA) a landing/

Codigo fuente de la landing de marketing, copiado desde el proyecto
separado VISION.IA (sin .git, sin node_modules). Sirve como base para
mover vision.saltia.com.ar a landing + /admin (ver spec
docs/superpowers/specs/2026-09-14-landing-page-design.md).
EOF
)"
```

---

### Task 2: Agregar placeholders de EmailJS a `.env.example`

**Files:**
- Modify: `Vision/.env.example`

**Interfaces:**
- Produces: variables de entorno `VITE_EMAILJS_SERVICE_ID`, `VITE_EMAILJS_TEMPLATE_ID`, `VITE_EMAILJS_PUBLIC_KEY` disponibles para Task 6 (build args del Dockerfile).

- [ ] **Step 1: Agregar la sección al final de `.env.example`**

Agregar al final del archivo (después del bloque `# ---- Puertos solo para uso LOCAL...`):

```
# ---- Landing (build-time, EmailJS para el formulario de demo) ----
# Sin configurar todavia (pendiente: crear cuenta en https://www.emailjs.com/).
# El boton "Solicitar Demo" de la landing va a fallar silenciosamente hasta
# que se carguen valores reales aca + se haga un rebuild del servicio
# frontend (se hornea en build, igual que VITE_API_BASE_URL).
VITE_EMAILJS_SERVICE_ID=
VITE_EMAILJS_TEMPLATE_ID=
VITE_EMAILJS_PUBLIC_KEY=
```

- [ ] **Step 2: Verificar**

Run: `tail -8 /home/seba/Escritorio/workspace/Vision/.env.example`
Expected: muestra las 3 líneas `VITE_EMAILJS_*` agregadas.

- [ ] **Step 3: Commit**

```bash
cd /home/seba/Escritorio/workspace/Vision
git add .env.example
git commit -m "docs: placeholders de EmailJS en .env.example para la landing"
```

---

### Task 3: Base path `/admin/` en `frontend/vite.config.ts`

**Files:**
- Modify: `Vision/frontend/vite.config.ts`

**Interfaces:**
- Consumes: nada (cambio autocontenido).
- Produces: build de `frontend/` con assets referenciados como `/admin/assets/...` en vez de `/assets/...` — consumido por Task 5 (Dockerfile stage `build-app`) y Task 6 (nginx sirviéndolo bajo `/admin/`).

- [ ] **Step 1: Confirmar el contenido actual**

Run: `cat /home/seba/Escritorio/workspace/Vision/frontend/vite.config.ts`
Expected:
```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({ plugins: [react()] })
```

- [ ] **Step 2: Agregar `base: '/admin/'`**

Reemplazar el contenido completo de `Vision/frontend/vite.config.ts` por:

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({ base: '/admin/', plugins: [react()] })
```

- [ ] **Step 3: Build local y verificar que los assets quedan bajo `/admin/`**

```bash
cd /home/seba/Escritorio/workspace/Vision/frontend
npm install --no-audit --no-fund
npm run build
grep -o '/admin/assets/[^"]*\.\(js\|css\)' dist/index.html
```

Expected: dos líneas, una `.js` y una `.css`, ambas con prefijo `/admin/assets/`.

- [ ] **Step 4: Commit**

```bash
cd /home/seba/Escritorio/workspace/Vision
git add frontend/vite.config.ts
git commit -m "frontend: base path /admin/ (se va a servir bajo ese subpath)"
```

---

### Task 4: Botón "Iniciar sesión" en `landing/src/components/Navbar.jsx`

**Files:**
- Modify: `Vision/landing/src/components/Navbar.jsx`

**Interfaces:**
- Consumes: nada nuevo (el componente ya recibe `darkMode`, `toggleTheme`, `onOpenDemo` como props, sin cambios en esa firma).
- Produces: link visible `href="/admin/"` en el navbar (desktop y mobile).

- [ ] **Step 1: Ubicar el bloque de "Action buttons" (desktop) actual**

El archivo `Vision/landing/src/components/Navbar.jsx` tiene, dentro de `{/* Action buttons */}`, este bloque (botón "Solicitar Demo"):

```jsx
          {/* Request Demo CTA */}
          <button
            onClick={onOpenDemo}
            className="hidden items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-emerald-500/20 transition-all duration-200 hover:from-emerald-600 hover:to-teal-700 hover:shadow-lg hover:shadow-emerald-500/30 active:scale-95 md:inline-flex"
          >
            <Sparkles size={15} />
            <span>Solicitar Demo</span>
          </button>
```

- [ ] **Step 2: Agregar el link "Iniciar sesión" justo antes de ese botón**

Reemplazar el bloque de arriba por (agrega el `<a>` antes del `<button>` existente, sin tocar el resto):

```jsx
          {/* Login link */}
          <a
            href="/admin/"
            className="hidden items-center gap-2 rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition-all duration-200 hover:border-emerald-500 hover:text-emerald-700 md:inline-flex dark:border-slate-700 dark:text-slate-200 dark:hover:border-emerald-500 dark:hover:text-emerald-400"
          >
            Iniciar sesión
          </a>

          {/* Request Demo CTA */}
          <button
            onClick={onOpenDemo}
            className="hidden items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-emerald-500/20 transition-all duration-200 hover:from-emerald-600 hover:to-teal-700 hover:shadow-lg hover:shadow-emerald-500/30 active:scale-95 md:inline-flex"
          >
            <Sparkles size={15} />
            <span>Solicitar Demo</span>
          </button>
```

- [ ] **Step 3: Ubicar el bloque del menú mobile (dentro de `{mobileOpen && (...)}`)**

El archivo tiene este botón dentro del dropdown mobile:

```jsx
            <button
              onClick={() => {
                setMobileOpen(false);
                onOpenDemo();
              }}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 px-4 py-3 text-sm font-semibold text-white shadow-md shadow-emerald-500/20"
            >
              <Sparkles size={16} />
              Solicitar Demostración
            </button>
```

- [ ] **Step 4: Agregar el link "Iniciar sesión" antes de ese botón mobile**

Reemplazar el bloque de arriba por:

```jsx
            <a
              href="/admin/"
              onClick={() => setMobileOpen(false)}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl border border-slate-300 px-4 py-3 text-sm font-semibold text-slate-700 dark:border-slate-700 dark:text-slate-200"
            >
              Iniciar sesión
            </a>

            <button
              onClick={() => {
                setMobileOpen(false);
                onOpenDemo();
              }}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 px-4 py-3 text-sm font-semibold text-white shadow-md shadow-emerald-500/20"
            >
              <Sparkles size={16} />
              Solicitar Demostración
            </button>
```

- [ ] **Step 5: Build local y verificar que el link quedó en el HTML/JS generado**

```bash
cd /home/seba/Escritorio/workspace/Vision/landing
npm run build
grep -c 'href="/admin/"' dist/assets/*.js
```

Expected: un número mayor a 0 (el string quedó embebido en el bundle).

- [ ] **Step 6: Commit**

```bash
cd /home/seba/Escritorio/workspace/Vision
git add landing/src/components/Navbar.jsx
git commit -m "landing: boton Iniciar sesion -> /admin/ en el navbar"
```

---

### Task 5: Dockerfile multi-stage + nginx.conf combinado

**Files:**
- Modify: `Vision/frontend/Dockerfile` (reemplaza el contenido actual, sigue siendo el único Dockerfile de este servicio)
- Modify: `Vision/frontend/nginx.conf`

**Interfaces:**
- Consumes: `Vision/landing/package.json` + `Vision/landing/` (Task 1), `Vision/frontend/vite.config.ts` con `base: '/admin/'` (Task 3), build args `VITE_API_BASE_URL`, `VITE_EMAILJS_SERVICE_ID`, `VITE_EMAILJS_TEMPLATE_ID`, `VITE_EMAILJS_PUBLIC_KEY`.
- Produces: imagen `nginx:1.27-alpine` sirviendo `/usr/share/nginx/html/` (landing) y `/usr/share/nginx/html/admin/` (app) — consumida por Task 6 (`compose.dokploy.yaml`, `build.context: .`).

- [ ] **Step 1: Reemplazar `Vision/frontend/Dockerfile` completo**

```dockerfile
# Stage 1: build de la landing (marketing, servida en /)
FROM node:22-alpine AS build-landing
WORKDIR /app
COPY landing/package*.json ./
RUN npm install --no-audit --no-fund
COPY landing/ .
ARG VITE_EMAILJS_SERVICE_ID
ARG VITE_EMAILJS_TEMPLATE_ID
ARG VITE_EMAILJS_PUBLIC_KEY
ENV VITE_EMAILJS_SERVICE_ID=$VITE_EMAILJS_SERVICE_ID
ENV VITE_EMAILJS_TEMPLATE_ID=$VITE_EMAILJS_TEMPLATE_ID
ENV VITE_EMAILJS_PUBLIC_KEY=$VITE_EMAILJS_PUBLIC_KEY
RUN npm run build

# Stage 2: build de la app (dashboard, servida en /admin/)
FROM node:22-alpine AS build-app
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ .
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# Stage 3: nginx sirviendo ambos builds por path
FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build-landing /app/dist /usr/share/nginx/html
COPY --from=build-app /app/dist /usr/share/nginx/html/admin
EXPOSE 80
```

Nota: este Dockerfile asume `build.context` = raíz del repo (Task 6 lo configura así) — por eso las rutas `COPY` empiezan con `landing/` y `frontend/` en vez de `./`.

- [ ] **Step 2: Reemplazar `Vision/frontend/nginx.conf` completo**

```nginx
server {
  listen 80;
  server_name _;
  root /usr/share/nginx/html;
  index index.html;

  location = /admin { return 301 /admin/; }

  location /admin/ {
    try_files $uri /admin/index.html;
  }

  location / {
    try_files $uri /index.html;
  }
}
```

- [ ] **Step 3: Build de la imagen localmente desde la raíz del repo**

```bash
cd /home/seba/Escritorio/workspace/Vision
docker build \
  -f frontend/Dockerfile \
  --build-arg VITE_API_BASE_URL=https://apivision.saltia.com.ar/api/v1 \
  --build-arg VITE_EMAILJS_SERVICE_ID= \
  --build-arg VITE_EMAILJS_TEMPLATE_ID= \
  --build-arg VITE_EMAILJS_PUBLIC_KEY= \
  -t test-frontend-landing \
  .
```

Expected: termina con `naming to docker.io/library/test-frontend-landing` sin errores.

- [ ] **Step 4: Verificar el contenido servido dentro de la imagen**

```bash
docker run --rm test-frontend-landing sh -c "ls /usr/share/nginx/html && echo --- && ls /usr/share/nginx/html/admin"
```

Expected: la primera lista incluye `index.html` y `assets` (landing); la segunda lista (después de `---`) también incluye `index.html` y `assets` (app bajo `/admin`).

- [ ] **Step 5: Levantar el contenedor y probar las dos rutas**

```bash
docker run -d --rm -p 18080:80 --name test-frontend-landing-run test-frontend-landing
sleep 1
curl -s -o /dev/null -w "landing /: %{http_code}\n" http://localhost:18080/
curl -s -o /dev/null -w "admin /admin/: %{http_code}\n" http://localhost:18080/admin/
curl -s -o /dev/null -w "admin sin slash (debe redirigir): %{http_code}\n" http://localhost:18080/admin
docker stop test-frontend-landing-run
```

Expected: `landing /: 200`, `admin /admin/: 200`, `admin sin slash (debe redirigir): 301`.

- [ ] **Step 6: Commit**

```bash
cd /home/seba/Escritorio/workspace/Vision
git add frontend/Dockerfile frontend/nginx.conf
git commit -m "$(cat <<'EOF'
frontend: Dockerfile multi-stage sirve landing en / y app en /admin/

nginx.conf ahora resuelve por path: location /admin/ (mas especifico,
prioridad automatica de nginx) sirve la app existente, location /
sirve la landing nueva. Requiere build.context = raiz del repo (ver
proximo commit en compose.dokploy.yaml).
EOF
)"
```

---

### Task 6: Actualizar `compose.dokploy.yaml`

**Files:**
- Modify: `Vision/compose.dokploy.yaml`

**Interfaces:**
- Consumes: `Vision/frontend/Dockerfile` (Task 5), variables `VITE_API_BASE_URL`, `VITE_EMAILJS_SERVICE_ID`, `VITE_EMAILJS_TEMPLATE_ID`, `VITE_EMAILJS_PUBLIC_KEY` (Task 2, vía `.env`).
- Produces: definición final del servicio `frontend` que Dokploy va a buildear y deployar.

- [ ] **Step 1: Confirmar el bloque actual del servicio `frontend`**

Run: `grep -n -A 12 '^  frontend:' /home/seba/Escritorio/workspace/Vision/compose.dokploy.yaml`
Expected:
```yaml
  frontend:
    image: hys-vision-v110-frontend:latest
    build:
      context: ./frontend
      args:
        VITE_API_BASE_URL: ${VITE_API_BASE_URL}
    restart: unless-stopped
    networks: [hysvision_internal, dokploy-network]
    depends_on:
```

- [ ] **Step 2: Reemplazar el bloque `build:` del servicio `frontend`**

Buscar en `Vision/compose.dokploy.yaml`:

```yaml
  frontend:
    image: hys-vision-v110-frontend:latest
    build:
      context: ./frontend
      args:
        VITE_API_BASE_URL: ${VITE_API_BASE_URL}
    restart: unless-stopped
```

Reemplazar por:

```yaml
  frontend:
    image: hys-vision-v110-frontend:latest
    build:
      context: .
      dockerfile: frontend/Dockerfile
      args:
        VITE_API_BASE_URL: ${VITE_API_BASE_URL}
        VITE_EMAILJS_SERVICE_ID: ${VITE_EMAILJS_SERVICE_ID}
        VITE_EMAILJS_TEMPLATE_ID: ${VITE_EMAILJS_TEMPLATE_ID}
        VITE_EMAILJS_PUBLIC_KEY: ${VITE_EMAILJS_PUBLIC_KEY}
    restart: unless-stopped
```

No tocar nada del resto del bloque (`networks:`, `depends_on:`, `healthcheck:`) — queda exactamente igual que antes.

- [ ] **Step 3: Validar el YAML y que nada más cambió en el servicio**

```bash
cd /home/seba/Escritorio/workspace/Vision
python3 -c "
import yaml
d = yaml.safe_load(open('compose.dokploy.yaml'))
fe = d['services']['frontend']
print('build:', fe['build'])
print('networks:', fe['networks'])
print('depends_on:', list(fe['depends_on'].keys()))
print('services (orden):', list(d['services'].keys()))
"
```

Expected:
```
build: {'context': '.', 'dockerfile': 'frontend/Dockerfile', 'args': {'VITE_API_BASE_URL': '${VITE_API_BASE_URL}', 'VITE_EMAILJS_SERVICE_ID': '${VITE_EMAILJS_SERVICE_ID}', 'VITE_EMAILJS_TEMPLATE_ID': '${VITE_EMAILJS_TEMPLATE_ID}', 'VITE_EMAILJS_PUBLIC_KEY': '${VITE_EMAILJS_PUBLIC_KEY}'}}
networks: ['hysvision_internal', 'dokploy-network']
depends_on: ['backend', 'camera-worker', 'vision-engine', 'alert-worker']
services (orden): ['redis', 'minio', 'backend', 'camera-worker', 'vision-engine', 'alert-worker', 'frontend']
```
(la lista de servicios y su orden debe ser **idéntica** a la de antes de este cambio — solo cambió `build:`)

- [ ] **Step 4: Validar que `docker compose config` no tira error de sintaxis**

```bash
cd /home/seba/Escritorio/workspace/Vision
VITE_API_BASE_URL=https://apivision.saltia.com.ar/api/v1 \
VITE_EMAILJS_SERVICE_ID= VITE_EMAILJS_TEMPLATE_ID= VITE_EMAILJS_PUBLIC_KEY= \
POSTGRES_DB=x POSTGRES_USER=x POSTGRES_PASSWORD=x \
MINIO_ACCESS_KEY=x MINIO_SECRET_KEY=x \
docker compose -f compose.dokploy.yaml config --quiet
```

Expected: sin salida, exit code 0 (si tira error de variable faltante que no sea de las nuestras, es esperable por otras env vars del `.env` real que no están seteadas acá — confirmar que el error específico no mencione `frontend`, `dockerfile` ni `context`).

- [ ] **Step 5: Commit**

```bash
cd /home/seba/Escritorio/workspace/Vision
git add compose.dokploy.yaml
git commit -m "$(cat <<'EOF'
compose.dokploy.yaml: frontend buildea desde la raiz (landing + admin)

build.context pasa de ./frontend a . (raiz del repo) y se agrega
dockerfile: frontend/Dockerfile, para que el Dockerfile multi-stage
pueda copiar tanto landing/ como frontend/. Se suman los build args de
EmailJS. Nombre del servicio, posicion en services:, networks: y
depends_on: quedan identicos a como estaban.
EOF
)"
```

---

### Task 7: Actualizar `docs/DEPLOY_DOKPLOY.md`

**Files:**
- Modify: `Vision/docs/DEPLOY_DOKPLOY.md`

**Interfaces:**
- Consumes: nada (documentación).
- Produces: nada consumido por otro task.

- [ ] **Step 1: Agregar una sección nueva antes de "## Qué se cambió respecto al compose.yaml local, y por qué"**

Insertar este bloque (buscar el heading `## Qué se cambió respecto al compose.yaml local, y por qué` y agregar el siguiente contenido justo antes):

```markdown
## Landing page + app bajo /admin

Desde el deploy que agregó `landing/`, el servicio `frontend` sirve **dos
apps por path** en el mismo dominio y el mismo `Domain` que ya estaba
configurado en Dokploy — no hace falta ninguna acción nueva en la pestaña
Domains ni DNS nuevo:

- `https://vision.saltia.com.ar/` → landing de marketing (`landing/`).
- `https://vision.saltia.com.ar/admin/` → la app/dashboard operativo
  (`frontend/`, con `base: '/admin/'` en su `vite.config.ts`).

`apivision.saltia.com.ar` (backend), `CORS_ORIGINS` y `VITE_API_BASE_URL` no
cambian — el split es solo de path en el frontend, no afecta el origen HTTP.

Si en algún momento se cargan credenciales reales de EmailJS
(`VITE_EMAILJS_SERVICE_ID`/`TEMPLATE_ID`/`PUBLIC_KEY` en el `.env` de
Dokploy), hace falta un **rebuild** del servicio `frontend` para que tomen
efecto (se hornean en build, igual que `VITE_API_BASE_URL`) — no alcanza con
reiniciar el contenedor.

```

- [ ] **Step 2: Verificar que el heading nuevo quedó bien ubicado**

Run: `grep -n '^## ' /home/seba/Escritorio/workspace/Vision/docs/DEPLOY_DOKPLOY.md`
Expected: `## Landing page + app bajo /admin` aparece como heading, antes de `## Qué se cambió respecto al compose.yaml local, y por qué`.

- [ ] **Step 3: Commit**

```bash
cd /home/seba/Escritorio/workspace/Vision
git add docs/DEPLOY_DOKPLOY.md
git commit -m "docs: documentar landing + app bajo /admin en DEPLOY_DOKPLOY.md"
```

---

### Task 8: Build de integración final, push y checklist de deploy

**Files:**
- Ninguno (task de verificación e integración, sin cambios de código nuevos).

**Interfaces:**
- Consumes: todo lo producido por Tasks 1-7.
- Produces: rama `main` en GitHub lista para que Dokploy la deploye.

- [ ] **Step 1: Build de integración completo desde cero (sin cache) para detectar cualquier error antes de pushear**

```bash
cd /home/seba/Escritorio/workspace/Vision
docker build \
  --no-cache \
  -f frontend/Dockerfile \
  --build-arg VITE_API_BASE_URL=https://apivision.saltia.com.ar/api/v1 \
  --build-arg VITE_EMAILJS_SERVICE_ID= \
  --build-arg VITE_EMAILJS_TEMPLATE_ID= \
  --build-arg VITE_EMAILJS_PUBLIC_KEY= \
  -t test-frontend-landing-final \
  .
```

Expected: build completo sin errores (repite la verificación de Task 5 pero sin cache, sobre el estado final de todos los archivos).

- [ ] **Step 2: Repetir el smoke test de las dos rutas**

```bash
docker run -d --rm -p 18081:80 --name test-frontend-landing-final-run test-frontend-landing-final
sleep 1
curl -s -o /dev/null -w "landing /: %{http_code}\n" http://localhost:18081/
curl -s -o /dev/null -w "admin /admin/: %{http_code}\n" http://localhost:18081/admin/
docker stop test-frontend-landing-final-run
docker rmi test-frontend-landing-final test-frontend-landing 2>/dev/null
```

Expected: `landing /: 200`, `admin /admin/: 200`.

- [ ] **Step 3: Confirmar que todos los commits de los Tasks 1-7 están en `main` y pushear**

```bash
cd /home/seba/Escritorio/workspace/Vision
git log --oneline -8
git push origin main
```

Expected: `git push` termina sin error, muestra el rango de commits nuevos subidos (`<hash_anterior>..<hash_nuevo> main -> main`).

- [ ] **Step 4: Checklist para el usuario antes de darle Deploy en Dokploy**

Esto no es un comando — es la lista a repasar con el usuario antes de que dispare el deploy real en Dokploy (el deploy en sí lo hace el usuario desde la UI de Dokploy, como en toda esta sesión):

1. No hace falta tocar Dokploy → Domains ni crear DNS nuevo (el `Domain` de `frontend` ya existe y sigue apuntando al mismo servicio/puerto).
2. El primer deploy después de este cambio va a reconstruir la imagen de `frontend` desde cero (cambió `build.context`) — esperar el build completo en el log antes de asumir que falló.
3. Después del deploy, probar `https://vision.saltia.com.ar/` (debe verse la landing) y `https://vision.saltia.com.ar/admin/` (debe pedir login, igual que la app hoy).
4. El botón "Solicitar Demo" de la landing va a fallar (EmailJS sin configurar) — es esperado, no es una regresión.
