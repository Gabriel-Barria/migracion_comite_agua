from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from database import get_db, init_db, importar_usuarios_excel
from weasyprint import HTML
from datetime import datetime
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER_COMPROBANTES'] = 'comprobantes'
app.config['UPLOAD_FOLDER_MEDIDORES'] = 'medidores'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER_COMPROBANTES'], exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER_MEDIDORES'], exist_ok=True)

# --- USUARIOS ---
@app.route('/')
def index():
    return redirect(url_for('usuarios'))

@app.route('/usuarios')
def usuarios():
    buscar = request.args.get('buscar', '')
    estado = request.args.get('estado', '')
    conn = get_db()
    query = 'SELECT * FROM usuarios WHERE 1=1'
    params = []
    if buscar:
        query += ' AND (nombre LIKE ? OR primer_apellido LIKE ? OR segundo_apellido LIKE ?)'
        params.extend([f'%{buscar}%', f'%{buscar}%', f'%{buscar}%'])
    if estado:
        query += ' AND estado = ?'
        params.append(estado)
    query += ' ORDER BY primer_apellido, nombre'
    usuarios = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('usuarios.html', usuarios=usuarios, buscar=buscar, estado=estado)

@app.route('/usuarios/nuevo', methods=['GET', 'POST'])
def usuario_nuevo():
    if request.method == 'POST':
        conn = get_db()
        conn.execute('''
            INSERT INTO usuarios (nombre, primer_apellido, segundo_apellido, rut, telefono, email, direccion, integrantes_hogar, estado, observaciones)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            request.form['nombre'], request.form['primer_apellido'], request.form.get('segundo_apellido'),
            request.form.get('rut'), request.form.get('telefono'), request.form.get('email'),
            request.form.get('direccion'), request.form.get('integrantes_hogar') or None,
            request.form.get('estado', 'Activo'), request.form.get('observaciones')
        ))
        conn.commit()
        conn.close()
        return redirect(url_for('usuarios'))
    return render_template('usuario_form.html', usuario=None)

@app.route('/usuarios/<int:id>/editar', methods=['GET', 'POST'])
def usuario_editar(id):
    conn = get_db()
    if request.method == 'POST':
        conn.execute('''
            UPDATE usuarios SET nombre=?, primer_apellido=?, segundo_apellido=?, rut=?, telefono=?, email=?, direccion=?, integrantes_hogar=?, estado=?, observaciones=?
            WHERE id=?
        ''', (
            request.form['nombre'], request.form['primer_apellido'], request.form.get('segundo_apellido'),
            request.form.get('rut'), request.form.get('telefono'), request.form.get('email'),
            request.form.get('direccion'), request.form.get('integrantes_hogar') or None,
            request.form.get('estado', 'Activo'), request.form.get('observaciones'), id
        ))
        conn.commit()
        conn.close()
        return redirect(url_for('usuarios'))
    usuario = conn.execute('SELECT * FROM usuarios WHERE id=?', (id,)).fetchone()
    conn.close()
    return render_template('usuario_form.html', usuario=usuario)

@app.route('/usuarios/<int:id>/eliminar', methods=['POST'])
def usuario_eliminar(id):
    conn = get_db()
    conn.execute('DELETE FROM usuarios WHERE id=?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('usuarios'))

# --- LECTURAS ---
@app.route('/lecturas')
def lecturas():
    usuario_id = request.args.get('usuario_id', '')
    periodo = request.args.get('periodo', '')
    estado_pago = request.args.get('estado_pago', '')
    sin_foto = request.args.get('sin_foto', '')
    conn = get_db()
    query = '''
        SELECT l.*, u.nombre, u.primer_apellido, u.segundo_apellido, u.telefono
        FROM lecturas l
        JOIN usuarios u ON l.usuario_id = u.id
        WHERE 1=1
    '''
    params = []
    if usuario_id:
        query += ' AND l.usuario_id = ?'
        params.append(usuario_id)
    if periodo:
        query += ' AND l.periodo = ?'
        params.append(periodo)
    if estado_pago:
        query += ' AND l.estado_pago = ?'
        params.append(estado_pago)
    if sin_foto:
        query += ' AND (l.imagen_medidor IS NULL OR l.imagen_medidor = "")'
    query += ' ORDER BY l.periodo DESC, u.primer_apellido'
    lecturas = conn.execute(query, params).fetchall()
    usuarios = conn.execute('SELECT id, nombre, primer_apellido FROM usuarios WHERE estado="Activo" ORDER BY primer_apellido').fetchall()
    periodos = conn.execute('SELECT DISTINCT periodo FROM lecturas ORDER BY periodo DESC').fetchall()
    conn.close()
    return render_template('lecturas.html', lecturas=lecturas, usuarios=usuarios, periodos=periodos,
                           usuario_id=usuario_id, periodo=periodo, estado_pago=estado_pago, sin_foto=sin_foto)

@app.route('/lecturas/nueva', methods=['GET', 'POST'])
def lectura_nueva():
    conn = get_db()
    if request.method == 'POST':
        lectura_anterior = float(request.form['lectura_anterior'] or 0)
        lectura_actual = float(request.form['lectura_actual'] or 0)
        tarifa = float(request.form.get('tarifa_m3') or 1182.6)
        cargo_fijo = float(request.form.get('cargo_fijo') or 5000)
        consumo = lectura_actual - lectura_anterior
        subtotal = consumo * tarifa
        total = subtotal + cargo_fijo
        monto_pagado = float(request.form.get('monto_pagado') or 0)
        saldo = total - monto_pagado

        imagen_medidor = None
        if 'imagen_medidor' in request.files:
            file = request.files['imagen_medidor']
            if file and file.filename:
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER_MEDIDORES'], filename))
                imagen_medidor = filename

        comprobante_pago = None
        if 'comprobante_pago' in request.files:
            file = request.files['comprobante_pago']
            if file and file.filename:
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER_COMPROBANTES'], filename))
                comprobante_pago = filename

        conn.execute('''
            INSERT INTO lecturas (usuario_id, periodo, lectura_anterior, lectura_actual, consumo_m3, tarifa_m3, subtotal_consumo, cargo_fijo, total_factura, fecha_lectura, estado_pago, monto_pagado, fecha_pago, forma_pago, saldo_pendiente, comprobante_pago, imagen_medidor)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            request.form['usuario_id'], request.form['periodo'], lectura_anterior, lectura_actual,
            consumo, tarifa, subtotal, cargo_fijo, total, request.form.get('fecha_lectura') or None,
            request.form.get('estado_pago', 'PENDIENTE'), monto_pagado,
            request.form.get('fecha_pago') or None, request.form.get('forma_pago'),
            saldo, comprobante_pago, imagen_medidor
        ))
        conn.commit()
        conn.close()
        return redirect(url_for('lecturas'))
    usuarios = conn.execute('SELECT id, nombre, primer_apellido FROM usuarios WHERE estado="Activo" ORDER BY primer_apellido').fetchall()
    conn.close()
    return render_template('lectura_form.html', lectura=None, usuarios=usuarios)

@app.route('/lecturas/<int:id>/editar', methods=['GET', 'POST'])
def lectura_editar(id):
    conn = get_db()
    if request.method == 'POST':
        lectura_anterior = float(request.form['lectura_anterior'] or 0)
        lectura_actual = float(request.form['lectura_actual'] or 0)
        tarifa = float(request.form.get('tarifa_m3') or 1182.6)
        cargo_fijo = float(request.form.get('cargo_fijo') or 5000)
        consumo = lectura_actual - lectura_anterior
        subtotal = consumo * tarifa
        total = subtotal + cargo_fijo
        monto_pagado = float(request.form.get('monto_pagado') or 0)
        saldo = total - monto_pagado

        lectura_actual_db = conn.execute('SELECT imagen_medidor, comprobante_pago FROM lecturas WHERE id=?', (id,)).fetchone()
        imagen_medidor = lectura_actual_db['imagen_medidor']
        comprobante_pago = lectura_actual_db['comprobante_pago']

        if 'imagen_medidor' in request.files:
            file = request.files['imagen_medidor']
            if file and file.filename:
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER_MEDIDORES'], filename))
                imagen_medidor = filename

        if 'comprobante_pago' in request.files:
            file = request.files['comprobante_pago']
            if file and file.filename:
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER_COMPROBANTES'], filename))
                comprobante_pago = filename

        conn.execute('''
            UPDATE lecturas SET usuario_id=?, periodo=?, lectura_anterior=?, lectura_actual=?, consumo_m3=?, tarifa_m3=?, subtotal_consumo=?, cargo_fijo=?, total_factura=?, fecha_lectura=?, estado_pago=?, monto_pagado=?, fecha_pago=?, forma_pago=?, saldo_pendiente=?, comprobante_pago=?, imagen_medidor=?
            WHERE id=?
        ''', (
            request.form['usuario_id'], request.form['periodo'], lectura_anterior, lectura_actual,
            consumo, tarifa, subtotal, cargo_fijo, total, request.form.get('fecha_lectura') or None,
            request.form.get('estado_pago', 'PENDIENTE'), monto_pagado,
            request.form.get('fecha_pago') or None, request.form.get('forma_pago'),
            saldo, comprobante_pago, imagen_medidor, id
        ))
        conn.commit()
        conn.close()
        return redirect(url_for('lecturas'))
    lectura = conn.execute('SELECT * FROM lecturas WHERE id=?', (id,)).fetchone()
    usuarios = conn.execute('SELECT id, nombre, primer_apellido FROM usuarios WHERE estado="Activo" ORDER BY primer_apellido').fetchall()
    conn.close()
    return render_template('lectura_form.html', lectura=lectura, usuarios=usuarios)

@app.route('/lecturas/<int:id>/eliminar', methods=['POST'])
def lectura_eliminar(id):
    conn = get_db()
    conn.execute('DELETE FROM lecturas WHERE id=?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('lecturas'))

@app.route('/lecturas/<int:id>/pdf')
def lectura_pdf(id):
    conn = get_db()
    lectura = conn.execute('''
        SELECT l.*, u.nombre, u.primer_apellido, u.segundo_apellido, u.telefono
        FROM lecturas l
        JOIN usuarios u ON l.usuario_id = u.id
        WHERE l.id = ?
    ''', (id,)).fetchone()
    conn.close()

    nombre_completo = f"{lectura['nombre']} {lectura['primer_apellido']}"
    if lectura['segundo_apellido']:
        nombre_completo += f" {lectura['segundo_apellido']}"

    html_content = f'''<!DOCTYPE html>
<html>
<head><title>Comprobante</title></head>
<style type="text/css">
    body{{ font-family: verdana; width: 80%; margin: auto; }}
    .head_container .data_container{{ display: block; height: 30px; }}
    .pay_container, .total_container{{ border:1px solid black; }}
    .pay_container{{ padding: 5px; }}
    .total_container{{ margin-bottom: 30px; font-weight: bold; height: 40px; display: flex; align-items: center; justify-content: center; }}
    .data_table{{ width: 100%; margin-bottom: 20px; border-collapse: collapse; }}
    .titulo{{ text-align: center; }}
    .data_table thead{{ background-color: #156082; color:white; height: 40px; }}
    .head_container{{ margin-bottom:15px; }}
    .number_container{{ height: 80px; display:flex; align-items: center; margin-bottom: 20px; }}
    td, th, tr{{ border:solid 1px black; text-align: center; padding: 8px; }}
    ol{{ list-style: disc; }}
</style>
<body>
    <h2 class="titulo">COBRO AGUA PASAJE BAUCHE</h2>
    <section class="number_container">
        COMPROBANTE N° <span>{lectura['id']}</span>
    </section>
    <section class="head_container">
        <div class="data_container"><label>Cliente:</label> <span>{nombre_completo}</span></div>
        <div class="data_container"><label>Teléfono:</label> <span>{lectura['telefono'] or 'N/A'}</span></div>
        <div class="data_container"><label>Periodo:</label> <span>{lectura['periodo']}</span></div>
        <div class="data_container"><label>Fecha:</label> <span>{lectura['fecha_lectura'] or datetime.now().strftime('%Y-%m-%d')}</span></div>
    </section>
    <section class="table_container">
        <table class="data_table">
            <thead>
                <tr><th>CANTIDAD</th><th>DESCRIPCION</th><th>VALOR</th><th>COSTO TOTAL</th></tr>
            </thead>
            <tbody>
                <tr>
                    <td>{lectura['consumo_m3']:.1f} m³</td>
                    <td>Consumo de agua (Lect. Ant: {lectura['lectura_anterior']:.0f} - Lect. Act: {lectura['lectura_actual']:.0f})</td>
                    <td>${lectura['tarifa_m3']:,.0f}/m³</td>
                    <td>${lectura['subtotal_consumo']:,.0f}</td>
                </tr>
                <tr>
                    <td>1</td>
                    <td>Cargo fijo mensual</td>
                    <td>${lectura['cargo_fijo']:,.0f}</td>
                    <td>${lectura['cargo_fijo']:,.0f}</td>
                </tr>
            </tbody>
        </table>
        <div class="total_container">Total: ${lectura['total_factura']:,.0f}</div>
    </section>
    <section class="pay_container">
        <h4>Métodos de pago:</h4>
        <div>1.-Efectivo</div>
        <div>2.-Transferencia a la siguiente cuenta:</div>
        <ol style="margin-top:2px;">
            <li>Banco: Banco Estado</li>
            <li>N° de cuenta: 82970400962</li>
            <li>RUT: 65096733-k</li>
            <li>Tipo de Cuenta: Cuenta Vista o Chequera electrónica</li>
            <li>Nombre: Comité de Trabajo Pasaje Bauche</li>
            <li>Email: comite.bauche@gmail.com</li>
        </ol>
    </section>
</body>
</html>'''

    pdf = HTML(string=html_content).write_pdf()
    from io import BytesIO
    return send_file(BytesIO(pdf), mimetype='application/pdf',
                     download_name=f'comprobante_{lectura["id"]}_{lectura["periodo"]}.pdf', as_attachment=True)

@app.route('/comprobantes/<filename>')
def ver_comprobante(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER_COMPROBANTES'], filename))

@app.route('/medidores/<filename>')
def ver_medidor(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER_MEDIDORES'], filename))

@app.route('/api/usuarios-disponibles')
def usuarios_disponibles():
    periodo = request.args.get('periodo', '')
    conn = get_db()
    if periodo:
        usuarios = conn.execute('''
            SELECT u.id, u.nombre, u.primer_apellido
            FROM usuarios u
            WHERE u.estado = "Activo"
            AND u.id NOT IN (SELECT usuario_id FROM lecturas WHERE periodo = ?)
            ORDER BY u.primer_apellido, u.nombre
        ''', (periodo,)).fetchall()
    else:
        usuarios = conn.execute('SELECT id, nombre, primer_apellido FROM usuarios WHERE estado="Activo" ORDER BY primer_apellido, nombre').fetchall()
    conn.close()
    return jsonify([{'id': u['id'], 'nombre': u['nombre'], 'primer_apellido': u['primer_apellido']} for u in usuarios])

@app.route('/api/lectura-anterior')
def lectura_anterior():
    usuario_id = request.args.get('usuario_id', '')
    periodo = request.args.get('periodo', '')
    if not usuario_id or not periodo:
        return jsonify({'lectura_anterior': 0})

    # Parsear periodo actual (MM-YYYY) para comparar correctamente
    try:
        mes, anio = periodo.split('-')
        mes = int(mes)
        anio = int(anio)
        # Convertir a formato YYYY-MM para ordenar cronológicamente
        periodo_ordenable = f"{anio:04d}-{mes:02d}"
    except:
        return jsonify({'lectura_anterior': 0})

    conn = get_db()
    # Buscar la lectura más reciente anterior al periodo seleccionado
    # Convertimos MM-YYYY a YYYY-MM para comparar correctamente
    lectura = conn.execute('''
        SELECT lectura_actual FROM lecturas
        WHERE usuario_id = ?
        AND (SUBSTR(periodo, 4, 4) || '-' || SUBSTR(periodo, 1, 2)) < ?
        ORDER BY (SUBSTR(periodo, 4, 4) || '-' || SUBSTR(periodo, 1, 2)) DESC
        LIMIT 1
    ''', (usuario_id, periodo_ordenable)).fetchone()
    conn.close()

    if lectura:
        return jsonify({'lectura_anterior': lectura['lectura_actual']})
    return jsonify({'lectura_anterior': 0})

if __name__ == '__main__':
    init_db()
    importar_usuarios_excel()
    app.run(host='0.0.0.0', port=5000, debug=True)
