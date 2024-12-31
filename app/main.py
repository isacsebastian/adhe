from collections import defaultdict
from datetime import datetime
from flask import Flask, request, render_template, send_from_directory
import os
import pandas as pd

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join('data', 'uploaded_files')
RESULT_FOLDER = os.path.join('data', 'results')
os.makedirs(RESULT_FOLDER, exist_ok=True)

FILE_NAME = 'Base.csv'
file_path = os.path.join(UPLOAD_FOLDER, FILE_NAME)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_client_data():
    client_id = request.form.get('client_id')
    vendedor = request.form.get('vendedor')

    if not os.path.exists(file_path):
        return f"Error: File '{FILE_NAME}' not found in '{UPLOAD_FOLDER}'.", 404

    try:
        # Leer el archivo CSV
        print("[DEBUG] Leyendo el archivo CSV...")
        df = pd.read_csv(file_path, dtype={'Cliente': str, 'Vendedor': str})
        print("[DEBUG] CSV cargado:")
        print(df.head())

        client_id = str(client_id).strip()
        vendedor = str(int(vendedor)).zfill(3)
        df['Cliente'] = df['Cliente'].str.strip()
        df['Vendedor'] = df['Vendedor'].str.strip().str.zfill(3)
        df.columns = df.columns.str.strip()

        # Filtrar filas del cliente y vendedor
        filtered_rows = df[(df['Cliente'] == client_id) & (df['Vendedor'] == vendedor)]
        print("[DEBUG] Filtrado de filas:")
        print(filtered_rows)

        if filtered_rows.empty:
            return render_template(
                'result.html',
                message=f"No records found for Client ID: {client_id} and Vendedor: {vendedor}",
                data=None
            )

        first_row = filtered_rows.iloc[0][['Vendedor', 'Cliente', 'Nombre']].to_dict()

        # Mapeo de meses en español
        month_mapping = {
            "January": "Enero",
            "February": "Febrero",
            "March": "Marzo",
            "April": "Abril",
            "May": "Mayo",
            "June": "Junio",
            "July": "Julio",
            "August": "Agosto",
            "September": "Septiembre",
            "October": "Octubre",
            "November": "Noviembre",
            "December": "Diciembre"
        }

        # Columnas del mes actual
        current_year = datetime.now().strftime("%y")
        current_month = f"{month_mapping[datetime.now().strftime('%B')]} {current_year}"
        month_columns = [f"{month_mapping[datetime.now().strftime('%B')]} 24", f"{month_mapping[datetime.now().strftime('%B')]} 25"]

        grouped_data = defaultdict(list)
        for index, row in filtered_rows.iterrows():
            # Excluir filas donde Diciembre 24 y Diciembre 25 sean 0 o NaN
            if row[month_columns].fillna(0).sum() == 0:
                continue

            # Preparar los datos para la fila
            row_dict = row.to_dict()
            row_dict['unique_id'] = f"{row['Categoria']}-{index}"  # ID único basado en categoría e índice
            row_dict['Pedido1'] = row.get('Pedido1', 0)
            row_dict['Pedido2'] = row.get('Pedido2', 0)
            row_dict['Total'] = row_dict['Pedido1'] + row_dict['Pedido2']
            row_dict['Filtered Months'] = {
                col: row[col] if col in row and pd.notnull(row[col]) else 0
                for col in month_columns
            }
            grouped_data[row['Categoria']].append(row_dict)

        print("[DEBUG] Datos agrupados por categoría:")
        for category, rows in grouped_data.items():
            print(f"- {category}: {rows}")

        return render_template(
            'result.html',
            header_data=first_row,
            grouped_data=grouped_data,
            message="Análisis Exitoso!",
            month_columns=month_columns,
            current_month=current_month
        )

    except Exception as e:
        return f"An error occurred: {e}", 500

@app.route('/download_excel', methods=['POST'])
def download_excel():
    try:
        # Obtener datos procesados enviados desde el frontend
        data = request.form.getlist('data[]')
        processed_data = [eval(row) for row in data]  # Convertir las cadenas JSON a diccionarios

        print("[DEBUG] Datos procesados recibidos para el Excel:")
        print(processed_data)

        # Crear DataFrame para generar el archivo Excel
        output_df = pd.DataFrame(processed_data)

        # Generar Excel
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file_name = f"export_{timestamp}.xlsx"
        output_file_path = os.path.join(RESULT_FOLDER, output_file_name)
        output_df.to_excel(output_file_path, index=False)
        print(f"[DEBUG] Archivo Excel generado: {output_file_path}")

        return send_from_directory(RESULT_FOLDER, output_file_name, as_attachment=True)

    except Exception as e:
        print(f"[ERROR] Error al generar el archivo Excel: {str(e)}")
        return f"Guardado Exitosamente!{str(e)}", 500


if __name__ == '__main__':
    app.run(debug=True)
