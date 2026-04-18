import psycopg2
import os

# Configurações do seu banco
DB_URL = "postgresql://ecclesia_user:368614011932lu@localhost:5432/access_db"

def migrate():
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cur = conn.cursor()

        print("--- Iniciando Migração para Tabela de Acompanhantes ---")

        # Criar tabela de acompanhantes
        cur.execute("""
            CREATE TABLE IF NOT EXISTS companion (
                id SERIAL PRIMARY KEY,
                access_log_id INTEGER NOT NULL REFERENCES access_log(id) ON DELETE CASCADE,
                name VARCHAR(100) NOT NULL,
                document VARCHAR(50) NOT NULL
            );
        """)
        print("Tabela 'companion' criada com sucesso!")

        # Migrar dados existentes (se houver campos antigos)
        # Primeiro verificar se as colunas antigas existem
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='access_log' AND column_name IN ('companion_name', 'companion_doc');
        """)
        old_columns = cur.fetchall()
        
        if len(old_columns) == 2:
            cur.execute("""
                SELECT id, companion_name, companion_doc 
                FROM access_log 
                WHERE companion_name IS NOT NULL AND companion_name != '';
            """)
            
            old_companions = cur.fetchall()
            migrated = 0
            
            for log_id, name, doc in old_companions:
                if name and doc:
                    cur.execute("""
                        INSERT INTO companion (access_log_id, name, document)
                        VALUES (%s, %s, %s)
                    """, (log_id, name, doc))
                    migrated += 1
            
            print(f"{migrated} acompanhantes migrados para a nova tabela.")
        else:
            print("Nenhum dado antigo para migrar.")
        
        cur.close()
        conn.close()
        print("--- Migração finalizada! ---")

    except Exception as e:
        print(f"Erro na migração: {e}")

if __name__ == "__main__":
    migrate()