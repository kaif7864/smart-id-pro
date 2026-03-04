from PIL import Image, ImageDraw, ImageFont, ImageFilter # ImageFilter zaroori hai
import io
from datetime import datetime   

def generate_marksheet_image(student_data):
    # 1. Template image load karein
    try:
        # Template ko RGBA mein convert karna zaroori hai layers merge karne ke liye
        img = Image.open("assets/2002.jpg").convert("RGBA")
    except FileNotFoundError:
        return None
        
    # 2. Ek nayi transparent layer banayein text ke liye
    text_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)
    
    # 3. Font set karein
    try:
        font = ImageFont.truetype("arial.ttf", 40) 
        bold_font = ImageFont.truetype("arial.ttf", 50)
    except IOError:
        font = ImageFont.load_default()
        bold_font = font

    # 4. Transparency aur Color set karein
    text_alpha = 200  # 0 to 255 (Transparency level)
    text_color = (0, 0, 0, text_alpha) # Black with transparency

    # 5. Data formatting
    try:
        date_obj = datetime.strptime(student_data.get('dob', ''), '%Y-%m-%d')
        formatted_dob = date_obj.strftime('%d/%m/%Y')
    except (ValueError, TypeError):
        formatted_dob = student_data.get('dob', '')

    student_Name = student_data.get('name', '').upper()

    # 6. Text ko sirf text_layer par likhein
    # Name
    draw.text((755, 650), student_Name, font=bold_font, fill=text_color)
    # DOB
    draw.text((1500, 650), formatted_dob, font=bold_font, fill=text_color)
    # Serial Number
    draw.text((300, 650), student_data.get('serial_number', ''), font=bold_font, fill=text_color)
    # Roll Number
    draw.text((1900, 650), student_data.get('roll_number', ''), font=bold_font, fill=text_color)
    
    # 7. Blur effect apply karein
    blur_radius = 1 # Itna kafi hai readable blur ke liye
    blurred_text_layer = text_layer.filter(ImageFilter.GaussianBlur(blur_radius))
    
    # 8. Background image aur Blurred text layer ko merge karein
    final_img = Image.alpha_composite(img, blurred_text_layer)
    
    # 9. PDF banane ke liye RGB mein convert karein
    final_img_rgb = final_img.convert("RGB")

    # 10. Memory mein save karein (PDF Format)
    img_io = io.BytesIO()
    final_img_rgb.save(img_io, 'PDF', resolution=100.0)
    img_io.seek(0)
    
    return img_io