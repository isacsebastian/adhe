from collections import defaultdict
from datetime import datetime
from flask import Flask, request, render_template, jsonify, send_file, make_response
import os
import pandas as pd
import tempfile
from fpdf import FPDF
import requests

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Definición de todas las carpetas base
BASE_DATA_DIR = 'data'
UPLOAD_FOLDER = os.path.join(BASE_DATA_DIR, 'uploaded_files')
RESULT_FOLDER = os.path.join(BASE_DATA_DIR, 'results')
ORDERS_FOLDER = os.path.join(BASE_DATA_DIR, 'orders')
ADDED_PRODUCTS_FOLDER = os.path.join(BASE_DATA_DIR, 'added_products')

# Definición de archivos
FILE_NAME = 'Basesdedatos.csv'
file_path = os.path.join(UPLOAD_FOLDER, FILE_NAME)
ADDED_PRODUCTS_FILE = os.path.join(ADDED_PRODUCTS_FOLDER, 'added_products.csv')

# Crear todas las carpetas necesarias
for folder in [UPLOAD_FOLDER, RESULT_FOLDER, ORDERS_FOLDER, ADDED_PRODUCTS_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Función para inicializar el archivo de persistencia
def initialize_persistence_file():
    if not os.path.exists(ADDED_PRODUCTS_FILE):
        # Crear el archivo CSV con las columnas necesarias
        pd.DataFrame(columns=[
            'Cliente', 'Vendedor', 'Categoria', 'Descripcion', 'Cantidad', 
            'Factor', 'Material', 'Presentacion', 'Embalaje'
        ]).to_csv(ADDED_PRODUCTS_FILE, index=False)

# Inicializar archivo de persistencia
initialize_persistence_file()

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
        # Leer el archivo CSV principal
        df = pd.read_csv(file_path, dtype={'Cliente': str, 'Vendedor': str})
        df.columns = df.columns.str.strip()

        client_id = str(client_id).strip()
        vendedor = str(int(vendedor)).zfill(3)
        df['Cliente'] = df['Cliente'].str.strip()
        df['Vendedor'] = df['Vendedor'].str.strip().str.zfill(3)

        # Buscar archivo de orders para este cliente/vendedor
        orders_file = f'latest_orders_{client_id}_{vendedor}.csv'
        orders_path = os.path.join(ORDERS_FOLDER, orders_file)

        # Crear diccionario de orders si existe el archivo
        orders_dict = {}
        if os.path.exists(orders_path):
            orders_df = pd.read_csv(orders_path)
            for _, order_row in orders_df.iterrows():
                orders_dict[order_row['material']] = {
                    'pedido1': order_row['pedido1'],
                    'pedido2': order_row['pedido2'],
                    'total': order_row['total']
                }

        month_columns = [
            "Jan-24", "Feb-24", "Mar-24", "Apr-24", "May-24", "Jun-24", "Jul-24", "Aug-24", "Sep-24", "Oct-24", "Nov-24", "Dec-24",
            "Jan-25", "Feb-25", "Mar-25", "Apr-25", "May-25", "Jun-25", "Jul-25", "Aug-25", "Sep-25", "Oct-25", "Nov-25", "Dec-25"
        ]

        for col in month_columns + ['Pedido1', 'Pedido2', 'Total']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        required_columns = ['Material', 'Descripcion', 'Presentacion']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return f"Error: Columnas faltantes en el archivo: {missing_columns}", 400

        filtered_rows = df[(df['Cliente'] == client_id) & (df['Vendedor'] == vendedor)]
        if filtered_rows.empty:
            return render_template('result.html', message=f"No records found for Client ID: {client_id} and Vendedor: {vendedor}", data=None)

        first_row = filtered_rows.iloc[0][['Vendedor', 'Cliente', 'Nombre']].to_dict()

        current_month = datetime.now().strftime("%b") + "-24"
        next_year_month = datetime.now().strftime("%b") + "-25"

        grouped_data = defaultdict(list)
        for index, row in filtered_rows.iterrows():
            current_month_value = row.get(current_month, 0)
            next_year_month_value = row.get(next_year_month, 0)
            if pd.isna(current_month_value) or current_month_value == 0:
                continue
            row_dict = row.to_dict()
            row_dict['unique_id'] = f"{row['Categoria']}-{index}"
            row_dict['Filtered Months'] = {
                current_month: current_month_value,
                next_year_month: next_year_month_value if not pd.isna(next_year_month_value) else 0
            }
            
            # Actualizar pedidos si existen en orders_dict y agregar indicador
            if row['Material'] in orders_dict:
                row_dict['Pedido1'] = orders_dict[row['Material']]['pedido1']
                row_dict['Pedido2'] = orders_dict[row['Material']]['pedido2']
                row_dict['Total'] = orders_dict[row['Material']]['total']
                row_dict['has_saved_order'] = True
            else:
                row_dict['Pedido1'] = 0
                row_dict['Pedido2'] = 0
                row_dict['Total'] = 0
                row_dict['has_saved_order'] = False
            
            grouped_data[row['Categoria']].append(row_dict)

        unique_categories = sorted(df['Categoria'].dropna().unique())

        # Leer productos agregados
        if os.path.exists(ADDED_PRODUCTS_FILE):
            added_df = pd.read_csv(ADDED_PRODUCTS_FILE, dtype=str)
        else:
            added_df = pd.DataFrame(columns=[
                'Cliente', 'Vendedor', 'Categoria', 'Descripcion', 'Cantidad', 
                'Factor', 'Material', 'Presentacion', 'Embalaje'
            ])

        filtered_products = added_df[
            (added_df['Cliente'] == client_id) & 
            (added_df['Vendedor'] == vendedor)
        ]

        products = filtered_products.to_dict(orient='records')

        return render_template(
            'result.html',
            header_data=first_row,
            grouped_data=grouped_data,
            message="Análisis Exitoso!",
            month_columns=[current_month, next_year_month],
            categorias=unique_categories,
            products=products,
            has_orders=bool(os.path.exists(orders_path)),
            current_month=current_month  
        )

    except Exception as e:
        return f"An error occurred: {e}", 500

@app.route('/save_orders', methods=['POST'])
def save_orders():
    try:
        # Obtener los datos del request
        data = request.get_json()
        client_id = data.get('client_id')
        vendedor = data.get('vendedor')
        orders = data.get('orders', [])
        
        # Crear el nombre del archivo fijo
        filename = f'latest_orders_{client_id}_{vendedor}.csv'
        orders_file = os.path.join(ORDERS_FOLDER, filename)
        
        # Eliminar archivo anterior si existe
        if os.path.exists(orders_file):
            os.remove(orders_file)
        
        # Crear DataFrame con los pedidos
        orders_df = pd.DataFrame(orders)
        orders_df['fecha_actualizacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        orders_df['cliente'] = client_id
        orders_df['vendedor'] = vendedor
        
        # Guardar en CSV
        orders_df.to_csv(orders_file, index=False)
        
        return jsonify({
            "success": True,
            "message": "Pedidos actualizados exitosamente",
            "filename": filename
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500



@app.route('/add_product', methods=['POST'])
def add_product():
    ADDED_PRODUCTS_FOLDER = os.path.join('data', 'added_products')
    ADDED_PRODUCTS_FILE = os.path.join(ADDED_PRODUCTS_FOLDER, 'added_products.csv')
    os.makedirs(ADDED_PRODUCTS_FOLDER, exist_ok=True)

    # Inicializar el archivo de persistencia si no existe
    if not os.path.exists(ADDED_PRODUCTS_FILE):
        pd.DataFrame(columns=['Cliente', 'Vendedor', 'Categoria', 'Descripcion', 'Cantidad', 'Factor', 'Material', 'Presentacion', 'Embalaje']) \
          .to_csv(ADDED_PRODUCTS_FILE, index=False)

    # Obtener datos del formulario
    categoria = request.form.get('categoria')
    producto = request.form.get('producto')
    cantidad = request.form.get('cantidad')
    client_id = request.form.get('client_id')
    vendedor = request.form.get('vendedor')

    # Validar los campos obligatorios
    if not all([categoria, producto, cantidad, client_id, vendedor]):
        return jsonify({"error": "Todos los campos son obligatorios. Verifica los datos ingresados."}), 400

    if not os.path.exists(file_path):
        return jsonify({"error": f"Archivo '{FILE_NAME}' no encontrado en '{UPLOAD_FOLDER}'."}), 404

    try:
        # Validar que cantidad sea un número positivo
        cantidad = int(cantidad)
        if cantidad <= 0:
            return jsonify({"error": "La cantidad debe ser mayor que 0."}), 400

        # Leer el archivo CSV original
        df = pd.read_csv(file_path, dtype=str, low_memory=False)
        df.columns = df.columns.str.strip()

        # Validar columnas necesarias
        required_columns = ['Categoria', 'Descripcion', 'Factor', 'Material', 'Presentacion', 'Embalaje']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return jsonify({"error": f"El archivo CSV no contiene las columnas requeridas: {missing_columns}"}), 400

        # Filtrar los datos según la categoría y descripción proporcionadas y eliminar duplicados
        filtered_row = df[(df['Categoria'].str.strip() == categoria) &
                         (df['Descripcion'].str.strip() == producto)] \
                        .drop_duplicates(subset=['Categoria', 'Descripcion']) \
                        .reset_index(drop=True)

        if filtered_row.empty:
            return jsonify({"error": "No se encontró un producto con la categoría y descripción proporcionadas."}), 404

        # Obtener valores preestablecidos del archivo original
        factor = int(filtered_row.iloc[0]['Factor'])
        material = filtered_row.iloc[0]['Material']
        presentacion = filtered_row.iloc[0]['Presentacion']
        embalaje = filtered_row.iloc[0]['Embalaje']

        # Validar cantidad múltiplo del factor
        if cantidad % factor != 0:
            return jsonify({
                "error": f"La cantidad debe ser múltiplo de {factor}. Por favor, ingrese un número que sea múltiplo de {factor}.",
                "factor": factor
            }), 400

        # Leer o inicializar el archivo de persistencia
        if os.path.exists(ADDED_PRODUCTS_FILE) and os.path.getsize(ADDED_PRODUCTS_FILE) > 0:
            added_df = pd.read_csv(ADDED_PRODUCTS_FILE, dtype=str)
        else:
            added_df = pd.DataFrame(columns=['Cliente', 'Vendedor', 'Categoria', 'Descripcion', 'Cantidad', 'Factor', 'Material', 'Presentacion', 'Embalaje'])

        # Verificar si ya existe un registro para cliente, vendedor, categoría y producto
        existing_row = added_df[(added_df['Cliente'].str.strip() == client_id) &
                              (added_df['Vendedor'].str.strip() == vendedor) &
                              (added_df['Categoria'].str.strip() == categoria) &
                              (added_df['Descripcion'].str.strip() == producto)]

        if not existing_row.empty:
            # Actualizar cantidad existente
            index = existing_row.index[0]
            added_df.at[index, 'Cantidad'] = int(added_df.at[index, 'Cantidad']) + cantidad
        else:
            # Agregar un nuevo registro
            new_row = {
                'Cliente': client_id.strip(),
                'Vendedor': vendedor.strip(),
                'Categoria': categoria.strip(),
                'Descripcion': producto.strip(),
                'Cantidad': cantidad,
                'Factor': factor,
                'Material': material,
                'Presentacion': presentacion,
                'Embalaje': embalaje
            }
            added_df = pd.concat([added_df, pd.DataFrame([new_row])], ignore_index=True)

        # Guardar los datos actualizados en el archivo de persistencia
        added_df.to_csv(ADDED_PRODUCTS_FILE, index=False)

        return jsonify({
            "success": True,
            "cliente": client_id,
            "vendedor": vendedor,
            "categoria": categoria,
            "producto": producto,
            "cantidad": cantidad,
            "factor": factor,
            "material": material,
            "presentacion": presentacion,
            "embalaje": embalaje,
            "message": "Producto agregado y persistido exitosamente."
        })

    except ValueError:
        return jsonify({"error": "La cantidad debe ser un número válido."}), 400

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

        # Modificamos esta línea para incluir Factor
        required_columns = ['Categoria', 'Descripcion', 'Material', 'Presentacion', 'Embalaje', 'Factor']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return jsonify({"error": f"El archivo CSV no contiene las columnas requeridas: {missing_columns}"}), 400

        # Modificamos esta línea para incluir Factor en la selección
        filtered_products = df[df['Categoria'].str.strip() == categoria][
            ['Descripcion', 'Material', 'Presentacion', 'Embalaje', 'Factor']
        ].dropna()

        if filtered_products.empty:
            return jsonify({"error": "No se encontraron productos para la categoría proporcionada."}), 404

        products = filtered_products.to_dict(orient='records')
        return jsonify({"products": products})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route('/get_products', methods=['GET'])
def get_products():
    try:
        categoria = request.args.get('categoria')
        if not categoria:
            return jsonify({"error": "Categoría no proporcionada"}), 400

        df = pd.read_csv(file_path, dtype=str, low_memory=False)
        df.columns = df.columns.str.strip()

        # Filtrado mejorado con limpieza de strings
        df['Categoria'] = df['Categoria'].str.strip()
        df['Descripcion'] = df['Descripcion'].str.strip()
        
        filtered_df = df[df['Categoria'] == categoria.strip()]
        
        # Eliminar duplicados considerando todas las características relevantes
        unique_products = filtered_df.drop_duplicates(
            subset=['Descripcion', 'Material', 'Presentacion', 'Factor'],
            keep='first'
        ).sort_values('Descripcion')

        productos = unique_products[['Descripcion', 'Material', 'Presentacion', 'Factor']].to_dict('records')
        return jsonify({"productos": productos})

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
        df = pd.read_csv(file_path, dtype={'Cliente': str, 'Vendedor': str})
        df.columns = df.columns.str.strip()

        client_id = client_id.strip()
        vendedor = str(int(vendedor)).zfill(3)
        df['Cliente'] = df['Cliente'].str.strip()
        df['Vendedor'] = df['Vendedor'].str.strip().str.zfill(3)

        filtered_rows = df[(df['Cliente'] == client_id) & (df['Vendedor'] == vendedor)]

        if filtered_rows.empty:
            return jsonify({"error": "No records found to export."}), 404

        month_column = datetime.now().strftime("%b") + "-24"
        required_columns = ['Vendedor', 'Cliente', 'Categoria', 'Material', 'Descripcion', month_column]
        missing_columns = [col for col in required_columns if col not in filtered_rows.columns]
        if missing_columns:
            return jsonify({"error": f"Columnas faltantes en el archivo: {missing_columns}"}), 400

        filtered_rows[month_column] = pd.to_numeric(filtered_rows[month_column], errors='coerce')
        filtered_rows = filtered_rows[filtered_rows[month_column] > 0]

        if filtered_rows.empty:
            return jsonify({"error": "No hay datos válidos después del filtrado."}), 404

        pdf = FPDF(orientation='L', unit='mm', format='A4')
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        pdf.set_font("Arial", style="B", size=14)
        pdf.cell(0, 10, f"Reporte de Datos Filtrados - {datetime.now().strftime('%B %Y')}", ln=True, align="C")
        pdf.ln(10)

        # Insertar PNG en el encabezado
        png_path = os.path.join('app', 'assets', 'Azul.png')
        if os.path.exists(png_path):
            pdf.image(png_path, x=10, y=8, w=30)  # Ajustar posición y tamaño del PNG

        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 10, "Información General", ln=True, align="L")
        pdf.set_font("Arial", size=10)
        pdf.cell(50, 10, f"Vendedor: {vendedor}", ln=True)
        pdf.cell(50, 10, f"Cliente: {client_id}", ln=True)
        pdf.ln(10)

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
    return render_template('result.html')

@app.route('/response')
def response():
    return render_template('response.html')

if __name__ == '__main__':
    app.run(debug=True)

