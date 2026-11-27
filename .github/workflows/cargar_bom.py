import os
import glob
import json
from pymongo import MongoClient

def cargar_eventos_bom():
    # 1. Conexión local a MongoDB (arrancado por el workflow de GitHub Actions)
    cliente = MongoClient("mongodb://localhost:27017/")
    
    # 2. Seleccionamos la base de datos (puedes ajustar el nombre si usan uno distinto)
    db = cliente["erp_simulator"]
    
    # 3. Creamos o seleccionamos la colección de tu tema
    coleccion_bom = db["BOM"]
    
    # 4. Buscamos los archivos JSON de BOM en cualquier parte del repositorio
    archivos_json = glob.glob("**/BOM/*.json", recursive=True)
    
    if not archivos_json:
        print("No se encontraron archivos .json en la carpeta BOM.")
        return

    # 5. Iteramos sobre cada archivo encontrado para insertarlo en Mongo
    for archivo in archivos_json:
        with open(archivo, "r", encoding="utf-8") as f:
            try:
                contenido = json.load(f)
                
                # Si el archivo tiene una lista de eventos
                if isinstance(contenido, list):
                    if contenido:
                        resultado = coleccion_bom.insert_many(contenido)
                        print(f"Éxito: {len(resultado.inserted_ids)} eventos cargados desde {archivo}")
                
                # Si el archivo tiene un solo evento
                elif isinstance(contenido, dict):
                    resultado = coleccion_bom.insert_one(contenido)
                    print(f"Éxito: 1 evento cargado desde {archivo}")
                    
            except json.JSONDecodeError:
                print(f"Error: El archivo {archivo} no tiene un formato JSON válido.")

    # Mostramos cuántos documentos quedaron en total para verificar en los logs de Actions
    total_documentos = coleccion_bom.count_documents({})
    print(f"\nTotal de documentos en la colección 'BOM': {total_documentos}")

if __name__ == "__main__":
    cargar_eventos_bom()
