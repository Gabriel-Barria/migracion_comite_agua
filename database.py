import sqlite3
import pandas as pd
import os

DB_PATH = 'data/comite.db'
EXCEL_PATH = 'base_antigua/01_Base_Usuarios.xlsx'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs('data', exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            primer_apellido TEXT NOT NULL,
            segundo_apellido TEXT,
            rut TEXT,
            telefono TEXT,
            email TEXT,
            direccion TEXT,
            fecha_incorporacion DATE,
            integrantes_hogar INTEGER,
            estado TEXT DEFAULT 'Activo',
            observaciones TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lecturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            periodo TEXT NOT NULL,
            lectura_anterior REAL,
            lectura_actual REAL,
            consumo_m3 REAL,
            tarifa_m3 REAL DEFAULT 1182.6,
            subtotal_consumo REAL,
            cargo_fijo REAL DEFAULT 5000,
            total_factura REAL,
            fecha_lectura DATE,
            estado_pago TEXT DEFAULT 'PENDIENTE',
            monto_pagado REAL DEFAULT 0,
            fecha_pago DATE,
            forma_pago TEXT,
            saldo_pendiente REAL,
            comprobante_pago TEXT,
            imagen_medidor TEXT,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    ''')

    conn.commit()
    conn.close()

def importar_usuarios_excel():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM usuarios')
    if cursor.fetchone()[0] > 0:
        conn.close()
        return False

    df = pd.read_excel(EXCEL_PATH, sheet_name='Usuarios')

    for _, row in df.iterrows():
        cursor.execute('''
            INSERT INTO usuarios (nombre, primer_apellido, segundo_apellido, rut, telefono, email, direccion, fecha_incorporacion, integrantes_hogar, estado, observaciones)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(row['Nombre']) if pd.notna(row['Nombre']) else '',
            str(row['Primer Apellido']) if pd.notna(row['Primer Apellido']) else '',
            str(row['Segundo Apellido']) if pd.notna(row['Segundo Apellido']) else None,
            str(row['RUT']) if pd.notna(row['RUT']) else None,
            str(int(row['Telefono'])) if pd.notna(row['Telefono']) else None,
            str(row['Email']) if pd.notna(row['Email']) else None,
            str(row['Direccion']) if pd.notna(row['Direccion']) else None,
            None,
            int(row['Integrantes Hogar']) if pd.notna(row['Integrantes Hogar']) else None,
            str(row['Estado']) if pd.notna(row['Estado']) else 'Activo',
            str(row['Observaciones']) if pd.notna(row['Observaciones']) else None
        ))

    conn.commit()
    conn.close()
    return True

if __name__ == '__main__':
    init_db()
    if importar_usuarios_excel():
        print('Usuarios importados correctamente')
    else:
        print('Los usuarios ya existen en la base de datos')
