from flask import render_template, url_for, flash, redirect, request
from app import db, bcrypt
from app.models import User
from app.auth import auth
from flask_login import login_user, current_user, logout_user, login_required

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
        # Novo usuário precisa de aprovação
        user = User(username=username, password=hashed_password, is_approved=False, is_admin=False)
        db.session.add(user)
        db.session.commit()
        
        flash('Sua conta foi criada! Aguarde a aprovação do administrador para fazer login.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', title='Cadastro')

@auth.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and bcrypt.check_password_hash(user.password, password):
            if not user.is_approved:
                flash('Sua conta aguarda aprovação do administrador.', 'warning')
                return redirect(url_for('auth.login'))
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
        else:
            flash('Falha no login. Verifique o usuário e a senha.', 'danger')
    return render_template('auth/login.html', title='Login')

@auth.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

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