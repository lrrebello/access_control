from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    is_approved = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relacionamentos
    workstations = db.relationship('WorkstationUser', back_populates='user', cascade='all, delete-orphan')
    active_workstation_id = db.Column(db.Integer, db.ForeignKey('workstation.id'), nullable=True)
    active_workstation = db.relationship('Workstation', foreign_keys=[active_workstation_id])
    
    @property
    def current_workstation(self):
        """Retorna o posto de trabalho ativo do usuário"""
        if self.active_workstation_id:
            return Workstation.query.get(self.active_workstation_id)
        return None
    
    @property
    def accessible_workstations(self):
        """Retorna lista de postos que o usuário pode acessar"""
        from datetime import date
        today = date.today()
        return [wu.workstation for wu in self.workstations if wu.is_active and wu.start_date <= today <= wu.end_date]


class Workstation(db.Model):
    """Posto de Trabalho (ex: Portaria 1, Portaria 2, etc)"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(255))
    location = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relacionamentos
    users = db.relationship('WorkstationUser', back_populates='workstation', cascade='all, delete-orphan')
    access_logs = db.relationship('AccessLog', back_populates='workstation')
    
    def __repr__(self):
        return f"<Workstation {self.name}>"
    
    @property
    def active_users(self):
        """Usuários ativos neste posto"""
        from datetime import date
        today = date.today()
        return [wu.user for wu in self.users if wu.is_active and wu.start_date <= today <= wu.end_date]
    
    @property
    def open_access_logs(self):
        """Registros em aberto (sem saída) deste posto"""
        return AccessLog.query.filter(
            AccessLog.workstation_id == self.id,
            AccessLog.exit_time == None
        ).all()


class WorkstationUser(db.Model):
    """Relacionamento entre usuários e postos com período de validade"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    workstation_id = db.Column(db.Integer, db.ForeignKey('workstation.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False, default=datetime.now().date)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relacionamentos
    user = db.relationship('User', back_populates='workstations')
    workstation = db.relationship('Workstation', back_populates='users')
    
    def __repr__(self):
        return f"<WorkstationUser {self.user.username} - {self.workstation.name}>"
    
    @property
    def is_valid(self):
        """Verifica se o acesso ainda é válido"""
        today = datetime.now().date()
        return self.is_active and self.start_date <= today <= self.end_date


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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    workstation_id = db.Column(db.Integer, db.ForeignKey('workstation.id'), nullable=True)
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
    
    # Relacionamentos
    user = db.relationship('User', backref='access_logs')
    workstation = db.relationship('Workstation', back_populates='access_logs')
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