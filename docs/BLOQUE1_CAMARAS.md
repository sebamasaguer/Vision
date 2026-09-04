# Bloque 1 — Cámaras + RTSP + Demo Camera

## Flujo implementado

`RTSP / MP4 -> camera-worker -> OpenCV/FFmpeg -> Redis (frame + metadata) -> FastAPI -> Frontend`

El backend web **no abre cámaras**. `camera-worker` mantiene un hilo independiente por cámara activa; una fuente caída no bloquea las demás ni a FastAPI.

## Estados

`ONLINE`, `OFFLINE`, `DEGRADADA`, `SIN_VIDEO`, `ERROR_AUTENTICACION`, `IA_DESACTIVADA`.

En v0.2.0 el worker asigna automáticamente `ONLINE`, `OFFLINE` y `SIN_VIDEO`. `ERROR_AUTENTICACION` queda modelado pero no se infiere de un mensaje ambiguo de OpenCV: no se inventa un 401 cuando la librería no lo expone de forma confiable.

## Seguridad RTSP

- URL, usuario y contraseña se cifran con Fernet (`CAMERA_CREDENTIAL_KEY`).
- La API nunca devuelve usuario ni contraseña.
- La URL devuelta se sanitiza y elimina userinfo/query string.
- El worker descifra sólo en memoria al abrir la fuente.
- No se escriben credenciales en logs.

## Demo Camera

`demo/demo_camera.mp4` es un video sintético generado para este proyecto, sin material de terceros. El worker lo reproduce en loop y publica frames reales.

## Streaming

- `GET /api/v1/cameras/{id}/snapshot.jpg`: último JPEG, autenticado.
- `GET /api/v1/cameras/{id}/stream.mjpeg`: multipart MJPEG autenticado.
- El frontend usa snapshots autenticados a ~1.5 FPS para evitar exponer JWT en query strings.

## Alcance

No hay detección de personas/EPP en este bloque. Eso se implementa en Bloques 3/4. `ai_enabled` queda reservado y por defecto es `false`.
