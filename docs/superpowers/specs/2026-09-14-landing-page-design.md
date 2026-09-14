# Landing page en `vision.saltia.com.ar`, app movida a `/admin`

## Contexto

Hoy `vision.saltia.com.ar` sirve directamente la app (dashboard operativo de
HYS Vision IA), servida por el servicio `frontend` del compose de producción.
Existe un proyecto de landing/marketing ya construido y separado
(`/home/seba/Escritorio/workspace/VISION.IA`, React 18 + Vite + Tailwind +
Framer Motion + EmailJS) que no forma parte del repo `Vision` ni de su deploy.

Se quiere que `vision.saltia.com.ar` (raíz) sirva la landing, y que la app
pase a vivir en `vision.saltia.com.ar/admin`.

## Decisiones (de la sesión de brainstorming)

- **Un solo dominio, split por path** — no un subdominio nuevo. Motivo: evita
  tocar la config de Domains/DNS en Dokploy, que ya mostró un bug real
  (labels de Traefik cruzadas entre servicios cuando cambia la forma del
  compose — ver commits `bc9e2fb`/`b7c6b51` y el troubleshooting previo de
  esta misma sesión). Reusar el `Domain` que ya funciona para `frontend` es
  la opción de menor riesgo.
- **Un solo servicio Docker (`frontend`)** sirviendo ambas apps con nginx,
  en vez de un servicio nuevo — mismo motivo: mantener el compose con la
  misma cantidad/orden de servicios que ya está validado.
- **EmailJS sin configurar por ahora** — el usuario no tiene las credenciales
  todavía. Se deja el modal de demo funcionalmente presente pero con env vars
  vacías; documentar que hace falta cargarlas + rebuild cuando existan.
- **Botón "Iniciar sesión"** en el navbar de la landing, link relativo a
  `/admin/`.

## Arquitectura

```
vision.saltia.com.ar/          -> nginx sirve landing (build de landing/)
vision.saltia.com.ar/admin/    -> nginx sirve la app (build de frontend/, base=/admin/)
apivision.saltia.com.ar/       -> backend (sin cambios)
```

Un solo contenedor `frontend` (nginx) sirve ambos builds desde rutas
distintas del mismo filesystem de imagen. Traefik/Dokploy siguen viendo un
único servicio con un único dominio — no hay cambios en `Domains`, DNS, redes
(`hysvision_internal`/`dokploy-network`) ni en las labels de Traefik.

## Componentes y cambios

### 1. Código fuente — `Vision/landing/`

Copiar el contenido de `VISION.IA/` (sin `.git`, sin `node_modules`,
sin `package-lock.json` si difiere del gestor de paquetes usado) a
`Vision/landing/`, como directorio hermano de `backend/` y `frontend/`.
Se pierde el historial git del proyecto original (era un repo no relacionado,
`Gonzalez-Gaston/VISION.IA`) — queda versionado desde cero dentro de `Vision`.

### 2. `landing/vite.config.js`

Sin cambios respecto al original (base por defecto `/`, la landing vive en
la raíz).

### 3. `frontend/vite.config.ts` (la app)

Agregar `base: '/admin/'` para que los assets built se referencien como
`/admin/assets/...` en vez de `/assets/...` — evita colisión con los assets
de la landing y hace que naveguen bien una vez servidos bajo ese subpath.
No requiere cambios de router porque el frontend no usa ninguno (`grep` no
encontró `react-router` ni navegación basada en URL — es una sola pantalla
con estado interno).

### 4. `frontend/Dockerfile` (reemplaza al actual, sigue siendo el único
   Dockerfile de este servicio)

Multi-stage:
1. `build-landing`: Node 22, `npm install` + `npm run build` sobre
   `landing/`, con build args para `VITE_EMAILJS_SERVICE_ID`,
   `VITE_EMAILJS_TEMPLATE_ID`, `VITE_EMAILJS_PUBLIC_KEY`.
2. `build-app`: Node 22, `npm install` + `npm run build` sobre `frontend/`
   (igual que hoy), con build arg `VITE_API_BASE_URL` (sin cambios).
3. Stage final `nginx:1.27-alpine`: copia `build-landing`'s `dist/` a
   `/usr/share/nginx/html/`, copia `build-app`'s `dist/` a
   `/usr/share/nginx/html/admin/`, copia `nginx.conf`.

### 5. `frontend/nginx.conf`

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

`location /admin/` es más específico que `location /` — nginx lo prioriza
automáticamente para cualquier request bajo ese prefijo, sin necesidad de
`location` con regex ni prioridad explícita.

### 6. `compose.dokploy.yaml`

Único cambio: el `build.context` del servicio `frontend` pasa de `./frontend`
a `.` (raíz del repo), y se agrega `dockerfile: frontend/Dockerfile` (el
Dockerfile deja de estar en la raíz del contexto). Los `args` del build pasan
a incluir las 3 variables de EmailJS además de `VITE_API_BASE_URL`. El
servicio conserva exactamente el mismo nombre (`frontend`), misma posición
en la lista de `services:`, mismas redes, mismo `depends_on` — nada más se
toca, para no repetir el bug de labels de Traefik ya visto en esta app.

### 7. `.env.example`

Agregar, como placeholders vacíos (documentados como pendientes hasta que el
usuario tenga las credenciales reales de EmailJS):

```
VITE_EMAILJS_SERVICE_ID=
VITE_EMAILJS_TEMPLATE_ID=
VITE_EMAILJS_PUBLIC_KEY=
```

### 8. `landing/src/components/Navbar.jsx`

Agregar un botón "Iniciar sesión" (desktop + mobile), estilo secundario,
`href="/admin/"`, junto al botón existente "Solicitar Demo".

### 9. `docs/DEPLOY_DOKPLOY.md`

Actualizar para reflejar que `frontend` ahora sirve dos apps por path, y que
no hace falta ninguna acción nueva en Domains/DNS para este cambio.

## Fuera de alcance

- Configurar EmailJS con credenciales reales (el usuario no las tiene aún).
- Cualquier cambio a `backend`, `apivision.saltia.com.ar`, CORS, o las redes
  del compose — ninguno de estos se toca.
- SEO/meta tags específicos de la landing, analytics, etc. — se deploya el
  proyecto `VISION.IA` tal cual está, sin agregarle features nuevas más allá
  del botón de login.

## Testing / verificación

- Build local de ambos proyectos (`npm run build` en `landing/` y en
  `frontend/`) antes de commitear, para detectar errores de compilación
  temprano.
- Verificar en el Dockerfile combinado que `docker build` corre bien
  localmente (`docker build -t test-frontend .` desde la raíz del repo) antes
  de pushear — reduce el riesgo de descubrir un error recién en el log de
  deploy de Dokploy (patrón ya sufrido varias veces en esta sesión).
- Tras el deploy: verificar `https://vision.saltia.com.ar/` (landing) y
  `https://vision.saltia.com.ar/admin/` (app, debe pedir login igual que
  hoy) devuelven 200 y cargan sus assets (`/assets/*.css`, `/assets/*.js`
  para la landing; `/admin/assets/*.js`, `/admin/assets/*.css` para la app).
- Confirmar que `apivision.saltia.com.ar` sigue funcionando sin cambios
  (login desde `/admin/` debe seguir autenticando contra el backend igual
  que antes).

## Riesgos conocidos

- Cambiar el `build.context` de `frontend` a la raíz del repo aumenta
  ligeramente el tamaño de contexto que se envía al build (ahora incluye
  todo el repo, no solo `frontend/`) — irrelevante en tamaño (el repo pesa
  ~48MB total) pero vale mencionarlo.
- Si el usuario carga las credenciales de EmailJS más adelante, va a
  necesitar un rebuild del servicio `frontend` (no alcanza con reiniciar el
  contenedor) — mismo patrón ya visto con `VITE_API_BASE_URL`.
