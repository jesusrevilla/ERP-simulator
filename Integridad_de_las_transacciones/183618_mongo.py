import os
import json
from pymongo import MongoClient

# 1. Configurar conexión a MongoDB
host = os.getenv('MONGO_HOST', 'localhost')
port = int(os.getenv('MONGO_PORT', 27017))

print(f"Conectando a MongoDB en {host}:{port}...")
client = MongoClient(host, port)

# 2. Crear BD y la colección de tu tema
db = client['erp_database']
coleccion = db['integridad_transacciones']
coleccion.delete_many({}) # Limpiar datos previos

# 3. Lista de los 4 archivos JSON de tu módulo
archivos_json = [
    "Integridad_de_las_transacciones/IntegridadTransacciones (1).json",
    "Integridad_de_las_transacciones/181619_Eventos_Integridad_Transacciones.json",
    "Integridad_de_las_transacciones/176535_eventos.json",
    "Integridad_de_las_transacciones/175456_IntTrscns.json"
]

archivos_cargados = 0

for ruta in archivos_json:
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                datos = json.load(f)
                if isinstance(datos, list):
                    coleccion.insert_many(datos)
                else:
                    coleccion.insert_one(datos)
            print(f"✅ Cargado exitosamente en Mongo: {ruta}")
            archivos_cargados += 1
        except Exception as e:
            print(f"❌ Error al cargar {ruta}: {e}")
    else:
        print(f"⚠️ Archivo no encontrado: {ruta}")

print(f"\nProceso terminado: {archivos_cargados} archivos guardados en la colección.")