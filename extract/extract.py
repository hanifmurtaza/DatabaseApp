import fitz  # PyMuPDF for PDF processing
import re
import pytesseract  # OCR for scanned PDFs
from PIL import Image, ImageEnhance, ImageFilter  # Image processing for OCR
from datetime import datetime

# Set Tesseract OCR Path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# Set the correct path for Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def ocr_extract_text(pdf_path):
    """ Extracts text from only the first page of scanned PDFs using Tesseract OCR. """
    doc = fitz.open(pdf_path)  # Open PDF
    text = ""

    if len(doc) > 0:  # Ensure the PDF is not empty
        pix = doc[0].get_pixmap()  # Get the first page as an image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(img, lang="ind+eng")  # Extract text using OCR (Indonesian + English)

    return text



def clean_extracted_text(text):
    """ Cleans OCR text by removing extra spaces, fixing line breaks, and standardizing formatting. """
    text = re.sub(r"\s{2,}", " ", text)  # Remove extra spaces
    text = re.sub(r"\n+", "\n", text).strip()  # Remove unnecessary new lines
    text = text.replace(" :", ":")  # Fix incorrect spacing before colons

    return text


def format_date(date_string):
    """ Converts date format from '21 Februari 2025' to '2025-02-21'. """
    month_map = {
        "Januari": "January", "Februari": "February", "Maret": "March",
        "April": "April", "Mei": "May", "Juni": "June",
        "Juli": "July", "Agustus": "August", "September": "September",
        "Oktober": "October", "November": "November", "Desember": "December"
    }

    try:
        for indo_month, eng_month in month_map.items():
            if indo_month in date_string:
                date_string = date_string.replace(indo_month, eng_month)
                break

        return datetime.strptime(date_string, "%d %B %Y").strftime("%Y-%m-%d")
    except ValueError:
        return "Unknown"


def safe_float(value):
    """ Convert string to float safely, handling commas and errors. """
    try:
        clean_value = re.sub(r"[^\d,.]", "", value).replace(",", "").strip()
        return float(clean_value)
    except (ValueError, AttributeError):
        return 0.0


def extract_value(text, patterns):
    """
    Extracts a value from text using multiple regex patterns.
    """
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return "Unknown"


def extract_invoice_data(pdf_path):
    """ Extracts invoice data from a PDF file, handling different invoice formats. """
    invoice_data = {
        "nomor": "Unknown", "tanggal": "Unknown", "kepada": "Unknown", "dari": "Unknown",
        "pembayaran": "Unknown", "jumlah": 0.0, "due_date": "Unknown", "vendor": "Unknown",
        "bank": "Unknown", "atas_nama": "Unknown", "rekening": "Unknown",
        "cost_center": "Unknown", "cost_element": "Unknown"
    }

    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        text = page.get_text("text").strip()

        # If no text is found, attempt OCR
        if not text:
            print(f"⚠ Warning: No text found in {pdf_path}. Attempting OCR...")
            text = ocr_extract_text(pdf_path)

        # Debugging: Print Extracted Text
        print(f"Extracted Text:\n{text}")

        # Extract "Untuk Pembayaran" (Payment Purpose)
        pembayaran_full = extract_value(text, [
            r"Untuk Pembayaran[:\s]+(.+?)(?=\s*(Jumlah|Total|Due Date|Vendor|Bank|$))",
            r"Deskripsi[:\s]+([^\n]+)"
        ]).strip()

        # Extract "Jumlah" from "Untuk Pembayaran" if it contains MYR
        jumlah_from_pembayaran = re.search(r"MYR\s*([\d,\.]+)", pembayaran_full)
        extracted_jumlah = safe_float(jumlah_from_pembayaran.group(1)) if jumlah_from_pembayaran else 0.0

        # If "Jumlah" wasn't found in "Untuk Pembayaran", search separately
        if extracted_jumlah == 0.0:
            jumlah_match = re.search(r"(Jumlah|Total|Grand Total)[:\s]*MYR?\s*([\d,\.]+)", text)
            if jumlah_match:
                extracted_jumlah = safe_float(jumlah_match.group(2))

        # Remove the extracted "Jumlah" value from "Untuk Pembayaran"
        pembayaran_cleaned = re.sub(r"MYR\s*[\d,\.]+", "", pembayaran_full).strip()

        # Debugging: Print values extracted
        print(f"✅ Extracted Pembayaran (Before Cleaning): {pembayaran_full}")
        print(f"✅ Extracted Jumlah (From Pembayaran): {jumlah_from_pembayaran.group(1) if jumlah_from_pembayaran else 'Not Found'}")
        print(f"✅ Extracted Jumlah (From Normal Search): {extracted_jumlah}")

        # Update invoice data
        invoice_data.update({
            "nomor": extract_value(text, [r"Nomor[:\s]+([^\n]+)", r"No[:\s]+([^\n]+)"]),
            "tanggal": format_date(extract_value(text, [r"Tanggal[:\s]+([^\n]+)", r"Date[:\s]+([^\n]+)"])),
            "kepada": extract_value(text, [r"Kepada[:\s]+([^\n]+)", r"To[:\s]+([^\n]+)"]),
            "dari": extract_value(text, [r"Dari[:\s]+([^\n]+)", r"From[:\s]+([^\n]+)"]),
            "pembayaran": pembayaran_cleaned if pembayaran_cleaned else "Unknown",
            "jumlah": extracted_jumlah,
            "due_date": format_date(extract_value(text, [r"Due Date[:\s]+([^\n]+)", r"Jatuh Tempo[:\s]+([^\n]+)"])),
            "vendor": extract_value(text, [r"Nama Vendor[:\s]+([^\n]+)", r"Penerima[:\s]+([^\n]+)"]),
            "bank": extract_value(text, [r"Nama Bank[:\s]+([^\n]+)", r"Bank Tujuan[:\s]+([^\n]+)"]),
            "atas_nama": extract_value(text, [r"Atas Nama Rekening[:\s]+([^\n]+)", r"Atas Nama[:\s]+([^\n]+)"]),
            "rekening": extract_value(text, [
                r"Nomor Rekening[:\s]+([\d\s]+)",
                r"Rekening[:\s]+([\d\s]+)",
                r"Bank Account[:\s]+([\d\s]+)",
                r"Bank ACC NO[:\s]+([\d\s]+)"
            ]),
            "cost_center": extract_value(text, [r"Cost Center[:\s]+([\w\d]+)", r"CC[:\s]+([\w\d]+)"]),
            "cost_element": extract_value(text, [r"Cost Element[:\s]+([\w\d]+)", r"CE[:\s]+([\w\d]+)"]),
        })

    except Exception as e:
        print(f"❌ Error extracting data from PDF: {e}")
        invoice_data["error"] = f"Extraction failed: {str(e)}"

    return invoice_data










