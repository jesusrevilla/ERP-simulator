import os
import glob
import json
from pymongo import MongoClient

def cargar_eventos_bom():
   
    cliente = MongoClient("mongodb://localhost:27017/")
    
    db = cliente["erp_simulator"]
    
    coleccion_bom = db["BOM"]
    
    archivos_json = glob.glob("BOM/*.json")
    
    if not archivos_json:
        print("No se encontraron archivos .json en la carpeta BOM.")
        return

    for archivo in archivos_json:
        with open(archivo, "r", encoding="utf-8") as f:
            try:
                contenido = json.load(f)
                
                if isinstance(contenido, list):
                    if contenido:
                        resultado = coleccion_bom.insert_many(contenido)
                        print(f"Éxito: {len(resultado.inserted_ids)} eventos cargados desde {archivo}")
                
                elif isinstance(contenido, dict):
                    resultado = coleccion_bom.insert_one(contenido)
                    print(f"Éxito: 1 evento cargado desde {archivo}")
                    
            except json.JSONDecodeError:
                print(f"Error: El archivo {archivo} no tiene un formato JSON válido.")

    total_documentos = coleccion_bom.count_documents({})
    print(f"\nTotal de documentos en la colección 'BOM': {total_documentos}")

if __name__ == "__main__":
    cargar_eventos_bom()
