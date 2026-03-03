import pymupdf
import re
import base64

def extract_aadhaar_details(pdf_path):
    doc = pymupdf.open(pdf_path)

    text = ""
    for page in doc:
        text += page.get_text()

    # Keep original for vertical fix
    raw_text = text

    # Clean text for normal extraction
    text_clean = text.replace("\n", " ")

    # ---------------- NAME ----------------
    name_match = re.search(r"\n([A-Za-z\s]+)\nजन्म तिथि/DOB", text)
    name = name_match.group(1).strip() if name_match else ""

    hindi_name_match = re.search(r"\n([\u0900-\u097F\s]+)\n[A-Za-z\s]+\nजन्म तिथि/DOB", text)
    hindi_name = hindi_name_match.group(1).strip() if hindi_name_match else ""

    # ---------------- FATHER ----------------
    father_match = re.search(r"S/O:\s*([A-Za-z\s]+?),", text)
    father_name = father_match.group(1).strip() if father_match else ""

    hindi_father_match = re.search(r"आत्मज:\s*([\u0900-\u097F\s]+?),", text)
    hindi_father = hindi_father_match.group(1).strip() if hindi_father_match else ""

    # ---------------- DOB ----------------
    dob_match = re.search(r"जन्म तिथि/DOB:\s*(\d{2}/\d{2}/\d{4})", text)
    dob = dob_match.group(1) if dob_match else ""

    # ---------------- GENDER ----------------
    gender_match = re.search(r"(पुरुष/ MALE|महिला/ FEMALE)", text)
    gender = gender_match.group(1) if gender_match else ""

    # ---------------- AADHAAR NUMBER ----------------
    aadhaar_numbers = re.findall(r"\b\d{4}\s\d{4}\s\d{4}\b", text)
    aadhaar_number = aadhaar_numbers[0] if aadhaar_numbers else ""

    # ---------------- VID ----------------
    vid_match = re.search(r"VID\s*:\s*(\d{4}\s\d{4}\s\d{4}\s\d{4})", text)
    vid_number = vid_match.group(1) if vid_match else ""

    # ---------------- VERTICAL DATE FIX ----------------
    compact_text = raw_text.replace("\n", "").replace(" ", "")

    issued_match = re.search(r"Aadhaarno\.issued:(\d{2}/\d{2}/\d{4})", compact_text)
    issued_date = issued_match.group(1) if issued_match else ""

    details_as_on_match = re.search(r"Details as on:\s*(\d{2}/\d{2}/\d{4})", text)
    details_as_on = details_as_on_match.group(1) if details_as_on_match else ""

    # ---------------- ADDRESS ----------------
    address_match = re.search(r"Address:\s*(.*?)Uttarakhand", text, re.DOTALL)
    address = "Address: " + address_match.group(1).strip() + " Uttarakhand 249407" if address_match else ""

    hindi_address_match = re.search(r"पता:\s*(.*?)249407", text, re.DOTALL)
    hindi_address = "पता:" + hindi_address_match.group(1).strip() + "249407" if hindi_address_match else ""

    # ---------------- IMAGE EXTRACTION ----------------
    photo_base64 = ""
    qr_base64 = ""

    for page in doc:
        images = page.get_images(full=True)

        for img in images:
            xref = img[0]
            base_image = doc.extract_image(xref)

            image_bytes = base_image["image"]
            width = base_image["width"]
            height = base_image["height"]

            image_base64 = base64.b64encode(image_bytes).decode("utf-8")

            # QR: square & smaller width
            if abs(width - height) < 50 and width < 250:
                if qr_base64 == "":
                    qr_base64 = image_base64
                    continue

            # PHOTO: tall rectangle
            if height > width and height > 120:
                if photo_base64 == "":
                    photo_base64 = image_base64
                    continue

    return {
        "name_english": name,
        "name_hindi": hindi_name,
        "father_english": father_name,
        "father_hindi": hindi_father,
        "dob": dob,
        "gender": gender,
        "aadhaar_number": aadhaar_number,
        "vid_number": vid_number,
        "issued_date": issued_date,
        "details_as_on": details_as_on,
        "address_english": address,
        "address_hindi": hindi_address,
        "photo_base64": photo_base64,
        "qr_base64": qr_base64
    }
