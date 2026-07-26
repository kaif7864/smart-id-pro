import os
import re
import textwrap
import unicodedata
from PIL import Image, ImageDraw, ImageFont
from networkx import draw
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

def clean_english_text(text):
    if not text:
        return text

    # Normalize unicode
    text = unicodedata.normalize("NFKC", text)

    # ===== Replace colon variants =====
    colon_variants = ["：", "﹕", "ː", "∶"]
    for c in colon_variants:
        text = text.replace(c, ":")

    # ===== Replace dash variants =====
    dash_variants = ["–", "—", "−", "-", "‒", "―"]
    for d in dash_variants:
        text = text.replace(d, "-")

    # ===== Replace fancy quotes =====
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")

    # ===== Remove zero-width characters =====
    zero_width_chars = [
        "\u200b", "\u200c", "\u200d",
        "\ufeff", "\u2060"
    ]
    for z in zero_width_chars:
        text = text.replace(z, "")

    # ===== Remove control characters =====
    text = "".join(
        ch for ch in text
        if unicodedata.category(ch)[0] != "C"
    )

    # ===== Optional: remove unsupported symbols =====
    # Allow only common printable characters
    text = re.sub(r"[^\x20-\x7E\n]", "", text)

    return text.strip()



def clean_hindi_text(text):
    if not text: return text
    text = unicodedata.normalize("NFKC", text)
    # Special characters replace
    text = text.replace("–", "-").replace("—", "-").replace("−", "-").replace("º", "०")
    # Invisible characters hatayein
    text = text.replace("\u200c", "").replace("\u200d", "")
    # Extra spaces clean karein
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


def wrap_hindi_text(text, font_path, font_size, max_width):
    if not text:
        return ""

    face = freetype.Face(font_path)
    face.set_char_size(font_size * 64)

    with open(font_path, "rb") as f:
        fontdata = f.read()

    hb_face = hb.Face(fontdata)
    hb_font = hb.Font(hb_face)
    hb_font.scale = (font_size * 64, font_size * 64)

    lines = []
    current_line = ""

    for char in text:
        test_line = current_line + char

        buf = hb.Buffer()
        buf.add_str(test_line)
        buf.guess_segment_properties()
        hb.shape(hb_font, buf)

        width = sum(pos.x_advance for pos in buf.glyph_positions) / 64

        if width <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = char

    if current_line:
        lines.append(current_line)

    return "\n".join(lines)

# ================= MAIN FUNCTION =================

def generate_aadhaar_card(data, photo_file):

    # --- Data Extraction ---
    name_en = data.get("name_english")
    name_hi = data.get("name_hindi")
    dob = data.get("dob")
    aadhaar_number = data.get("aadhaar_number")
    address_en = data.get("address_english")
    address_hi = data.get("address_hindi")
    vid = data.get("vid_number")
    issued_date = data.get("issued_date")
    details_as_on = data.get("details_as_on")
    gender_key= data.get("gender", "male").lower()

    # --- Load Assets ---
    bg_front = Image.open(os.path.join(ASSETS_FOLDER, "front.png")).convert("RGBA")
    bg_back = Image.open(os.path.join(ASSETS_FOLDER, "back.png")).convert("RGBA")
    user_photo = Image.open(photo_file.stream).convert("RGBA")
    
    draw_f = ImageDraw.Draw(bg_front)
    draw_b = ImageDraw.Draw(bg_back)
    # bg = Image.open(bg_back).convert("RGBA")
    bg_width, bg_height = bg_front.size
    font_path_en = os.path.join(ASSETS_FOLDER, "arial.ttf")
    font_path_hi = os.path.join(ASSETS_FOLDER, "NotoSansDevanagari-Regular.ttf")
    font_is=os.path.join(ASSETS_FOLDER, "arialbd.ttf")

    font_name_en = ImageFont.truetype(font_path_en, int(bg_height * 0.035))
    font_data_en = ImageFont.truetype(font_path_en, int(bg_height * 0.025))
    font_bd = ImageFont.truetype(font_path_en, int(bg_height * 0.029))
    

    # --- Cleaning ---
    name_en = clean_english_text(name_en)
    address_en = clean_english_text(address_en)
    dob = clean_english_text(dob)
    issued_date = clean_english_text(issued_date)
    details_as_on = clean_english_text(details_as_on)

    # ================= FRONT SIDE ONLY =================

# ================= PHOTO SECTION (LEFT COLOUR + RIGHT B/W) =================

# --- 1. Main Left Photo (Colour) ---
    photo_width_main = int(bg_width * 0.227)
    photo_height_main = int(bg_height * 0.448)

# Resize original photo for left side
    user_photo_left = user_photo.resize((photo_width_main, photo_height_main))

# Paste Colour Photo on Left (Original Position)
    bg_front.paste(
        user_photo_left, 
    (int(bg_width * 0.048), int(bg_height * 0.289)), 
    user_photo_left
)


# --- 2. Small Right Photo (Black & White) ---
# Note: Iska size thoda chota rakhenge original Aadhaar ki tarah (Aapne 0.60 likha tha wo bahut bada ho jayega)
    photo_width_bw = int(bg_width * 0.08)  # Right side ke liye chota size (Adjustable)
    photo_height_bw = int(bg_height * 0.13) 

# Step A: Black & White mein convert karein ("L" mode)
    user_photo_bw = user_photo.convert("L")

# Step B: Resize karein
    user_photo_bw = user_photo_bw.resize((photo_width_bw, photo_height_bw))

# Step C: Wapas RGBA mein convert karein taaki paste ho sake
    user_photo_bw_final = user_photo_bw.convert("RGBA")

# Step D: Right side mein paste karein 
# Coordinates: x ko badha kar 0.75-0.80 ke paas rakhein taaki wo right mein jaye
    bg_front.paste(
        user_photo_bw_final, 
    (int(bg_width * 0.85), int(bg_height * 0.29)), # Right side position
    user_photo_bw_final
)
    # English Name
    if name_en:
        draw_f.text((int(bg_width * 0.30), int(bg_height * 0.33)), name_en, fill="black", font=font_name_en)

    # Hindi Name
    if name_hi:
        draw_hindi_text(bg_front, name_hi, (int(bg_width * 0.30), int(bg_height * 0.31)), font_path_hi, int(bg_height * 0.041))

    # DOB
    if dob:
    # 1. Naya font variable banayein bade size ke liye
    # Aapne 0.051 manga hai, jo kafi bada size hai
        # font_dob_en = ImageFont.truetype(font_path_en, int(bg_height * 0.036))

    # 2. Hindi mein "जन्म तिथि /" draw karein
        draw_hindi_text(
        bg_front, 
        f"जन्म तिथि/DOB:{dob} ", 
        (int(bg_width * 0.30), int(bg_height * 0.426)), 
        font_path_hi, 
        int(bg_height * 0.041) # Hindi size normal rakhein
    )

    # 3. English DOB draw karein naye font ke saath
    # Note: Maine yahan 'font=font_dob_en' use kiya hai aur 'size' hata diya hai
    # draw_f.text(
    #     (int(bg_width * 0.41), int(bg_height * 0.398)), 
    #     f"DOB: {dob}", 
    #     fill="black", 
    #     font=font_dob_en
    # )


    


    # Gender
    gender_hi = " महिला/ FEMALE" if gender_key == "female" else " पुरुष/ MALE"
    # gender_hi = "महिला/ " if gender_key == "female" else "पुरुष/ "

    # font_gender_en = ImageFont.truetype(font_path_en, int(bg_height * 0.036))

    
    # draw_f.text((int(bg_width * 0.333), int(bg_height * 0.445)), gender_en, fill="black", font=font_gender_en)
    draw_hindi_text(bg_front, gender_hi, (int(bg_width * 0.30), int(bg_height * 0.487)), font_path_hi, int(bg_height * 0.041))

    # Issued Date (Front Only)
    # ================= VERTICAL ISSUED DATE =================
    if issued_date:
        text_to_draw = f"Aadhaar No. Issued:{issued_date}"
        txt_img = Image.new("RGBA", (500, 60), (255, 255, 255, 0))
        d = ImageDraw.Draw(txt_img)
        d.text((0, 0), text_to_draw, fill="black", font=font_bd)
        w = txt_img.rotate(90, expand=True)
        bg_front.paste(w, (int(bg_width * 0.013), int(bg_height * 0.3)), w)
    # ================= BACK SIDE ONLY =================

    # English Address
# English Address

    # Backend ki generate_aadhaar_card function ke andar address section:
# --- Address Section (Back Side) ---
    # --- 1. Font Size Update (English ko Hindi ke barabar karein) ---
# generate_aadhaar_card function ke shuruat mein jahan fonts define hain:
    font_data_en = ImageFont.truetype(font_path_en, int(bg_height * 0.035)) # Pehle 0.025 tha

# --- 2. Address Logic (Back Side) ---
    if address_hi:
        final_address_hi = clean_hindi_text(address_hi)
        hindi_x = int(bg_width * 0.06)
        hindi_y = int(bg_height * 0.28)

    # Hindi Text Draw
        draw_hindi_text(
            bg_back,
            final_address_hi, 
            (hindi_x, hindi_y),
            font_path_hi,
            int(bg_height * 0.035)
    )
    
    # --- Dynamic Gap Adjust ---
        num_lines_hi = len(final_address_hi.split('\n'))
    # Line height ko thoda badhaya hai (0.045 -> 0.05) taaki bade font mein gap sahi dikhe
        line_height_hi = int(bg_height * 0.05) 
        english_y_dynamic = hindi_y + (num_lines_hi * line_height_hi) + 5
    else:
        english_y_dynamic = int(bg_height * 0.43)

# --- English Address (Same Size & Alignment) ---
    # --- English Address (Preserve Frontend Lines) ---
    if address_en:
        final_address_en = clean_english_text(address_en)
    
    # 1. Frontend ke manual breaks (\n) ko split karein
    raw_lines = final_address_en.split('\n')
    wrapped_lines = []
    
    for line in raw_lines:
        # AGAR line 35 characters se lambi hai, TABHI wrap karein
        # Width ko 35-38 rakhein taaki wo jaldi break ho aur lines bani rahein
        if len(line.strip()) > 42:
            w_line = textwrap.fill(line, width=42)
            wrapped_lines.append(w_line)
        else:
            # Agar chhoti line hai (jaise frontend se aayi), toh use wrap mat karein
            wrapped_lines.append(line)
    
    final_wrapped_text = "\n".join(wrapped_lines)

    # 2. Draw Text
    draw_b.multiline_text(
        (int(bg_width * 0.06), english_y_dynamic), 
        "Address:\n" + final_wrapped_text, # Manual "Address:" aur fir aapka text
        fill="black",
        font=font_data_en,
        spacing=6
    )
    # VID
    if vid:
        font_vid_en = ImageFont.truetype(font_path_en, int(bg_height * 0.035))
        draw_b.text((int(bg_width * 0.36), int(bg_height * 0.84)), f"VID: {clean_english_text(vid)}", fill="black", font=font_vid_en)
        draw_f.text((int(bg_width * 0.36), int(bg_height * 0.84)), f"VID: {clean_english_text(vid)}", fill="black", font=font_vid_en)
    # Details As On
    if details_as_on:
        v_text = f"Details as on: {details_as_on}"
        v_font = ImageFont.truetype(font_path_en, int(bg_height * 0.03))
        v_img = Image.new("RGBA", (500, 60), (255, 255, 255, 0))
        v_draw = ImageDraw.Draw(v_img)
        v_draw.text((0, 0), v_text, fill="black", font=v_font)
        v_rot = v_img.rotate(90, expand=True)
        bg_back.paste(v_rot, (int(bg_width * 0.013), int(bg_height * 0.12)), v_rot)
    # ================= BOTH SIDES (AADHAAR NUMBER) =================

    if aadhaar_number:
        aadhaar_number = "".join(filter(str.isdigit, aadhaar_number))
        formatted = " ".join([aadhaar_number[i:i+4] for i in range(0, len(aadhaar_number), 4)])

        font_aadhar_en = ImageFont.truetype(font_path_en, int(bg_height * 0.08))
        font_aadhar_sm = ImageFont.truetype(font_path_en, int(bg_height * 0.018))
        # Front
        
        draw_f.text((int(bg_width * 0.85), int(bg_height * 0.42 )), formatted, fill="black", font=font_aadhar_sm)
        draw_f.text((int(bg_width * 0.32), int(bg_height * 0.768)), formatted, fill="black", font=font_aadhar_en)
        # Back
        draw_b.text((int(bg_width * 0.32), int(bg_height * 0.768)), formatted, fill="black", font=font_aadhar_en)

    # ================= SAVE & PDF =================

    front_path = os.path.join(OUTPUT_FOLDER, "front_processed.png")
    back_path = os.path.join(OUTPUT_FOLDER, "back_processed.png")
    bg_front.convert("RGB").save(front_path)
    bg_back.convert("RGB").save(back_path)

    pdf_path = os.path.join(OUTPUT_FOLDER, "final_aadhaar.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=A4)

    max_width = 7 * inch
    aspect = bg_height / bg_width
    pdf_height = max_width * aspect

    elements = [
        RLImage(front_path, width=max_width, height=pdf_height),
        RLImage(back_path, width=max_width, height=pdf_height)
    ]
    doc.build(elements)

    return pdf_path