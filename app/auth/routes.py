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
        user = User(username=username, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Sua conta foi criada! Agora você pode fazer o login.', 'success')
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
