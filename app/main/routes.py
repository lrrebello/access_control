from flask import render_template, url_for, flash, redirect, request, jsonify, current_app
from app import db
from app.models import AccessLog, AuthorizedVehicle, AuthorizedTrailer, AuthorizedDriver, Companion, Workstation, Occurrence
from app.main import main
from flask_login import login_required, current_user
from datetime import datetime

# Filtro Jinja2 para converter quebras de linha em <br>
@main.app_template_filter("nl2br")
def nl2br_filter(s):
    if not s:
        return ""
    return s.replace("\n", "<br>\n")

# ====================== DASHBOARD ======================
@main.route("/")
@main.route("/dashboard")
@login_required
def dashboard():
    # Garantir que o usuário tem um posto ativo
    if not current_user.active_workstation_id:
        return redirect(url_for("auth.select_workstation"))
    
    filter_type = request.args.get("filter", "active")
    search_query = request.args.get("search", "").strip()
    
    today = datetime.now().date()
    today_start = datetime(today.year, today.month, today.day, 0, 0, 0)
    today_end = datetime(today.year, today.month, today.day, 23, 59, 59)
    
    workstation_id = current_user.active_workstation_id
    
    query = AccessLog.query
    
    # Filtrar por posto de trabalho
    query = query.filter(AccessLog.workstation_id == workstation_id)
    
    # Admins veem tudo do posto, outros veem só seus registros
    if not current_user.is_admin:
        query = query.filter(AccessLog.user_id == current_user.id)
    
    if search_query:
        query = query.filter(
            (AccessLog.vehicle_plate.ilike(f"%{search_query}%")) |
            (AccessLog.driver_name.ilike(f"%{search_query}%")) |
            (AccessLog.company.ilike(f"%{search_query}%"))
        )
    
    # FILTROS DA TABELA
    if filter_type == "active":
        logs = query.filter(AccessLog.exit_time == None).order_by(AccessLog.entry_time.desc()).all()
    elif filter_type == "today_entries":
        logs = query.filter(
            AccessLog.entry_time >= today_start,
            AccessLog.entry_time <= today_end
        ).order_by(AccessLog.entry_time.desc()).all()
    elif filter_type == "today_exits":
        logs = query.filter(
            AccessLog.exit_time != None,
            AccessLog.exit_time >= today_start,
            AccessLog.exit_time <= today_end
        ).order_by(AccessLog.exit_time.desc()).all()
    elif filter_type == "finished":
        logs = query.filter(AccessLog.exit_time != None).order_by(AccessLog.exit_time.desc()).all()
    else:
        logs = query.order_by(AccessLog.entry_time.desc()).all()
    
    # ==================== ESTATÍSTICAS ====================
    
    # Veículos e pedestres ativos (sem saída)
    active_query = AccessLog.query.filter(
        AccessLog.exit_time == None,
        AccessLog.workstation_id == workstation_id
    )
    active_logs = active_query.all()
    
    # Apenas veículos (excluindo pedestres)
    vehicles_inside = [log for log in active_logs if log.vehicle_type != "pedestre"]
    total_vehicles_inside = len(vehicles_inside)
    
    # Total de pessoas (motorista + acompanhantes)
    people_inside = sum(log.total_people for log in active_logs)
    
    # Apenas pedestres
    pedestrians_inside = [log for log in active_logs if log.vehicle_type == "pedestre"]
    total_pedestrians_only = len(pedestrians_inside)
    
    # Saídas de HOJE
    today_exits = AccessLog.query.filter(
        AccessLog.exit_time != None,
        AccessLog.exit_time >= today_start,
        AccessLog.exit_time <= today_end,
        AccessLog.workstation_id == workstation_id
    ).count()
    
    # Entradas de HOJE
    today_entries = AccessLog.query.filter(
        AccessLog.entry_time >= today_start,
        AccessLog.entry_time <= today_end,
        AccessLog.workstation_id == workstation_id
    ).count()
    
    # Entradas de veículos HOJE
    today_vehicles_entries = AccessLog.query.filter(
        AccessLog.entry_time >= today_start,
        AccessLog.entry_time <= today_end,
        AccessLog.workstation_id == workstation_id,
        AccessLog.vehicle_type != "pedestre"
    ).count()
    
    # Entradas de pedestres HOJE
    today_pedestrians_entries = AccessLog.query.filter(
        AccessLog.entry_time >= today_start,
        AccessLog.entry_time <= today_end,
        AccessLog.workstation_id == workstation_id,
        AccessLog.vehicle_type == "pedestre"
    ).count()
    
    # Dados para autocomplete
    auth_vehicles = AuthorizedVehicle.query.all()
    auth_trailers = AuthorizedTrailer.query.all()
    auth_drivers = AuthorizedDriver.query.all()
    
    return render_template("main/dashboard.html", 
                           logs=logs, 
                           total_vehicles=total_vehicles_inside,
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
@main.route("/access/new", methods=["POST"])
@login_required
def new_access():
    if not current_user.active_workstation_id:
        flash("Selecione um posto de trabalho primeiro.", "warning")
        return redirect(url_for("auth.select_workstation"))
    
    vehicle_type = request.form.get("vehicle_type")
    driver_name = request.form.get("driver_name", "").strip()
    driver_doc = request.form.get("driver_doc", "").strip()
    
    if vehicle_type == "pedestre":
        vehicle_plate = "PEDESTRE"
        trailer_plate = None
        company = request.form.get("company", "").strip() or "Não informada"
    else:
        vehicle_plate = request.form.get("vehicle_plate", "").upper().strip()
        trailer_plate = request.form.get("trailer_plate", "").upper().strip() or None
        company = request.form.get("company", "").strip()
    
    if vehicle_type != "pedestre" and not vehicle_plate:
        flash("Matrícula do veículo é obrigatória!", "danger")
        return redirect(url_for("main.dashboard"))
    
    if not driver_name:
        flash("Nome do condutor é obrigatório!", "danger")
        return redirect(url_for("main.dashboard"))
    
    alert_msg = ""
    today = datetime.now().date()

    if vehicle_type != "pedestre":
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
        driver_doc=driver_doc,
        company=company,
        observations=request.form.get("observations", ""),
        alert_msg=alert_msg if alert_msg else None
    )
    db.session.add(log)
    db.session.flush()

    companion_names = request.form.getlist("companion_name[]")
    companion_docs = request.form.getlist("companion_doc[]")
    
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
    
    if vehicle_type == "pedestre":
        flash_msg = f"🚶 Pedestre registrado! Total: {total_people} pessoas"
    else:
        flash_msg = f"🚗 Veículo {vehicle_plate} registrado! Total: {total_people} pessoas"
    
    if alert_msg:
        flash(f"{flash_msg} | ⚠️ {alert_msg}", "warning")
    else:
        flash(flash_msg, "success")
    
    return redirect(url_for("main.dashboard"))

# ====================== REGISTRO DE SAÍDA ======================
@main.route("/access/exit/<int:log_id>", methods=["POST"])
@login_required
def exit_access(log_id):
    log = AccessLog.query.get_or_404(log_id)
    if not log.exit_time:
        log.exit_time = datetime.now()
        db.session.commit()
        flash("Saída registrada com sucesso!", "success")
    return redirect(url_for("main.dashboard"))

@main.route("/access/remove_exit/<int:log_id>", methods=["POST"])
@login_required
def remove_exit(log_id):
    log = AccessLog.query.get_or_404(log_id)
    if log.exit_time:
        log.exit_time = None
        db.session.commit()
        flash("Saída removida! O veículo voltou para a lista de ativos.", "warning")
    return redirect(url_for("main.dashboard"))

# ====================== EDITAR REGISTRO ======================
@main.route("/access/edit/<int:log_id>", methods=["GET", "POST"])
@login_required
def edit_access(log_id):
    log = AccessLog.query.get_or_404(log_id)
    
    if request.method == "POST":
        log.vehicle_plate = request.form.get("vehicle_plate", "").upper().strip()
        log.trailer_plate = request.form.get("trailer_plate", "").upper().strip() or None
        log.vehicle_type = request.form.get("vehicle_type")
        log.driver_name = request.form.get("driver_name", "").strip()
        log.driver_doc = request.form.get("driver_doc", "").strip()
        log.company = request.form.get("company", "").strip()
        log.observations = request.form.get("observations", "").strip() or None
        
        # Processar data/hora de entrada
        entry_time_str = request.form.get("entry_time")
        if entry_time_str:
            log.entry_time = datetime.strptime(entry_time_str, "%Y-%m-%dT%H:%M")
        
        # Processar data/hora de saída
        exit_time_str = request.form.get("exit_time")
        if exit_time_str:
            log.exit_time = datetime.strptime(exit_time_str, "%Y-%m-%dT%H:%M")
        else:
            log.exit_time = None
        
        # Remover acompanhantes existentes
        for companion in log.companions:
            db.session.delete(companion)
        
        # Adicionar novos acompanhantes
        companion_names = request.form.getlist("companion_name[]")
        companion_docs = request.form.getlist("companion_doc[]")
        
        for name, doc in zip(companion_names, companion_docs):
            if name and doc:
                companion = Companion(
                    access_log_id=log.id,
                    name=name.strip(),
                    document=doc.strip()
                )
                db.session.add(companion)
        
        # Recalcular alertas
        alert_msg = ""
        today = datetime.now().date()
        
        if log.vehicle_type != "pedestre":
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
        flash("Registro atualizado com sucesso!", "success")
        return redirect(url_for("main.dashboard"))
    
    auth_vehicles = AuthorizedVehicle.query.all()
    auth_trailers = AuthorizedTrailer.query.all()
    auth_drivers = AuthorizedDriver.query.all()
    
    return render_template("main/edit_access.html", 
                           log=log,
                           auth_vehicles=auth_vehicles,
                           auth_trailers=auth_trailers,
                           auth_drivers=auth_drivers)


# ====================== GERENCIAMENTO DE AUTORIZADOS ======================
@main.route("/management")
@login_required
def management():
    vehicles = AuthorizedVehicle.query.order_by(AuthorizedVehicle.plate).all()
    trailers = AuthorizedTrailer.query.order_by(AuthorizedTrailer.plate).all()
    drivers = AuthorizedDriver.query.order_by(AuthorizedDriver.name).all()
    return render_template("main/management.html", vehicles=vehicles, trailers=trailers, drivers=drivers)

@main.route("/management/add/<string:m_type>", methods=["POST"])
@login_required
def add_authorized(m_type):
    expiry_str = request.form.get("expiry_date")
    expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date() if expiry_str else None

    if m_type == "vehicle":
        new_item = AuthorizedVehicle(
            plate=request.form.get("plate", "").upper().strip(),
            vehicle_type=request.form.get("vehicle_type"),
            company=request.form.get("company"),
            expiry_date=expiry
        )
    elif m_type == "trailer":
        new_item = AuthorizedTrailer(
            plate=request.form.get("plate", "").upper().strip(),
            company=request.form.get("company"),
            expiry_date=expiry
        )
    elif m_type == "driver":
        new_item = AuthorizedDriver(
            name=request.form.get("driver_name"),
            document=request.form.get("driver_document"),
            company=request.form.get("company"),
            expiry_date=expiry
        )
    else:
        flash("Tipo inválido.", "danger")
        return redirect(url_for("main.management"))

    db.session.add(new_item)
    db.session.commit()
    flash("Autorização cadastrada com sucesso!", "success")
    return redirect(url_for("main.management"))

# ====================== EDIÇÃO DE AUTORIZADOS ======================
@main.route("/management/edit/<string:item_type>/<int:id>", methods=["GET", "POST"])
@login_required
def edit_authorized(item_type, id):
    if item_type == "vehicle":
        item = AuthorizedVehicle.query.get_or_404(id)
        title = "Editar Veículo"
    elif item_type == "trailer":
        item = AuthorizedTrailer.query.get_or_404(id)
        title = "Editar Reboque"
    elif item_type == "driver":
        item = AuthorizedDriver.query.get_or_404(id)
        title = "Editar Condutor"
    else:
        flash("Tipo inválido.", "danger")
        return redirect(url_for("main.management"))

    if request.method == "POST":
        expiry_str = request.form.get("expiry_date")
        expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date() if expiry_str else None

        if item_type == "vehicle":
            item.plate = request.form.get("plate", "").upper().strip()
            item.vehicle_type = request.form.get("vehicle_type")
            item.company = request.form.get("company")
            item.expiry_date = expiry
        elif item_type == "trailer":
            item.plate = request.form.get("plate", "").upper().strip()
            item.company = request.form.get("company")
            item.expiry_date = expiry
        elif item_type == "driver":
            item.name = request.form.get("name")
            item.document = request.form.get("document")
            item.company = request.form.get("company")
            item.expiry_date = expiry

        db.session.commit()
        flash(f"{title} atualizado com sucesso!", "success")
        return redirect(url_for("main.management"))

    return render_template("main/edit_authorized.html", 
                           item=item, 
                           item_type=item_type, 
                           title=title)

# ====================== OCORRÊNCIAS ======================
@main.route("/occurrences")
@login_required
def occurrences():
    """Lista de ocorrências do usuário"""
    if not current_user.active_workstation_id:
        flash("Selecione um posto de trabalho primeiro.", "warning")
        return redirect(url_for("auth.select_workstation"))
    
    occurrences = Occurrence.query.filter_by(
        user_id=current_user.id,
        workstation_id=current_user.active_workstation_id
    ).order_by(Occurrence.created_at.desc()).all()
    
    return render_template("main/occurrences.html", occurrences=occurrences)

@main.route("/occurrence/new", methods=["GET", "POST"])
@login_required
def new_occurrence():
    """Criar ou editar ocorrência do dia"""
    if not current_user.active_workstation_id:
        flash("Selecione um posto de trabalho primeiro.", "warning")
        return redirect(url_for("auth.select_workstation"))
    
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    existing = Occurrence.query.filter(
        Occurrence.user_id == current_user.id,
        Occurrence.workstation_id == current_user.active_workstation_id,
        Occurrence.shift_start >= today_start
    ).first()
    
    if existing and request.method == "GET":
        return redirect(url_for("main.edit_occurrence", id=existing.id))
    
    if request.method == "POST":
        shift_start_str = request.form.get("shift_start")
        if shift_start_str:
            shift_start = datetime.strptime(shift_start_str, "%Y-%m-%dT%H:%M")
        else:
            shift_start = datetime.now()
        
        occurrence = Occurrence(
            user_id=current_user.id,
            workstation_id=current_user.active_workstation_id,
            shift_start=shift_start,
            content=request.form.get("content", ""),
            signature=request.form.get("signature", "")
        )
        db.session.add(occurrence)
        db.session.commit()
        
        flash("Relatório de ocorrências iniciado!", "success")
        return redirect(url_for("main.edit_occurrence", id=occurrence.id))
    
    return render_template("main/new_occurrence.html", now=datetime.now())

@main.route("/occurrence/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_occurrence(id):
    """Editar ocorrência (com salvamento automático)"""
    occurrence = Occurrence.query.get_or_404(id)
    
    if occurrence.user_id != current_user.id and not current_user.is_admin:
        flash("Acesso negado.", "danger")
        return redirect(url_for("main.occurrences"))
    
    if request.method == "POST":
        occurrence.content = request.form.get("content", "")
        occurrence.signature = request.form.get("signature", "")
        
        shift_end_str = request.form.get("shift_end")
        if shift_end_str:
            occurrence.shift_end = datetime.strptime(shift_end_str, "%Y-%m-%dT%H:%M")
        
        occurrence.updated_at = datetime.now()
        db.session.commit()
        
        flash("Relatório salvo com sucesso!", "success")
        return redirect(url_for("main.occurrences"))
    
    return render_template("main/edit_occurrence.html", occurrence=occurrence)

@main.route("/occurrence/auto-save/<int:id>", methods=["POST"])
@login_required
def auto_save_occurrence(id):
    """Salvamento automático via AJAX"""
    occurrence = Occurrence.query.get_or_404(id)
    
    if occurrence.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "Acesso negado"}), 403
    
    data = request.get_json()
    occurrence.content = data.get("content", "")
    occurrence.signature = data.get("signature", "")
    occurrence.updated_at = datetime.now()
    
    shift_end_str = data.get("shift_end")
    if shift_end_str:
        occurrence.shift_end = datetime.strptime(shift_end_str, "%Y-%m-%dT%H:%M")
    
    db.session.commit()
    
    return jsonify({"success": True, "updated_at": occurrence.updated_at.strftime("%d/%m/%Y %H:%M:%S")})

@main.route("/occurrence/preview/<int:id>")
@login_required
def preview_occurrence(id):
    """Pré-visualizar ocorrência em nova aba"""
    occurrence = Occurrence.query.get_or_404(id)
    
    if occurrence.user_id != current_user.id and not current_user.is_admin:
        flash("Acesso negado.", "danger")
        return redirect(url_for("main.occurrences"))
    
    return render_template("main/preview_occurrence.html", occurrence=occurrence)

@main.route("/occurrence/pdf/<int:id>")
@login_required
def pdf_occurrence(id):
    """Gerar PDF da ocorrência"""
    from xhtml2pdf import pisa
    from io import BytesIO
    from flask import send_file
    from PIL import Image
    import os
    
    occurrence = Occurrence.query.get_or_404(id)
    
    if occurrence.user_id != current_user.id and not current_user.is_admin:
        flash("Acesso negado.", "danger")
        return redirect(url_for("main.occurrences"))
    
    # Redimensionar logo para o PDF
    logo_path = os.path.join(current_app.root_path, "static", "logo.png")
    resized_logo_path = os.path.join(current_app.root_path, "static", "logo_resized.png")
    
    try:
        if os.path.exists(logo_path):
            img = Image.open(logo_path).convert("RGBA")
            img.thumbnail((220, 60), Image.Resampling.LANCZOS)
            img.save(resized_logo_path, format="PNG", optimize=True)
    except Exception as e:
        print(f"Erro ao redimensionar logo: {e}")
    
    html = render_template("main/pdf_occurrence.html", occurrence=occurrence)
    
    output = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), dest=output)
    
    if pdf.err:
        flash("Erro ao gerar PDF.", "danger")
        return redirect(url_for("main.occurrences"))
    
    output.seek(0)
    filename = f"relatorio_ocorrencias_{occurrence.id}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    
    return send_file(output, as_attachment=True, download_name=filename, mimetype="application/pdf")

@main.route("/occurrence/delete/<int:id>")
@login_required
def delete_occurrence(id):
    """Excluir ocorrência"""
    occurrence = Occurrence.query.get_or_404(id)
    
    if occurrence.user_id != current_user.id and not current_user.is_admin:
        flash("Acesso negado.", "danger")
        return redirect(url_for("main.occurrences"))
    
    db.session.delete(occurrence)
    db.session.commit()
    
    flash("Relatório excluído com sucesso!", "success")
    return redirect(url_for("main.occurrences"))

# ====================== CONFIGURAÇÕES DO SISTEMA ======================
@main.route("/admin/logo")
@login_required
def admin_logo():
    """Página de configuração da logo"""
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    return render_template('main/admin_logo.html')

@main.route("/admin/logo/upload", methods=['POST'])
@login_required
def upload_logo():
    """Upload da nova logo"""
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    from PIL import Image
    import os
    
    if 'logo' not in request.files:
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('main.admin_logo'))
    
    file = request.files['logo']
    
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('main.admin_logo'))
    
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
        flash('Formato não suportado. Use PNG, JPG, JPEG, GIF ou WEBP.', 'danger')
        return redirect(url_for('main.admin_logo'))
    
    # Salvar logo original
    logo_path = os.path.join(current_app.root_path, 'static', 'logo.png')
    file.save(logo_path)
    
    # Criar versão redimensionada
    resized_logo_path = os.path.join(current_app.root_path, 'static', 'logo_resized.png')
    try:
        img = Image.open(logo_path).convert("RGBA")
        img.thumbnail((220, 60), Image.Resampling.LANCZOS)
        img.save(resized_logo_path, format='PNG', optimize=True)
    except Exception as e:
        print(f"Erro ao redimensionar logo: {e}")
    
    flash('Logo atualizada com sucesso!', 'success')
    return redirect(url_for('main.admin_logo'))

@main.route("/admin/logo/restore", methods=['POST'])
@login_required
def restore_default_logo():
    """Restaurar logo padrão"""
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    import os
    import shutil
    from PIL import Image
    
    logo_path = os.path.join(current_app.root_path, 'static', 'logo.png')
    resized_logo_path = os.path.join(current_app.root_path, 'static', 'logo_resized.png')
    
    # Remover logo atual
    if os.path.exists(logo_path):
        os.remove(logo_path)
    if os.path.exists(resized_logo_path):
        os.remove(resized_logo_path)
    
    flash('Logo removida. O sistema usará o texto padrão.', 'warning')
    return redirect(url_for('main.admin_logo'))