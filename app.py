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
import requests
from services.aadhar.aadhar_extract import extract_aadhaar_details
import cloudinary
import cloudinary.uploader 
from cloudinary.utils import cloudinary_url
from services.aadhar.aadhaar_maker import generate_aadhaar_card
import fitz
from services.dom.dom import generate_hindi_id_card

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Localhost aur Future Live URL dono ke liye
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
            # Agar chahiye to wildcard subdomain ke liye (Vercel/Netlify ke preview URLs ke liye bahut helpful)
            r"https://*.vercel.app",
            r"https://*.netlify.app",
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        "allow_headers": [
            "Content-Type",
            "Authorization",
            "Accept",
            "X-Requested-With",
            "Origin"
        ],
        "supports_credentials": True,  # agar future mein cookies/auth token bhejna ho
        "max_age": 86400               # preflight cache 24 hours
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
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"), 
    api_key = os.getenv("CLOUDINARY_API_KEY"), 
    api_secret = os.getenv("CLOUDINARY_API_SECRET"),
    secure = True
)

# ==========================================
# 1. DATABASE CONFIGURATION
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
    orders_collection = db['orders']  # For tracking payment orders
    
    # Create unique index on payment_id to prevent duplicates
    transactions_collection.create_index("payment_id", unique=False, sparse=True)
    orders_collection.create_index("razorpay_payment_id", unique=True, sparse=True)
    
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
        
    user = users_collection.find_one({"email": email}, {"password": 0}) # Password hide rakhein
    
    if user:
        # MongoDB ID ko string mein badlein
        user['_id'] = str(user['_id'])
        return jsonify(user), 200
    
    return jsonify({"error": "User not found"}), 404



@app.route('/api/user/update', methods=['POST'])
def update_profile():
    data = request.json
    email = data.get('email')
    
    if not email:
        return jsonify({"error": "Email missing"}), 400

    # DB mein update karein
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
# 💳 RAZORPAY PAYMENT & WEBHOOK
# ==========================================

@app.route('/api/create-order', methods=['POST'])
def create_razorpay_order():
    try:
        data = request.json
        amount = int(float(data.get('amount')) * 100)  # Amount in paise
        email = data.get('email')

        if amount <= 0:
            return jsonify({"error": "Amount must be greater than 0"}), 400

        order_data = {
            "amount": amount,
            "currency": "INR",
            "receipt": f"receipt_{int(datetime.now().timestamp())}",
            "payment_capture": 1
        }

        razorpay_order = razorpay_client.order.create(data=order_data)
        
        # ✅ Store order in DB for tracking
        orders_collection.insert_one({
            "razorpay_order_id": razorpay_order['id'],
            "user_email": email,
            "amount": float(data.get('amount')),
            "status": "pending",
            "created_at": datetime.now()
        })
        
        return jsonify(razorpay_order), 200

    except Exception as e:
        print(f"Order Creation Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/verify-payment', methods=['POST'])
def verify_payment():
    try:
        data = request.json
        payment_id = data.get('razorpay_payment_id')
        order_id = data.get('razorpay_order_id')
        email = data.get('email')
        payment_type = data.get('payment_type', 'service')  # 'wallet' or 'service' (default)
        
        # 🔍 DEBUG: Print what we're receiving
        print(f"✅ VERIFY-PAYMENT DEBUG:")
        print(f"   - payment_id: {payment_id}")
        print(f"   - payment_type: {payment_type}")
        print(f"   - email: {email}")
        print(f"   -service_name: {data.get('service_name', 'N/A')}")
        print(f"   - Full data: {data}")

        if not email:
            return jsonify({"status": "error", "message": "Email is required"}), 400

        # ✅ Check if this payment_id already processed (prevent double payment)
        existing_payment = transactions_collection.find_one({"payment_id": payment_id})
        if existing_payment:
            print(f"⚠️ Duplicate payment detected: {payment_id}")
            return jsonify({"status": "success", "message": "Payment already processed"}), 200

        # Razorpay signature verification
        params_dict = {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': data.get('razorpay_signature')
        }

        # Verify Signature - Yeh line error degi agar signature galat hua
        razorpay_client.utility.verify_payment_signature(params_dict)
        
        # ✅ FETCH ACTUAL AMOUNT FROM RAZORPAY (NOT from frontend!)
        try:
            payment_details = razorpay_client.payment.fetch(payment_id)
            actual_amount = payment_details['amount'] / 100  # Razorpay returns in paise
        except Exception as e:
            print(f"Error fetching payment details: {e}")
            actual_amount = data.get('amount', 0)  # Fallback to frontend amount
        
        # 🔍 DEBUG: Print wallet update decision
        print(f"   - actual_amount: {actual_amount}")
        print(f"   - Will update wallet: {payment_type == 'wallet'}")
        
        # ✅ SIRF WALLET RECHARGE MEIN PAISE ADD KARNA (not for service)
        if payment_type == 'wallet':
            print(f"   ✅ UPDATING WALLET for {email} by +{actual_amount}")
            result = users_collection.update_one(
                {"email": email}, 
                {"$inc": {"wallet_balance": float(actual_amount)}}
            )
            
            if result.matched_count == 0:
                return jsonify({"status": "error", "message": "User not found"}), 404
        else:
            print(f"   ❌ NOT updating wallet (payment_type={payment_type})")
        
        # ✅ Log Transaction with payment_id (unique tracking)
        transaction_type = "Wallet Recharge" if payment_type == 'wallet' else "Service Payment"
        transaction_description = "Online Recharge via Razorpay" if payment_type == 'wallet' else f"Payment for {data.get('service_name', 'ID Generation')}"
        
        # ✅ Amount को negative करो service payments के लिए (deduction दिखाने के लिए)
        transaction_amount = float(actual_amount) if payment_type == 'wallet' else -float(actual_amount)
        
        transactions_collection.insert_one({
            "user_email": email,
            "type": transaction_type,
            "amount": transaction_amount,  # Negative for service, positive for wallet
            "order_id": order_id,
            "payment_id": payment_id,  # For idempotency
            "payment_type": payment_type,
            "service_name": data.get('service_name', 'N/A'),
            "date": datetime.now(),
            "status": "completed",
            "description": transaction_description
        })

        # ✅ Track order status
        orders_collection.update_one(
            {"razorpay_order_id": order_id},
            {"$set": {
                "status": "completed",
                "payment_id": payment_id,
                "user_email": email,
                "amount": float(actual_amount),
                "payment_type": payment_type,
                "completed_at": datetime.now()
            }},
            upsert=True
        )

        message = "Payment verified and wallet updated" if payment_type == 'wallet' else "Payment verified successfully"
        print(f"   ✅ Response: {message}\n")
        return jsonify({"status": "success", "message": message}), 200
    except razorpay.errors.SignatureVerificationError:
        return jsonify({"status": "error", "message": "Signature Verification Failed"}), 400
    except Exception as e:
        print(f"VERIFY ERROR: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 400
    
@app.route('/api/razorpay-webhook', methods=['POST'])
def razorpay_webhook(): 
    # Webhook secret se signature verify karna chahiye (security ke liye)
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
    received_signature = request.headers.get('X-Razorpay-Signature')
    payload = request.data

    try:
        razorpay_client.utility.verify_webhook_signature(payload, received_signature, webhook_secret)
        event_data = request.json
        event = event_data.get('event')
        print(f"Webhook Event Received: {event}")

        # Handle payment.authorized and payment.completed events
        if event == 'payment.authorized' or event == 'payment.captured':
            payment_payload = event_data.get('payload', {}).get('payment', {})
            payment_id = payment_payload.get('entity', {}).get('id')
            
            # ✅ Check if already processed
            if transactions_collection.find_one({"payment_id": payment_id}):
                print(f"⚠️ Webhook: Payment {payment_id} already processed, skipping")
                return jsonify({"status": "success"}), 200
            
            print(f"✅ Webhook: Processing payment {payment_id}")

        return jsonify({"status": "success"}), 200
    except razorpay.errors.SignatureVerificationError:
        print("Webhook Signature Verification Failed")
        return jsonify({"status": "error", "message": "Signature Verification Failed"}), 400
    except Exception as e:
        print(f"Webhook Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 400
    
# Helper function
# Updated Helper function
def deduct_wallet(email, amount, service_type="Service"):
    user = users_collection.find_one({"email": email})
    
    # Check if user exists and has enough balance
    if not user or user.get('wallet_balance', 0) < amount:
        return False
    
    # 1. Deduct from User Collection
    users_collection.update_one(
        {"email": email}, 
        {"$inc": {"wallet_balance": -float(amount)}} # Minus sign ensures deduction
    )

    # 2. Log in Transactions Collection
    transactions_collection.insert_one({
        "user_email": email,
        "type": f"{service_type} Deduction",
        "amount": -float(amount), # Isko negative (-) rakhein taaki UI mein Red/Deduct dikhe
        "date": datetime.now(),
        "description": f"Charges for generating {service_type}"
    })

    return True

# ✅ NEW: Verify if Razorpay payment is completed
def verify_razorpay_payment(order_id):
    """Check if payment for this order_id is completed and verified"""
    order = orders_collection.find_one({"razorpay_order_id": order_id})
    
    if not order:
        return False, "Order not found"
    
    if order.get("status") == "completed":
        return True, "Payment verified"
    
    return False, "Payment not completed yet"
# ==========================================
# 📄 ID GENERATION ROUTES (PAN & MARKSHEET)
# ==========================================

@app.route("/generate-pan", methods=["POST"])
def pan_route():
    try:
        form_data = request.form
        user_email = form_data.get('email')
        payment_method = form_data.get('payment_method')
        order_id = form_data.get('razorpay_order_id')  # For online payment verification
        cost = 1

        if not user_email: 
            return jsonify({"error": "Email is required"}), 400

        # ✅ Verify payment based on method
        if payment_method == "wallet":
            if not deduct_wallet(user_email, cost, service_type="PAN Card"):
                return jsonify({"error": "Insufficient wallet balance"}), 400
        
        elif payment_method == "razorpay":
            # ✅ Check if Razorpay payment is verified
            is_verified, message = verify_razorpay_payment(order_id)
            if not is_verified:
                return jsonify({"error": f"Payment verification failed: {message}"}), 400

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
        order_id = data.get('razorpay_order_id')  # For online payment verification
        cost = 65

        if not user_email: return jsonify({"error": "Email is required"}), 400

        # ✅ Verify payment based on method
        if payment_method == "wallet":
            if not deduct_wallet(user_email, cost, service_type="Marksheet"):
                return jsonify({"error": "Insufficient balance"}), 400
        
        elif payment_method == "razorpay":
            # ✅ Check if Razorpay payment is verified
            is_verified, message = verify_razorpay_payment(order_id)
            if not is_verified:
                return jsonify({"error": f"Payment verification failed: {message}"}), 400

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
# 📊 WALLET & STATS ROUTES
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
    for t in txns: t['_id'] = str(t['_id'])
    return jsonify(txns), 200

@app.route('/api/prints', methods=['GET'])
def get_prints():
    user_email = request.args.get('email')
    prints = list(prints_collection.find({"user_email": user_email}).sort("date", -1))
    for p in prints: p['_id'] = str(p['_id'])
    return jsonify(prints), 200

@app.route('/api/stats', methods=['GET'])
def get_dashboard_stats():
    user_email = request.args.get('email')
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    user_today_count = prints_collection.count_documents({"user_email": user_email, "date": {"$gte": today}})
    total_system_count = prints_collection.count_documents({})
    return jsonify({"userToday": user_today_count, "systemTotal": total_system_count}), 200

# ==========================================
# 🆔 AADHAAR ROUTES
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
        order_id = form_data.get('razorpay_order_id')  # For online payment verification
        cost = 20

        if not user_email: return jsonify({"error": "Email is required"}), 400

        # ✅ Verify payment based on method
        if payment_method == "wallet":
            if not deduct_wallet(user_email, cost, service_type="Aadhaar Card"):
                return jsonify({"error": "Insufficient wallet balance"}), 400
        
        elif payment_method == "razorpay":
            # ✅ Check if Razorpay payment is verified
            is_verified, message = verify_razorpay_payment(order_id)
            if not is_verified:
                return jsonify({"error": f"Payment verification failed: {message}"}), 400

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
        # PAN Card ki tarah direct form data uthayein
        form_data = request.form 
        user_email = form_data.get('email')
        payment_method = form_data.get('payment_method')
        order_id = form_data.get('razorpay_order_id')  # For online payment verification
        cost = 65

        if not user_email: 
            return jsonify({"error": "Email is required"}), 400

        # ✅ Verify payment based on method
        if payment_method == "wallet":
            if not deduct_wallet(user_email, cost, service_type="Hindi ID"):
                return jsonify({"error": "Insufficient wallet balance"}), 400
        
        elif payment_method == "razorpay":
            # ✅ Check if Razorpay payment is verified
            is_verified, message = verify_razorpay_payment(order_id)
            if not is_verified:
                return jsonify({"error": f"Payment verification failed: {message}"}), 400

        # Files (Photo) handle karein
        # Frontend mein name 'files' hai toh yahan bhi 'files' rakhein
        photo = request.files.get('files') 
        
        # ID Generate karein (dom.py wala function call)
        # Hum pura form_data aur photo bhej rahe hain
        image_io = generate_hindi_id_card(form_data, photo)

        if not image_io:
            return jsonify({"error": "Failed to generate image"}), 500

        # Cloudinary Upload
        temp_filename = f"hindi_id_{int(datetime.now().timestamp())}.jpg"
        temp_path = os.path.join(tempfile.gettempdir(), temp_filename)
        with open(temp_path, "wb") as f:
            f.write(image_io.getbuffer())

        upload_result = cloudinary.uploader.upload(
            temp_path,
            folder="generated_ids/hindi_id"
        )
        file_url = upload_result.get("secure_url")
        os.remove(temp_path)

        # MongoDB Entry
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

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
