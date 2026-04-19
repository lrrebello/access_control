import psycopg2
import os
from datetime import datetime, timedelta

DB_URL = "postgresql://ecclesia_user:368614011932lu@localhost:5432/access_db"

def migrate():
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cur = conn.cursor()

        print("--- Criando tabelas de Postos de Trabalho ---")
        
        # Criar tabela workstation
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workstation (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                description VARCHAR(255),
                location VARCHAR(100),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        print("Tabela 'workstation' criada!")
        
        # Criar tabela workstation_user
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workstation_user (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
                workstation_id INTEGER NOT NULL REFERENCES workstation(id) ON DELETE CASCADE,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(user_id, workstation_id)
            );
        """)
        print("Tabela 'workstation_user' criada!")
        
        # Adicionar coluna active_workstation_id na tabela user
        cur.execute("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='user' AND column_name='active_workstation_id') THEN
                    ALTER TABLE "user" ADD COLUMN active_workstation_id INTEGER REFERENCES workstation(id);
                    RAISE NOTICE 'Coluna active_workstation_id adicionada!';
                END IF;
            END $$;
        """)
        
        # Adicionar coluna workstation_id na tabela access_log
        cur.execute("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='access_log' AND column_name='workstation_id') THEN
                    ALTER TABLE access_log ADD COLUMN workstation_id INTEGER REFERENCES workstation(id);
                    RAISE NOTICE 'Coluna workstation_id adicionada!';
                END IF;
            END $$;
        """)
        
        # Criar posto padrão
        cur.execute("""
            INSERT INTO workstation (name, description, location) 
            VALUES ('Portaria Principal', 'Posto principal de controle de acesso', 'Entrada Principal')
            ON CONFLICT (name) DO NOTHING;
        """)
        
        # Associar admin ao posto padrão - VERSÃO CORRIGIDA
        cur.execute("""
            DO $$
            DECLARE
                admin_id INTEGER;
                work_id INTEGER;
            BEGIN
                SELECT id INTO admin_id FROM "user" WHERE username = 'admin' LIMIT 1;
                SELECT id INTO work_id FROM workstation WHERE name = 'Portaria Principal' LIMIT 1;
                
                IF admin_id IS NOT NULL AND work_id IS NOT NULL THEN
                    IF NOT EXISTS (SELECT 1 FROM workstation_user WHERE user_id = admin_id AND workstation_id = work_id) THEN
                        INSERT INTO workstation_user (user_id, workstation_id, start_date, end_date) 
                        VALUES (admin_id, work_id, CURRENT_DATE, CURRENT_DATE + INTERVAL '3650 days');
                    END IF;
                    
                    UPDATE "user" SET active_workstation_id = work_id WHERE id = admin_id;
                END IF;
            END $$;
        """)
        
        print("--- Migração concluída! ---")
        
        cur.close()
        conn.close()

    except Exception as e:
        print(f"Erro na migração: {e}")

if __name__ == "__main__":
    migrate()