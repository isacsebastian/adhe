from collections import defaultdict
from datetime import datetime
from flask import Flask, request, render_template, redirect, url_for
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
        df = pd.read_csv(file_path, dtype={'Cliente': str, 'Vendedor': str})
        client_id = str(client_id).strip()
        vendedor = str(int(vendedor)).zfill(3)
        df['Cliente'] = df['Cliente'].str.strip()
        df['Vendedor'] = df['Vendedor'].str.strip().str.zfill(3)
        df.columns = df.columns.str.strip()

        filtered_rows = df[(df['Cliente'] == client_id) & (df['Vendedor'] == vendedor)]
        if filtered_rows.empty:
            return render_template(
                'result.html',
                message=f"No records found for Client ID: {client_id} and Vendedor: {vendedor}",
                data=None
            )

        first_row = filtered_rows.iloc[0][['Vendedor', 'Cliente', 'Nombre']].to_dict()

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

        current_year = datetime.now().strftime("%y")
        current_month = f"{month_mapping[datetime.now().strftime('%B')]} {current_year}"
        month_columns = [f"{month_mapping[datetime.now().strftime('%B')]} 24", f"{month_mapping[datetime.now().strftime('%B')]} 25"]

        grouped_data = defaultdict(list)
        for index, row in filtered_rows.iterrows():
            row_dict = row.to_dict()
            row_dict['unique_id'] = f"{row['Categoria']}-{index}"  # ID único basado en categoría e índice
            row_dict['Pedido1'] = row.get('Pedido1', 0)
            row_dict['Pedido2'] = row.get('Pedido2', 0)
            row_dict['Total'] = row_dict['Pedido1'] + row_dict['Pedido2']
            row_dict['Filtered Months'] = {col: row[col] if col in row and pd.notnull(row[col]) else 0 for col in month_columns}
            grouped_data[row['Categoria']].append(row_dict)

        return render_template(
            'result.html',
            header_data=first_row,
            grouped_data=grouped_data,
            message="Analysis successful!",
            month_columns=month_columns,
            current_month=current_month
        )

    except Exception as e:
        return f"An error occurred: {e}", 500

@app.route('/save', methods=['POST'])
def save_data():
    try:
        form_data = request.form.to_dict()

        output_data = []

        for key, value in form_data.items():
            if key.startswith('pedido1-') or key.startswith('pedido2-'):
                parts = key.split('-')
                unique_id = parts[1]  # Obtenemos el identificador único
                while len(output_data) <= len(output_data):
                    output_data.append({'Unique ID': unique_id, 'Pedido1': 0, 'Pedido2': 0, 'Total': 0, 'Estado': '', 'Referencia': 0})
                if key.startswith('pedido1-'):
                    output_data[-1]['Pedido1'] = float(value) if value else 0
                elif key.startswith('pedido2-'):
                    output_data[-1]['Pedido2'] = float(value) if value else 0

        for row in output_data:
            row['Total'] = row['Pedido1'] + row['Pedido2']
            referencia = float(row.get('Referencia', 0))
            row['Estado'] = 'Mayor' if row['Total'] > referencia else 'Menor'

        output_df = pd.DataFrame(output_data)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file_path = os.path.join(RESULT_FOLDER, f"output_{timestamp}.xlsx")
        output_df.to_excel(output_file_path, index=False)

        return f"Datos guardados exitosamente en {output_file_path}", 200
    except Exception as e:
        return f"Error al guardar los datos: {e}", 500

if __name__ == '__main__':
    app.run(debug=True)
