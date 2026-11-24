import psycopg2

def main():
    conn = psycopg2.connect(host="localhost", user="erp_user", password="erp_password", dbname="techassembly_db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS inventario (
            id SERIAL PRIMARY KEY,
            componente VARCHAR(100) NOT NULL,
            cantidad_disponible INT NOT NULL
        );
    """)
    componentes = [
        ('CPU Ryzen 7', 50), ('Motherboard B650', 50), 
        ('RAM 16GB DDR5', 100), ('SSD 1TB NVMe', 50), 
        ('Power Supply 750W', 50), ('Graphics Card RTX', 30)
    ]
    cur.executemany("INSERT INTO inventario (componente, cantidad_disponible) VALUES (%s, %s)", componentes)
    conn.commit()
    cur.close()
    conn.close()
    print("PostgreSQL: OK")

if __name__ == "__main__":
    main()