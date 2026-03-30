from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import uharfbuzz as hb
import freetype
from datetime import datetime


# ================= HINDI TEXT RENDER (FIX MATRA ISSUE) =================
def draw_hindi_text(image, text, position, font_path, font_size, fill=(0, 0, 0), opacity=255):
    if not text:
        return

    x, y = position

    face = freetype.Face(font_path)
    face.set_char_size(font_size * 64)

    with open(font_path, "rb") as f:
        fontdata = f.read()

    hb_face = hb.Face(fontdata)
    hb_font = hb.Font(hb_face)
    hb_font.scale = (font_size * 64, font_size * 64)

    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf)

    infos = buf.glyph_infos
    positions = buf.glyph_positions

    pen_x = 0

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

            rgba = Image.new("RGBA", (w, h), (fill[0], fill[1], fill[2], opacity))
            rgba.putalpha(glyph_image)

            image.paste(
                rgba,
                (int(x + pen_x + left), int(y - top)),
                rgba
            )

        pen_x += pos.x_advance / 64


# ================= ENGLISH TEXT RENDER (Arial Bold) =================
def draw_english_text(image, text, position, font_path, font_size, fill=(0, 0, 0), transparency=200, blur=1):
    """Draw English/Numbers text using PIL (for Arial Bold dates) with transparency and blur"""
    if not text:
        return
    
    try:
        font = ImageFont.truetype(font_path, int(font_size))
    except:
        font = ImageFont.load_default()
    
    # Create a temporary transparent layer for text
    text_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)
    
    # Add alpha (transparency) to fill color
    fill_with_alpha = (fill[0], fill[1], fill[2], transparency)
    
    # Draw text on temporary layer
    text_draw.text(position, text, font=font, fill=fill_with_alpha)
    
    # Apply blur effect
    if blur > 0:
        text_layer = text_layer.filter(ImageFilter.GaussianBlur(radius=blur))
    
    # Composite the text layer onto the main image
    image = Image.alpha_composite(image, text_layer)
    
    return image


# ================= MAIN FUNCTION =================
def generate_hindi_id_card(data, photo_file=None):

    # ===== FORMAT DATE (DD-Month-YYYY) =====
    def format_date(date_str):
        if not date_str:
            return ""
        try:
            # If date is in YYYY-MM-DD format (from HTML date input)
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            months = ['January', 'February', 'March', 'April', 'May', 'June',
                     'July', 'August', 'September', 'October', 'November', 'December']
            day = date_obj.day
            month = months[date_obj.month - 1]
            year = date_obj.year
            return f"{day}-{month}-{year}"
        except:
            # If already in correct format or unknown format
            return date_str

    # ===== TEMPLATE LOAD =====
    try:
        img = Image.open("assets/cas.jpeg").convert("RGBA")
    except FileNotFoundError:
        print("Template not found!")
        return None

    bg_width, bg_height = img.size

    # ===== FONT PATH (IMPORTANT) =====
    hindi_font_path = "assets/NotoSansDevanagari-Regular.ttf"
    english_font_path = "assets/arialbd.ttf"  # Arial Bold for dates

    # ===== FONT SIZES =====
    font_small = int(bg_height * 0.012)
    font_medium = int(bg_height * 0.0106)
    font_large = int(bg_height * 0.013)

    text_color = (0, 0, 0, 255)

    # ===== PHOTO =====
    photo_config = {
        'width': int(bg_width * 0.16),
        'height': int(bg_height * 0.13),
        'x': int(bg_width * 0.78),
        'y': int(bg_height * 0.23)
    }

    if photo_file:
        try:
            user_photo = Image.open(photo_file).convert("RGBA")
            user_photo = user_photo.resize(
                (photo_config['width'], photo_config['height'])
            )

            img.paste(
                user_photo,
                (photo_config['x'], photo_config['y']),
                user_photo
            )
        except Exception as e:
            print("Photo error:", e)

    # ===== TEXT DATA =====
    text_positions = [
        {
            'text': f"{data.get('name', '')}",
            'x': int(bg_width * 0.36),
            'y': int(bg_height * 0.387),
            'size': font_large
        },
        {
            'text': f"{data.get('fatherName', '')}",
            'x': int(bg_width * 0.36),
            'y': int(bg_height * 0.406),
            'size': font_large
        },
        {
            'text': f"{data.get('idNumber', '').upper()}",
            'x': int(bg_width * 0.81),
            'y': int(bg_height * 0.0568),
            'size': font_medium
        },
        {
            'text': f"{data.get('state', '')}",
            'x': int(bg_width * 0.36),
            'y': int(bg_height * 0.428),
            'size': font_large
        },
        {
            'text': f"{data.get('state', '')}",
            'x': int(bg_width * 0.36),
            'y': int(bg_height * 0.472),
            'size': font_large
        },
        {
            'text': f"{data.get('district', '')}",
            'x': int(bg_width * 0.36),
            'y': int(bg_height * 0.516),
            'size': font_large
        },
        {
            'text': f"{data.get('tehsil', '')}",
            'x': int(bg_width * 0.36),
            'y': int(bg_height * 0.493),
            'size': font_large
        },
        {
            'text': f":{format_date(data.get('date', ''))}",
            'x': int(bg_width * 0.133),
            'y': int(bg_height * 0.237),
            'size': int(bg_height * 0.01),
            'type': 'date'  # Use Arial Bold for dates
        },
         {
            'text': f"  {format_date(data.get('date', ''))}",
            'x': int(bg_width * 0.829),
            'y': int(bg_height * 0.8318),
            'size': int(bg_height * 0.0085),
            'type': 'date'  # Use Arial Bold for dates
        },
        {
            'text': f"{data.get('address', '')[:50]}",
            'x': int(bg_width * 0.36),
            'y': int(bg_height * 0.45),
            'size': font_large,
            'font_path': english_font_path
        }
    ]

    # ===== DRAW TEXT (HINDI FIXED + ENGLISH DATES) =====
    for item in text_positions:
        if item.get('type') == 'date':
            # Use English Arial Bold for dates with transparency and blur
            img = draw_english_text(
                img,
                item['text'],
                (item['x'], item['y']),
                english_font_path,
                item['size'],
                text_color,
                transparency=200,  # 0-255 (lower = more transparent)
                blur=0.3           # Blur radius
            )
        else:
            # Use Hindi font for other text
            draw_hindi_text(
                img,
                item['text'],
                (item['x'], item['y']),
                hindi_font_path,
                item['size'],
                text_color,
                opacity=200  # 0-255 (lower = more transparent)
            )

    # ===== FINAL SAVE =====
    final_img = img.convert("RGB")

    img_io = io.BytesIO()
    final_img.save(img_io, "JPEG", quality=95)
    img_io.seek(0)

    return img_io