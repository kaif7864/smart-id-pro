import os
import qrcode
from PIL import Image, ImageDraw, ImageFont
from reportlab.platypus import SimpleDocTemplate, Image as RLImage, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def generate_rc_front_image(data):
    """
    Generates the Front Side Image of Registration Certificate (Form 23).
    Uses rcf.jpg as the base template — only values are drawn on top.
    """
    template_path = os.path.join("assets/rc/rcf.jpg")
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Front template not found: {template_path}")

    bg = Image.open(template_path).convert("RGBA")
    width, height = bg.size
    draw = ImageDraw.Draw(bg)

    # ── FONTS & WEIGHT CONTROL ────────────────────────────────────────────────
    # FRONT_TEXT_WIDTH_SCALE: 1.0=normal | <1.0=condensed/narrow (0.88 matches original)
    # FRONT_TEXT_STROKE     : 0.0=light/regular | 0.3=semi-bold | 1.0=bold
    FRONT_TEXT_WIDTH_SCALE = 0.99  # ← TUNE THIS (try 0.80 – 1.00)
    FRONT_TEXT_STROKE      = 0.1   # ← TUNE THIS (0.0=light, 0.2=medium, 0.5=bold)

    try:
        font_val      = ImageFont.truetype("assets/font/arial.ttf",   26)   # regular values
        font_bold_val = ImageFont.truetype("assets/font/arialbd.ttf", 26)   # bold values
        font_sr       = ImageFont.truetype("assets/font/arialbd.ttf", 34)   # Owner Sr.No circle
    except:
        font_val = font_bold_val = font_sr = ImageFont.load_default()

    def draw_front_text(x, y, text, font, width_scale=FRONT_TEXT_WIDTH_SCALE, stroke=FRONT_TEXT_STROKE):
        """Draw front text with width scaling and fractional stroke control."""
        bbox = font.getbbox(text)
        if bbox[2] <= bbox[0]:
            return
        text_w  = bbox[2] - bbox[0]
        text_h  = bbox[3] - bbox[1]
        stroke_int  = int(stroke)
        stroke_frac = stroke - stroke_int
        pad = stroke_int + 6
        canvas_w = text_w + pad * 2
        canvas_h = text_h + pad * 2
        draw_x = pad - bbox[0]
        draw_y = pad - bbox[1]

        tmp = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        tmp_draw = ImageDraw.Draw(tmp)
        tmp_draw.text((draw_x, draw_y), text, fill="black", font=font,
                      stroke_width=stroke_int, stroke_fill="black")

        if stroke_frac > 0.01:
            alpha = int(255 * stroke_frac)
            overlay = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            ov_draw = ImageDraw.Draw(overlay)
            fc = (0, 0, 0, alpha)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ov_draw.text((draw_x + dx, draw_y + dy), text, fill=fc, font=font,
                             stroke_width=stroke_int, stroke_fill=fc)
            tmp = Image.alpha_composite(tmp, overlay)

        new_w = max(1, int(text_w * width_scale))
        tmp = tmp.resize((new_w + pad * 2, canvas_h), Image.LANCZOS)
        bg.paste(tmp, (x - pad + bbox[0], y - pad + bbox[1]), tmp)

    # ── VALUE POSITIONS — pixel-analysed from rcf.jpg ─────────────────────────
    # Row 1 ── Regn No | Date of Regn | Regn.Validity
    draw_front_text(408, 258, str(data.get("regn_no",  "")).upper(), font_bold_val)
    draw_front_text(618, 258, str(data.get("reg_date", "")).upper(), font_val)
    draw_front_text(824, 258, str(data.get("validity", "")).upper(), font_val)

    # Row 2 ── Chassis No | Owner Sr.No (circle)
    draw_front_text(408, 331, str(data.get("chassis_no", "")).upper(), font_val)

    owner_sr   = str(data.get("owner_sr_no", "1"))
    sr_bbox    = font_sr.getbbox(owner_sr)
    sr_w, sr_h = sr_bbox[2] - sr_bbox[0], sr_bbox[3] - sr_bbox[1]
    draw.text((1156 - sr_w // 2, 337 - sr_h // 2), owner_sr, fill="black", font=font_sr)

    # Row 3 ── Engine No
    draw_front_text(409, 406, str(data.get("engine_no", "")).upper(), font_val)

    # Row 4 ── Owner Name
    draw_front_text(409, 478, str(data.get("owner_name", "")).upper(), font_val)

    # Row 5 ── Son/Daughter/Wife of
    draw_front_text(409, 551, str(data.get("relation_name", "")).upper(), font_val)

    # Row 6 ── Address (Exact user lines / line-breaks as entered)
    address_raw = str(data.get("address", "")).upper()
    raw_lines = [l.strip() for l in address_raw.splitlines() if l.strip()]
    if not raw_lines:
        raw_lines = [address_raw]

    # Process lines: if any line > 50 chars, wrap it into sub-lines
    formatted_lines = []
    for line in raw_lines:
        while len(line) > 50:
            formatted_lines.append(line[:50])
            line = line[50:].strip()
        if line:
            formatted_lines.append(line)

    start_y = 628
    line_spacing = 30
    for i, line_str in enumerate(formatted_lines[:3]):
        draw_front_text(409, start_y + (i * line_spacing), line_str, font_val)

    # Bottom-left ── Fuel Used | Emission Norms
    draw_front_text(123, 656, str(data.get("fuel_used",      "PETROL")).upper(),          font_val)
    draw_front_text(123, 730, str(data.get("emission_norms", "BHARAT STAGE IV")).upper(), font_val)

    # ── ROTATED SIDE TAG (Right edge: NEW / DUP / HPT/TO etc.) ───────────────
    side_tag = str(data.get("side_tag", data.get("hpt_to", data.get("card_tag", data.get("card_type", ""))))).upper().strip()
    if side_tag and side_tag != "NONE":
        try:
            font_side = ImageFont.truetype("assets/font/arialbd.ttf", 24)
        except:
            font_side = font_bold_val

        bbox = font_side.getbbox(side_tag)
        tw = bbox[2] - bbox[0] + 12
        th = bbox[3] - bbox[1] + 12
        txt_img = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        txt_draw = ImageDraw.Draw(txt_img)
        txt_draw.text((6, 6), side_tag, fill="black", font=font_side)
        rotated = txt_img.rotate(270, expand=True)
        bg.paste(rotated, (1195, 480), rotated)

    return bg

def generate_rc_back_image(data):
    """
    Generates the Back Side Image of Registration Certificate (Form 23A).

    Positioning method:
      1. NumPy dark-pixel analysis on the BLANK rcb.jpg template to find
         exact bottom-Y of each bold label band.
      2. Value text is drawn (label_bottom + 8px) so it sits just below.
      3. Font: 22px Arial Bold  (renders ~16px tall) – visually matches
         the reference printed card.
    """
    template_path = os.path.join("assets/rc/rcb.jpg")
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template image not found: {template_path}")

    bg = Image.open(template_path).convert("RGBA")
    draw = ImageDraw.Draw(bg)

    # Regular Arial for values – matches reference card's light/regular weight text
    try:
        font_val = ImageFont.truetype("assets/font/arial.ttf", 27)
    except:
        font_val = ImageFont.load_default()

    # ── FONT WIDTH & WEIGHT CONTROL ───────────────────────────────────────────
    # TEXT_WIDTH_SCALE : 1.0=normal | <1.0=condensed/narrow | >1.0=expanded/wide
    # TEXT_STROKE      : float 0.0–2.0  (0=light, 0.3=medium-light, 0.5=medium,
    #                    1.0=semi-bold, 1.5=bold, 2.0=heavy)
    TEXT_WIDTH_SCALE = 0.90   # ← TUNE THIS (try 0.80 – 1.10)
    TEXT_STROKE      = 0.1    # ← TUNE THIS — float OK: 0.0 / 0.3 / 0.5 / 1.0 / 1.5 / 2.0

    def draw_text_scaled(x, y, text, font, width_scale=TEXT_WIDTH_SCALE, stroke=TEXT_STROKE):
        """Draw text with custom width scaling and fractional stroke (fine bold control)."""
        bbox = font.getbbox(text)
        if bbox[2] <= bbox[0]:
            return

        text_w  = bbox[2] - bbox[0]
        text_h  = bbox[3] - bbox[1]
        stroke_int  = int(stroke)          # integer part  → PIL stroke_width
        stroke_frac = stroke - stroke_int  # decimal part  → alpha-blend overlay

        # Generous padding so descenders/stroke never clip
        pad = stroke_int + 6

        canvas_w = text_w + pad * 2
        canvas_h = text_h + pad * 2

        # Offsets so bbox origin lands exactly at (pad, pad)
        draw_x = pad - bbox[0]
        draw_y = pad - bbox[1]

        # ── Base text layer ──────────────────────────────────────────────────
        tmp = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        tmp_draw = ImageDraw.Draw(tmp)
        tmp_draw.text((draw_x, draw_y), text, fill="black", font=font,
                      stroke_width=stroke_int, stroke_fill="black")

        # ── Fractional bold overlay (alpha-blended shifted copies) ───────────
        # e.g. stroke=0.5 → draws semi-transparent shifted copy giving medium weight
        if stroke_frac > 0.01:
            alpha = int(255 * stroke_frac)
            overlay = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            ov_draw = ImageDraw.Draw(overlay)
            fc = (0, 0, 0, alpha)
            # Shift in 4 directions for smooth thickening
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ov_draw.text((draw_x + dx, draw_y + dy), text, fill=fc, font=font,
                             stroke_width=stroke_int, stroke_fill=fc)
            tmp = Image.alpha_composite(tmp, overlay)

        # ── Scale width ──────────────────────────────────────────────────────
        new_w  = max(1, int(text_w * width_scale))
        tmp = tmp.resize((new_w + pad * 2, canvas_h), Image.LANCZOS)

        # Paste so that text visually starts at (x, y)
        bg.paste(tmp, (x - pad + bbox[0], y - pad + bbox[1]), tmp)

    # ── LEFT COLUMN (x = 98) ───────────────────────────────────────────────
    # draw_y = label_band_bottom - 1
    # Reasoning: 3px visual gap wanted − 4px PIL ascender offset = draw at label_bottom-1
    # Label boundaries are from NumPy dark-pixel analysis of blank rcb.jpg template.
    draw_text_scaled(130, 226, str(data.get("regn_no",    "")).upper(), font_val)  # Regn.No
    draw_text_scaled(130, 295, str(data.get("mfg_date",   "")).upper(), font_val)  # Month&Yr
    draw_text_scaled(130, 366, str(data.get("wheel_base", "")).upper(), font_val)  # WheelBase
    draw_text_scaled(130, 441, str(data.get("cc",         "")).upper(), font_val)  # CubicCap
    draw_text_scaled(130, 513, str(data.get("cylinders", "1")).upper(), font_val)  # NoCylinders
    draw_text_scaled(130, 584, str(data.get("ulw",        "")).upper(), font_val)  # ULW

    # ── MIDDLE COLUMN (x = 365) ───────────────────────────────────────────
    draw_text_scaled(365, 117, str(data.get("vehicle_class", "")).upper(), font_val)  # VehicleClass
    draw_text_scaled(365, 188, str(data.get("maker_name",    "")).upper(), font_val)  # MakerName
    draw_text_scaled(365, 260, str(data.get("model_name",    "")).upper(), font_val)  # ModelName
    draw_text_scaled(365, 331, str(data.get("colour",        "")).upper(), font_val)  # Colour
    draw_text_scaled(365, 408, str(data.get("body_type",     "")).upper(), font_val)  # BodyType
    draw_text_scaled(365, 479, str(data.get("seating",       "")).upper(), font_val)  # Seating

    # ── REGISTERING AUTHORITY (Bottom Right) ──────────────────────────────
    draw_text_scaled(895, 673, str(data.get("registering_authority", "")).upper(), font_val)

    # ── FINANCIER NAME (Below QR code if present) ───────────────────────────
    financier_name = str(data.get("financier_name", "")).strip().upper()
    if financier_name:
        try:
            font_label_bold = ImageFont.truetype("assets/font/arialbd.ttf", 25)
        except:
            font_label_bold = font_val

        draw_text_scaled(890, 405, "Financier Name", font_label_bold, stroke=0.30, width_scale=1.0 )
        draw_text_scaled(890, 435, financier_name, font_val)

    # ── DYNAMIC QR CODE (top-right corner) — dense/complex like original ──────
    qr_payload = (
        f"REGN:{data.get('regn_no', '')}"
        f"|REG_DATE:{data.get('reg_date', '')}"
        f"|VALIDITY:{data.get('validity', '')}"
        f"|CH:{data.get('chassis_no', '')}"
        f"|ENG:{data.get('engine_no', '')}"
        f"|OWNER:{data.get('owner_name', '')}"
        f"|ADDR:{data.get('address', '')}"
        f"|CLASS:{data.get('vehicle_class', '')}"
        f"|MAKER:{data.get('maker_name', '')}"
        f"|MODEL:{data.get('model_name', '')}"
        f"|COLOUR:{data.get('colour', '')}"
        f"|BODY:{data.get('body_type', '')}"
        f"|FUEL:{data.get('fuel_used', '')}"
        f"|CC:{data.get('cc', '')}"
        f"|CYL:{data.get('cylinders', '')}"
        f"|WB:{data.get('wheel_base', '')}"
        f"|ULW:{data.get('ulw', '')}"
        f"|SEAT:{data.get('seating', '')}"
        f"|MFG:{data.get('mfg_date', '')}"
        f"|NORM:{data.get('emission_norms', '')}"
        f"|AUTH:{data.get('registering_authority', 'HARIDWAR ARTO')}"
    )
    # ERROR_CORRECT_H = highest (30% redundancy) → more modules → denser pattern
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=4,
        border=1
    )
    # ── QR COLOUR CONTROL ─────────────────────────────────────────────────────
    # Change these two RGB values to whatever colour you want:
    QR_DOT_COLOR = (0,   0,   0  )   # ← dark modules colour  (default: black)
    QR_BG_COLOR  = (230, 230, 230)   # ← background colour    (default: white)
    #
    # Examples:
    #   Dark navy dots  : QR_DOT_COLOR = (20, 40, 80)
    #   Light grey bg   : QR_BG_COLOR  = (220, 220, 220)
    #   Blue-tinted bg  : QR_BG_COLOR  = (210, 230, 245)
    #   Dark on cream   : QR_DOT_COLOR = (30, 30, 30), QR_BG_COLOR = (245, 240, 220)

    qr.add_data(qr_payload)
    qr.make(fit=True)

    qr_img = qr.make_image(
        fill_color=QR_DOT_COLOR,
        back_color=QR_BG_COLOR
    ).convert("RGBA")
    qr_img = qr_img.resize((302, 300))
    bg.paste(qr_img, (887, 100))

    # ── AUTHORITY SIGNATURE SELECTION (Presets 1..5, Upload, Text, None) ────
    sign_mode = str(data.get("sign_mode", "preset")).lower().strip()
    sign_id = str(data.get("sign_id", "1")).strip()
    custom_sign_img = data.get("custom_sign_img")

    # If sign_mode is NOT default preset '1', patch the default template signature
    if sign_mode != "preset" or sign_id != "1":
        bg_patch = bg.crop((730, 570, 880, 645))
        bg.paste(bg_patch, (880, 570))

    # Fixed starting X and Y position so all signatures start at the exact same spot
    SIGN_START_X = 895
    SIGN_START_Y = 565

    if sign_mode == "preset":
        preset_file = os.path.join("assets", "rc", "sign", f"{sign_id}.png")
        if os.path.exists(preset_file):
            sign_img = Image.open(preset_file).convert("RGBA")
            sign_img.thumbnail((140, 70), Image.LANCZOS)
            bg.paste(sign_img, (SIGN_START_X, SIGN_START_Y), sign_img)

    elif sign_mode == "upload" and custom_sign_img:
        try:
            if isinstance(custom_sign_img, str) and custom_sign_img.startswith("data:image"):
                import base64, io
                b64_str = custom_sign_img.split(",")[-1]
                img_bytes = base64.b64decode(b64_str)
                sign_img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
            elif isinstance(custom_sign_img, str) and os.path.exists(custom_sign_img):
                sign_img = Image.open(custom_sign_img).convert("RGBA")
            elif hasattr(custom_sign_img, "read"):
                sign_img = Image.open(custom_sign_img).convert("RGBA")
            elif isinstance(custom_sign_img, Image.Image):
                sign_img = custom_sign_img.convert("RGBA")
            else:
                sign_img = None

            if sign_img:
                sign_img.thumbnail((140, 70), Image.LANCZOS)
                bg.paste(sign_img, (SIGN_START_X, SIGN_START_Y), sign_img)
        except Exception as e:
            print(f"[WARNING] Custom signature processing failed: {e}")

    elif sign_mode == "text":
        sign_text = str(data.get("sign_text", "R.K. Sharma")).strip()
        if sign_text:
            try:
                font_sign = ImageFont.truetype("assets/font/ARJUN.TTF", 28)
            except:
                font_sign = font_val

            bbox = font_sign.getbbox(sign_text)
            text_w = bbox[2] - bbox[0]
            tmp_s = Image.new("RGBA", (text_w + 20, 50), (0, 0, 0, 0))
            tmp_draw = ImageDraw.Draw(tmp_s)
            tmp_draw.text((10, 5), sign_text, fill=(20, 50, 140, 255), font=font_sign)
            bg.paste(tmp_s, (950 - text_w // 2, 595), tmp_s)

    return bg

def generate_rc_card(data):
    front_img = generate_rc_front_image(data)
    back_img = generate_rc_back_image(data)

    final_front_path = os.path.join(OUTPUT_FOLDER, "rc_front_generated.png")
    final_back_path = os.path.join(OUTPUT_FOLDER, "rc_back_generated.png")
    pdf_path = os.path.join(OUTPUT_FOLDER, f"rc_{data.get('regn_no', 'card')}.pdf")

    front_img.convert("RGB").save(final_front_path)
    back_img.convert("RGB").save(final_back_path)

    # Build PDF for printing (larger size with proper vertical spacing)
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    elements = []

    card_w = 3.65 * inch
    card_h = 2.40 * inch

    elements.append(RLImage(final_front_path, width=card_w, height=card_h))
    elements.append(Spacer(1, 0.35 * inch))  # Gap between Front & Back card
    elements.append(RLImage(final_back_path, width=card_w, height=card_h))

    doc.build(elements)
    return pdf_path
