from flask import Flask, request, send_file
import requests
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import time
import traceback

app = Flask(__name__)


# 🔹 Health check
@app.route("/ping")
def ping():
    return "ok"


# 🔹 Endpoint principal
@app.route("/firmar", methods=["GET"])
def firmar_pdf():
    try:
        pdf_url = request.args.get("pdf_url")
        firma_url = request.args.get("firma_url")
        firma2_url = request.args.get("firma2_url")
        fecha1 = request.args.get("fecha1")
        fecha2 = request.args.get("fecha2")

        if not pdf_url:
            return {"error": "Falta pdf_url"}, 400

        # 🔹 Descargar PDF
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/pdf"
        }

        pdf_response = requests.get(pdf_url, headers=headers)

        if pdf_response.status_code != 200:
            return {"error": "Error descargando PDF"}, 400

        pdf_bytes = pdf_response.content

        # 🔹 Función procesar firma
        def procesar_firma(url):
            if not url:
                return None

            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "image/*"
            }

            r = requests.get(url, headers=headers)

            if r.status_code != 200:
                return None

            if "image" not in r.headers.get("Content-Type", ""):
                return None

            img = Image.open(BytesIO(r.content)).convert("RGBA")

            # eliminar fondo
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
            c.drawImage(firma1, x=width - 300, y=270, width=140, height=40, mask='auto')
            if fecha1:
                c.setFont("Helvetica", 8)
                c.drawString(width - 150, 280, f"Fecha Firma: {fecha1}")

        # 🖊 FIRMA IZQUIERDA
        if firma2:
            c.drawImage(firma2, x=30, y=270, width=140, height=40, mask='auto')
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

        # 🔥 DEVOLVER PDF DIRECTAMENTE
        return send_file(
            output,
            download_name=filename,
            as_attachment=False,
            mimetype="application/pdf"
        )

    except Exception as e:
        print("ERROR GENERAL:")
        traceback.print_exc()
        return {"error": str(e)}, 500


# 🔹 Run local (Render usa gunicorn)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
