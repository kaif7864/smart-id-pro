import os
from PIL import Image, ImageDraw, ImageFont
from reportlab.platypus import SimpleDocTemplate, Image as RLImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from datetime import datetime

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def generate_pan_card(data, files):
    id_number = data.get("id_number").upper()
    name = data.get("name").upper()
    father_name = data.get("father_name").upper()
    dob = data.get("dob")

    photo = files.get("photo")
    sign = files.get("sign")

    if not all([id_number, name, father_name, dob, photo, sign]):
        raise ValueError("All fields required")

    photo_path = os.path.join(UPLOAD_FOLDER, photo.filename)
    sign_path = os.path.join(UPLOAD_FOLDER, sign.filename)
    
    photo.save(photo_path)
    sign.save(sign_path)

    # ===== OPEN BACKGROUND TEMPLATE =====
    # Make sure this path exists
    bg = Image.open("assets/background.jpeg").convert("RGBA")
    draw = ImageDraw.Draw(bg)

    bg_width, bg_height = bg.size

    # ===== LOAD FONTS =====
    # Make sure fonts exist in assets folder
    font_small = ImageFont.truetype("assets/arialbd.ttf", int(bg_height * 0.042))
    font_large = ImageFont.truetype("assets/arialbd.ttf", int(bg_height * 0.058))

    # 📸 PHOTO
    photo_width = int(bg_width * 0.14)
    photo_height = int(bg_height * 0.23)
    user_photo = Image.open(photo_path).convert("RGBA")
    user_photo = user_photo.resize((photo_width, photo_height))
    photo_x = int(bg_width * 0.052)
    photo_y = int(bg_height * 0.30)
    bg.paste(user_photo, (photo_x, photo_y))

    # 📝 TEXT
    draw.text((int(bg_width * 0.05), int(bg_height * 0.61)),
              name.upper(), fill="black", font=font_small)
    draw.text((int(bg_width * 0.05), int(bg_height * 0.74)),
              father_name.upper(), fill="black", font=font_small)
    
    try:
        date_obj = datetime.strptime(dob, '%Y-%m-%d')
        formatted_dob = date_obj.strftime('%d/%m/%Y')
    except ValueError:
        formatted_dob = dob

    draw.text((int(bg_width * 0.05), int(bg_height * 0.898)),
              formatted_dob, fill="black", font=font_small)      

    # 🆔 PAN NUMBER
    draw.text((int(bg_width*0.33), int(bg_height * 0.37)),
              id_number.upper(), fill="black", font=font_large)

    # ✍ SIGNATURE
    sign_width = int(bg_width * 0.18)
    sign_height = int(bg_height * 0.10)
    user_sign = Image.open(sign_path).convert("RGBA")
    user_sign = user_sign.resize((sign_width, sign_height))
    bg.paste(user_sign,
             (int(bg_width * 0.40), int(bg_height * 0.835)),
             user_sign)

    # ===== SAVE FINAL IMAGE =====
    final_image_path = os.path.join(OUTPUT_FOLDER, "final_pan.png")
    bg.convert("RGB").save(final_image_path)

    # ===== PDF GENERATION =====
    pdf_path = os.path.join(OUTPUT_FOLDER, "final_pan.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    elements = []

    # Front Image
    max_width = 6 * inch
    aspect = bg_height / bg_width
    pdf_height = max_width * aspect
    elements.append(RLImage(final_image_path, width=max_width, height=pdf_height))
    
    # Back Image
    static_image_path = os.path.join("assets", "back.jpeg")
    if os.path.exists(static_image_path):
        with Image.open(static_image_path) as img:
            s_width, s_height = img.size
        max_s_width = 6 * inch
        s_aspect = s_height / s_width
        s_pdf_height = max_s_width * s_aspect
        elements.append(RLImage(static_image_path, width=max_s_width, height=s_pdf_height))

    doc.build(elements)
    return pdf_path