from collections import defaultdict
from datetime import datetime
from flask import Flask, request, render_template, jsonify, send_file, redirect, url_for, session, make_response
import os
import pandas as pd
import tempfile
from fpdf import FPDF


app = Flask(__name__)
app.secret_key = "your_secret_key"

UPLOAD_FOLDER = os.path.join('data', 'uploaded_files')
RESULT_FOLDER = os.path.join('data', 'results')
os.makedirs(RESULT_FOLDER, exist_ok=True)

FILE_NAME = 'NuevaBase.csv'
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
        df.columns = df.columns.str.strip()  # Limpiar espacios en los nombres de columnas
        print("[DEBUG] Columnas disponibles en el archivo:")
        print(df.columns.tolist())

        client_id = str(client_id).strip()
        vendedor = str(int(vendedor)).zfill(3)
        df['Cliente'] = df['Cliente'].str.strip()
        df['Vendedor'] = df['Vendedor'].str.strip().str.zfill(3)

        # Asegúrate de que todas las columnas de meses sean numéricas
        month_columns = [
            "Jan-24", "Feb-24", "Mar-24", "Apr-24", "May-24", "Jun-24", "Jul-24", "Aug-24", "Sep-24", "Oct-24", "Nov-24", "Dec-24",
            "Jan-25", "Feb-25", "Mar-25", "Apr-25", "May-25", "Jun-25", "Jul-25", "Aug-25", "Sep-25", "Oct-25", "Nov-25", "Dec-25"
        ]

        for col in month_columns + ['Pedido1', 'Pedido2', 'Total']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Convertir Presentación a texto para asegurar valores consistentes
        if 'Presentacion' in df.columns:
            df['Presentacion'] = df['Presentacion'].fillna('N/A').astype(str)

        # Validar que las columnas requeridas estén presentes
        required_columns = ['Material', 'Descripcion', 'Presentacion']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return f"Error: Columnas faltantes en el archivo: {missing_columns}", 400

        # Filtrar filas del cliente y vendedor
        filtered_rows = df[(df['Cliente'] == client_id) & (df['Vendedor'] == vendedor)]
        print("[DEBUG] Filtrado de filas:")
        print(filtered_rows)

        if filtered_rows.empty:
            return render_template('result.html', message=f"No records found for Client ID: {client_id} and Vendedor: {vendedor}", data=None)

        first_row = filtered_rows.iloc[0][['Vendedor', 'Cliente', 'Nombre']].to_dict()

        # Obtener el mes actual
        current_month = datetime.now().strftime("%b") + "-24"
        next_year_month = datetime.now().strftime("%b") + "-25"

        if current_month not in month_columns or next_year_month not in month_columns:
            return render_template('result.html', message="Mes actual no encontrado en las columnas.", data=None)

        grouped_data = defaultdict(list)
        for index, row in filtered_rows.iterrows():
            # Preparar los datos para la fila
            current_month_value = row.get(current_month, 0)
            next_year_month_value = row.get(next_year_month, 0)

            # Omitir si el valor del mes actual es 0 o NaN
            if pd.isna(current_month_value) or current_month_value == 0:
                continue

            row_dict = row.to_dict()
            row_dict['unique_id'] = f"{row['Categoria']}-{index}"

            row_dict['Filtered Months'] = {
                current_month: current_month_value,
                next_year_month: next_year_month_value if not pd.isna(next_year_month_value) else 0
            }

            # Asegurarse de que Material, Descripcion, y Presentacion estén presentes
            row_dict['Material'] = row.get('Material', 'N/A')
            row_dict['Descripcion'] = row.get('Descripcion', 'N/A')
            row_dict['Presentacion'] = row.get('Presentacion', 'N/A')

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
            month_columns=[current_month, next_year_month],
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
        df.columns = df.columns.str.strip()

        # Asegurarse de que las columnas clave estén presentes
        if 'Categoria' not in df.columns or 'Descripcion' not in df.columns:
            return jsonify({"error": "Las columnas necesarias no están presentes en el archivo CSV."}), 400

        # Filtrar productos por categoría
        filtered_products = df[df['Categoria'].str.strip() == categoria]['Descripcion'].dropna().unique().tolist()

        if not filtered_products:
            return jsonify({"error": "No se encontraron productos para la categoría proporcionada."}), 404

        # Devolver los productos como JSON
        return jsonify({"products": filtered_products})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add_product', methods=['POST'])
def add_product():
    # Obtener los datos enviados desde el formulario
    categoria = request.form.get('categoria')
    producto = request.form.get('producto')
    cantidad = request.form.get('cantidad')

    # Validar los datos
    if not categoria or not producto or not cantidad:
        return jsonify({"error": "Todos los campos son obligatorios."}), 400

    try:
        cantidad = int(cantidad)
        if cantidad <= 0:
            return jsonify({"error": "La cantidad debe ser mayor que 0."}), 400

        # Devolver una respuesta para confirmar que se recibió correctamente
        return jsonify({
            "success": True,
            "categoria": categoria,
            "producto": producto,
            "cantidad": cantidad
        })

    except ValueError:
        return jsonify({"error": "La cantidad debe ser un número válido."}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/download_filtered_data', methods=['POST'])
def download_filtered_data():
    client_id = request.form.get('client_id')
    vendedor = request.form.get('vendedor')

    if not client_id or not vendedor:
        return jsonify({"error": "Los campos Cliente y Vendedor son obligatorios."}), 400

    if not os.path.exists(file_path):
        return jsonify({"error": f"File '{FILE_NAME}' not found in '{UPLOAD_FOLDER}'."}), 404

    try:
        # Leer el archivo CSV
        df = pd.read_csv(file_path, dtype={'Cliente': str, 'Vendedor': str})
        df.columns = df.columns.str.strip()

        client_id = client_id.strip()
        vendedor = str(int(vendedor)).zfill(3)
        df['Cliente'] = df['Cliente'].str.strip()
        df['Vendedor'] = df['Vendedor'].str.strip().str.zfill(3)

        # Filtrar filas del cliente y vendedor
        filtered_rows = df[(df['Cliente'] == client_id) & (df['Vendedor'] == vendedor)]

        if filtered_rows.empty:
            return jsonify({"error": "No records found to export."}), 404

        # Filtrar valores 0 o NaN de las columnas requeridas
        month_column = datetime.now().strftime("%b") + "-24"
        required_columns = ['Vendedor', 'Cliente', 'Categoria', 'Material', 'Descripcion', month_column]
        missing_columns = [col for col in required_columns if col not in filtered_rows.columns]
        if missing_columns:
            return jsonify({"error": f"Columnas faltantes en el archivo: {missing_columns}"}), 400

        # Eliminar filas con 0 o NaN en el mes actual
        filtered_rows[month_column] = pd.to_numeric(filtered_rows[month_column], errors='coerce')
        filtered_rows = filtered_rows[filtered_rows[month_column] > 0]

        if filtered_rows.empty:
            return jsonify({"error": "No hay datos válidos después del filtrado."}), 404

        # Obtener productos nuevos desde la sesión (puedes adaptarlo a tu fuente de datos)
        new_products = session.get('productos', [])

        # Crear el PDF
        pdf = FPDF(orientation='L', unit='mm', format='A4')
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        # Encabezado principal
        pdf.set_font("Arial", style="B", size=14)
        pdf.cell(0, 10, f"Reporte de Datos Filtrados - {datetime.now().strftime('%B %Y')}", ln=True, align="C")
        pdf.ln(10)

        # Información general
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 10, "Información General", ln=True, align="L")
        pdf.set_font("Arial", size=10)
        pdf.cell(50, 10, f"Vendedor: {vendedor}", ln=True)
        pdf.cell(50, 10, f"Cliente: {client_id}", ln=True)
        pdf.ln(10)

        # Tabla de datos filtrados
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 10, "Datos Filtrados", ln=True, align="L")
        pdf.ln(5)

        column_widths = [25, 25, 70, 30, 85, 20]
        headers = ['Vendedor', 'Cliente', 'Categoria', 'Material', 'Descripcion', month_column]
        pdf.set_font("Arial", style="B", size=10)
        for i, header in enumerate(headers):
            pdf.cell(column_widths[i], 10, header, border=1, align="C")
        pdf.ln()

        for _, row in filtered_rows.iterrows():
            pdf.set_font("Arial", size=10)
            pdf.cell(column_widths[0], 10, str(row['Vendedor']), border=1, align="C")
            pdf.cell(column_widths[1], 10, str(row['Cliente']), border=1, align="C")
            pdf.cell(column_widths[2], 10, str(row['Categoria']), border=1, align="L")
            pdf.cell(column_widths[3], 10, str(row['Material']), border=1, align="C")
            pdf.cell(column_widths[4], 10, str(row['Descripcion']), border=1, align="L")
            pdf.cell(column_widths[5], 10, f"{row[month_column]:.2f}", border=1, align="C")
            pdf.ln()

        # Agregar tabla de productos nuevos
        if new_products:
            pdf.ln(10)
            pdf.set_font("Arial", style="B", size=12)
            pdf.cell(0, 10, "Productos Nuevos Agregados", ln=True, align="L")
            pdf.ln(5)

            column_widths = [70, 70, 30]
            headers = ['Categoria', 'Producto', 'Cantidad']
            pdf.set_font("Arial", style="B", size=10)
            for i, header in enumerate(headers):
                pdf.cell(column_widths[i], 10, header, border=1, align="C")
            pdf.ln()

            for product in new_products:
                pdf.set_font("Arial", size=10)
                pdf.cell(column_widths[0], 10, product['categoria'], border=1, align="L")
                pdf.cell(column_widths[1], 10, product['producto'], border=1, align="L")
                pdf.cell(column_widths[2], 10, str(product['cantidad']), border=1, align="C")
                pdf.ln()

        # Guardar y devolver el PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            temp_pdf_path = temp_pdf.name
            pdf.output(temp_pdf_path)

        response = make_response(send_file(
            temp_pdf_path,
            as_attachment=True,
            download_name=f"Datos_Adheplast_{client_id}_{vendedor}.pdf",
            mimetype='application/pdf'
        ))
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f"attachment; filename=Datos_Adheplast_{client_id}_{vendedor}.pdf"
        return response

    except ValueError as ve:
        return jsonify({"error": f"Error de validación: {ve}"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/result')
def result():
    # Renderiza la página de resultados
    return render_template('result.html')

@app.route('/response')
def response():
    # Renderiza la página de respuesta
    return render_template('response.html')

if __name__ == '__main__':
    app.run(debug=True)
