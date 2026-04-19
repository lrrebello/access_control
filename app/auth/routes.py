from flask import render_template, url_for, flash, redirect, request, jsonify
from app import db, bcrypt
from app.models import User, Workstation, WorkstationUser
from app.auth import auth
from flask_login import login_user, current_user, logout_user, login_required
from datetime import datetime, timedelta


@auth.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('Por favor, preencha todos os campos.', 'warning')
            return redirect(url_for('auth.register'))
        
        user_exists = User.query.filter_by(username=username).first()
        if user_exists:
            flash('Este nome de usuário já está em uso.', 'danger')
            return redirect(url_for('auth.register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, password=hashed_password, is_approved=False, is_admin=False)
        db.session.add(user)
        db.session.commit()
        
        flash('Sua conta foi criada! Aguarde a aprovação do administrador para fazer login.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', title='Cadastro')

@auth.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # Se já tem posto ativo, vai direto
        if current_user.active_workstation_id:
            return redirect(url_for('main.dashboard'))
        return redirect(url_for('auth.select_workstation'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and bcrypt.check_password_hash(user.password, password):
            if not user.is_approved:
                flash('Sua conta aguarda aprovação do administrador.', 'warning')
                return redirect(url_for('auth.login'))
            login_user(user)
            
            # Verificar se usuário tem postos disponíveis
            if user.accessible_workstations:
                return redirect(url_for('auth.select_workstation'))
            else:
                flash('Você não tem nenhum posto de trabalho associado. Contate o administrador.', 'warning')
                return redirect(url_for('auth.logout'))
        else:
            flash('Falha no login. Verifique o usuário e a senha.', 'danger')
    return render_template('auth/login.html', title='Login')

@auth.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth.route("/select-workstation", methods=['GET', 'POST'])
@login_required
def select_workstation():
    workstations = current_user.accessible_workstations
    
    if request.method == 'POST':
        workstation_id = request.form.get('workstation_id')
        workstation = Workstation.query.get_or_404(workstation_id)
        
        # Verificar se usuário tem permissão
        if workstation not in current_user.accessible_workstations:
            flash('Você não tem permissão para acessar este posto.', 'danger')
            return redirect(url_for('auth.select_workstation'))
        
        current_user.active_workstation_id = workstation.id
        db.session.commit()
        
        flash(f'Você está operando no posto: {workstation.name}', 'success')
        return redirect(url_for('main.dashboard'))
    
    return render_template('auth/select_workstation.html', workstations=workstations)

@auth.route("/switch-workstation", methods=['POST'])
@login_required
def switch_workstation():
    workstation_id = request.form.get('workstation_id')
    workstation = Workstation.query.get_or_404(workstation_id)
    
    if workstation not in current_user.accessible_workstations:
        flash('Você não tem permissão para acessar este posto.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    current_user.active_workstation_id = workstation.id
    db.session.commit()
    
    flash(f'Posto alterado para: {workstation.name}', 'success')
    return redirect(url_for('main.dashboard'))

# Rotas de administração
@auth.route("/admin/users")
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('auth/admin_users.html', users=users)

@auth.route("/admin/approve/<int:user_id>")
@login_required
def approve_user(user_id):
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    flash(f'Usuário {user.username} foi aprovado!', 'success')
    return redirect(url_for('auth.admin_users'))

@auth.route("/admin/revoke/<int:user_id>")
@login_required
def revoke_user(user_id):
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Você não pode revogar seu próprio acesso.', 'danger')
        return redirect(url_for('auth.admin_users'))
    
    user.is_approved = False
    db.session.commit()
    flash(f'Usuário {user.username} foi bloqueado!', 'warning')
    return redirect(url_for('auth.admin_users'))

@auth.route("/admin/make_admin/<int:user_id>")
@login_required
def make_admin(user_id):
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Você já é administrador.', 'info')
        return redirect(url_for('auth.admin_users'))
    
    user.is_admin = True
    db.session.commit()
    flash(f'Usuário {user.username} agora é administrador!', 'success')
    return redirect(url_for('auth.admin_users'))

@auth.route("/admin/delete/<int:user_id>")
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('Você não pode excluir sua própria conta!', 'danger')
        return redirect(url_for('auth.admin_users'))
    
    if user.is_admin and user.id == 1:
        flash('Este é o administrador principal e não pode ser excluído!', 'danger')
        return redirect(url_for('auth.admin_users'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    flash(f'Usuário "{username}" foi excluído permanentemente!', 'success')
    return redirect(url_for('auth.admin_users'))

# ==================== ROTAS DE POSTOS DE TRABALHO (ADMIN) ====================

@auth.route("/admin/workstations")
@login_required
def admin_workstations():
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    workstations = Workstation.query.order_by(Workstation.name).all()
    return render_template('auth/admin_workstations.html', workstations=workstations)

@auth.route("/admin/workstation/add", methods=['GET', 'POST'])
@login_required
def add_workstation():
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        location = request.form.get('location')
        
        if Workstation.query.filter_by(name=name).first():
            flash('Já existe um posto com este nome.', 'danger')
            return redirect(url_for('auth.add_workstation'))
        
        workstation = Workstation(
            name=name,
            description=description,
            location=location
        )
        db.session.add(workstation)
        db.session.commit()
        flash(f'Posto "{name}" criado com sucesso!', 'success')
        return redirect(url_for('auth.admin_workstations'))
    
    return render_template('auth/add_workstation.html')

@auth.route("/admin/workstation/edit/<int:id>", methods=['GET', 'POST'])
@login_required
def edit_workstation(id):
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    workstation = Workstation.query.get_or_404(id)
    
    if request.method == 'POST':
        workstation.name = request.form.get('name')
        workstation.description = request.form.get('description')
        workstation.location = request.form.get('location')
        workstation.is_active = 'is_active' in request.form
        
        db.session.commit()
        flash(f'Posto "{workstation.name}" atualizado!', 'success')
        return redirect(url_for('auth.admin_workstations'))
    
    return render_template('auth/edit_workstation.html', workstation=workstation)

@auth.route("/admin/workstation/delete/<int:id>")
@login_required
def delete_workstation(id):
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    workstation = Workstation.query.get_or_404(id)
    name = workstation.name
    db.session.delete(workstation)
    db.session.commit()
    flash(f'Posto "{name}" excluído!', 'success')
    return redirect(url_for('auth.admin_workstations'))

@auth.route("/admin/workstation/users/<int:id>")
@login_required
def workstation_users(id):
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    workstation = Workstation.query.get_or_404(id)
    users = User.query.filter(User.is_approved == True).order_by(User.username).all()
    assignments = WorkstationUser.query.filter_by(workstation_id=id).all()
    
    now = datetime.now()
    next_year = now + timedelta(days=365)
    
    return render_template('auth/workstation_users.html', 
                          workstation=workstation, 
                          users=users, 
                          assignments=assignments,
                          now=now,
                          next_year=next_year)  # <-- USANDO next_year

@auth.route("/admin/workstation/add_user", methods=['POST'])
@login_required
def add_workstation_user():
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    user_id = request.form.get('user_id')
    workstation_id = request.form.get('workstation_id')
    start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
    end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
    
    existing = WorkstationUser.query.filter_by(
        user_id=user_id, 
        workstation_id=workstation_id
    ).first()
    
    if existing:
        existing.start_date = start_date
        existing.end_date = end_date
        existing.is_active = True
    else:
        assignment = WorkstationUser(
            user_id=user_id,
            workstation_id=workstation_id,
            start_date=start_date,
            end_date=end_date
        )
        db.session.add(assignment)
    
    db.session.commit()
    flash('Usuário associado ao posto com sucesso!', 'success')
    return redirect(url_for('auth.workstation_users', id=workstation_id))

@auth.route("/admin/workstation/remove_user/<int:id>")
@login_required
def remove_workstation_user(id):
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    assignment = WorkstationUser.query.get_or_404(id)
    workstation_id = assignment.workstation_id
    
    # Se o usuário estava ativo neste posto, limpar
    user = assignment.user
    if user.active_workstation_id == workstation_id:
        user.active_workstation_id = None
    
    db.session.delete(assignment)
    db.session.commit()
    flash('Usuário removido do posto!', 'success')
    return redirect(url_for('auth.workstation_users', id=workstation_id))