# Backup Prototype (Tkinter + Google Drive)

Aplicación de escritorio en **Python (Tkinter)** que permite comprimir archivos o carpetas en formato ZIP, calcular su checksum SHA-256 y subir el resultado a Google Drive. Incluye opciones de ejecución manual y automática, además de un historial de operaciones en formato CSV.


## Funcionalidades

- **Interfaz gráfica local** (Tkinter).
- **Backup automático**: comprime archivos o carpetas en ZIP con timestamp.
- **Subida a Google Drive** (especificando Folder ID).
- **Parámetros configurables en UI**:
  - Ruta de origen.
  - Carpeta local de destino.
  - Folder ID de Google Drive.
  - Intervalo de ejecución.
- **Registro de operaciones** en `backup_log.csv` con:
  - Fecha.
  - Ruta.
  - Tamaño.
  - Checksum SHA-256.
  - File ID en Drive.
  - Estado.


## Requisitos

- **Python 3.10+**
- Paquetes necesarios:
  ```bash
  pip install pydrive2 python-dotenv
  ```
  - **Archivo `client_secrets.json`** (OAuth de escritorio) en la misma carpeta que el script.
## 🔧 Configuración de Google Drive

1. **En [Google Cloud Console](https://console.cloud.google.com/):**
   - Habilitar la **Google Drive API**.
   - Configurar la pantalla de consentimiento OAuth.
   - Crear un **OAuth Client ID** de tipo **Aplicación de escritorio**.
2. Descargar el archivo JSON de credenciales y guardarlo como `client_secrets.json` junto al script.
3. **Primera ejecución:**
   - Se abrirá el navegador para autorizar el acceso.
   - Se generará automáticamente el archivo `credentials.json`.
     
## Instalación y Ejecución

1. Instalación
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install pydrive2 python-dotenv
  ```
2. Ejecución
     ```bash
     python backup_gui.py
     ```

## Uso (UI)

- **Origen (archivo o carpeta):** Ruta del archivo o carpeta a respaldar.
- **Carpeta local para ZIPs:** Destino local donde se guardarán los archivos `.zip`.
- **Google Drive Folder ID (opcional):** ID de la carpeta en Google Drive (visible en la URL: `.../folders/<ID>`). Si se deja vacío, se sube a “Mi unidad”.
- **Intervalo automático (minutos):** Periodo para la ejecución en segundo plano.

### Botones
- **Guardar configuración:** Persiste la configuración en `backup_config.json`.
- **Ejecutar ahora:** Realiza un backup inmediato.
- **Iniciar automático / Detener automático:** Activa o detiene el scheduler interno.

## Carpeta de Google Drive

1. Crear o elegir una carpeta en Google Drive.
2. Abrirla y copiar el valor que aparece tras `/folders/` en la URL.
3. Pegar ese **Folder ID** en la UI de la aplicación.

## Artefactos y logs

- **ZIPs:** Se generan como `backup-<nombre>-YYYYMMDD-HHMMSS.zip` en la carpeta local destino.
- **CSV:** El archivo `backup_log.csv` contiene los siguientes campos:
  - `date_time`
  - `source`
  - `zip_path`
  - `zip_size`
  - `checksum`
  - `drive_file_id`
  - `status`
  - `message`

