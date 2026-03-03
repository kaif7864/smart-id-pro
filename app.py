import os
import hmac
import hashlib
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
# --- IMPORT ADDED ---
from services.aadhar.aadhaar_maker import generate_aadhaar_card
# --------------------
import fitz

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

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
    # Collections
    users_collection = db['users']
    prints_collection = db['prints'] 
    transactions_collection = db['transactions']
    print("✅ Connected to MongoDB Atlas")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")

# Folder Setup
os.makedirs("uploads", exist_ok=True)
os.makedirs("output", exist_ok=True)
# --- Ensure Assets exists ---
os.makedirs("assets", exist_ok=True)
# ----------------------------

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

# ==========================================
# 💳 CASHFREE PAYMENT & WEBHOOK
# ==========================================

@app.route('/api/create-order', methods=['POST'])
def create_cashfree_order():
    try:
        data = request.json
        user_email = data.get('email')
        amount = data.get('amount')

        app_id = os.getenv("CASHFREE_APP_ID")
        secret_key = os.getenv("CASHFREE_SECRET_KEY")
        env = os.getenv("CASHFREE_ENV", "sandbox")
        base_url = "https://sandbox.cashfree.com/pg" if env == "sandbox" else "https://api.cashfree.com/pg"
        
        # Order ID generation (max 45 chars)
        order_id = f"ORD_{int(datetime.now().timestamp())}_{user_email.split('@')[0]}"[:45]
        
        order_payload = {
            "order_id": order_id,
            "order_amount": float(amount),
            "order_currency": "INR",
            "customer_details": {
                "customer_id": user_email.replace("@", "_").replace(".", "_"),
                "customer_email": user_email,
                "customer_phone": "9999999999"
            },
            "order_meta": {
                "notify_url": "https://your-domain.com/api/cashfree-webhook" # Replace with your live URL
            }
        }

        headers = {
            "x-client-id": app_id,
            "x-client-secret": secret_key,
            "x-api-version": "2023-08-01",
            "Content-Type": "application/json"
        }

        response = requests.post(f"{base_url}/orders", json=order_payload, headers=headers)
        return jsonify(response.json()), response.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/cashfree-webhook', methods=['POST'])
def cashfree_webhook():
    try:
        data = request.json
        # Note: In production, verify the Cashfree signature here for security!
        
        event_type = data.get('type')
        if event_type == "PAYMENT_SUCCESS_WEBHOOK":
            payment_data = data.get('data', {}).get('payment', {})
            order_data = data.get('data', {}).get('order', {})
            
            email = order_data.get('customer_details', {}).get('customer_email')
            amount = order_data.get('order_amount')

            # Update User Wallet Balance
            users_collection.update_one(
                {"email": email}, 
                {"$inc": {"wallet_balance": float(amount)}}
            )
            
            # Log Transaction
            transactions_collection.insert_one({
                "user_email": email,
                "type": "Wallet Recharge",
                "amount": float(amount),
                "order_id": order_data.get('order_id'),
                "date": datetime.now(),
                "description": "Online Recharge via Cashfree"
            })
            
        return jsonify({"status": "received"}), 200
    except Exception as e:
        print(f"Webhook Error: {e}")
        return jsonify({"error": str(e)}), 500

# ==========================================
# 📄 ID GENERATION ROUTES (PAN & MARKSHEET)
# ==========================================

@app.route("/generate-pan", methods=["POST"])
def pan_route():
    try:
        form_data = request.form
        user_email = form_data.get('email')
        payment_method = form_data.get('payment_method')
        cost = 10.0 

        if not user_email:
            return jsonify({"error": "Email is required"}), 400

        # Wallet Deduction
        if payment_method == "wallet":
            user = users_collection.find_one({"email": user_email})
            if not user or user.get('wallet_balance', 0) < cost:
                return jsonify({"error": "Insufficient wallet balance"}), 400
            
            users_collection.update_one({"email": user_email}, {"$inc": {"wallet_balance": -cost}})

        # Generate PAN
        pdf_path = generate_pan_card(form_data, request.files)
        
        # Logging
        users_collection.update_one({"email": user_email}, {"$inc": {"total_ids_generated": 1}})
        prints_collection.insert_one({
            "user_email": user_email,
            "id_number": form_data.get("id_number", "").upper(),
            "name": form_data.get("name", "").upper(),
            "type": "PAN",
            "date": datetime.now(),
            "status": "Printed"
        })
        transactions_collection.insert_one({
            "user_email": user_email,
            "type": f"PAN Gen ({payment_method})",
            "amount": -cost if payment_method == "wallet" else 0.0,
            "date": datetime.now(),
            "description": f"PAN for {form_data.get('name')}"
        })

        return send_file(pdf_path, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/generate-marksheet', methods=['POST'])
def get_marksheet():
    try:
        data = request.json
        user_email = data.get('email')
        payment_method = data.get('payment_method')
        cost = 15.0

        if not user_email:
            return jsonify({"error": "Email is required"}), 400

        # Wallet Deduction Logic
        if payment_method == "wallet":
            user = users_collection.find_one({"email": user_email})
            if not user or user.get('wallet_balance', 0) < cost:
                return jsonify({"error": "Insufficient balance"}), 400
            
            users_collection.update_one({"email": user_email}, {"$inc": {"wallet_balance": -cost}})

        # Generate Marksheet Image (from service)
        image_io = generate_marksheet_image(data)
        
        if image_io:
            # Update Logs
            users_collection.update_one({"email": user_email}, {"$inc": {"total_ids_generated": 1}})
            transactions_collection.insert_one({
                "user_email": user_email,
                "type": f"Marksheet Gen ({payment_method})",
                "amount": -cost if payment_method == "wallet" else 0.0,
                "date": datetime.now(),
                "description": f"Marksheet for {data.get('name')}"
            })
            
            return send_file(image_io, mimetype='image/jpeg', as_attachment=True, download_name=f"{data.get('name')}_marksheet.jpg")
        
        return jsonify({"error": "Template generation failed"}), 500
            
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
    
    return jsonify({
        "userToday": user_today_count,
        "systemTotal": total_system_count
    }), 200

# ==========================================
# 🆔 AADHAAR ROUTES
# ==========================================

@app.route("/extract-aadhaar", methods=["POST"])
def extract_aadhaar():
    try:
        file = request.files["pdf"]
        file.save("temp.pdf")

        details = extract_aadhaar_details("temp.pdf")

        print("Extracted:", details)  # 👈 Debug

        return jsonify(details)

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500

# --- ROUTE ADDED ---
@app.route("/generate-aadhaar", methods=["POST"])
def generate_aadhaar_route():
    try:
        form_data = request.form
        user_email = form_data.get('email')
        payment_method = form_data.get('payment_method')
        cost = 20.0 # Adjust cost

        # 👈 DEBUG: Backend mein data check karein
        print("Backend received form data:", form_data.to_dict())
        print("Backend received files:", request.files)

        if not user_email:
            return jsonify({"error": "Email is required"}), 400

        # Wallet Deduction
        if payment_method == "wallet":
            user = users_collection.find_one({"email": user_email})
            if not user or user.get('wallet_balance', 0) < cost:
                return jsonify({"error": "Insufficient wallet balance"}), 400
            
            users_collection.update_one({"email": user_email}, {"$inc": {"wallet_balance": -cost}})

        # Generate Aadhaar
        photo = request.files.get('photo')
        
        # 👈 VALIDATION: Photo check karein
        if not photo:
            print("ERROR: Photo file not received in request")
            return jsonify({"error": "Photo file is mandatory"}), 400

        pdf_path = generate_aadhaar_card(form_data, photo)
        
        # Logging
        users_collection.update_one({"email": user_email}, {"$inc": {"total_ids_generated": 1}})
        prints_collection.insert_one({
            "user_email": user_email,
            "id_number": form_data.get("aadhaar_number", ""),
            "name": form_data.get("name_english", "").upper(),
            "type": "AADHAAR",
            "date": datetime.now(),
            "status": "Printed"
        })
        transactions_collection.insert_one({
            "user_email": user_email,
            "type": f"Aadhaar Gen ({payment_method})",
            "amount": -cost if payment_method == "wallet" else 0.0,
            "date": datetime.now(),
            "description": f"Aadhaar for {form_data.get('name_english')}"
        })

        return send_file(pdf_path, as_attachment=True)
    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500
# --------------------

# ==========================================
# 🚀 SERVER START
# ==========================================
if __name__ == '__main__':
    app.run(debug=True, port=5000)