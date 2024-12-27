from collections import defaultdict
from datetime import datetime
from flask import Flask, request, render_template
import os
import pandas as pd

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join('data', 'uploaded_files')
RESULT_FOLDER = os.path.join('data', 'filtered_results')
FILE_NAME = 'Basetest.xlsx'
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
        # Leer el archivo Excel y forzar las columnas 'Cliente' y 'Vendedor' como cadenas
        df = pd.read_excel(file_path, dtype={'Cliente': str, 'Vendedor': str})

        # Normalizar los valores ingresados por el usuario
        client_id = str(client_id).strip()
        vendedor = str(int(vendedor)).zfill(3)

        # Normalizar los valores en el DataFrame
        df['Cliente'] = df['Cliente'].str.strip()
        df['Vendedor'] = df['Vendedor'].str.strip().str.zfill(3)
        df.columns = df.columns.str.strip()

        # Verificar los nombres de las columnas
        print("Nombres de las columnas en el DataFrame:")
        print(df.columns.tolist())

        # Filtrar las filas que coincidan con el cliente y el vendedor
        filtered_rows = df[(df['Cliente'] == client_id) & (df['Vendedor'] == vendedor)]
        if filtered_rows.empty:
            return render_template(
                'result.html', 
                message=f"No records found for Client ID: {client_id} and Vendedor: {vendedor}", 
                data=None
            )

        # Obtener la primera fila (para Vendedor, Cliente, Nombre)
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

        # Obtener el mes actual en español
        current_year = datetime.now().strftime("%y")  # Año corto, e.g., '25'
        current_month = f"{month_mapping[datetime.now().strftime('%B')]} {current_year}"
        month_columns = [f"{month_mapping[datetime.now().strftime('%B')]} 24", f"{month_mapping[datetime.now().strftime('%B')]} 25"]
        
        # Agrupar los datos por categoría
        grouped_data = defaultdict(list)
        for _, row in filtered_rows.iterrows():
            category = row['Categoria']
            print(f"Categoría: {category}")
            print(f"Filtrando meses: {month_columns}")
            print("Datos antes de filtrar meses:")
            print(row)

            row_dict = row.to_dict()
            row_dict['Filtered Months'] = {
                col: row[col] if col in row and pd.notnull(row[col]) else 0
                for col in month_columns
            }

            # Verificar si todos los valores de 'Filtered Months' son 0 o NaN
            if all(value == 0 for value in row_dict['Filtered Months'].values()):
                continue  # Omitir esta fila si todos los valores son 0

            # Agregar valores por defecto para las nuevas columnas
            row_dict['pedido1'] = 0
            row_dict['pedido2'] = 0
            row_dict['total'] = 0

            print("Meses filtrados (Filtered Months):")
            print(row_dict['Filtered Months'])

            grouped_data[category].append(row_dict)

        # Imprimir datos enviados para depuración
        print("Datos agrupados por categoría:")
        for category, rows in grouped_data.items():
            print(f"Categoría: {category}, Filas: {rows}")

        return render_template(
            'result.html', 
            header_data=first_row, 
            grouped_data=grouped_data, 
            message="Analysis successful!",
            month_columns=month_columns,
            current_month=current_month  # Asegura que current_month esté disponible
        )

    except Exception as e:
        return f"An error occurred: {e}", 500

@app.route('/save', methods=['POST'])
def save_data():
    """Guarda los valores ingresados de Pedido1, Pedido2 y Total en el archivo Excel."""
    try:
        # Leer los datos enviados desde el formulario
        pedidos = request.form.to_dict()

        # Leer el archivo Excel original
        df = pd.read_excel(file_path)

        # Crear columnas para Pedido1, Pedido2 y Total si no existen
        if 'Pedido1' not in df.columns:
            df['Pedido1'] = None
        if 'Pedido2' not in df.columns:
            df['Pedido2'] = None
        if 'Total' not in df.columns:
            df['Total'] = None

        # Actualizar el DataFrame con los valores recibidos
        for key, value in pedidos.items():
            if key.startswith('pedido1-'):
                index = int(key.split('-')[1])
                df.at[index, 'Pedido1'] = float(value) if value else None
            elif key.startswith('pedido2-'):
                index = int(key.split('-')[1])
                df.at[index, 'Pedido2'] = float(value) if value else None
            elif key.startswith('total-'):
                index = int(key.split('-')[1])
                df.at[index, 'Total'] = float(value) if value else None

        # Guardar los datos actualizados en el archivo Excel
        df.to_excel(file_path, index=False)

        return "Datos guardados exitosamente.", 200
    except Exception as e:
        return f"Error al guardar los datos: {e}", 500

if __name__ == '__main__':
    app.run(debug=True)
