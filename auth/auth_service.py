import os
from pymongo import MongoClient
from flask import jsonify
import bcrypt
from urllib.parse import quote_plus
from dotenv import load_dotenv

# 1. Sabse pehle .env load karein
load_dotenv()

# 2. Database credentials read karein
username = os.getenv("MONGO_USER")
password = os.getenv("MONGO_PASSWORD")
host = os.getenv("MONGO_HOST")
db_name = os.getenv("DB_NAME", "smartid_pro")

# 3. 🔐 Password ko encode karein (urllib.parse.quote_plus)
encoded_password = quote_plus(password)

# 4. Connection string banayein
MONGO_URI = f"mongodb+srv://{username}:{encoded_password}@{host}/{db_name}?retryWrites=true&w=majority"
client = MongoClient(MONGO_URI)
db = client[db_name]
users_collection = db['users']

# ... baki functions (signup_user, login_user) same rahenge ...

def signup_user(data):
    # Check if user exists
    if users_collection.find_one({"email": data['email']}):
        return {"status": "error", "message": "User already exists"}, 400

    # Hash the password
    hashed_pw = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
    
    new_user = {
        "name": data['name'],
        "email": data['email'],
        "phone": data['phone'],
        "password": hashed_pw,
        "wallet_balance": 0  # Initial balance
    }
    
    users_collection.insert_one(new_user)
    return {"status": "success", "message": "User created successfully"}, 201

def login_user(email, password):
    user = users_collection.find_one({"email": email})
    
    if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
        return {
            "status": "success", 
            "user": {
                "name": user['name'],
                "email": user['email'],
                "balance": user.get('wallet_balance', 0)
            }
        }, 200
    
    return {"status": "error", "message": "Invalid email or password"}, 401