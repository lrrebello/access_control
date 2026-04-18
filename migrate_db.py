import psycopg2
import os

# Configurações do seu banco
DB_URL = "postgresql://ecclesia_user:368614011932lu@localhost:5432/access_db"

def migrate():
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cur = conn.cursor()

        print("--- Iniciando Migração do Banco de Dados ---")

        # Adicionar coluna company na tabela authorized_trailer se não existir
        cur.execute("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='authorized_trailer' AND column_name='company') THEN
                    ALTER TABLE authorized_trailer ADD COLUMN company VARCHAR(100);
                    RAISE NOTICE 'Coluna company adicionada na tabela authorized_trailer.';
                ELSE
                    RAISE NOTICE 'Coluna company já existe na tabela authorized_trailer.';
                END IF;
            END $$;
        """)

        # Garantir que as outras tabelas existam (caso precise)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS authorized_vehicle (
                id SERIAL PRIMARY KEY,
                plate VARCHAR(20) UNIQUE NOT NULL,
                vehicle_type VARCHAR(20) NOT NULL,
                company VARCHAR(100),
                expiry_date DATE
            );
            
            CREATE TABLE IF NOT EXISTS authorized_trailer (
                id SERIAL PRIMARY KEY,
                plate VARCHAR(20) UNIQUE NOT NULL,
                company VARCHAR(100),
                expiry_date DATE
            );
            
            CREATE TABLE IF NOT EXISTS authorized_driver (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                document VARCHAR(50) NOT NULL,
                company VARCHAR(100),
                expiry_date DATE
            );
        """)
        
        print("Migração de colunas concluída com sucesso.")
        
        cur.close()
        conn.close()
        print("--- Migração finalizada! ---")

    except Exception as e:
        print(f"Erro na migração: {e}")

if __name__ == "__main__":
    migrate()