from collections import defaultdict
from datetime import datetime
from flask import Flask, request, render_template, jsonify, send_file
import os
import pandas as pd
import tempfile
from flask import redirect, url_for

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

    if not client_id or not vendedor:
        return render_template('index.html', error="Los campos Cliente ID y Vendedor ID son obligatorios.")

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
            return render_template('result.html', message=f"No records found for Client ID: {client_id} and Vendedor: {vendedor}", data=None)

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
            # Excluir filas donde las columnas de los meses sean 0 o NaN
            if row[month_columns].fillna(0).sum() == 0:
                continue

            # Preparar los datos para la fila
            row_dict = row.to_dict()
            row_dict['unique_id'] = f"{row['Categoria']}-{index}"
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

        # Obtener las categorías únicas para la lista desplegable
        unique_categories = sorted(df['Categoria'].dropna().unique())

        return render_template(
            'result.html',
            header_data=first_row,
            grouped_data=grouped_data,
            message="Análisis Exitoso!",
            month_columns=month_columns,
            current_month=current_month,
            categorias=unique_categories
        )

    except ValueError as ve:
        return render_template('index.html', error=f"Error en los datos de entrada: {ve}")

    except Exception as e:
        return f"An error occurred: {e}", 500

@app.route('/products_by_category', methods=['GET'])
def products_by_category():
    categoria = request.args.get('categoria')

    if not categoria:
        return jsonify({"error": "El campo categoría es obligatorio."}), 400

    if not os.path.exists(file_path):
        return jsonify({"error": f"File '{FILE_NAME}' not found in '{UPLOAD_FOLDER}'."}), 404

    try:
        # Leer el archivo CSV
        df = pd.read_csv(file_path)

        # Asegurarse de que las columnas clave estén presentes
        if 'Categoria' not in df.columns or 'Descripción' not in df.columns:
            return jsonify({"error": "Las columnas necesarias no están presentes en el archivo CSV."}), 400

        # Filtrar productos por categoría
        filtered_products = df[df['Categoria'].str.strip() == categoria]['Descripción'].dropna().unique().tolist()

        if not filtered_products:
            return jsonify({"error": "No se encontraron productos para la categoría proporcionada."}), 404

        # Devolver los productos como JSON
        return jsonify({"products": filtered_products})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

from flask import redirect, url_for

@app.route('/add_product', methods=['POST'])
def add_product():
    categoria = request.form.get('categoria')
    producto = request.form.get('producto')
    cantidad = request.form.get('cantidad')

    if not categoria or not producto or not cantidad:
        return render_template('response.html', message="Error: Todos los campos son obligatorios.")

    try:
        # Simular guardar el producto (puedes agregar la lógica de guardado aquí)
        print(f"[DEBUG] Producto agregado: Categoría={categoria}, Producto={producto}, Cantidad={cantidad}")

        # Renderizar response.html con un mensaje de éxito
        return render_template('response.html', message=f"Producto '{producto}' agregado exitosamente a la categoría '{categoria}' con cantidad {cantidad}.")
    except Exception as e:
        # Manejar errores y renderizar response.html con un mensaje de error
        return render_template('response.html', message=f"Error al agregar el producto: {e}")

@app.route('/download_filtered_data', methods=['POST'])
def download_filtered_data():
    client_id = request.form.get('client_id')
    vendedor = request.form.get('vendedor')

    # Validar entrada
    if not client_id or not vendedor:
        return jsonify({"error": "Los campos Cliente y Vendedor son obligatorios."}), 400

    if not os.path.exists(file_path):
        return jsonify({"error": f"File '{FILE_NAME}' not found in '{UPLOAD_FOLDER}'."}), 404

    try:
        # Leer el archivo CSV
        df = pd.read_csv(file_path, dtype={'Cliente': str, 'Vendedor': str})

        client_id = client_id.strip()
        vendedor = str(int(vendedor)).zfill(3)
        df['Cliente'] = df['Cliente'].str.strip()
        df['Vendedor'] = df['Vendedor'].str.strip().str.zfill(3)

        # Filtrar filas del cliente y vendedor
        filtered_rows = df[(df['Cliente'] == client_id) & (df['Vendedor'] == vendedor)]

        if filtered_rows.empty:
            return jsonify({"error": "No records found to export."}), 404

        # Guardar el archivo temporalmente y descargar directamente
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
            filtered_rows.to_csv(temp_file.name, index=False)
            temp_file_path = temp_file.name

        return send_file(
            temp_file_path,
            as_attachment=True,
            download_name=f"filtered_data_{client_id}_{vendedor}.csv",
            mimetype='text/csv'
        )

    except ValueError as ve:
        return jsonify({"error": f"Error de validación: {ve}"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
