import psycopg2
from psycopg2 import sql
import os

# Configurações do seu PostgreSQL (Ajuste se necessário)
DB_ADMIN_USER = "postgres"  # Usuário administrador padrão
DB_ADMIN_PASS = "postgres"  # Senha do administrador
DB_HOST = "localhost"
DB_PORT = "5432"

# Dados do novo banco e usuário para a aplicação
APP_DB_NAME = "access_db"
APP_DB_USER = "access_user"
APP_DB_PASS = "access_pass123"

def setup_postgresql():
    try:
        # 1. Conectar ao PostgreSQL como administrador
        conn = psycopg2.connect(
            user=DB_ADMIN_USER,
            password=DB_ADMIN_PASS,
            host=DB_HOST,
            port=DB_PORT,
            database="postgres" # Conecta ao banco padrão para criar o novo
        )
        conn.autocommit = True
        cur = conn.cursor()

        print(f"--- Iniciando configuração do banco de dados ---")

        # 2. Criar o Usuário se não existir
        cur.execute(sql.SQL("SELECT 1 FROM pg_roles WHERE rolname = %s"), [APP_DB_USER])
        if not cur.fetchone():
            cur.execute(sql.SQL("CREATE USER {} WITH PASSWORD %s").format(sql.Identifier(APP_DB_USER)), [APP_DB_PASS])
            print(f"Usuário '{APP_DB_USER}' criado.")
        else:
            print(f"Usuário '{APP_DB_USER}' já existe.")

        # 3. Criar o Banco de Dados se não existir
        cur.execute(sql.SQL("SELECT 1 FROM pg_database WHERE datname = %s"), [APP_DB_NAME])
        if not cur.fetchone():
            cur.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(APP_DB_NAME), 
                sql.Identifier(APP_DB_USER)
            ))
            print(f"Banco de dados '{APP_DB_NAME}' criado.")
        else:
            print(f"Banco de dados '{APP_DB_NAME}' já existe.")

        cur.close()
        conn.close()
        print(f"--- Configuração concluída com sucesso! ---")
        print(f"\nSua URL de conexão será: postgresql://{APP_DB_USER}:{APP_DB_PASS}@{DB_HOST}:{DB_PORT}/{APP_DB_NAME}")
        
    except Exception as e:
        print(f"Erro ao configurar o banco: {e}")
        print("\nVerifique se o PostgreSQL está rodando e se as credenciais de administrador no topo deste script estão corretas.")

if __name__ == "__main__":
    setup_postgresql()
