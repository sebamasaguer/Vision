# Validación de construcción — HYS Vision IA v0.1.0

Fecha de construcción: 2026-09-01

## Controles ejecutados en el entorno de construcción

| Control | Resultado |
|---|---|
| Compilación sintáctica Python (`compileall`) | PASS |
| Tests backend | PASS — 10/10 |
| Autenticación + JWT + Argon2 | PASS |
| RBAC | PASS |
| Aislamiento entre organizaciones | PASS |
| Alta Organización → Establecimiento → Planta → Sector | PASS |
| Duplicados de organización/establecimiento | PASS |
| Auditoría de alta | PASS |
| Alembic `upgrade head` | PASS |
| Alembic revision actual | PASS — `0001_block0 (head)` |
| Parseo YAML de `compose.yaml` | PASS |
| Sintaxis TypeScript/TSX | PASS |
| Ejecución Docker Compose completa | PENDIENTE EN HOST — el entorno de construcción no dispone de Docker Engine |
| Build NPM con descarga de dependencias | PENDIENTE EN HOST — el entorno de construcción no tiene acceso de red a npm |

## Certificación en la PC destino

Ejecutar:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\scripts\instalar_bloque0.ps1
.\scripts\validar_bloque0.ps1
```

El validador exige que PostgreSQL, Redis, MinIO, backend y frontend estén corriendo/healthy, comprueba `/health`, `/ready`, HTTP 200 del frontend y vuelve a ejecutar los tests dentro del contenedor backend.
