import os
import tempfile
import razorpay
from urllib.parse import quote_plus
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from auth.auth_service import login_user, signup_user
from services.pan_service import generate_pan_card
from services.marksheet_service import generate_marksheet_image
from dotenv import load_dotenv
from datetime import datetime
import atexit
from services.aadhar.aadhar_extract import extract_aadhaar_details
import cloudinary
import cloudinary.uploader
from services.aadhar.aadhaar_maker import generate_aadhaar_card
import fitz
from services.dom.dom import generate_hindi_id_card

# Load environment variables
load_dotenv()

app = Flask(__name__)

# CORS Configuration
CORS(app, resources={
    r"/*": {
        "origins": [
            "https://glowing-mousse-811953.netlify.app",
            "https://smart-id-pro.vercel.app",
            "http://localhost:3000",
            "https://smart-id-pro-red.vercel.app",
            "https://smart-id-pro-k4503wesf-ansaris-projects-4395478a.vercel.app",
            "https://smart-id-pro-git-main-ansaris-projects-4395478a.vercel.app",
            "https://print-ease.vercel.app",
            r"https://*.vercel.app",
            r"https://*.netlify.app",
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        "allow_headers": ["Content-Type", "Authorization", "Accept", "X-Requested-With", "Origin"],
        "supports_credentials": True,
        "max_age": 86400
    }
})

@app.route('/')
def home():
    return {"message": "Hello from Flask!"}

# Razorpay Client Setup
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# ==========================================
# DATABASE CONFIGURATION
# ==========================================
username = os.getenv("MONGO_USER")
password = os.getenv("MONGO_PASSWORD")
host = os.getenv("MONGO_HOST")
db_name = os.getenv("DB_NAME", "smartid_pro")

encoded_password = quote_plus(password)
MONGO_URI = f"mongodb+srv://{username}:{encoded_password}@{host}/{db_name}?retryWrites=true&w=majority"

try:
    client = MongoClient(MONGO_URI)
    db = client[db_name]
    users_collection = db['users']
    prints_collection = db['prints']
    transactions_collection = db['transactions']
    print("✅ Connected to MongoDB Atlas")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")

# Folder Setup
os.makedirs("uploads", exist_ok=True)
os.makedirs("output", exist_ok=True)
os.makedirs("assets", exist_ok=True)

@atexit.register
def close_db():
    client.close()

# ==========================================
# 🔐 AUTHENTICATION ROUTES
# ==========================================
@app.route('/api/signup', methods=['POST'])
def signup():
    return signup_user(request.json)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    return login_user(data.get('email'), data.get('password'))

@app.route('/api/user/profile', methods=['GET'])
def get_user_profile():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Email is required"}), 400
       
    user = users_collection.find_one({"email": email}, {"password": 0})
    if user:
        user['_id'] = str(user['_id'])
        return jsonify(user), 200
    return jsonify({"error": "User not found"}), 404

@app.route('/api/user/update', methods=['POST'])
def update_profile():
    data = request.json
    email = data.get('email')
    if not email:
        return jsonify({"error": "Email missing"}), 400
    
    result = users_collection.update_one(
        {"email": email},
        {"$set": {
            "name": data.get('name'),
            "phone": data.get('phone'),
            "avatar": data.get('avatar')
        }}
    )
    if result.modified_count > 0 or result.matched_count > 0:
        return jsonify({"message": "Profile updated successfully"}), 200
    return jsonify({"error": "Update failed"}), 400

# ==========================================
# 💳 RAZORPAY PAYMENT ROUTES (Only for Add Money)
# ==========================================
@app.route('/api/create-order', methods=['POST'])
def create_razorpay_order():
    try:
        data = request.json
        amount = int(float(data.get('amount', 0)) * 100)

        if amount <= 0:
            return jsonify({"error": "Amount must be greater than 0"}), 400

        order_data = {
            "amount": amount,
            "currency": "INR",
            "receipt": f"receipt_{int(datetime.now().timestamp())}",
            "payment_capture": 1
        }

        razorpay_order = razorpay_client.order.create(data=order_data)

        return jsonify({
            "id": razorpay_order["id"],
            "amount": razorpay_order["amount"],
            "currency": razorpay_order["currency"]
        }), 200

    except Exception as e:
        print(f"Create Order Error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/verify-payment', methods=['POST'])
def verify_payment():
    try:
        data = request.json
        email = data.get('email')
        amount = data.get('amount')

        if not email:
            return jsonify({"status": "error", "message": "Email is required"}), 400

        # Signature Verification
        params_dict = {
            'razorpay_order_id': data.get('razorpay_order_id'),
            'razorpay_payment_id': data.get('razorpay_payment_id'),
            'razorpay_signature': data.get('razorpay_signature')
        }
        razorpay_client.utility.verify_payment_signature(params_dict)

        # Wallet Update (Only for Add Money)
        result = users_collection.update_one(
            {"email": email},
            {"$inc": {"wallet_balance": float(amount)}}
        )

        if result.matched_count == 0:
            return jsonify({"status": "error", "message": "User not found"}), 404

        # Log Transaction
        transactions_collection.insert_one({
            "user_email": email,
            "type": "Wallet Recharge",
            "amount": float(amount),
            "order_id": data.get('razorpay_order_id'),
            "payment_id": data.get('razorpay_payment_id'),
            "date": datetime.now(),
            "description": "Online Recharge via Razorpay"
        })

        return jsonify({"status": "success", "message": "Wallet updated successfully"}), 200

    except razorpay.errors.SignatureVerificationError:
        return jsonify({"status": "error", "message": "Signature Verification Failed"}), 400
    except Exception as e:
        print(f"VERIFY ERROR: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================
# HELPER FUNCTION - Wallet Deduction
# ==========================================
def deduct_wallet(email, amount, service_type="Service"):
    user = users_collection.find_one({"email": email})
    if not user or user.get('wallet_balance', 0) < amount:
        return False

    users_collection.update_one(
        {"email": email},
        {"$inc": {"wallet_balance": -float(amount)}}
    )

    transactions_collection.insert_one({
        "user_email": email,
        "type": f"{service_type} Deduction",
        "amount": -float(amount),
        "date": datetime.now(),
        "description": f"Charges for generating {service_type}"
    })
    return True

# ==========================================
# 📄 ID GENERATION ROUTES (Only Wallet Payment)
# ==========================================
@app.route("/generate-pan", methods=["POST"])
def pan_route():
    try:
        form_data = request.form
        user_email = form_data.get('email')
        payment_method = form_data.get('payment_method')
        cost = 15

        if not user_email:
            return jsonify({"error": "Email is required"}), 400

        if payment_method == "wallet":
            if not deduct_wallet(user_email, cost, service_type="PAN Card"):
                return jsonify({"error": "Insufficient wallet balance"}), 400

        pdf_path = generate_pan_card(form_data, request.files)

        upload_result = cloudinary.uploader.upload(
            pdf_path,
            resource_type="raw",
            folder="generated_ids/pan",
            public_id=f"pan_{form_data.get('id_number')}_{int(datetime.now().timestamp())}"
        )
        file_url = upload_result.get("secure_url")

        prints_collection.insert_one({
            "user_email": user_email,
            "id_number": form_data.get("id_number", "").upper(),
            "name": form_data.get("name", "").upper(),
            "type": "PAN",
            "file_url": file_url,
            "date": datetime.now(),
            "status": "Printed"
        })

        return send_file(pdf_path, as_attachment=True)
    except Exception as e:
        print(f"PAN ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/generate-marksheet', methods=['POST'])
def get_marksheet():
    try:
        data = request.json
        user_email = data.get('email')
        payment_method = data.get('payment_method')
        cost = 65

        if not user_email: return jsonify({"error": "Email is required"}), 400

        if payment_method == "wallet":
            if not deduct_wallet(user_email, cost, service_type="Marksheet"):
                return jsonify({"error": "Insufficient balance"}), 400

        image_io = generate_marksheet_image(data)
        
        temp_filename = f"marksheet_{int(datetime.now().timestamp())}.jpg"
        temp_path = os.path.join(tempfile.gettempdir(), temp_filename)
        
        with open(temp_path, "wb") as f:
            f.write(image_io.getbuffer())

        upload_result = cloudinary.uploader.upload(
            temp_path,
            folder="generated_ids/marksheet"
        )
        file_url = upload_result.get("secure_url")
        os.remove(temp_path)

        prints_collection.insert_one({
            "user_email": user_email,
            "id_number": data.get("roll_no", "N/A"),
            "name": data.get("name", "").upper(),
            "type": "MARKSHEET",
            "file_url": file_url,
            "date": datetime.now(),
            "status": "Printed"
        })

        image_io.seek(0)
        return send_file(image_io, mimetype='image/jpeg', as_attachment=True, download_name="marksheet.jpg")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================


@app.route("/extract-aadhaar", methods=["POST"])
def extract_aadhaar():
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400
            
        file = request.files["file"]
        password = request.form.get("password")

        if file.filename == '':
            return jsonify({"status": "error", "message": "No selected file"}), 400

        temp_path = os.path.join("/tmp", "temp.pdf")
        file.save(temp_path)
        details = extract_aadhaar_details(temp_path, password)
        return jsonify(details)

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if os.path.exists("temp.pdf"):
            os.remove("temp.pdf")




@app.route("/generate-aadhaar", methods=["POST"])
def generate_aadhaar_route():
    try:
        form_data = request.form
        user_email = form_data.get('email')
        payment_method = form_data.get('payment_method')
        cost = 20

        if not user_email:
            return jsonify({"error": "Email is required"}), 400

        if payment_method == "wallet":
            if not deduct_wallet(user_email, cost, service_type="Aadhaar Card"):
                return jsonify({"error": "Insufficient wallet balance"}), 400

        photo = request.files.get('photo')
        temp_pdf_path = generate_aadhaar_card(form_data, photo)

        upload_result = cloudinary.uploader.upload(
            temp_pdf_path,
            resource_type="raw",
            folder="generated_ids/aadhaar",
            public_id=f"aadhaar_{form_data.get('aadhaar_number')}_{int(datetime.now().timestamp())}"
        )
        file_url = upload_result.get("secure_url")

        prints_collection.insert_one({
            "user_email": user_email,
            "id_number": form_data.get("aadhaar_number", "").replace(" ", ""),
            "name": form_data.get("name_english", "").upper(),
            "type": "AADHAAR",
            "file_url": file_url,
            "date": datetime.now(),
            "status": "Printed"
        })

        return send_file(temp_pdf_path, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/dom", methods=["POST"])
def hindi_id_route():
    try:
        form_data = request.form
        user_email = form_data.get('email')
        payment_method = form_data.get('payment_method')
        cost = 65

        if not user_email:
            return jsonify({"error": "Email is required"}), 400

        if payment_method == "wallet":
            if not deduct_wallet(user_email, cost, service_type="Hindi ID"):
                return jsonify({"error": "Insufficient wallet balance"}), 400

        photo = request.files.get('files')
        image_io = generate_hindi_id_card(form_data, photo)

        if not image_io:
            return jsonify({"error": "Failed to generate image"}), 500

        temp_filename = f"hindi_id_{int(datetime.now().timestamp())}.jpg"
        temp_path = os.path.join(tempfile.gettempdir(), temp_filename)
        with open(temp_path, "wb") as f:
            f.write(image_io.getbuffer())

        upload_result = cloudinary.uploader.upload(temp_path, folder="generated_ids/hindi_id")
        file_url = upload_result.get("secure_url")
        os.remove(temp_path)

        prints_collection.insert_one({
            "user_email": user_email,
            "id_number": form_data.get("idNumber", ""),
            "name": form_data.get("name", ""),
            "type": "HINDI_ID",
            "file_url": file_url,
            "date": datetime.now(),
            "status": "Printed"
        })

        image_io.seek(0)
        return send_file(image_io, mimetype='image/jpeg', as_attachment=True, download_name="ID_Card.jpg")
    except Exception as e:
        print(f"HINDI ID ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/download-again/<id_number>", methods=["GET"])
def download_again(id_number):
    try:
        record = prints_collection.find_one({"id_number": id_number})
        if record and "file_url" in record:
            return jsonify({"download_url": record["file_url"]})
        return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==========================================
# WALLET & STATS ROUTES
# ==========================================
@app.route('/api/wallet/balance', methods=['GET'])
def get_wallet_balance():
    email = request.args.get('email')
    user = users_collection.find_one({"email": email})
    if user:
        return jsonify({"balance": user.get('wallet_balance', 0.0)}), 200
    return jsonify({"balance": 0.0}), 200

@app.route('/api/wallet/transactions', methods=['GET'])
def get_transactions():
    user_email = request.args.get('email')
    txns = list(transactions_collection.find({"user_email": user_email}).sort("date", -1))
    for t in txns:
        t['_id'] = str(t['_id'])
    return jsonify(txns), 200

@app.route('/api/prints', methods=['GET'])
def get_prints():
    user_email = request.args.get('email')
    prints = list(prints_collection.find({"user_email": user_email}).sort("date", -1))
    for p in prints:
        p['_id'] = str(p['_id'])
    return jsonify(prints), 200

@app.route('/api/stats', methods=['GET'])
def get_dashboard_stats():
    user_email = request.args.get('email')
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    user_today_count = prints_collection.count_documents({"user_email": user_email, "date": {"$gte": today}})
    total_system_count = prints_collection.count_documents({})
    return jsonify({"userToday": user_today_count, "systemTotal": total_system_count}), 200





if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
