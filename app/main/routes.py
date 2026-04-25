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
    
    if vehicle_type == "pedestre":
        vehicle_plate = "PEDESTRE"
        trailer_plate = None
        company = request.form.get("company", "").strip()
    else:
        vehicle_plate = request.form.get("vehicle_plate", "").upper().strip()
        trailer_plate = request.form.get("trailer_plate", "").upper().strip()
        company = request.form.get("company", "").strip()

    entry_time_str = request.form.get("entry_time")
    entry_time = datetime.strptime(entry_time_str, "%Y-%m-%dT%H:%M") if entry_time_str else datetime.now()

    total_people = 1 # Motorista
    companions_data = []
    for i in range(1, 5):
        companion_name = request.form.get(f"companion_name_{i}", "").strip()
        companion_document = request.form.get(f"companion_document_{i}", "").strip()
        if companion_name:
            companions_data.append({"name": companion_name, "document": companion_document})
            total_people += 1

    new_log = AccessLog(
        user_id=current_user.id,
        workstation_id=current_user.active_workstation_id,
        vehicle_type=vehicle_type,
        vehicle_plate=vehicle_plate,
        trailer_plate=trailer_plate,
        driver_name=driver_name,
        company=company,
        entry_time=entry_time,
        total_people=total_people
    )
    db.session.add(new_log)
    db.session.commit()

    for comp_data in companions_data:
        companion = Companion(
            access_log_id=new_log.id,
            name=comp_data["name"],
            document=comp_data["document"]
        )
        db.session.add(companion)
    db.session.commit()

    flash("Acesso registrado com sucesso!", "success")
    return redirect(url_for("main.dashboard"))

# ====================== REGISTRO DE SAÍDA ======================
@main.route("/access/exit/<int:log_id>", methods=["POST"])
@login_required
def exit_access(log_id):
    log = AccessLog.query.get_or_404(log_id)
    if log.workstation_id != current_user.active_workstation_id:
        flash("Acesso negado.", "danger")
        return redirect(url_for("main.dashboard"))
    
    log.exit_time = datetime.now()
    db.session.commit()
    flash("Saída registrada com sucesso!", "success")
    return redirect(url_for("main.dashboard"))

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
    from flask import jsonify
    
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
    
    # Passar logo_path para o template
    html = render_template("main/pdf_occurrence.html", 
                          occurrence=occurrence,
                          logo_exists=os.path.exists(resized_logo_path))
    
    output = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), dest=output)
    
    if pdf.err:
        flash("Erro ao gerar PDF.", "danger")
        return redirect(url_for("main.occurrences"))
    
    output.seek(0)
    filename = f"relatorio_ocorrencias_{occurrence.id}_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf"
    
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
