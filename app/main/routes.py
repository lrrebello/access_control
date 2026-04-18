from flask import render_template, url_for, flash, redirect, request, jsonify
from app import db
from app.models import AccessLog, AuthorizedVehicle, AuthorizedTrailer, AuthorizedDriver, Companion
from app.main import main
from flask_login import login_required, current_user
from datetime import datetime

# ====================== DASHBOARD ======================
@main.route("/")
@main.route("/dashboard")
@login_required
def dashboard():
    filter_type = request.args.get('filter', 'active')
    search_query = request.args.get('search', '').strip()
    
    query = AccessLog.query
    
    # Filtrar por usuário - ADMINS veem tudo, outros veem só seus registros
    if not current_user.is_admin:
        query = query.filter(AccessLog.user_id == current_user.id)
    
    if search_query:
        query = query.filter(
            (AccessLog.vehicle_plate.ilike(f'%{search_query}%')) |
            (AccessLog.driver_name.ilike(f'%{search_query}%')) |
            (AccessLog.company.ilike(f'%{search_query}%'))
        )

    if filter_type == 'active':
        logs = query.filter(AccessLog.exit_time == None).order_by(AccessLog.entry_time.desc()).all()
    elif filter_type == 'finished':
        logs = query.filter(AccessLog.exit_time != None).order_by(AccessLog.exit_time.desc()).all()
    else:
        logs = query.order_by(AccessLog.entry_time.desc()).all()

    # CORRIGIDO: Filtrar ativos pelo usuário atual
    active_query = AccessLog.query.filter(AccessLog.exit_time == None)
    if not current_user.is_admin:
        active_query = active_query.filter(AccessLog.user_id == current_user.id)
    active_logs = active_query.all()
    total_vehicles_inside = len(active_logs)
    people_inside = sum(log.total_people for log in active_logs)

    # CORRIGIDO: Contagem de saídas de HOJE pelo usuário atual
    today = datetime.now().date()
    today_exits_query = AccessLog.query.filter(db.func.date(AccessLog.exit_time) == today)
    if not current_user.is_admin:
        today_exits_query = today_exits_query.filter(AccessLog.user_id == current_user.id)
    today_exits = today_exits_query.count()
    
    # CORRIGIDO: Pessoas controladas hoje pelo usuário atual
    today_movements_query = AccessLog.query.filter(
        (db.func.date(AccessLog.entry_time) == today) | 
        (db.func.date(AccessLog.exit_time) == today)
    )
    if not current_user.is_admin:
        today_movements_query = today_movements_query.filter(AccessLog.user_id == current_user.id)
    today_movements = today_movements_query.all()
    daily_people = sum(log.total_people for log in today_movements)

    auth_vehicles = AuthorizedVehicle.query.all()
    auth_trailers = AuthorizedTrailer.query.all()
    auth_drivers = AuthorizedDriver.query.all()

    return render_template('main/dashboard.html', 
                           logs=logs, 
                           total_vehicles=total_vehicles_inside,
                           people_inside=people_inside,
                           today_exits=today_exits,
                           daily_people=daily_people,
                           auth_vehicles=auth_vehicles,
                           auth_trailers=auth_trailers,
                           auth_drivers=auth_drivers,
                           filter_type=filter_type,
                           search_query=search_query,
                           now=datetime.now())  # <-- ADICIONE ESTA LINHA)


# ====================== REGISTRO DE ACESSO ======================
@main.route("/access/new", methods=['POST'])
@login_required
def new_access():
    vehicle_type = request.form.get('vehicle_type')
    driver_name = request.form.get('driver_name', '').strip()
    
    # Tratamento especial para pedestres
    if vehicle_type == 'pedestre':
        # Para pedestre, a matrícula é automática
        vehicle_plate = 'PEDESTRE'
        trailer_plate = None
        company = request.form.get('company', '').strip() or 'Não informada'
    else:
        # Para veículos normais
        vehicle_plate = request.form.get('vehicle_plate', '').upper().strip()
        trailer_plate = request.form.get('trailer_plate', '').upper().strip() or None
        company = request.form.get('company', '').strip()
    
    # Validações básicas
    if vehicle_type != 'pedestre' and not vehicle_plate:
        flash('Matrícula do veículo é obrigatória!', 'danger')
        return redirect(url_for('main.dashboard'))
    
    if not driver_name:
        flash('Nome do condutor é obrigatório!', 'danger')
        return redirect(url_for('main.dashboard'))
    
    if not request.form.get('driver_doc'):
        flash('Documento do condutor é obrigatório!', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Alertas de vencimento (apenas para veículos normais)
    alert_msg = ""
    today = datetime.now().date()

    if vehicle_type != 'pedestre':
        auth_v = AuthorizedVehicle.query.filter_by(plate=vehicle_plate).first()
        if auth_v and auth_v.expiry_date and auth_v.expiry_date < today:
            alert_msg += f"VEÍCULO VENCIDO ({auth_v.expiry_date.strftime('%d/%m/%Y')}). "

    if trailer_plate:
        auth_t = AuthorizedTrailer.query.filter_by(plate=trailer_plate).first()
        if auth_t and auth_t.expiry_date and auth_t.expiry_date < today:
            alert_msg += f"REBOQUE VENCIDO ({auth_t.expiry_date.strftime('%d/%m/%Y')}). "

    auth_d = AuthorizedDriver.query.filter_by(name=driver_name).first()
    if auth_d and auth_d.expiry_date and auth_d.expiry_date < today:
        alert_msg += f"CONDUTOR VENCIDO ({auth_d.expiry_date.strftime('%d/%m/%Y')}). "

    # Criar o registro de acesso
    log = AccessLog(
        user_id=current_user.id,
        vehicle_plate=vehicle_plate,
        trailer_plate=trailer_plate,
        vehicle_type=vehicle_type,
        driver_name=driver_name,
        driver_doc=request.form.get('driver_doc'),
        company=company,
        observations=request.form.get('observations'),
        alert_msg=alert_msg if alert_msg else None
    )
    db.session.add(log)
    db.session.flush()  # Para obter o ID do log antes de adicionar acompanhantes

    # Processar acompanhantes dinâmicos
    companion_names = request.form.getlist('companion_name[]')
    companion_docs = request.form.getlist('companion_doc[]')
    
    for name, doc in zip(companion_names, companion_docs):
        if name and doc:  # Só adiciona se ambos forem preenchidos
            companion = Companion(
                access_log_id=log.id,
                name=name.strip(),
                document=doc.strip()
            )
            db.session.add(companion)

    db.session.commit()
    
    total_people = 1 + len([n for n in companion_names if n])
    
    # Mensagem personalizada para pedestre
    if vehicle_type == 'pedestre':
        flash_msg = f'🚶 Pedestre registrado com sucesso! Total de pessoas: {total_people}'
    else:
        flash_msg = f'🚗 Veículo {vehicle_plate} registrado com sucesso! Total de pessoas: {total_people}'
    
    if alert_msg:
        flash(f'{flash_msg} | ⚠️ {alert_msg}', 'warning')
    else:
        flash(flash_msg, 'success')
    
    return redirect(url_for('main.dashboard'))


# ====================== MARCAR SAÍDA ======================
@main.route("/access/exit/<int:log_id>")
@login_required
def mark_exit(log_id):
    log = AccessLog.query.get_or_404(log_id)
    if not log.exit_time:
        log.exit_time = datetime.now()
        db.session.commit()
        flash('Saída registrada com sucesso!', 'success')
    return redirect(url_for('main.dashboard'))


# ====================== REMOVER SAÍDA ======================
@main.route("/access/remove_exit/<int:log_id>")
@login_required
def remove_exit(log_id):
    log = AccessLog.query.get_or_404(log_id)
    if log.exit_time:
        log.exit_time = None
        db.session.commit()
        flash('Saída removida! O veículo voltou para a lista de ativos.', 'warning')
    return redirect(url_for('main.dashboard'))


# ====================== EDITAR REGISTRO COMPLETO ======================
@main.route("/access/edit/<int:log_id>", methods=['GET', 'POST'])
@login_required
def edit_access(log_id):
    log = AccessLog.query.get_or_404(log_id)
    
    if request.method == 'POST':
        # Atualizar campos principais
        log.vehicle_plate = request.form.get('vehicle_plate', '').upper().strip()
        log.trailer_plate = request.form.get('trailer_plate', '').upper().strip() or None
        log.vehicle_type = request.form.get('vehicle_type')
        log.driver_name = request.form.get('driver_name', '').strip()
        log.driver_doc = request.form.get('driver_doc', '').strip()
        log.company = request.form.get('company', '').strip()
        log.observations = request.form.get('observations', '').strip() or None
        
        # Verificar se a saída foi marcada/desmarcada no formulário
        exit_status = request.form.get('exit_status')
        if exit_status == 'checked_out' and not log.exit_time:
            log.exit_time = datetime.now()
        elif exit_status == 'still_inside':
            log.exit_time = None
        
        # Remover acompanhantes existentes
        for companion in log.companions:
            db.session.delete(companion)
        
        # Adicionar novos acompanhantes
        companion_names = request.form.getlist('companion_name[]')
        companion_docs = request.form.getlist('companion_doc[]')
        
        for name, doc in zip(companion_names, companion_docs):
            if name and doc:
                companion = Companion(
                    access_log_id=log.id,
                    name=name.strip(),
                    document=doc.strip()
                )
                db.session.add(companion)
        
        # Recalcular alertas de vencimento
        alert_msg = ""
        today = datetime.now().date()
        
        auth_v = AuthorizedVehicle.query.filter_by(plate=log.vehicle_plate).first()
        if auth_v and auth_v.expiry_date and auth_v.expiry_date < today:
            alert_msg += f"VEÍCULO VENCIDO ({auth_v.expiry_date.strftime('%d/%m/%Y')}). "
        
        if log.trailer_plate:
            auth_t = AuthorizedTrailer.query.filter_by(plate=log.trailer_plate).first()
            if auth_t and auth_t.expiry_date and auth_t.expiry_date < today:
                alert_msg += f"REBOQUE VENCIDO ({auth_t.expiry_date.strftime('%d/%m/%Y')}). "
        
        auth_d = AuthorizedDriver.query.filter_by(name=log.driver_name).first()
        if auth_d and auth_d.expiry_date and auth_d.expiry_date < today:
            alert_msg += f"CONDUTOR VENCIDO ({auth_d.expiry_date.strftime('%d/%m/%Y')}). "
        
        log.alert_msg = alert_msg if alert_msg else None
        
        db.session.commit()
        flash('Registro atualizado com sucesso!', 'success')
        return redirect(url_for('main.dashboard'))
    
    # GET - mostrar formulário de edição
    auth_vehicles = AuthorizedVehicle.query.all()
    auth_trailers = AuthorizedTrailer.query.all()
    auth_drivers = AuthorizedDriver.query.all()
    
    return render_template('main/edit_access.html', 
                           log=log,
                           auth_vehicles=auth_vehicles,
                           auth_trailers=auth_trailers,
                           auth_drivers=auth_drivers)


# ====================== GESTÃO (Lista + Novo) ======================
@main.route("/management", methods=['GET', 'POST'])
@login_required
def management():
    if request.method == 'POST':
        m_type = request.form.get('type')
        expiry_str = request.form.get('expiry_date')
        expiry = datetime.strptime(expiry_str, '%Y-%m-%d').date() if expiry_str else None

        if m_type == 'vehicle':
            plate = request.form.get('vehicle_plate', '').upper().strip()
            vehicle_type = request.form.get('vehicle_type')
            company = request.form.get('company')
            
            if not plate:
                flash('A matrícula do veículo é obrigatória!', 'danger')
                return redirect(url_for('main.management'))
            
            new_item = AuthorizedVehicle(
                plate=plate,
                vehicle_type=vehicle_type,
                company=company,
                expiry_date=expiry
            )
            db.session.add(new_item)
            db.session.commit()
            flash('Veículo cadastrado com sucesso!', 'success')
            
        elif m_type == 'trailer':
            plate = request.form.get('trailer_plate', '').upper().strip()
            company = request.form.get('company')
            
            print(f"DEBUG: plate='{plate}', company='{company}'")  # Debug
            
            if not plate:
                flash('A matrícula do reboque é obrigatória!', 'danger')
                return redirect(url_for('main.management'))
            
            new_item = AuthorizedTrailer(
                plate=plate,
                company=company,
                expiry_date=expiry
            )
            db.session.add(new_item)
            db.session.commit()
            flash('Reboque cadastrado com sucesso!', 'success')
            
        elif m_type == 'driver':
            name = request.form.get('driver_name')
            document = request.form.get('driver_document')
            company = request.form.get('company')
            
            if not name or not document:
                flash('Nome e documento do condutor são obrigatórios!', 'danger')
                return redirect(url_for('main.management'))
            
            new_item = AuthorizedDriver(
                name=name,
                document=document,
                company=company,
                expiry_date=expiry
            )
            db.session.add(new_item)
            db.session.commit()
            flash('Condutor cadastrado com sucesso!', 'success')
            
        else:
            flash('Tipo inválido.', 'danger')
            return redirect(url_for('main.management'))

        return redirect(url_for('main.management'))

    vehicles = AuthorizedVehicle.query.order_by(AuthorizedVehicle.plate).all()
    trailers = AuthorizedTrailer.query.order_by(AuthorizedTrailer.plate).all()
    drivers = AuthorizedDriver.query.order_by(AuthorizedDriver.name).all()

    return render_template('main/management.html', 
                           vehicles=vehicles, 
                           trailers=trailers, 
                           drivers=drivers)


# ====================== EDIÇÃO DE AUTORIZADOS ======================
@main.route("/management/edit/<string:item_type>/<int:id>", methods=['GET', 'POST'])
@login_required
def edit_authorized(item_type, id):
    if item_type == 'vehicle':
        item = AuthorizedVehicle.query.get_or_404(id)
        title = "Editar Veículo"
    elif item_type == 'trailer':
        item = AuthorizedTrailer.query.get_or_404(id)
        title = "Editar Reboque"
    elif item_type == 'driver':
        item = AuthorizedDriver.query.get_or_404(id)
        title = "Editar Condutor"
    else:
        flash('Tipo inválido.', 'danger')
        return redirect(url_for('main.management'))

    if request.method == 'POST':
        expiry_str = request.form.get('expiry_date')
        expiry = datetime.strptime(expiry_str, '%Y-%m-%d').date() if expiry_str else None

        if item_type == 'vehicle':
            item.plate = request.form.get('plate', '').upper().strip()
            item.vehicle_type = request.form.get('vehicle_type')
            item.company = request.form.get('company')
            item.expiry_date = expiry
        elif item_type == 'trailer':
            item.plate = request.form.get('plate', '').upper().strip()
            item.company = request.form.get('company')
            item.expiry_date = expiry
        elif item_type == 'driver':
            item.name = request.form.get('name')
            item.document = request.form.get('document')
            item.company = request.form.get('company')
            item.expiry_date = expiry

        db.session.commit()
        flash(f'{title} atualizado com sucesso!', 'success')
        return redirect(url_for('main.management'))

    # GET - mostra o formulário preenchido
    return render_template('main/edit_authorized.html', 
                           item=item, 
                           item_type=item_type, 
                           title=title)