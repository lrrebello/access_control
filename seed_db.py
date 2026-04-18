from app import create_app, db, bcrypt
from app.models import User, AccessLog, AuthorizedVehicle, AuthorizedDriver, AuthorizedTrailer
from datetime import datetime, timedelta
import os

# Forçamos a URL para garantir que o seed vá para o banco correto
os.environ['DATABASE_URL'] = "postgresql://ecclesia_user:368614011932lu@localhost:5432/access_db"

app = create_app()

def seed():
    with app.app_context():
        print("--- Inicializando Banco de Dados (access_db) ---")
        db.create_all()
        
        # 1. Criar usuário administrador inicial
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            hashed_pw = bcrypt.generate_password_hash('admin123').decode('utf-8')
            admin = User(username='admin', password=hashed_pw)
            db.session.add(admin)
            print("Usuário 'admin' criado (Senha: admin123)")
        
        # 2. Criar alguns registros de exemplo de autorização (vencidos e válidos)
        today = datetime.now().date()
        
        # Veículo Válido
        if not AuthorizedVehicle.query.filter_by(plate="VIG-2026").first():
            v1 = AuthorizedVehicle(plate="VIG-2026", vehicle_type="ligeiro", company="Segurança Total", expiry_date=today + timedelta(days=30))
            db.session.add(v1)
            
        # Veículo Vencido
        if not AuthorizedVehicle.query.filter_by(plate="OLD-1990").first():
            v2 = AuthorizedVehicle(plate="OLD-1990", vehicle_type="pesado", company="Transportes Antigos", expiry_date=today - timedelta(days=5))
            db.session.add(v2)
            
        # Condutor Autorizado
        if not AuthorizedDriver.query.filter_by(name="Lucas Vigilante").first():
            d1 = AuthorizedDriver(name="Lucas Vigilante", document="RG-123456", company="Vigilância Ativa", expiry_date=today + timedelta(days=365))
            db.session.add(d1)

        db.session.commit()
        print("--- Seed concluído com sucesso! ---")

if __name__ == "__main__":
    seed()
