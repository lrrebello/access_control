from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)

# ==================== TABELAS DE AUTORIZAÇÃO ====================

class AuthorizedVehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate = db.Column(db.String(20), unique=True, nullable=False)
    vehicle_type = db.Column(db.String(20), nullable=False)
    company = db.Column(db.String(100))
    expiry_date = db.Column(db.Date)

    def __repr__(self):
        return f"<AuthorizedVehicle {self.plate}>"


class AuthorizedTrailer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate = db.Column(db.String(20), unique=True, nullable=False)
    company = db.Column(db.String(100))
    expiry_date = db.Column(db.Date)

    def __repr__(self):
        return f"<AuthorizedTrailer {self.plate}>"


class AuthorizedDriver(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    document = db.Column(db.String(50), nullable=False)
    company = db.Column(db.String(100))
    expiry_date = db.Column(db.Date)

    def __repr__(self):
        return f"<AuthorizedDriver {self.name}>"

# ==================== ACOMPANHANTES ====================

class Companion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    access_log_id = db.Column(db.Integer, db.ForeignKey('access_log.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    document = db.Column(db.String(50), nullable=False)
    
    # Relacionamento
    access_log = db.relationship('AccessLog', back_populates='companions')

    def __repr__(self):
        return f"<Companion {self.name}>"

# ==================== REGISTRO DE ACESSO ====================

class AccessLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_plate = db.Column(db.String(20), nullable=False)
    trailer_plate = db.Column(db.String(20))
    vehicle_type = db.Column(db.String(20), nullable=False)
    driver_name = db.Column(db.String(100), nullable=False)
    driver_doc = db.Column(db.String(50), nullable=False)
    company = db.Column(db.String(100), nullable=False)
    entry_time = db.Column(db.DateTime, nullable=False, default=datetime.now)
    exit_time = db.Column(db.DateTime)
    observations = db.Column(db.Text)
    alert_msg = db.Column(db.String(255))
    
    # Relacionamento com acompanhantes
    companions = db.relationship('Companion', back_populates='access_log', cascade='all, delete-orphan')

    @property
    def total_people(self):
        """Total de pessoas (motorista + acompanhantes)"""
        return 1 + len(self.companions)
    
    @property
    def companions_list(self):
        """Retorna lista de dicionários com os acompanhantes"""
        return [{'name': c.name, 'document': c.document} for c in self.companions]
    
    @property
    def duration(self):
        if self.exit_time:
            diff = self.exit_time - self.entry_time
        else:
            diff = datetime.now() - self.entry_time
        
        days = diff.days
        hours, remainder = divmod(diff.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        return f"{hours}h {minutes}m"