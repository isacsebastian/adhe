from collections import defaultdict
from datetime import datetime
from flask import Flask, request, render_template, jsonify, send_file, make_response
import os
import pandas as pd
import tempfile
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Configuración de carpetas
UPLOAD_FOLDER = os.path.join('data', 'uploaded_files')
ANALYZED_FOLDER = os.path.join('data', 'analyzed')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ANALYZED_FOLDER, exist_ok=True)

FILE_NAME = 'Basesdedatos.csv'
file_path = os.path.join(UPLOAD_FOLDER, FILE_NAME)
csv_file = os.path.join(ANALYZED_FOLDER, 'persisted_data.csv')

# Funciones para manejo de persistencia en CSV
def load_from_csv():
    if os.path.exists(csv_file):
        return pd.read_csv(csv_file)
    else:
        return pd.DataFrame()

def save_to_csv(data):
    if os.path.exists(csv_file):
        existing_data = pd.read_csv(csv_file)
        combined_data = pd.concat([existing_data, data], ignore_index=True)
        combined_data = combined_data.drop_duplicates(subset=['Vendedor', 'Cliente', 'Categoria', 'Material', 'Descripcion'])
    else:
        combined_data = data
    combined_data.to_csv(csv_file, index=False)

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
        # Leer el archivo base
        df = pd.read_csv(file_path, dtype={'Cliente': str, 'Vendedor': str})
        df.columns = df.columns.str.strip()

        client_id = str(client_id).strip()
        vendedor = str(int(vendedor)).zfill(3)
        df['Cliente'] = df['Cliente'].str.strip()
        df['Vendedor'] = df['Vendedor'].str.strip().str.zfill(3)

        filtered_rows = df[(df['Cliente'] == client_id) & (df['Vendedor'] == vendedor)]
        if filtered_rows.empty:
            return render_template('result.html', message=f"No records found for Client ID: {client_id} and Vendedor: {vendedor}", data=None)

        # Guardar datos filtrados
        save_to_csv(filtered_rows)

        # Agrupar datos para visualización
        grouped_data = defaultdict(list)
        for _, row in filtered_rows.iterrows():
            row_dict = row.to_dict()
            grouped_data[row['Categoria']].append(row_dict)

        return render_template(
            'result.html',
            grouped_data=grouped_data,
            message="Análisis Exitoso!"
        )

    except Exception as e:
        return f"An error occurred: {e}", 500

@app.route('/add_product', methods=['POST'])
def add_product():
    categoria = request.form.get('categoria')
    producto = request.form.get('producto')
    cantidad = request.form.get('cantidad')
    vendedor = request.form.get('vendedor')
    cliente = request.form.get('client_id')

    if not categoria or not producto or not cantidad or not vendedor or not cliente:
        return jsonify({"error": "Todos los campos son obligatorios."}), 400

    try:
        new_data = pd.DataFrame([{
            'Cliente': cliente,
            'Vendedor': vendedor,
            'Categoria': categoria,
            'Descripcion': producto,
            'Cantidad': int(cantidad)
        }])

        save_to_csv(new_data)

        return jsonify({"success": True, "message": "Producto agregado exitosamente."})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/products_by_category', methods=['GET'])
def products_by_category():
    categoria = request.args.get('categoria')

    if not categoria:
        return jsonify({"error": "El campo categoría es obligatorio."}), 400

    if not os.path.exists(file_path):
        return jsonify({"error": f"File '{FILE_NAME}' not found in '{UPLOAD_FOLDER}'."}), 404

    try:
        df = pd.read_csv(file_path)
        df.columns = df.columns.str.strip()

        filtered_products = df[df['Categoria'].str.strip() == categoria]['Descripcion'].dropna().unique().tolist()

        if not filtered_products:
            return jsonify({"error": "No se encontraron productos para la categoría proporcionada."}), 404

        return jsonify({"products": filtered_products})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download_filtered_data', methods=['POST'])
def download_filtered_data():
    client_id = request.form.get('client_id')
    vendedor = request.form.get('vendedor')

    if not client_id or not vendedor:
        return jsonify({"error": "Los campos Cliente y Vendedor son obligatorios."}), 400

    try:
        df = load_from_csv()

        filtered_rows = df[(df['Cliente'] == client_id) & (df['Vendedor'] == vendedor)]

        if filtered_rows.empty:
            return jsonify({"error": "No records found to export."}), 404

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        pdf.cell(200, 10, txt="Reporte de Datos Filtrados", ln=True, align='C')

        for index, row in filtered_rows.iterrows():
            pdf.cell(200, 10, txt=str(row.to_dict()), ln=True)

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            pdf.output(temp_pdf.name)
            return send_file(temp_pdf.name, as_attachment=True, download_name="Filtered_Data.pdf")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
