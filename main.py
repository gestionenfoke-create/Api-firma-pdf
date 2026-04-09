from flask import Flask, request, send_file
import requests
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import time
import os
import json

# 🔹 Google Drive
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

app = Flask(__name__)


# 🔹 Health check
@app.route("/ping")
def ping():
    return "ok"


# 🔹 Subir archivo a Drive
def subir_a_drive(file_stream, filename):
    SCOPES = ['https://www.googleapis.com/auth/drive']

    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])

    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=SCOPES
    )

    service = build('drive', 'v3', credentials=creds)

    file_metadata = {
        'name': filename,
        'parents': ['1N184C4DQfz7cY085TdLl8DXks8ZSkyx3']  # 👈 REEMPLAZAR
    }

    media = MediaIoBaseUpload(file_stream, mimetype='application/pdf')

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    return file.get('id')


# 🔹 Endpoint principal
@app.route("/firmar", methods=["GET"])
def firmar_pdf():
    try:
        # 🔹 Parámetros
        pdf_url = request.args.get("pdf_url")
        firma_url = request.args.get("firma_url")
        firma2_url = request.args.get("firma2_url")
        fecha1 = request.args.get("fecha1")
        fecha2 = request.args.get("fecha2")

        if not pdf_url:
            return {"error": "Falta pdf_url"}, 400

        # 🔹 Descargar PDF (IMPORTANTE: headers)
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/pdf"
        }

        pdf_response = requests.get(pdf_url, headers=headers)

        if pdf_response.status_code != 200:
            return {"error": "No se pudo descargar el PDF"}, 400

        pdf_bytes = pdf_response.content

        # 🔹 Función para procesar firma
        def procesar_firma(url):
            if not url:
                return None

            headers_img = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "image/*"
            }

            r = requests.get(url, headers=headers_img)

            if r.status_code != 200:
                return None

            if "image" not in r.headers.get("Content-Type", ""):
                return None

            img = Image.open(BytesIO(r.content)).convert("RGBA")

            # 🔥 eliminar fondo negro
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])

            buffer = BytesIO()
            background.save(buffer, format="PNG")
            buffer.seek(0)

            return ImageReader(buffer)

        # 🔹 Procesar firmas
        firma1 = procesar_firma(firma_url)
        firma2 = procesar_firma(firma2_url)

        # 🔹 Leer PDF original
        original = PdfReader(BytesIO(pdf_bytes))
        last_page = original.pages[-1]
        width = float(last_page.mediabox.width)

        # 🔹 Crear overlay
        packet = BytesIO()
        c = canvas.Canvas(packet)

        # 🖊 FIRMA DERECHA
        if firma1:
            c.drawImage(
                firma1,
                x=width - 300,
                y=270,
                width=140,
                height=40,
                mask='auto'
            )

            if fecha1:
                c.setFont("Helvetica", 8)
                c.drawString(width - 150, 280, f"Fecha Firma: {fecha1}")

        # 🖊 FIRMA IZQUIERDA
        if firma2:
            c.drawImage(
                firma2,
                x=30,
                y=270,
                width=140,
                height=40,
                mask='auto'
            )

            if fecha2:
                c.setFont("Helvetica", 8)
                c.drawString(180, 280, f"Fecha Firma: {fecha2}")

        c.save()
        packet.seek(0)

        # 🔹 Merge PDF
        overlay = PdfReader(packet)
        overlay_page = overlay.pages[0]

        writer = PdfWriter()

        for i in range(len(original.pages)):
            page = original.pages[i]
            if i == len(original.pages) - 1:
                page.merge_page(overlay_page)
            writer.add_page(page)

        output = BytesIO()
        writer.write(output)
        output.seek(0)

        # 🔹 Nombre archivo
        filename = f"firmado_{int(time.time())}.pdf"

        # 🔹 Subir a Drive
    
            print("SUBIENDO A DRIVE...")

            file_id = subir_a_drive(output, filename)

            print("FILE ID:", file_id)

            ruta_appsheet = f"Prime_Firma_PDF_Files_/{filename}"

            return {
                "file": ruta_appsheet,
                "file_id": file_id
            }

        except Exception as e:
            print("ERROR SUBIENDO A DRIVE:", str(e))
            return {"error": str(e)}, 500


# 🔹 Run
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
