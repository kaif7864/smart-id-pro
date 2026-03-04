import pymupdf
import re
import base64

def extract_aadhaar_details(pdf_path, password=None):
    # 1. PDF Open karein
    doc = pymupdf.open(pdf_path)

    # 2. 🔐 Password Protection Handle Karein
    if doc.is_encrypted:
        if password:
            # Password se unlock karne ki koshish karein
            auth_status = doc.authenticate(password)
            if not auth_status > 0:
                return {"status": "error", "message": "Incorrect password. Failed to unlock PDF."}
        else:
            return {"status": "error", "message": "PDF is password protected. Please provide a password."}

    # 3. Text Extraction Start
    text = ""
    for page in doc:
        text += page.get_text()

    raw_text = text
    text_clean = text.replace("\n", " ")

    # ---------------- NAME EXTRACTION ----------------
    name_match = re.search(r"\n([A-Za-z\s]+)\nजन्म तिथि/DOB", text)
    name = name_match.group(1).strip() if name_match else ""

    hindi_name_match = re.search(r"\n([\u0900-\u097F\s]+)\n[A-Za-z\s]+\nजन्म तिथि/DOB", text)
    hindi_name = hindi_name_match.group(1).strip() if hindi_name_match else ""

    # ---------------- FATHER NAME EXTRACTION ----------------
    father_match = re.search(r"S/O:\s*([A-Za-z\s]+?),", text)
    father_name = father_match.group(1).strip() if father_match else ""

    hindi_father_match = re.search(r"आत्मज:\s*([\u0900-\u097F\s]+?),", text)
    hindi_father = hindi_father_match.group(1).strip() if hindi_father_match else ""

    # ---------------- DOB EXTRACTION ----------------
    dob_match = re.search(r"जन्म तिथि/DOB:\s*(\d{2}/\d{2}/\d{4})", text)
    dob = dob_match.group(1) if dob_match else ""

    # ---------------- GENDER EXTRACTION ----------------
    gender_match = re.search(r"(पुरुष/ MALE|महिला/ FEMALE|MALE|FEMALE)", text, re.IGNORECASE)
    gender_key = "M"
    if gender_match:
        g_raw = gender_match.group(1).upper()
        if "FEMALE" in g_raw or "महिला" in g_raw:
            gender_key = "F"

    # ---------------- AADHAAR NUMBER EXTRACTION ----------------
    aadhaar_numbers = re.findall(r"\b\d{4}\s\d{4}\s\d{4}\b", text)
    aadhaar_number = aadhaar_numbers[0] if aadhaar_numbers else ""

    # ---------------- VID EXTRACTION ----------------
    vid_match = re.search(r"VID\s*:\s*(\d{4}\s\d{4}\s\d{4}\s\d{4})", text)
    vid_number = vid_match.group(1) if vid_match else ""

    # ---------------- DATE FIXES ----------------
    compact_text = raw_text.replace("\n", "").replace(" ", "")
    issued_match = re.search(r"Aadhaarno\.issued:(\d{2}/\d{2}/\d{4})", compact_text)
    issued_date = issued_match.group(1) if issued_match else ""

    details_as_on_match = re.search(r"Details as on:\s*(\d{2}/\d{2}/\d{4})", text)
    details_as_on = details_as_on_match.group(1) if details_as_on_match else ""

    # ---------------- ADDRESS EXTRACTION ----------------
    address_match = re.search(r"Address:\s*(.*?)Uttarakhand", text, re.DOTALL)
    address = address_match.group(1).strip() + " Uttarakhand 249407" if address_match else ""

    hindi_address_match = re.search(r"पता:\s*(.*?)249407", text, re.DOTALL)
    hindi_address = "पता:\n" + hindi_address_match.group(1).strip() + "249407" if hindi_address_match else ""

    # ---------------- SMART PHOTO EXTRACTION (IMPROVED) ----------------
    photo_base64 = ""
    target_xref = None

    for page in doc:
        images = page.get_images(full=True)
        for img in images:
            xref = img[0]
            try:
                base_image = doc.extract_image(xref)
                width = base_image["width"]
                height = base_image["height"]
                aspect_ratio = width / height
                
                # Filter logic: Portrait ratio (not square QR)
                if 2000 < (width * height) < 100000:
                    if 0.6 < aspect_ratio < 1.0: 
                        target_xref = xref
                        break 
            except Exception:
                continue

    if target_xref:
        selected_img = doc.extract_image(target_xref)
        photo_base64 = base64.b64encode(selected_img["image"]).decode("utf-8")

    # ---------------- FINAL RETURN ----------------
    return {
        "status": "success",
        "name_english": name,
        "name_hindi": hindi_name,
        "father_english": father_name,
        "father_hindi": hindi_father,
        "dob": dob,
        "gender": gender_key,
        "aadhaar_number": aadhaar_number,
        "vid_number": vid_number,
        "issued_date": issued_date,
        "details_as_on": details_as_on,
        "address_english": address,
        "address_hindi": hindi_address,
        "photo_base64": photo_base64,
        "raw_text": raw_text
    }