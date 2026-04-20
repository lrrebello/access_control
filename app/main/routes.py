from flask import render_template, url_for, flash, redirect, request, jsonify
from app import db
from app.models import AccessLog, AuthorizedVehicle, AuthorizedTrailer, AuthorizedDriver, Companion, Workstation
from app.main import main
from flask_login import login_required, current_user
from datetime import datetime

# ====================== DASHBOARD ======================
@main.route("/")
@main.route("/dashboard")
@login_required
def dashboard():
    # Garantir que o usuário tem um posto ativo
    if not current_user.active_workstation_id:
        return redirect(url_for('auth.select_workstation'))
    
    filter_type = request.args.get('filter', 'active')
    search_query = request.args.get('search', '').strip()
    
    today = datetime.now().date()
    workstation_id = current_user.active_workstation_id
    
    query = AccessLog.query
    
    # Filtrar por posto de trabalho
    query = query.filter(AccessLog.workstation_id == workstation_id)
    
    # Admins veem tudo do posto, outros veem só seus registros
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
        logs = query.filter(
            AccessLog.exit_time != None,
            db.func.date(AccessLog.exit_time) == today
        ).order_by(AccessLog.exit_time.desc()).all()
    else:
        logs = query.order_by(AccessLog.entry_time.desc()).all()
    
    # CORRIGIDO: Separar veículos e pedestres
    active_query = AccessLog.query.filter(
        AccessLog.exit_time == None,
        AccessLog.workstation_id == workstation_id
    )
    active_logs = active_query.all()
    
    # Apenas veículos (excluindo pedestres) para o card "Veículos no Local"
    vehicles_inside = [log for log in active_logs if log.vehicle_type != 'pedestre']
    total_vehicles_inside = len(vehicles_inside)  # <-- CORRIGIDO: só veículos
    
    # Total de pessoas (motorista + acompanhantes de TODOS, incluindo pedestres)
    people_inside = sum(log.total_people for log in active_logs)
    
    # Apenas pedestres (para detalhamento opcional)
    pedestrians_inside = [log for log in active_logs if log.vehicle_type == 'pedestre']
    total_pedestrians_only = len(pedestrians_inside)
    
    today_exits = AccessLog.query.filter(
        AccessLog.exit_time != None,
        db.func.date(AccessLog.exit_time) == today,
        AccessLog.workstation_id == workstation_id
    ).count()
    
    today_entries = AccessLog.query.filter(
        db.func.date(AccessLog.entry_time) == today,
        AccessLog.workstation_id == workstation_id
    ).count()
    
    # Entradas separadas por tipo
    today_vehicles_entries = AccessLog.query.filter(
        db.func.date(AccessLog.entry_time) == today,
        AccessLog.workstation_id == workstation_id,
        AccessLog.vehicle_type != 'pedestre'
    ).count()
    
    today_pedestrians_entries = AccessLog.query.filter(
        db.func.date(AccessLog.entry_time) == today,
        AccessLog.workstation_id == workstation_id,
        AccessLog.vehicle_type == 'pedestre'
    ).count()
    
    auth_vehicles = AuthorizedVehicle.query.all()
    auth_trailers = AuthorizedTrailer.query.all()
    auth_drivers = AuthorizedDriver.query.all()
    
    return render_template('main/dashboard.html', 
                           logs=logs, 
                           total_vehicles=total_vehicles_inside,  # <-- AGORA SÓ VEÍCULOS
                           total_pedestrians=total_pedestrians_only,
                           people_inside=people_inside,
                           today_exits=today_exits,
                           today_entries=today_entries,
                           today_vehicles_entries=today_vehicles_entries,
                           today_pedestrians_entries=today_pedestrians_entries,
                           auth_vehicles=auth_vehicles,
                           auth_trailers=auth_trailers,
                           auth_drivers=auth_drivers,
                           filter_type=filter_type,
                           search_query=search_query,
                           now=datetime.now())

# ====================== REGISTRO DE ACESSO ======================
@main.route("/access/new", methods=['POST'])
@login_required
def new_access():
    if not current_user.active_workstation_id:
        flash('Selecione um posto de trabalho primeiro.', 'warning')
        return redirect(url_for('auth.select_workstation'))
    
    vehicle_type = request.form.get('vehicle_type')
    driver_name = request.form.get('driver_name', '').strip()
    
    if vehicle_type == 'pedestre':
        vehicle_plate = 'PEDESTRE'
        trailer_plate = None
        company = request.form.get('company', '').strip() or 'Não informada'
    else:
        vehicle_plate = request.form.get('vehicle_plate', '').upper().strip()
        trailer_plate = request.form.get('trailer_plate', '').upper().strip() or None
        company = request.form.get('company', '').strip()
    
    if vehicle_type != 'pedestre' and not vehicle_plate:
        flash('Matrícula do veículo é obrigatória!', 'danger')
        return redirect(url_for('main.dashboard'))
    
    if not driver_name:
        flash('Nome do condutor é obrigatório!', 'danger')
        return redirect(url_for('main.dashboard'))
    
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

    log = AccessLog(
        user_id=current_user.id,
        workstation_id=current_user.active_workstation_id,
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
    db.session.flush()

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

    db.session.commit()
    
    total_people = 1 + len([n for n in companion_names if n])
    
    if vehicle_type == 'pedestre':
        flash_msg = f'🚶 Pedestre registrado! Total: {total_people} pessoas'
    else:
        flash_msg = f'🚗 Veículo {vehicle_plate} registrado! Total: {total_people} pessoas'
    
    if alert_msg:
        flash(f'{flash_msg} | ⚠️ {alert_msg}', 'warning')
    else:
        flash(flash_msg, 'success')
    
    return redirect(url_for('main.dashboard'))


@main.route("/access/exit/<int:log_id>")
@login_required
def mark_exit(log_id):
    log = AccessLog.query.get_or_404(log_id)
    if not log.exit_time:
        log.exit_time = datetime.now()
        db.session.commit()
        flash('Saída registrada com sucesso!', 'success')
    return redirect(url_for('main.dashboard'))


@main.route("/access/remove_exit/<int:log_id>")
@login_required
def remove_exit(log_id):
    log = AccessLog.query.get_or_404(log_id)
    if log.exit_time:
        log.exit_time = None
        db.session.commit()
        flash('Saída removida! O veículo voltou para a lista de ativos.', 'warning')
    return redirect(url_for('main.dashboard'))


@main.route("/access/edit/<int:log_id>", methods=['GET', 'POST'])
@login_required
def edit_access(log_id):
    log = AccessLog.query.get_or_404(log_id)
    
    if request.method == 'POST':
        log.vehicle_plate = request.form.get('vehicle_plate', '').upper().strip()
        log.trailer_plate = request.form.get('trailer_plate', '').upper().strip() or None
        log.vehicle_type = request.form.get('vehicle_type')
        log.driver_name = request.form.get('driver_name', '').strip()
        log.driver_doc = request.form.get('driver_doc', '').strip()
        log.company = request.form.get('company', '').strip()
        log.observations = request.form.get('observations', '').strip() or None
        
        exit_status = request.form.get('exit_status')
        if exit_status == 'checked_out' and not log.exit_time:
            log.exit_time = datetime.now()
        elif exit_status == 'still_inside':
            log.exit_time = None
        
        for companion in log.companions:
            db.session.delete(companion)
        
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
        
        alert_msg = ""
        today = datetime.now().date()
        
        if log.vehicle_type != 'pedestre':
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
            new_item = AuthorizedVehicle(
                plate=request.form.get('vehicle_plate', '').upper().strip(),
                vehicle_type=request.form.get('vehicle_type'),
                company=request.form.get('company'),
                expiry_date=expiry
            )
        elif m_type == 'trailer':
            new_item = AuthorizedTrailer(
                plate=request.form.get('trailer_plate', '').upper().strip(),
                company=request.form.get('company'),
                expiry_date=expiry
            )
        elif m_type == 'driver':
            new_item = AuthorizedDriver(
                name=request.form.get('driver_name'),
                document=request.form.get('driver_document'),
                company=request.form.get('company'),
                expiry_date=expiry
            )
        else:
            flash('Tipo inválido.', 'danger')
            return redirect(url_for('main.management'))

        db.session.add(new_item)
        db.session.commit()
        flash('Autorização cadastrada com sucesso!', 'success')
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

    return render_template('main/edit_authorized.html', 
                           item=item, 
                           item_type=item_type, 
                           title=title)