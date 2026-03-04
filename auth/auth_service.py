import os
import datetime
import jwt  # pip install pyjwt
import bcrypt
from pymongo import MongoClient
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

# --- Database Connection ---
username = os.getenv("MONGO_USER")
password = os.getenv("MONGO_PASSWORD")
host = os.getenv("MONGO_HOST")
db_name = os.getenv("DB_NAME", "smartid_pro")
# SECRET_KEY ka use token sign karne ke liye hota hai
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key-123") 

encoded_password = quote_plus(password)
MONGO_URI = f"mongodb+srv://{username}:{encoded_password}@{host}/{db_name}?retryWrites=true&w=majority"
client = MongoClient(MONGO_URI)
db = client[db_name]
users_collection = db['users']

# --- Functions ---

def signup_user(data):
    if users_collection.find_one({"email": data['email']}):
        return {"status": "error", "message": "User already exists"}, 400

    hashed_pw = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
    
    new_user = {
        "name": data['name'],
        "email": data['email'],
        "phone": data['phone'],
        "password": hashed_pw,
        "wallet_balance": 0,
        "created_at": datetime.datetime.utcnow()
    }
    
    users_collection.insert_one(new_user)
    return {"status": "success", "message": "User created successfully"}, 201

def login_user(email, password):
    user = users_collection.find_one({"email": email})
    
    if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
        # 🛡️ JWT Token Generate Karein (2 Hours Expiry)
        # 'exp' field automatic logout handle karta hai
        token_payload = {
            "email": user['email'],
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2) 
        }
        
        token = jwt.encode(token_payload, SECRET_KEY, algorithm="HS256")

        return {
            "status": "success", 
            "token": token,  # 👈 Yeh token frontend ko jayega
            "user": {
                "name": user['name'],
                "email": user['email'],
                "balance": user.get('wallet_balance', 0)
            }
        }, 200
    
    return {"status": "error", "message": "Invalid email or password"}, 401