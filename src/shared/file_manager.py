
import os
import shutil
import logging
from pathlib import Path
from uuid import UUID

# Configuración básica de logging
logger = logging.getLogger(__name__)

# Definir la raíz del almacenamiento. 
# En producción Docker, /app/storage está montado al disco grande.
STORAGE_ROOT = Path(os.getenv("PATH_STORAGE", "/app/storage"))

class FileManager:
    """
    Gestor centralizado de archivos físicos en disco.
    Asegura que todos los archivos se guarden bajo la estructura:
    /app/storage/documents/{client_id}/{filename}
    """

    @staticmethod
    def _get_client_dir(client_id: UUID) -> Path:
        return STORAGE_ROOT / "documents" / str(client_id)

    @classmethod
    def save_upload(cls, file_bytes: bytes, filename: str, client_id: UUID) -> str:
        """
        Guarda un archivo subido en el directorio del cliente.
        Retorna la ruta absoluta del archivo guardado.
        """
        client_dir = cls._get_client_dir(client_id)
        
        # 1. Asegurar que existe el directorio
        try:
            client_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Error creando directorio {client_dir}: {e}")
            raise IOError(f"No se pudo crear directorio para cliente {client_id}")

        # 2. Ruta final
        file_path = client_dir / filename
        
        # 3. Escribir bytes
        try:
            with open(file_path, "wb") as f:
                f.write(file_bytes)
            logger.info(f"Archivo guardado: {file_path}")
            return str(file_path)
        except Exception as e:
            logger.error(f"Error escribiendo archivo {file_path}: {e}")
            raise IOError(f"Fallo al escribir archivo en disco")

    @classmethod
    def delete_document(cls, client_id: UUID, filename: str) -> bool:
        """
        Borra un archivo específico de un cliente.
        """
        file_path = cls._get_client_dir(client_id) / filename
        if file_path.exists():
            try:
                os.remove(file_path)
                logger.info(f"Archivo eliminado: {file_path}")
                return True
            except OSError as e:
                logger.error(f"Error borrando archivo {file_path}: {e}")
                return False
        else:
            logger.warning(f"Intento de borrar archivo inexistente: {file_path}")
            return False

    @classmethod
    def delete_client_folder(cls, client_id: UUID) -> bool:
        """
        Elimina recursivamente todo el directorio de un cliente.
        Usar con precaución (Baja de Cliente).
        """
        client_dir = cls._get_client_dir(client_id)
        if client_dir.exists():
            try:
                shutil.rmtree(client_dir)
                logger.info(f"Directorio de cliente eliminado completamente: {client_dir}")
                return True
            except OSError as e:
                logger.error(f"Error borrando directorio cliente {client_dir}: {e}")
                return False
        return True # Si no existe, "ya estaba borrado"

    @classmethod
    def list_files(cls, client_id: UUID) -> list[str]:
        """Listar archivos de un cliente"""
        client_dir = cls._get_client_dir(client_id)
        if not client_dir.exists():
            return []
        return [f.name for f in client_dir.iterdir() if f.is_file()]
