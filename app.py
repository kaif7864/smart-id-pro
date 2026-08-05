import os
import tempfile
import razorpay
from urllib.parse import quote_plus
from flask import Flask, request, send_file, send_from_directory, jsonify
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
from services.rc.rc_service import generate_rc_card
from services.swagger_docs import swagger_bp

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.register_blueprint(swagger_bp)


# CORS Configuration
CORS(app, resources={
    r"/*": {
        "origins": [
            "https://glowing-mousse-811953.netlify.app",
            "https://smart-id-pro.vercel.app",
            "http://localhost:3000",
            "http://localhost:5173",
            "https://smart-id-pro-red.vercel.app",
            "https://smart-id-pro-k4503wesf-ansaris-projects-4395478a.vercel.app",
            "https://smart-id-pro-git-main-ansaris-projects-4395478a.vercel.app",
            "https://print-ease.vercel.app",
            r"https://*.vercel.app",
            r"https://*.netlify.app",
            "*"
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

client = None
db = None
users_collection = None
prints_collection = None
transactions_collection = None

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
    db = client[db_name]
    users_collection = db['users']
    prints_collection = db['prints']
    transactions_collection = db['transactions']
    print("[SUCCESS] Connected to MongoDB Atlas")
except Exception as e:
    print(f"[ERROR] MongoDB Connection Error: {e}")

# Folder Setup
os.makedirs("uploads", exist_ok=True)
os.makedirs("output", exist_ok=True)
os.makedirs("assets", exist_ok=True)

@atexit.register
def close_db():
    if client:
        try:
            client.close()
        except Exception:
            pass

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

def check_db():
    global client, db, users_collection, prints_collection, transactions_collection
    if users_collection is None:
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000)
            db = client[db_name]
            users_collection = db['users']
            prints_collection = db['prints']
            transactions_collection = db['transactions']
        except Exception:
            pass

@app.route('/api/user/profile', methods=['GET'])
def get_user_profile():
    check_db()
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Email is required"}), 400

    if users_collection is None:
        return jsonify({"name": email.split("@")[0].upper(), "email": email, "offline": True}), 200

    try:
        user = users_collection.find_one({"email": email}, {"password": 0})
        if user:
            user['_id'] = str(user['_id'])
            return jsonify(user), 200
        return jsonify({"name": email.split("@")[0].upper(), "email": email}), 200
    except Exception as e:
        return jsonify({"name": email.split("@")[0].upper(), "email": email, "error": str(e)}), 200

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
# 💳 RAZORPAY - ONLY FOR WALLET RECHARGE
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

        params_dict = {
            'razorpay_order_id': data.get('razorpay_order_id'),
            'razorpay_payment_id': data.get('razorpay_payment_id'),
            'razorpay_signature': data.get('razorpay_signature')
        }
        razorpay_client.utility.verify_payment_signature(params_dict)

        # Wallet Update
        result = users_collection.update_one(
            {"email": email},
            {"$inc": {"wallet_balance": float(amount)}}
        )

        if result.matched_count == 0:
            return jsonify({"status": "error", "message": "User not found"}), 404

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
# HELPER - Wallet Deduction
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
# ID GENERATION ROUTES (Only Wallet)
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
            pdf_path, resource_type="raw", folder="generated_ids/pan",
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

        if not user_email:
            return jsonify({"error": "Email is required"}), 400

        if payment_method == "wallet":
            if not deduct_wallet(user_email, cost, service_type="Marksheet"):
                return jsonify({"error": "Insufficient balance"}), 400

        image_io = generate_marksheet_image(data)
        
        temp_filename = f"marksheet_{int(datetime.now().timestamp())}.jpg"
        temp_path = os.path.join(tempfile.gettempdir(), temp_filename)
        
        with open(temp_path, "wb") as f:
            f.write(image_io.getbuffer())

        upload_result = cloudinary.uploader.upload(temp_path, folder="generated_ids/marksheet")
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


@app.route("/extract-aadhaar", methods=["POST"])
def extract_aadhaar():
    temp_path = None
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400
           
        file = request.files["file"]
        password = request.form.get("password")

        if file.filename == '':
            return jsonify({"status": "error", "message": "No selected file"}), 400

        # Cross-platform temporary file
        temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        temp_path = temp_file.name
        temp_file.close()

        file.save(temp_path)

        # Extract details
        details = extract_aadhaar_details(temp_path, password)

        return jsonify(details)

    except Exception as e:
        print(f"❌ AADHAAR EXTRACT ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as cleanup_error:
                print(f"Cleanup warning: {cleanup_error}")


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
            "name": form_data.get("name_english", ""),
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

        pdf_io = generate_hindi_id_card(form_data, photo)

        if not pdf_io:
            return jsonify({"error": "Failed to generate Hindi ID Card"}), 500

        prints_collection.insert_one({
            "user_email": user_email,
            "id_number": form_data.get("idNumber", ""),
            "name": form_data.get("name", ""),
            "type": "HINDI_ID",
            "file_url": None,
            "date": datetime.now(),
            "status": "Printed"
        })

        return send_file(
            pdf_io,
            mimetype='application/pdf',
            as_attachment=True,
            download_name="Hindi_ID_Card.pdf"
        )

    except Exception as e:
        print(f"HINDI ID ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
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
    check_db()
    email = request.args.get('email')
    if users_collection is None:
        return jsonify({"balance": 0.0, "offline": True}), 200
    try:
        user = users_collection.find_one({"email": email})
        if user:
            return jsonify({"balance": user.get('wallet_balance', 0.0)}), 200
        return jsonify({"balance": 0.0}), 200
    except Exception:
        return jsonify({"balance": 0.0}), 200

@app.route('/api/wallet/transactions', methods=['GET'])
def get_transactions():
    check_db()
    if transactions_collection is None:
        return jsonify([]), 200
    try:
        user_email = request.args.get('email')
        txns = list(transactions_collection.find({"user_email": user_email}).sort("date", -1))
        for t in txns:
            t['_id'] = str(t['_id'])
        return jsonify(txns), 200
    except Exception:
        return jsonify([]), 200

@app.route('/api/prints', methods=['GET'])
def get_prints():
    check_db()
    if prints_collection is None:
        return jsonify([]), 200
    try:
        user_email = request.args.get('email')
        prints = list(prints_collection.find({"user_email": user_email}).sort("date", -1))
        for p in prints:
            p['_id'] = str(p['_id'])
        return jsonify(prints), 200
    except Exception:
        return jsonify([]), 200

@app.route('/api/stats', methods=['GET'])
def get_dashboard_stats():
    check_db()
    if prints_collection is None:
        return jsonify({"userToday": 0, "systemTotal": 0}), 200
    try:
        user_email = request.args.get('email')
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        user_today_count = prints_collection.count_documents({"user_email": user_email, "date": {"$gte": today}})
        total_system_count = prints_collection.count_documents({})
        return jsonify({"userToday": user_today_count, "systemTotal": total_system_count}), 200
    except Exception:
        return jsonify({"userToday": 0, "systemTotal": 0}), 200


@app.route('/api/rc/signatures/<filename>', methods=['GET'])
def get_rc_signature(filename):
    sign_dir = os.path.join(app.root_path, "assets", "rc", "sign")
    return send_from_directory(sign_dir, filename)

@app.route('/api/rc/generate', methods=['GET', 'POST'])
def handle_generate_rc():
    try:
        check_db()
        data = {}
        if request.method == 'POST':
            data = request.json or request.form.to_dict() or {}
        elif request.method == 'GET':
            data = request.args.to_dict() or {}

        # Fallback default sample data if no parameters provided (for browser testing)
        if not data:
            data = {
                "regn_no": "UK08AU0521",
                "reg_date": "30-Apr-2019",
                "validity": "29-Apr-2034",
                "chassis_no": "MBLHAR078JHL23636",
                "engine_no": "HA10AGJHL38423",
                "owner_name": "LALIT",
                "relation_name": "VINOD KUMAR",
                "address": "KANEWALI RAISINGH, RAISI, HARIDWAR, HARDWAR-UTTARAKHAND-247671",
                "owner_sr_no": "2",
                "fuel_used": "PETROL",
                "emission_norms": "BHARAT STAGE IV",
                "mfg_date": "04/2019",
                "wheel_base": "1238",
                "cc": "109.19",
                "cylinders": "1",
                "ulw": "109",
                "vehicle_class": "M-CYCLE/SCOOTER(2WN)",
                "maker_name": "HONDA MOTORCYCLE & SCOOTER (I) P LTD",
                "model_name": "ACTIVA 5G",
                "colour": "BLUE",
                "body_type": "SOLO",
                "seating": "2",
                "registering_authority": "HARIDWAR ARTO"
            }
        
        user_email = data.get('email')
        payment_method = data.get('payment_method', 'wallet')
        cost = 150.0

        if not user_email:
            return jsonify({"error": "User email is required"}), 400

        if payment_method == "wallet":
            if not deduct_wallet(user_email, cost, service_type="RC Card"):
                return jsonify({"error": f"Insufficient wallet balance. RC Card generation costs Rs. {int(cost)}."}), 400

        pdf_path = generate_rc_card(data)

        # Upload to Cloudinary and insert into prints_collection
        file_url = ""
        try:
            upload_result = cloudinary.uploader.upload(
                pdf_path,
                resource_type="raw",
                folder="generated_ids/rc",
                public_id=f"rc_{data.get('regn_no', 'card')}_{int(datetime.now().timestamp())}"
            )
            file_url = upload_result.get("secure_url", "")
        except Exception as cloud_err:
            print(f"[WARNING] Cloudinary upload warning for RC Card: {cloud_err}")

        if user_email and prints_collection is not None:
            try:
                prints_collection.insert_one({
                    "user_email": user_email,
                    "id_number": str(data.get("regn_no", "")).upper(),
                    "name": str(data.get("owner_name", "")).upper(),
                    "type": "RC CARD",
                    "file_url": file_url,
                    "date": datetime.now(),
                    "status": "Printed"
                })
            except Exception as db_err:
                print(f"[WARNING] DB print record insert warning for RC Card: {db_err}")

        return send_file(pdf_path, as_attachment=False, mimetype='application/pdf', download_name=f"rc_{data.get('regn_no', 'card')}.pdf")
    except Exception as e:
        print(f"RC GENERATION ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":

    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
