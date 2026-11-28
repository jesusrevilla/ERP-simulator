"""
Carga los eventos JSON de Integridad de las transacciones en MongoDB (184661)

"""

import glob
import json
import os
import sys

COLECCION = "integridad_de_las_transacciones"


def leer_eventos(carpeta):
    documentos = []
    for ruta in sorted(glob.glob(os.path.join(carpeta, "*.json"))):
        archivo = os.path.basename(ruta)
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        eventos = datos.get("event_sequence") if isinstance(datos, dict) else None
        if not eventos:
            print(f"Se omite {archivo}: no trae 'event_sequence'")
            continue
        for evento in eventos:
            if not evento.get("idempotency_key"):
                print(f"Se omite {evento.get('event_id')}: no trae idempotency_key")
                continue
            documentos.append({**evento,
                               "archivo_origen": archivo,
                               "subsystem": datos.get("subsystem"),
                               "patron": datos.get("transaction_integrity_pattern")})
        print(f"{archivo}: {len(eventos)} eventos leídos")
    return documentos


def main():
    from pymongo import MongoClient

    carpeta = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    host = os.getenv("MONGO_HOST", "localhost")
    port = os.getenv("MONGO_PORT", "27017")

    # Conexión a MongoDB
    cliente = MongoClient(f"mongodb://{host}:{port}/", serverSelectionTimeoutMS=30000)
    cliente.admin.command("ping")
    print(f"Conectado a MongoDB en {host}:{port}")
    db = cliente[os.getenv("MONGO_DB", "erpdb")]

    # Crear la colección del tema
    if COLECCION not in db.list_collection_names():
        db.create_collection(COLECCION)
        print(f"Colección creada: {COLECCION}")
    coleccion = db[COLECCION]
    coleccion.create_index("idempotency_key", unique=True)

    # Cargar los eventos
    for doc in leer_eventos(carpeta):
        coleccion.replace_one({"idempotency_key": doc["idempotency_key"]}, doc, upsert=True)

    # Verificar lo que quedó guardado
    print(f"\nDocumentos en {db.name}.{COLECCION}: {coleccion.count_documents({})}")
    for e in coleccion.find({}, {"_id": 0, "step": 1, "event_name": 1,
                                 "transaction_context.phase": 1}).sort("step", 1):
        print(f"  {e['step']:>2}. {e['event_name']} ({e['transaction_context']['phase']})")
    cliente.close()


if __name__ == "__main__":
    main()
