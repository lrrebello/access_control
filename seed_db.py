import psycopg2
import os

# Configurações do seu banco
DB_URL = "postgresql://ecclesia_user:368614011932lu@localhost:5432/access_db"

def migrate():
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cur = conn.cursor()

        print("--- Aumentando tamanho do campo username para 100 caracteres ---")
        
        # Alterar o tamanho da coluna username
        cur.execute("""
            ALTER TABLE "user" ALTER COLUMN username TYPE VARCHAR(100);
        """)
        
        print("Campo username alterado com sucesso para VARCHAR(100)!")
        
        cur.close()
        conn.close()
        print("--- Migração concluída! ---")

    except Exception as e:
        print(f"Erro na migração: {e}")

if __name__ == "__main__":
    migrate()