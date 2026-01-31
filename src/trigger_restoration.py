
import os
import sys
from redis import Redis
from rq import Queue

# Configurar sys.path
sys.path.append("/app/src")

from src.ETL_IMAGES.worker_tasks import restore_images_task, run_tagging_task

def main():
    redis_conn = Redis(host='localhost', port=6379, db=0)
    q = Queue('etl_queue', connection=redis_conn)

    # 1. Encolar Restauración de AltaVista (FULL)
    job_av_restore = q.enqueue(
        restore_images_task,
        args=("AltaVista", None), # Sin límite, procesar todo
        job_timeout=10800, # 3 horas
        job_id="restore_altavista_full"
    )
    print(f"✅ Encolada restauración AltaVista COMPLETA (Job: {job_av_restore.id})")

    # 2. Encolar Restauración de ZonaPlus (FULL)
    job_zp_restore = q.enqueue(
        restore_images_task,
        args=("ZonaPlus", None), # Sin límite
        job_timeout=10800, # 3 horas
        job_id="restore_zonaplus_full"
    )
    print(f"✅ Encolada restauración ZonaPlus (Job: {job_zp_restore.id})")

    # 3. Encolar Etiquetado AI (Dependiente del éxito de la restauración)
    # RQ no soporta dependencias directas fácilmente sin módulos extra
    # así que los encolamos directamente después (se ejecutarán en orden si hay un solo worker)
    # o simplemente los lanzamos como tareas independientes.
    
    job_av_tag = q.enqueue(
        run_tagging_task,
        args=("AltaVista", 50),
        job_timeout=1800,
        job_id="tag_altavista",
        depends_on=job_av_restore # Solo corre si el restore termina bien
    )
    print(f"✅ Encolado etiquetado AltaVista (Depende de restauración)")

    job_zp_tag = q.enqueue(
        run_tagging_task,
        args=("ZonaPlus", 50),
        job_timeout=1800,
        job_id="tag_zonaplus",
        depends_on=job_zp_restore
    )
    print(f"✅ Encolado etiquetado ZonaPlus (Depende de restauración)")

    print("\n🚀 Todos los trabajos han sido enviados al Worker.")

if __name__ == "__main__":
    main()
