from flask import render_template, request, send_file, flash, redirect, url_for, current_app, render_template_string
from app import db
from app.models import AccessLog
from app.reports import reports
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO
import os
from PIL import Image

# Mapeamento seguro para ordenação
SORT_MAPPING = {
    'vehicle_plate': AccessLog.vehicle_plate,
    'trailer_plate': AccessLog.trailer_plate,
    'driver_name': AccessLog.driver_name,
    'company': AccessLog.company,
    'entry_time': AccessLog.entry_time,
    'exit_time': AccessLog.exit_time,
    'vehicle_type': AccessLog.vehicle_type,
}

@reports.route("/reports", methods=['GET', 'POST'])
@login_required
def view_reports():
    # Ordenação
    sort_by = request.args.get('sort_by', 'entry_time')
    sort_dir = request.args.get('sort_dir', 'desc')

    if sort_by not in SORT_MAPPING:
        sort_by = 'entry_time'
    if sort_dir not in ['asc', 'desc']:
        sort_dir = 'desc'

    # Filtros de data
    start_date_str = request.form.get('start_date') or request.args.get('start_date')
    end_date_str = request.form.get('end_date') or request.args.get('end_date')

    query = AccessLog.query
    
    # FILTRO POR USUÁRIO - ADMINS veem tudo, outros veem só seus registros
    if not current_user.is_admin:
        query = query.filter(AccessLog.user_id == current_user.id)

    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        query = query.filter(AccessLog.entry_time >= start_date)
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(AccessLog.entry_time < end_date)

    # Aplicar ordenação
    order_column = SORT_MAPPING[sort_by]
    query = query.order_by(order_column.desc() if sort_dir == 'desc' else order_column.asc())

    logs = query.all()

    # Exportações
    if request.method == 'POST':
        if 'export_excel' in request.form:
            return export_excel(logs)
        if 'export_pdf' in request.form:
            return export_pdf(logs, start_date=start_date_str, end_date=end_date_str)

    return render_template('reports/reports.html',
                           logs=logs,
                           title='Relatórios',
                           start_date=start_date_str,
                           end_date=end_date_str,
                           sort_by=sort_by,
                           sort_dir=sort_dir)


def export_excel(logs):
    """Exporta para Excel com coluna de acompanhantes"""
    data = []
    for log in logs:
        # Formatar lista de acompanhantes
        companions_text = ""
        if log.companions:
            companions_list = [f"{c.name} ({c.document})" for c in log.companions]
            companions_text = "\n".join(companions_list)
        
        data.append({
            'Matrícula': log.vehicle_plate,
            'Reboque': log.trailer_plate or '',
            'Tipo Veículo': log.vehicle_type,
            'Condutor': log.driver_name,
            'Doc. Condutor': log.driver_doc,
            'Acompanhantes': companions_text,
            'Qtd. Acomp.': len(log.companions),
            'Total Pessoas': log.total_people,
            'Empresa': log.company,
            'Entrada': log.entry_time.strftime('%d/%m/%Y %H:%M'),
            'Saída': log.exit_time.strftime('%d/%m/%Y %H:%M') if log.exit_time else 'Em local',
            'Tempo Permanência': log.duration if log.exit_time else 'Em local',
            'Observação': log.observations or '',
            'Alerta': log.alert_msg or ''
        })
    
    df = pd.DataFrame(data)
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatório de Acessos')
        
        # Acessar a planilha
        worksheet = writer.sheets['Relatório de Acessos']
        
        # Adicionar cabeçalho com informações do usuário
        from openpyxl.styles import Font, Alignment
        
        # Inserir linhas no topo
        worksheet.insert_rows(0, 4)
        
        # Título do relatório
        worksheet['A1'] = 'RELATÓRIO DE CONTROLE DE ACESSO'
        worksheet['A1'].font = Font(bold=True, size=14)
        worksheet.merge_cells('A1:N1')
        worksheet['A1'].alignment = Alignment(horizontal='center')
        
        # Informações do relatório
        worksheet['A2'] = f'Gerado por: {current_user.username}'
        worksheet['A3'] = f'Data: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}'
        worksheet['A4'] = f'Período: {request.form.get("start_date", "Tudo")} até {request.form.get("end_date", "Tudo")}'
        
        # Ajustar largura das colunas
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    filename = f"relatorio_acessos_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


def export_pdf(logs, start_date=None, end_date=None):
    """Gera PDF com acompanhantes"""
    from xhtml2pdf import pisa
    from io import BytesIO
    from PIL import Image
    import sys
    
    # Caminho da logo original e redimensionada
    logo_path = os.path.join(current_app.root_path, 'static', 'logo.png')
    resized_logo_path = os.path.join(current_app.root_path, 'static', 'logo_resized.png')

    # Redimensiona a logo (máximo 220x60)
    try:
        if os.path.exists(logo_path):
            img = Image.open(logo_path).convert("RGBA")
            img.thumbnail((220, 60), Image.Resampling.LANCZOS)
            img.save(resized_logo_path, format='PNG', optimize=True)
            logo_to_use = resized_logo_path
        else:
            logo_to_use = ""
    except Exception:
        logo_to_use = ""

    try:
        # Ler o template HTML
        template_path = os.path.join(current_app.root_path, 'templates', 'reports', 'pdf_template.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Converter current_user para dados simples (evita erro de serialização)
        user_data = {
            'username': str(current_user.username),
            'is_admin': bool(current_user.is_admin)
        }
        
        # Preparar dados para o template
        from datetime import datetime as dt
        now = dt.now()
        
        # Processar logs para garantir que os dados estão corretos
        logs_data = []
        for log in logs:
            log_dict = {
                'vehicle_plate': str(log.vehicle_plate),
                'trailer_plate': str(log.trailer_plate) if log.trailer_plate else '',
                'vehicle_type': str(log.vehicle_type),
                'driver_name': str(log.driver_name),
                'driver_doc': str(log.driver_doc),
                'company': str(log.company),
                'entry_time': log.entry_time,
                'exit_time': log.exit_time,
                'observations': str(log.observations) if log.observations else '',
                'duration': str(log.duration) if log.duration else '',
                'companions': []
            }
            
            # Adicionar acompanhantes
            for companion in log.companions:
                log_dict['companions'].append({
                    'name': str(companion.name),
                    'document': str(companion.document)
                })
            
            logs_data.append(log_dict)
        
        # Renderizar o HTML
        html = render_template_string(
            html_content,
            logs=logs_data,
            now=now,
            start_date=start_date or '',
            end_date=end_date or '',
            logo_path=logo_to_use,
            user=user_data
        )

        # Gerar PDF
        output = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), dest=output)

        if pdf.err:
            flash('Erro ao gerar o PDF.', 'danger')
            return redirect(url_for('reports.view_reports'))

        output.seek(0)
        filename = f"relatorio_acessos_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

        return send_file(
            output, 
            as_attachment=True, 
            download_name=filename, 
            mimetype='application/pdf'
        )

    except Exception as e:
        flash(f'Erro ao gerar PDF: {str(e)}', 'danger')
        return redirect(url_for('reports.view_reports'))