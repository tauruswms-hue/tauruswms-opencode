"""
procesar_intercambio.py — Script para ejecutar el proceso de intercambio WMS.

Lee los registros 'pendiente' de la base de intercambio (intercambio_*: materiales,
rutas, transportes, asignaciones ruta<->transporte y clientes) y los aplica sobre
las tablas operativas del WMS. Para programar:

    # Windows Task Scheduler / cron
    python procesar_intercambio.py
    python procesar_intercambio.py --tenant 1     # solo un tenant

Salida: resumen por consola y log de ejecucion en intercambio_log.
"""

import argparse
import sys

from modules.intercambio import procesar_intercambio


def main():
    parser = argparse.ArgumentParser(description="Procesa la base de intercambio hacia el WMS")
    parser.add_argument("--tenant", type=int, default=None,
                        help="ID de tenant (opcional). Si se omite, procesa todos.")
    args = parser.parse_args()

    try:
        resultado = procesar_intercambio(tenant_id=args.tenant, usuario='scheduler')
    except Exception as e:
        print(f"[ERROR] No se pudo procesar el intercambio: {e}", file=sys.stderr)
        sys.exit(1)

    print("=" * 50)
    print("RESULTADO DEL PROCESO DE INTERCAMBIO")
    print("=" * 50)
    print(f"  Procesados: {resultado['procesados']}")
    print(f"  Errores:    {resultado['errores']}")
    if resultado.get('aviso'):
        print(f"  Aviso:      {resultado['aviso']}")
    for det in resultado.get('errores_detalle', []):
        print(f"  - id={det['id']} codigo={det['codigo']}: {det['error']}")

    if resultado['errores'] > 0:
        sys.exit(2)
    sys.exit(0)


if __name__ == '__main__':
    main()
