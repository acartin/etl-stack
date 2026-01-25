
#!/bin/bash

# --- CONFIGURACIÓN ---
CTID=401
HOSTNAME="prd-media-processor-01"
IP="192.168.0.40"
PASS="Techimi.15"
TEMPLATE="local:vztmpl/debian-12-standard_12.12-1_amd64.tar.zst"

# --- TAMAÑOS ---
ROOT_SIZE=8        # Sistema Base
STAGING_SIZE=40    # Zona de trabajo NVMe (ETL)

# --- TU CLAVE SSH (Limpia) ---
# Se eliminó el caracter '>' del final para evitar errores de sintaxis
TU_PUBLIC_KEY="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDgNskIdU2UkN70T1b+G8U2oDngfMEk7RB1R/1XGSjyBDH2N+6oy+N8pnYOqrxQnJb6ZeBAsa1h8WQdCmQjREKMjZMlLkYsMnRf+MQDOBp4ZkQafgvr+gw55Foaq+N/GQTQ+aS8qDyMm5vk3oRjH12bj/g9i"

# --- 1. LIMPIEZA ---
if pct list | grep -q $CTID; then
    echo "⚠️  Destruyendo contenedor $CTID anterior..."
    pct stop $CTID
    pct destroy $CTID
fi

# --- 2. CREACIÓN ---
echo "🔨 Creando Motor ETL (Geo + Data)..."
pct create $CTID $TEMPLATE \
  --hostname $HOSTNAME \
  --cores 4 --memory 8192 --swap 1024 \
  --net0 name=eth0,bridge=vmbr0,ip=$IP/24,gw=192.168.0.1 \
  --rootfs local-lvm:$ROOT_SIZE \
  --password $PASS \
  --unprivileged 1 \
  --features nesting=1 \
  --start 0

# --- 3. ALMACENAMIENTO ---
echo "🔌 Configurando Discos..."
# Staging (NVMe)
pct set $CTID --mp0 local-lvm:$STAGING_SIZE,mp=/app/staging
# Storage (HDD)
mkdir -p /mnt/storage/data
chmod 777 /mnt/storage/data
pct set $CTID --mp1 /mnt/storage/data,mp=/app/storage

# --- 4. INSTALACIÓN SISTEMA ---
echo "🚀 Instalando Sistema Base + Drivers Geo + Redis..."
pct start $CTID
sleep 10

pct exec $CTID -- bash -c "apt-get update && apt-get install -y \
  python3-full python3-pip libpq-dev libwebp-dev zlib1g-dev \
  libjpeg-dev postgresql-client git nano openssh-server samba \
  poppler-utils tesseract-ocr \
  libgeos-dev libgdal-dev gdal-bin redis-server"

# --- 5. CARPETAS ---
echo "📂 Creando estructura ETL..."
pct exec $CTID -- mkdir -p /app/src
pct exec $CTID -- mkdir -p /app/staging/{images_raw,documents_in,data_raw,temp_work}
pct exec $CTID -- mkdir -p /app/storage/{images_web,documents_arch,datasets_clean}
pct exec $CTID -- chmod -R 777 /app/staging /app/storage

# --- 6. SSH ---
echo "🔑 Configurando SSH..."
pct exec $CTID -- mkdir -p /root/.ssh
# Inyección segura de la clave
pct exec $CTID -- bash -c "echo \"$TU_PUBLIC_KEY\" >> /root/.ssh/authorized_keys"
pct exec $CTID -- chmod 700 /root/.ssh
pct exec $CTID -- chmod 600 /root/.ssh/authorized_keys
pct exec $CTID -- bash -c "sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config"
pct exec $CTID -- service ssh restart

# --- 7. SAMBA ---
echo "📂 Configurando Samba..."
pct exec $CTID -- bash -c "cat <<SMBEOF > /etc/samba/smb.conf
[global]
   workgroup = WORKGROUP
   server string = ETL Engine
   security = user
   map to guest = Bad User
[app]
   path = /app
   browsable = yes
   writable = yes
   guest ok = no
   read only = no
   create mask = 0777
   directory mask = 0777
   force user = root
SMBEOF"
pct exec $CTID -- bash -c "(echo '$PASS'; echo '$PASS') | smbpasswd -s -a root"
pct exec $CTID -- service smbd restart

# --- 8. PYTHON STACK ---
echo "🐍 Instalando Librerías (Geo, Data, APIs, Redis Queue)..."

# Stack Geoespacial + Data + OCR (SIN Playwright)
pct exec $CTID -- bash -c "pip3 install --break-system-packages \
  fastapi uvicorn[standard] sqlalchemy psycopg2-binary \
  python-multipart python-jose[cryptography] passlib[bcrypt] \
  python-dotenv pillow duckdb google-genai requests \
  pypdf pdf2image pytesseract pandas openpyxl \
  geopandas shapely osmnx networkx geopy folium rq"

echo "✅ MOTOR ETL COMPLETO."
