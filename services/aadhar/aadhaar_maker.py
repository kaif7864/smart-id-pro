import os
import unicodedata
import textwrap
from PIL import Image, ImageDraw, ImageFont
from reportlab.platypus import SimpleDocTemplate, Image as RLImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
import uharfbuzz as hb
import freetype

# ===== FOLDERS =====
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
ASSETS_FOLDER = "assets"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ================= CLEAN FUNCTIONS =================

def clean_hindi_text(text):
    if not text:
        return text

    text = unicodedata.normalize("NFKC", text)

    # Fix dash
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")

    # Fix ordinal issue
    text = text.replace("º", "०")

    # Remove zero width chars
    text = text.replace("\u200c", "").replace("\u200d", "")

    return text.strip()


def clean_english_text(text):
    if not text:
        return text

    text = unicodedata.normalize("NFKC", text)

    # Fix colon & dash variants
    text = text.replace("：", ":").replace("﹕", ":")
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")

    return text.strip()


# ================= HARFBUZZ DRAW =================

def draw_hindi_text(image, text, position, font_path, font_size, fill=(0, 0, 0)):

    if not text:
        return

    text = clean_hindi_text(text)

    x, y = position

    face = freetype.Face(font_path)
    face.set_char_size(font_size * 64)

    with open(font_path, "rb") as f:
        fontdata = f.read()

    hb_face = hb.Face(fontdata)
    hb_font = hb.Font(hb_face)
    hb_font.scale = (font_size * 64, font_size * 64)

    lines = text.split("\n")
    line_height = int(font_size * 1.35)

    for line_index, line in enumerate(lines):

        buf = hb.Buffer()
        buf.add_str(line)
        buf.guess_segment_properties()
        hb.shape(hb_font, buf)

        infos = buf.glyph_infos
        positions = buf.glyph_positions

        pen_x = 0
        base_y = y + (line_index * line_height)

        for info, pos in zip(infos, positions):

            # 🔥 FIX: महिला and complex glyph issue fix
            face.load_glyph(info.codepoint, freetype.FT_LOAD_DEFAULT)
            face.glyph.render(freetype.FT_RENDER_MODE_NORMAL)

            bitmap = face.glyph.bitmap
            top = face.glyph.bitmap_top
            left = face.glyph.bitmap_left

            w, h = bitmap.width, bitmap.rows

            if w > 0 and h > 0:
                glyph_pixels = bytes(bitmap.buffer)

                glyph_image = Image.frombytes("L", (w, h), glyph_pixels)

                rgba = Image.new("RGBA", (w, h), fill)
                rgba.putalpha(glyph_image)

                image.paste(
                    rgba,
                    (int(x + pen_x + left), int(base_y - top)),
                    rgba
                )

            pen_x += pos.x_advance / 64


# ================= MAIN FUNCTION =================

def generate_aadhaar_card(data, photo_file):

    name_en = data.get("name_english")
    name_hi = data.get("name_hindi")
    dob = data.get("dob")
    gender = data.get("gender")
    aadhaar_number = data.get("aadhaar_number")
    address_en = data.get("address_english")
    address_hi = data.get("address_hindi")
    vid = data.get("vid_number")
    issued_date = data.get("issued_date")
    details_as_on = data.get("details_as_on")

    # ===== LOAD PHOTO =====
    user_photo = Image.open(photo_file.stream).convert("RGBA")

    # ===== LOAD TEMPLATE =====
    bg_path = os.path.join(ASSETS_FOLDER, "front.png")
    bg = Image.open(bg_path).convert("RGBA")
    draw = ImageDraw.Draw(bg)
    bg_width, bg_height = bg.size

    # ===== FONTS =====
    font_path_en = os.path.join(ASSETS_FOLDER, "arial.ttf")
    font_path_hi = os.path.join(ASSETS_FOLDER, "NotoSansDevanagari-Regular.ttf")

    font_name_en = ImageFont.truetype(font_path_en, int(bg_height * 0.035))
    font_data_en = ImageFont.truetype(font_path_en, int(bg_height * 0.025))

    # ===== PHOTO =====
    photo_width = int(bg_width * 0.18)
    photo_height = int(bg_height * 0.28)
    user_photo = user_photo.resize((photo_width, photo_height))

    photo_x = int(bg_width * 0.05)
    photo_y = int(bg_height * 0.30)
    bg.paste(user_photo, (photo_x, photo_y), user_photo)

    # ===== ENGLISH CLEAN =====
    name_en = clean_english_text(name_en)
    address_en = clean_english_text(address_en)
    dob = clean_english_text(dob)
    gender = clean_english_text(gender)
    issued_date = clean_english_text(issued_date)
    details_as_on = clean_english_text(details_as_on)

    # ===== ENGLISH DRAW =====
    if name_en:
        draw.text(
            (int(bg_width * 0.28), int(bg_height * 0.35)),
            name_en.upper(),
            fill="black",
            font=font_name_en
        )

    if dob:
        draw.text(
            (int(bg_width * 0.28), int(bg_height * 0.47)),
            f"DOB: {dob}",
            fill="black",
            font=font_data_en
        )

    if gender:
        draw.text(
            (int(bg_width * 0.45), int(bg_height * 0.47)),
            gender,
            fill="black",
            font=font_data_en
        )

    # 🔥 FIX: Aadhaar 4-4 digit proper
    if aadhaar_number:
        aadhaar_number = "".join(filter(str.isdigit, aadhaar_number))
        formatted = " ".join(
            [aadhaar_number[i:i+4] for i in range(0, len(aadhaar_number), 4)]
        )
        draw.text(
            (int(bg_width * 0.35), int(bg_height * 0.65)),
            formatted,
            fill="black",
            font=font_name_en
        )

    # 🔥 Address wrap
    if address_en:
        wrapped = textwrap.fill(address_en, width=45)
        draw.text(
            (int(bg_width * 0.28), int(bg_height * 0.52)),
            wrapped,
            fill="black",
            font=font_data_en
        )

    if vid:
        vid = clean_english_text(vid)
        draw.text(
            (int(bg_width * 0.05), int(bg_height * 0.85)),
            f"VID: {vid}",
            fill="black",
            font=font_data_en
        )

    if issued_date:
        draw.text(
            (int(bg_width * 0.05), int(bg_height * 0.88)),
            f"Issued: {issued_date}",
            fill="black",
            font=font_data_en
        )

    if details_as_on:
        draw.text(
            (int(bg_width * 0.05), int(bg_height * 0.91)),
            f"As On: {details_as_on}",
            fill="black",
            font=font_data_en
        )

    # ===== HINDI DRAW =====
    if name_hi:
        draw_hindi_text(
            bg,
            name_hi,
            (int(bg_width * 0.38), int(bg_height * 0.44)),
            font_path_hi,
            int(bg_height * 0.035)
        )

    if address_hi:
        address_hi = clean_hindi_text(address_hi)
        wrapped_hi = textwrap.fill(address_hi, width=40)
        draw_hindi_text(
            bg,
            wrapped_hi,
            (int(bg_width * 0.28), int(bg_height * 0.56)),
            font_path_hi,
            int(bg_height * 0.025)
        )

    # ===== SAVE IMAGE =====
    final_image_path = os.path.join(OUTPUT_FOLDER, "final_aadhaar.png")
    bg.convert("RGB").save(final_image_path)

    # ===== PDF =====
    pdf_path = os.path.join(OUTPUT_FOLDER, "final_aadhaar.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    elements = []

    max_width = 7 * inch
    aspect = bg_height / bg_width
    pdf_height = max_width * aspect

    elements.append(
        RLImage(final_image_path, width=max_width, height=pdf_height)
    )

    doc.build(elements)

    return pdf_path