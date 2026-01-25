
# ⚙️ Manual de Servicios Systemd (DevOps)

Este documento detalla la configuración de los servicios que mantienen viva la plataforma ETL en el servidor Linux.

## 📋 Resumen de Servicios
Tenemos dos servicios principales ejecutándose en el contenedor:

1.  **`etl-api.service`**: El servidor web FastAPI (Puerto 8000).
2.  **`etl-worker.service`**: El procesador de cola de tareas (Redis Worker).

Ambos están configurados para iniciarse automáticamente (`enabled`) y reiniciarse si fallan (`Restart=always`).

---

## 1. Servicio API (FastAPI)

**Archivo:** `/etc/systemd/system/etl-api.service`

```ini
[Unit]
Description=ETL Agentic API (FastAPI)
After=network.target redis-server.service

[Service]
Type=simple
User=root
# Directorio raíz de la aplicación
WorkingDirectory=/app
# Importante: PYTHONPATH para que Python encuentre 'src'
Environment=PYTHONPATH=/app
# Comando de arranque (uvicorn)
ExecStart=/usr/bin/python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

## 2. Servicio Worker (RQ/Redis)

**Archivo:** `/etc/systemd/system/etl-worker.service`

```ini
[Unit]
Description=ETL Agentic Worker (RQ)
After=network.target redis-server.service etl-api.service

[Service]
Type=simple
User=root
WorkingDirectory=/app
Environment=PYTHONPATH=/app
# Comando de arranque del Worker
ExecStart=/usr/bin/python3 -m src.worker_service
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## 🛠️ Comandos de Gestión

### Ver Estado (Status)
Verifica si están corriendo (Active: active (running)).
```bash
systemctl status etl-api etl-worker
```

### Reiniciar (Restart)
Útil después de desplegar cambios en el código Python.
```bash
systemctl restart etl-api etl-worker
```

### Ver Logs (Journalctl)
Para depurar errores o ver prints.
```bash
# Ver últimos 50 logs de la API
journalctl -u etl-api -n 50 -f

# Ver últimos 50 logs del Worker
journalctl -u etl-worker -n 50 -f
```

### Detener (Stop)
```bash
systemctl stop etl-api etl-worker
```

### Habilitar/Deshabilitar Arranque Automático
```bash
# Habilitar (Default)
systemctl enable etl-api etl-worker

# Deshabilitar
systemctl disable etl-api etl-worker
```
