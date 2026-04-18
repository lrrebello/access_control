import psycopg2

DB_URL = "postgresql://ecclesia_user:368614011932lu@localhost:5432/access_db"

def migrate():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    # Adicionar novas colunas
    cur.execute("""
        ALTER TABLE "user" ADD COLUMN IF NOT EXISTS is_approved BOOLEAN DEFAULT FALSE;
        ALTER TABLE "user" ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;
        ALTER TABLE "user" ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();
        
        -- Tornar o primeiro usuário admin (seu usuário)
        UPDATE "user" SET is_admin = TRUE, is_approved = TRUE WHERE id = 1;
    """)
    
    # Adicionar user_id ao access_log
    cur.execute("""
        ALTER TABLE access_log ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES "user"(id);
        
        -- Vincular registros existentes ao admin (user_id=1)
        UPDATE access_log SET user_id = 1 WHERE user_id IS NULL;
        
        -- Tornar obrigatório
        ALTER TABLE access_log ALTER COLUMN user_id SET NOT NULL;
    """)
    
    print("Migração concluída!")
    cur.close()
    conn.close()

if __name__ == "__main__":
    migrate()