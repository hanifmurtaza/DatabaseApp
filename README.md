# HanifDB – Automated Invoice Management System

HanifDB is a lightweight, end-to-end web application that automates the extraction, storage, visualization, and export of financial invoice data for internal company use. Built with Flask and SQLite, it streamlines the process of managing SP3 Cash In (Excel) and Cash Out (PDF) invoices — from file upload to dashboard.

## 🚀 Features

- 📄 Upload Invoices:
  - PDF invoices for Cash Out
  - Excel invoices for Cash In
- 🧠 Automatic Data Extraction:
  - Uses PyMuPDF and Tesseract OCR for PDFs
  - Parses Excel files with pandas and openpyxl
- 🧾 Structured Data Storage:
  - Stores all information in a centralized SQLite database
- 📊 Dynamic Dashboard:
  - View total invoices
  - See Cash In/Out for the current month
  - See Cash In/Out for the current year
  - Visualize monthly trends with a line chart (Chart.js)
- 🔎 Advanced Filtering:
  - Filter by month, year, or search terms
- ✏️ Edit & Delete:
  - Edit and delete invoice records with confirmation
- 📥 Excel Export:
  - Export all or filtered data to an Excel file

## 🖥️ Tech Stack

- Backend: Flask (Python)
- Frontend: HTML, Bootstrap 5, JavaScript
- Database: SQLite
- PDF Handling: PyMuPDF, Tesseract OCR
- Excel Handling: pandas, openpyxl
- Visualization: Chart.js

## 📂 Folder Structure

.
├── app.py                  # Main Flask application
├── extract/                # PDF/Excel extraction logic
│   ├── extract.py
│   └── __init__.py
├── templates/              # HTML templates for dashboard, edit pages, etc.
├── static/
│   └── styles.css          # Custom styles for the UI
├── uploads/                # Uploaded invoice files
├── database.db             # SQLite database file (production/test data)
└── requirements.txt        # Python dependencies list

## ⚙️ Setup Instructions

1. Clone this repository

git clone https://github.com/hanifmurtaza/DatabaseApp.git
cd hanifdb

2. Create a virtual environment and install dependencies

python -m venv venv
source venv/bin/activate  (On Windows: venv\Scripts\activate)
pip install -r requirements.txt

3. (Optional) Install Tesseract OCR

- Download: https://github.com/tesseract-ocr/tesseract
- Set the path in extract.py:
  pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

4. Run the application

python app.py

5. Open your browser and navigate to

http://localhost:5000

## 🛠 Deployment

HanifDB is designed for internal company use and can be deployed on:
- Local servers or intranet environments
- VPS setups (Gunicorn + Nginx)
- Dockerized environments

SQLite is great for prototyping and small teams. The structure also supports easy migration to PostgreSQL or MySQL.

## 📈 Future Improvements

- User authentication and role-based access
- Cloud database integration
- Enhanced document template mapping
- PDF preview before extraction
- Advanced reporting (e.g., PDF export)

## 🙌 Author

Muhammad Hanif Murtaza  
Universiti Putra Malaysia (UPM)

---

## 📦 requirements.txt

Flask
PyMuPDF
pytesseract
Pillow
pandas
openpyxl

---
