import os
import sqlite3
import logging
import pandas as pd
import io
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, send_file, jsonify
from werkzeug.utils import secure_filename
from extract import extract_invoice_data
from datetime import datetime
from calendar import monthrange

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Configure upload folder
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Allowed file extensions
ALLOWED_EXTENSIONS = {"pdf", "xlsx", "xls"}

# Database initialization
DATABASE = "database.db"

def get_db_connection():
    """Helper function to connect to the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database and create tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # ✅ Recreate the invoices table WITHOUT the 'category' column
    cursor.execute('''CREATE TABLE IF NOT EXISTS invoices (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nomor TEXT,
                        tanggal DATE,
                        kepada TEXT,
                        dari TEXT,
                        pembayaran TEXT,
                        jumlah DECIMAL(10,2),
                        due_date DATE,
                        vendor TEXT,
                        bank TEXT,
                        atas_nama TEXT,
                        rekening TEXT,
                        cost_center TEXT,
                        cost_element TEXT,
                        file_name TEXT
                    )''')

    # ✅ Create a separate table for Cash In (Excel-based)
    cursor.execute('''CREATE TABLE IF NOT EXISTS cash_in (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_number TEXT,
                        assignment TEXT,
                        gl_account TEXT,
                        document_type TEXT,
                        posting_period TEXT,
                        posting_date DATE,
                        document_date DATE,
                        posting_key TEXT,
                        jumlah_myr DECIMAL(15,2),
                        local_currency TEXT,
                        tax_code TEXT,
                        amount_in_doc_currency DECIMAL(15,2), 
                        amount_loc_curr_3 DECIMAL(15,2),
                        document_currency TEXT,
                        reference TEXT,
                        user_name TEXT,
                        clearing_document TEXT,
                        text TEXT,
                        file_name TEXT
                    )''')

    conn.commit()
    conn.close()

def allowed_file(filename):
    """Check if the uploaded file is a PDF or Excel."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/", methods=["GET", "POST"])
def dashboard():
    """Dashboard for file upload and displaying the latest invoices."""
    success = False  # ✅ Initialize the variable
    msg = "Unknown error occurred"

    if request.method == "POST":
        if "files" not in request.files:
            flash("No file uploaded!", "error")
            return redirect(request.url)

        files = request.files.getlist("files")
        category = request.form.get("category", "Cash In")  # Cash In or Cash Out

        for file in files:
            if file.filename == "":
                flash("No selected file!", "error")
                return redirect(request.url)

            if not allowed_file(file.filename):
                flash("Invalid file format! Only PDF & Excel files are allowed.", "error")
                return redirect(request.url)

            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)

            try:
                if category == "Cash In" and filename.lower().endswith((".xlsx", ".xls")):
                    success, msg = process_cash_in_excel(filepath, filename)  # ✅ Process Cash In Excel
                elif category == "Cash Out" and filename.lower().endswith(".pdf"):
                    invoice_data = extract_invoice_data(filepath)  # ✅ Process Cash Out PDF
                    if invoice_data:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute('''INSERT INTO invoices
                                        (nomor, tanggal, kepada, dari, pembayaran, jumlah, due_date,
                                        vendor, bank, atas_nama, rekening, cost_center, cost_element, file_name)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                    (invoice_data["nomor"], invoice_data["tanggal"], invoice_data["kepada"],
                                    invoice_data["dari"], invoice_data["pembayaran"], invoice_data["jumlah"],
                                    invoice_data["due_date"], invoice_data["vendor"], invoice_data["bank"],
                                    invoice_data["atas_nama"], invoice_data["rekening"],
                                    invoice_data["cost_center"], invoice_data["cost_element"], filename))
                        conn.commit()
                        conn.close()

                        success, msg = True, "✅ PDF invoice processed successfully!"
                    else:
                        success, msg = False, "❌ Failed to extract invoice data from PDF."

                else:
                    msg = "❌ Invalid file format for selected category!"
                    success = False

                if success:
                    flash(msg, "success")
                else:
                    flash(msg, "error")

            except Exception as e:
                logging.error(f"❌ Error processing file {filename}: {e}")
                flash(f"❌ Error processing file: {e}", "error")

        return redirect(url_for("dashboard"))

    # ✅ Fetch latest Cash Out invoices
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices ORDER BY id DESC LIMIT 5")
    latest_invoices = cursor.fetchall()

    # ✅ Fetch latest Cash In transactions
    cursor.execute("SELECT * FROM cash_in ORDER BY id DESC LIMIT 5")
    latest_cash_in = cursor.fetchall()

    # Fetch all data
    cursor.execute("SELECT * FROM invoices")
    cash_out = cursor.fetchall()

    cursor.execute("SELECT * FROM cash_in")
    cash_in = cursor.fetchall()


    # Total invoices
    total_invoices = len(cash_out) + len(cash_in)

    # Get current month and year
    now = datetime.now()
    current_year = now.strftime("%Y")
    current_month = now.strftime("%Y-%m")

    cash_in_total = sum(
        abs(float(tx["jumlah_myr"])) for tx in cash_in
        if tx["posting_date"] and tx["posting_date"].startswith(current_month)
        and tx["jumlah_myr"] not in [None, "", "Unknown"]
    )

    cash_out_total = sum(
        float(tx["jumlah"]) for tx in cash_out
        if tx["tanggal"] and tx["tanggal"].startswith(current_month)
        and tx["jumlah"] not in [None, "", "Unknown"]
    )

    cash_in_year_total = sum(
        abs(float(tx["jumlah_myr"])) for tx in cash_in
        if tx["posting_date"] and tx["posting_date"].startswith(current_year)
        and tx["jumlah_myr"] not in [None, "", "Unknown"]
    )

    cash_out_year_total = sum(
        float(tx["jumlah"]) for tx in cash_out
        if tx["tanggal"] and tx["tanggal"].startswith(current_year)
        and tx["jumlah"] not in [None, "", "Unknown"]
    )

    # Build monthly trend data (for line chart)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    chart_labels = months
    chart_cash_in = []
    chart_cash_out = []

    for month_index in range(1, 13):
        month_str = f"{current_year}-{month_index:02d}"

        # Cash In
        monthly_in = sum(
            abs(float(tx["jumlah_myr"])) for tx in cash_in
            if tx["posting_date"] and tx["posting_date"].startswith(month_str)
        )

        chart_cash_in.append(round(monthly_in, 2))

        # Cash Out
        monthly_out = sum(
            float(tx["jumlah"]) for tx in cash_out
            if tx["tanggal"] and tx["tanggal"].startswith(month_str)
        )
        chart_cash_out.append(round(monthly_out, 2))

    # Fetch latest invoices for tables (as before)
    latest_invoices = sorted(cash_out, key=lambda x: x["id"], reverse=True)[:5]
    latest_cash_in = sorted(cash_in, key=lambda x: x["id"], reverse=True)[:5]

    conn.close()

    return render_template("dashboard.html",
                           latest_invoices=latest_invoices,
                           latest_cash_in=latest_cash_in,
                           total_invoices=total_invoices,
                           cash_in_total=round(cash_in_total, 2),
                           cash_out_total=round(cash_out_total, 2),
                           cash_in_year_total=round(cash_in_year_total, 2),
                           cash_out_year_total=round(cash_out_year_total, 2),
                           chart_labels=chart_labels,
                           chart_cash_in=chart_cash_in,
                           chart_cash_out=chart_cash_out
                           )


@app.route("/cash-in")
def cash_in():
    """Displays only Cash In invoices with available years for filtering."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # ✅ Fetch all Cash In invoices from the new `cash_in` table
    cursor.execute("SELECT id, document_number, assignment, gl_account, document_type, posting_period, posting_date, document_date, posting_key,jumlah_myr, tax_code, reference, user_name, clearing_document,text, file_name FROM cash_in")

    invoices = cursor.fetchall()

    # ✅ Fetch available years from 'posting_date' in the new `cash_in` table
    cursor.execute(
        "SELECT DISTINCT strftime('%Y', posting_date) FROM cash_in WHERE posting_date IS NOT NULL"
    )
    available_years = [row[0] for row in cursor.fetchall() if row[0] is not None]

    conn.close()
    return render_template("cash_in.html", invoices=invoices, available_years=available_years)



@app.route("/cash-out")
def cash_out():
    """Displays only Cash Out invoices with available years for filtering."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM invoices")  # ✅ No need to filter by category anymore
    invoices = cursor.fetchall()

    # Fetch available years from 'tanggal' column
    cursor.execute(
        "SELECT DISTINCT strftime('%Y', tanggal) FROM invoices WHERE tanggal IS NOT NULL"
    )
    available_years = [row[0] for row in cursor.fetchall() if row[0] is not None]

    conn.close()
    return render_template("cash_out.html", invoices=invoices, available_years=available_years)



# 📌 File Download
@app.route('/download/<path:filename>')
def download_file(filename):
    """Allows users to download the uploaded PDF files."""
    try:
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)
    except FileNotFoundError:
        flash("File not found!", "error")
        return redirect(url_for("dashboard"))

@app.route('/export-excel/<category>')
def export_excel(category):
    """Export invoices to an Excel file based on the selected category."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if category == "Cash In":
        cursor.execute("SELECT * FROM cash_in")  # ✅ Fetch from `cash_in` table
        invoices = cursor.fetchall()
        columns = ["ID", "Document Number", "Assignment", "G/L Account", "Document Type", "Posting Period",
                   "Posting Date", "Document Date", "Posting Key", "Jumlah (MYR)", "Tax Code", "Reference",
                   "User Name", "Clearing Document", "Text", "File Name"]
    else:  # Assume it's "Cash Out"
        cursor.execute("SELECT * FROM invoices")  # ✅ Fetch from `invoices` table
        invoices = cursor.fetchall()
        columns = ["ID", "Nomor", "Tanggal", "Kepada", "Dari", "Pembayaran", "Jumlah (MYR)",
                   "Due Date", "Vendor", "Bank", "Atas Nama", "Rekening", "Cost Center",
                   "Cost Element", "File Name"]

    conn.close()

    if not invoices:
        flash(f"No {category} data to export!", "error")
        return redirect(url_for("dashboard"))

    # Convert data into a Pandas DataFrame
    df = pd.DataFrame(invoices, columns=columns)

    # Save Excel file to memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=f"{category}_Data")

    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"{category}_Report.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route('/export-excel-filtered', methods=["POST"])
def export_excel_filtered():
    """Export only currently filtered transactions to an Excel file."""
    data = request.json
    invoices = data.get("invoices", [])
    category = data.get("category", "Cash In")  # Detect whether it's Cash In or Cash Out

    if not invoices:
        return jsonify({"error": "No data to export"}), 400

    # ✅ Define correct columns based on the category
    if category == "Cash In":
        columns = [
            "ID", "Document Number", "Assignment", "G/L Account", "Document Type",
            "Posting Period", "Posting Date", "Document Date", "Posting Key",
            "Jumlah (MYR)", "Tax Code", "Reference", "User Name", "Clearing Document",
            "Text", "File Name"
        ]

        rename_mapping = {
            "id": "ID",
            "document_number": "Document Number",
            "assignment": "Assignment",
            "gl_account": "G/L Account",
            "document_type": "Document Type",
            "posting_period": "Posting Period",
            "posting_date": "Posting Date",
            "document_date": "Document Date",
            "posting_key": "Posting Key",
            "jumlah_myr": "Jumlah (MYR)",
            "tax_code": "Tax Code",
            "reference": "Reference",
            "user_name": "User Name",
            "clearing_document": "Clearing Document",
            "text": "Text",
            "file_name": "File Name"
        }

    else:  # Assume it's "Cash Out"
        columns = [
            "ID", "Nomor", "Tanggal", "Kepada", "Dari", "Pembayaran", "Due Date",
            "Vendor", "Bank", "Atas Nama", "Rekening", "Cost Center",
            "Cost Element", "File Name", "Jumlah (MYR)"
        ]

        rename_mapping = {
            "id": "ID",
            "nomor": "Nomor",
            "tanggal": "Tanggal",
            "kepada": "Kepada",
            "dari": "Dari",
            "pembayaran": "Pembayaran",
            "due_date": "Due Date",
            "vendor": "Vendor",
            "bank": "Bank",
            "atas_nama": "Atas Nama",
            "rekening": "Rekening",
            "cost_center": "Cost Center",
            "cost_element": "Cost Element",
            "file_name": "File Name",
            "jumlah": "Jumlah (MYR)"
        }

    # ✅ Convert transactions to a DataFrame
    df = pd.DataFrame(invoices)

    # ✅ Rename columns correctly
    df.rename(columns=rename_mapping, inplace=True)

    # ✅ Ensure all necessary columns exist
    for col in columns:
        if col not in df.columns:
            df[col] = ""  # Fill missing columns with empty values

    # ✅ Reorder DataFrame to match expected structure
    df = df[columns]

    # ✅ Convert numeric fields properly
    if "Jumlah (MYR)" in df.columns:
        df["Jumlah (MYR)"] = df["Jumlah (MYR)"].replace(",", "", regex=True)
        df["Jumlah (MYR)"] = pd.to_numeric(df["Jumlah (MYR)"], errors="coerce")

    # ✅ Use BytesIO to create an in-memory Excel file
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=f"{category}_Filtered_Data")

    output.seek(0)  # Reset pointer

    return send_file(output, as_attachment=True, download_name=f"Filtered_{category}_Report.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# 📌 Delete Invoice Route
@app.route("/delete/<int:invoice_id>", methods=["GET"])
def delete_invoice(invoice_id):
    """Delete an invoice."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM invoices WHERE id=?", (invoice_id,))
        conn.commit()
        conn.close()
        flash("Invoice deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting invoice: {e}", "error")

    return redirect(url_for("dashboard"))

def process_cash_in_excel(file_path, file_name):
    """Extracts data from the correct sheet in the Excel file and stores it in the database."""
    try:
        # ✅ Explicitly read from Sheet 2 (Index 1 since Python is 0-based)
        df = pd.read_excel(file_path, sheet_name=1, dtype=str, header=0)

        # 🔍 Debug: Print available sheet names (if needed)
        # xls = pd.ExcelFile(file_path)
        # print("Available sheets:", xls.sheet_names)

        # 🔍 Debug: Print original column names
        print("📌 Original Column Names:", df.columns.tolist())

        df = df.rename(columns={
            "Document Number": "document_number",
            "Assignment": "assignment",
            "G/L Account": "gl_account",
            "Document Type": "document_type",
            "Posting Period": "posting_period",
            "Posting Date": "posting_date",
            "Document Date": "document_date",
            "Posting Key": "posting_key",
            "Amount in local currency": "jumlah_myr",  # ✅ Extracted amount in MYR
            "Local Currency": "local_currency",  # ✅ Ensure this exists
            "Tax code": "tax_code",
            "Amount in doc. curr.": "amount_in_doc_currency",
            "Amt in loc.curr. 3": "amount_loc_curr_3",
            "Document currency": "document_currency",
            "Reference": "reference",
            "User name": "user_name",
            "Clearing Document": "clearing_document",
            "Text": "text"
        })

        # 🔍 Debug: Print renamed column names
        print("✅ Renamed Column Names:", df.columns.tolist())

        # ✅ Check if 'jumlah_myr' column exists
        if "jumlah_myr" not in df.columns:
            return False, f"❌ 'jumlah_myr' column missing. Actual columns: {df.columns.tolist()}"

        # ✅ Convert "Amount in Local Currency" to float
        df["jumlah_myr"] = df["jumlah_myr"].replace(",", "", regex=True).astype(float)

        # ✅ Convert date columns correctly
        df["posting_date"] = pd.to_datetime(df["posting_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        df["document_date"] = pd.to_datetime(df["document_date"], errors="coerce").dt.strftime("%Y-%m-%d")

        # ✅ Add filename for tracking
        df["file_name"] = file_name

        # ✅ Insert into database
        conn = get_db_connection()
        df.to_sql("cash_in", conn, if_exists="append", index=False)
        conn.close()

        return True, f"✅ Processed {len(df)} transactions from Excel."

    except Exception as e:
        return False, f"❌ Error processing Excel: {str(e)}"

@app.route("/edit/<int:invoice_id>", methods=["GET", "POST"])
def edit_invoice(invoice_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch invoice details
    cursor.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,))
    invoice = cursor.fetchone()

    if not invoice:
        flash("Invoice not found!", "error")
        return redirect(url_for("cash_out"))

    if request.method == "POST":
        # Get updated values from the form
        updated_data = (
            request.form["nomor"],
            request.form["tanggal"],
            request.form["kepada"],
            request.form["dari"],
            request.form["pembayaran"],
            request.form["due_date"],
            request.form["vendor"],
            request.form["bank"],
            request.form["atas_nama"],
            request.form["rekening"],
            request.form["cost_center"],
            request.form["cost_element"],
            request.form["jumlah"],
            invoice_id  # ID for the WHERE clause
        )

        # Update the database
        cursor.execute("""
            UPDATE invoices
            SET nomor=?, tanggal=?, kepada=?, dari=?, pembayaran=?, due_date=?, vendor=?, bank=?,
                atas_nama=?, rekening=?, cost_center=?, cost_element=?, jumlah=?
            WHERE id=?
        """, updated_data)

        conn.commit()
        conn.close()
        flash("Invoice updated successfully!", "success")
        return redirect(url_for("cash_out"))

    conn.close()
    return render_template("edit.html", invoice=invoice)

@app.route('/edit-cash-in/<int:id>', methods=['GET', 'POST'])
def edit_cash_in(id):
    conn = get_db_connection()
    cash_in = conn.execute('SELECT * FROM cash_in WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        # Fetch form data and update logic here...
        document_number = request.form['document_number']
        assignment = request.form['assignment']
        gl_account = request.form['gl_account']
        document_type = request.form['document_type']
        posting_period = request.form['posting_period']
        posting_date = request.form['posting_date']
        document_date = request.form['document_date']
        posting_key = request.form['posting_key']
        jumlah_myr = request.form['jumlah_myr']
        tax_code = request.form['tax_code']
        reference = request.form['reference']
        user_name = request.form['user_name']
        clearing_document = request.form['clearing_document']
        text = request.form['text']
        file_name = request.form['file_name']

        conn.execute('''
            UPDATE cash_in SET
                document_number = ?, assignment = ?, gl_account = ?, document_type = ?,
                posting_period = ?, posting_date = ?, document_date = ?, posting_key = ?,
                jumlah_myr = ?, tax_code = ?, reference = ?, user_name = ?,
                clearing_document = ?, text = ?, file_name = ?
            WHERE id = ?
        ''', (
            document_number, assignment, gl_account, document_type,
            posting_period, posting_date, document_date, posting_key,
            jumlah_myr, tax_code, reference, user_name,
            clearing_document, text, file_name, id
        ))
        conn.commit()
        conn.close()
        flash("Cash In updated successfully!", "success")
        return redirect(url_for('dashboard'))

    conn.close()
    return render_template("edit_cash_in.html", cash_in=cash_in)


@app.route("/delete-cashin/<int:cashin_id>")
def delete_cash_in(cashin_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cash_in WHERE id = ?", (cashin_id,))
    conn.commit()
    conn.close()
    flash("Cash In record deleted.", "success")
    return redirect(url_for("dashboard"))




if __name__ == "__main__":
    if not os.path.exists(DATABASE):
        init_db()  # Run only if database does not exist
    app.run(debug=True)

