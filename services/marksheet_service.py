from PIL import Image, ImageDraw, ImageFont
import io
from datetime import datetime   

def generate_marksheet_image(student_data):
    # 1. Template image load karein
    try:
        img = Image.open("assets/2002.jpg").convert("RGB")
    except FileNotFoundError:
        return None
        
    draw = ImageDraw.Draw(img)
    
    # 2. Font set karein
    try:
        font = ImageFont.truetype("arial.ttf", 40) 
        bold_font = ImageFont.truetype("arial.ttf", 50)
    except IOError:
        font = ImageFont.load_default()
        bold_font = font

    # 3. Data ko image par likhein
    text_color = (0, 0, 0)

    try:
        date_obj = datetime.strptime(student_data['dob'], '%Y-%m-%d')
        formatted_dob = date_obj.strftime('%d/%m/%Y')
    except ValueError:
        formatted_dob = student_data['dob']

    student_Name = student_data['name'].upper()

    
    # --- YAHAN COORDINATES ADJUST KAREIN ---
    # Name
    draw.text((755, 650), student_Name, font=bold_font, fill=text_color)
    # DOB
    draw.text((1500, 650), formatted_dob, font=bold_font, fill=text_color)
    # Serial Number
    draw.text((300, 650), student_data['serial_number'], font=bold_font, fill=text_color)
    # Roll Number
    draw.text((1900, 650), student_data['roll_number'], font=bold_font, fill=text_color)
    
    # Subjects (Example)
   
    
    # 4. Image ko memory me save karein
    img_io = io.BytesIO()
    img.save(img_io, 'JPEG', quality=95)
    img_io.seek(0)
    
    return img_io