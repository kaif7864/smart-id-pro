from flask import Blueprint, jsonify, render_template_string

swagger_bp = Blueprint('swagger_bp', __name__)

OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Smart ID Pro API Documentation",
        "description": "Comprehensive REST API documentation for Smart ID Pro Backend Services. Supports Authentication, Wallet Recharges via Razorpay, ID & Document Generation (Aadhaar, PAN, Marksheet, Hindi Domicile, Vehicle RC), and History Tracking.",
        "version": "1.0.0",
        "contact": {
            "name": "Smart ID Pro Technical Support",
            "email": "support@smartidpro.com"
        }
    },
    "servers": [
        {
            "url": "http://localhost:5000",
            "description": "Local Development Server"
        }
    ],
    "tags": [
        {
            "name": "Authentication & User Profile",
            "description": "Endpoints for user registration, authentication, profile fetching, and updates."
        },
        {
            "name": "Wallet & Payments",
            "description": "Razorpay order creation, payment signature verification, balance checks, and transaction logs."
        },
        {
            "name": "Document & ID Card Generation",
            "description": "API endpoints to generate Aadhaar, PAN, Marksheet, Hindi Domicile, and Vehicle RC cards."
        },
        {
            "name": "Prints & Dashboard History",
            "description": "Endpoints to view print history, dashboard stats, and re-download generated files."
        }
    ],
    "paths": {
        "/": {
            "get": {
                "tags": ["Authentication & User Profile"],
                "summary": "API Health Check",
                "description": "Returns basic API status message.",
                "responses": {
                    "200": {
                        "description": "API is running successfully",
                        "content": {
                            "application/json": {
                                "example": {"message": "Hello from Flask!"}
                            }
                        }
                    }
                }
            }
        },
        "/api/signup": {
            "post": {
                "tags": ["Authentication & User Profile"],
                "summary": "User Signup / Registration",
                "description": "Registers a new user account.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name", "email", "password"],
                                "properties": {
                                    "name": {"type": "string", "example": "Kaif Ansari"},
                                    "email": {"type": "string", "format": "email", "example": "kaif@example.com"},
                                    "password": {"type": "string", "example": "password123"},
                                    "phone": {"type": "string", "example": "9876543210"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "User created successfully",
                        "content": {
                            "application/json": {
                                "example": {"message": "User registered successfully", "status": "success"}
                            }
                        }
                    },
                    "400": {
                        "description": "User already exists or missing parameters"
                    }
                }
            }
        },
        "/api/login": {
            "post": {
                "tags": ["Authentication & User Profile"],
                "summary": "User Login",
                "description": "Authenticates user credentials and returns user details.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["email", "password"],
                                "properties": {
                                    "email": {"type": "string", "format": "email", "example": "kaif@example.com"},
                                    "password": {"type": "string", "example": "password123"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Login successful",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "user": {
                                        "name": "Kaif Ansari",
                                        "email": "kaif@example.com",
                                        "wallet_balance": 150.0
                                    }
                                }
                            }
                        }
                    },
                    "400": {"description": "Invalid credentials or missing fields"}
                }
            }
        },
        "/api/user/profile": {
            "get": {
                "tags": ["Authentication & User Profile"],
                "summary": "Get User Profile",
                "description": "Fetches user profile details by email address.",
                "parameters": [
                    {
                        "name": "email",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string", "format": "email"},
                        "example": "kaif@example.com"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "User profile object",
                        "content": {
                            "application/json": {
                                "example": {
                                    "_id": "648f123456789",
                                    "name": "Kaif Ansari",
                                    "email": "kaif@example.com",
                                    "phone": "9876543210",
                                    "wallet_balance": 150.0
                                }
                            }
                        }
                    },
                    "400": {"description": "Email parameter is required"},
                    "404": {"description": "User not found"}
                }
            }
        },
        "/api/user/update": {
            "post": {
                "tags": ["Authentication & User Profile"],
                "summary": "Update Profile Details",
                "description": "Updates user's name, phone, or avatar.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["email"],
                                "properties": {
                                    "email": {"type": "string", "format": "email", "example": "kaif@example.com"},
                                    "name": {"type": "string", "example": "Kaif Ansari Updated"},
                                    "phone": {"type": "string", "example": "9998887770"},
                                    "avatar": {"type": "string", "example": "https://example.com/avatar.jpg"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Profile updated successfully",
                        "content": {
                            "application/json": {
                                "example": {"message": "Profile updated successfully"}
                            }
                        }
                    },
                    "400": {"description": "Email missing or update failed"}
                }
            }
        },
        "/api/create-order": {
            "post": {
                "tags": ["Wallet & Payments"],
                "summary": "Create Razorpay Recharge Order",
                "description": "Creates a Razorpay order for online wallet balance recharge.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["amount"],
                                "properties": {
                                    "amount": {"type": "number", "example": 100, "description": "Amount in INR to add to wallet"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Razorpay order created successfully",
                        "content": {
                            "application/json": {
                                "example": {
                                    "id": "order_M1234567890",
                                    "amount": 10000,
                                    "currency": "INR"
                                }
                            }
                        }
                    },
                    "400": {"description": "Amount must be greater than 0"}
                }
            }
        },
        "/api/verify-payment": {
            "post": {
                "tags": ["Wallet & Payments"],
                "summary": "Verify Razorpay Payment & Add Balance",
                "description": "Verifies payment signature and credits the specified amount to user's wallet.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["email", "amount", "razorpay_order_id", "razorpay_payment_id", "razorpay_signature"],
                                "properties": {
                                    "email": {"type": "string", "format": "email", "example": "kaif@example.com"},
                                    "amount": {"type": "number", "example": 100},
                                    "razorpay_order_id": {"type": "string", "example": "order_M1234567890"},
                                    "razorpay_payment_id": {"type": "string", "example": "pay_P1234567890"},
                                    "razorpay_signature": {"type": "string", "example": "a1b2c3d4e5f6..."}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Payment verified and wallet credited",
                        "content": {
                            "application/json": {
                                "example": {"status": "success", "message": "Wallet updated successfully"}
                            }
                        }
                    },
                    "400": {"description": "Signature verification failed or missing params"}
                }
            }
        },
        "/api/wallet/balance": {
            "get": {
                "tags": ["Wallet & Payments"],
                "summary": "Get Wallet Balance",
                "description": "Returns current wallet balance for the user.",
                "parameters": [
                    {
                        "name": "email",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string", "format": "email"},
                        "example": "kaif@example.com"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Wallet balance response",
                        "content": {
                            "application/json": {
                                "example": {"balance": 150.0}
                            }
                        }
                    }
                }
            }
        },
        "/api/wallet/transactions": {
            "get": {
                "tags": ["Wallet & Payments"],
                "summary": "Get Transaction Logs",
                "description": "Returns list of wallet recharge and service deduction logs.",
                "parameters": [
                    {
                        "name": "email",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string", "format": "email"},
                        "example": "kaif@example.com"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "List of transactions",
                        "content": {
                            "application/json": {
                                "example": [
                                    {
                                        "_id": "648f987654",
                                        "user_email": "kaif@example.com",
                                        "type": "Wallet Recharge",
                                        "amount": 100.0,
                                        "date": "2026-08-04T00:00:00Z",
                                        "description": "Online Recharge via Razorpay"
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        },
        "/generate-pan": {
            "post": {
                "tags": ["Document & ID Card Generation"],
                "summary": "Generate PAN Card PDF (Deducts ₹15)",
                "description": "Generates printable PAN Card PDF using user data and uploaded photo & signature.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "required": ["email", "id_number", "name", "father_name", "dob", "photo", "sign"],
                                "properties": {
                                    "email": {"type": "string", "format": "email", "example": "kaif@example.com"},
                                    "payment_method": {"type": "string", "example": "wallet"},
                                    "id_number": {"type": "string", "example": "ABCDE1234F"},
                                    "name": {"type": "string", "example": "KAIF ANSARI"},
                                    "father_name": {"type": "string", "example": "RAFIQ ANSARI"},
                                    "dob": {"type": "string", "example": "1998-05-15"},
                                    "photo": {"type": "string", "format": "binary", "description": "Passport photo image"},
                                    "sign": {"type": "string", "format": "binary", "description": "Signature image"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Generated PAN Card PDF File",
                        "content": {
                            "application/pdf": {}
                        }
                    },
                    "400": {"description": "Insufficient wallet balance or missing fields"}
                }
            }
        },
        "/generate-marksheet": {
            "post": {
                "tags": ["Document & ID Card Generation"],
                "summary": "Generate High School Marksheet Image (Deducts ₹65)",
                "description": "Generates High School Marksheet image based on provided roll number and details.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["email", "roll_no", "name"],
                                "properties": {
                                    "email": {"type": "string", "format": "email", "example": "kaif@example.com"},
                                    "payment_method": {"type": "string", "example": "wallet"},
                                    "roll_no": {"type": "string", "example": "0415836"},
                                    "name": {"type": "string", "example": "KAIF ANSARI"},
                                    "father_name": {"type": "string", "example": "RAFIQ ANSARI"},
                                    "dob": {"type": "string", "example": "2002-04-10"},
                                    "school_name": {"type": "string", "example": "B H S INTER COLLEGE SAHARANPUR"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Generated Marksheet Image File",
                        "content": {
                            "image/jpeg": {}
                        }
                    },
                    "400": {"description": "Insufficient balance or invalid payload"}
                }
            }
        },
        "/extract-aadhaar": {
            "post": {
                "tags": ["Document & ID Card Generation"],
                "summary": "Extract Encrypted Aadhaar PDF Data",
                "description": "Uploads encrypted e-Aadhaar PDF and password, extracts demographic details automatically.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "required": ["file", "password"],
                                "properties": {
                                    "file": {"type": "string", "format": "binary", "description": "Encrypted e-Aadhaar PDF file"},
                                    "password": {"type": "string", "example": "KAIF1998", "description": "PDF Password (First 4 caps of name + Birth Year)"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Extracted Aadhaar Data",
                        "content": {
                            "application/json": {
                                "example": {
                                    "name_english": "KAIF ANSARI",
                                    "aadhaar_number": "1234 5678 9012",
                                    "dob": "15/05/1998",
                                    "gender": "MALE",
                                    "address": "HARIDWAR, UTTARAKHAND-247671"
                                }
                            }
                        }
                    },
                    "400": {"description": "No file uploaded or invalid PDF password"}
                }
            }
        },
        "/generate-aadhaar": {
            "post": {
                "tags": ["Document & ID Card Generation"],
                "summary": "Generate Aadhaar Smart Card PDF (Deducts ₹20)",
                "description": "Generates official printable Aadhaar Card PDF layout.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "required": ["email", "aadhaar_number", "name_english", "dob", "gender", "address_english"],
                                "properties": {
                                    "email": {"type": "string", "format": "email", "example": "kaif@example.com"},
                                    "payment_method": {"type": "string", "example": "wallet"},
                                    "aadhaar_number": {"type": "string", "example": "1234 5678 9012"},
                                    "name_english": {"type": "string", "example": "KAIF ANSARI"},
                                    "name_hindi": {"type": "string", "example": "कैफ अंसारी"},
                                    "dob": {"type": "string", "example": "15/05/1998"},
                                    "gender": {"type": "string", "example": "MALE"},
                                    "address_english": {"type": "string", "example": "HARIDWAR, UTTARAKHAND"},
                                    "address_hindi": {"type": "string", "example": "हरिद्वार, उत्तराखंड"},
                                    "photo": {"type": "string", "format": "binary"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Generated Aadhaar Card PDF File",
                        "content": {
                            "application/pdf": {}
                        }
                    }
                }
            }
        },
        "/dom": {
            "post": {
                "tags": ["Document & ID Card Generation"],
                "summary": "Generate Hindi Domicile ID Card (Deducts ₹65)",
                "description": "Generates Hindi Domicile / Residence Certificate ID Card PDF.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "required": ["email", "idNumber", "name"],
                                "properties": {
                                    "email": {"type": "string", "format": "email", "example": "kaif@example.com"},
                                    "payment_method": {"type": "string", "example": "wallet"},
                                    "idNumber": {"type": "string", "example": "UK1234567"},
                                    "name": {"type": "string", "example": "KAIF ANSARI"},
                                    "files": {"type": "string", "format": "binary"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Generated Hindi ID Card PDF File",
                        "content": {"application/pdf": {}}
                    }
                }
            }
        },
        "/api/rc/generate": {
            "get": {
                "tags": ["Document & ID Card Generation"],
                "summary": "Preview Default RC Smart Card PDF (Form 23 & 23A)",
                "description": "Direct browser GET endpoint to view/preview default sample RC Card PDF.",
                "responses": {
                    "200": {
                        "description": "Sample RC Card PDF File",
                        "content": {"application/pdf": {}}
                    }
                }
            },
            "post": {
                "tags": ["Document & ID Card Generation"],
                "summary": "Generate Vehicle RC Smart Card PDF (Form 23 & 23A)",
                "description": "Generates high-resolution front & back Vehicle Registration Certificate smart card with dynamic 2D QR code.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["regn_no", "chassis_no", "engine_no", "owner_name"],
                                "properties": {
                                    "regn_no": {"type": "string", "example": "UK08AU0521"},
                                    "reg_date": {"type": "string", "example": "30-Apr-2019"},
                                    "validity": {"type": "string", "example": "29-Apr-2034"},
                                    "chassis_no": {"type": "string", "example": "MBLHAR078JHL23636"},
                                    "engine_no": {"type": "string", "example": "HA10AGJHL38423"},
                                    "owner_name": {"type": "string", "example": "LALIT"},
                                    "relation_name": {"type": "string", "example": "VINOD KUMAR"},
                                    "address": {"type": "string", "example": "KANEWALI RAISINGH, RAISI, HARIDWAR, HARDWAR-UTTARAKHAND-247671"},
                                    "owner_sr_no": {"type": "string", "example": "2"},
                                    "fuel_used": {"type": "string", "example": "PETROL"},
                                    "emission_norms": {"type": "string", "example": "BHARAT STAGE IV"},
                                    "mfg_date": {"type": "string", "example": "04/2019"},
                                    "wheel_base": {"type": "string", "example": "1238"},
                                    "cc": {"type": "string", "example": "109.19"},
                                    "cylinders": {"type": "string", "example": "1"},
                                    "ulw": {"type": "string", "example": "109"},
                                    "vehicle_class": {"type": "string", "example": "M-CYCLE/SCOOTER(2WN)"},
                                    "maker_name": {"type": "string", "example": "HONDA MOTORCYCLE & SCOOTER (I) P LTD"},
                                    "model_name": {"type": "string", "example": "ACTIVA 5G"},
                                    "colour": {"type": "string", "example": "BLUE"},
                                    "body_type": {"type": "string", "example": "SOLO"},
                                    "seating": {"type": "string", "example": "2"},
                                    "registering_authority": {"type": "string", "example": "HARIDWAR ARTO"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Generated Vehicle RC Card PDF File",
                        "content": {"application/pdf": {}}
                    }
                }
            }
        },
        "/api/download-again/{id_number}": {
            "get": {
                "tags": ["Prints & Dashboard History"],
                "summary": "Re-download Generated Document",
                "description": "Retrieves Cloudinary download URL for a previously generated document by ID / Document number.",
                "parameters": [
                    {
                        "name": "id_number",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "example": "UK08AU0521"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Cloudinary file URL",
                        "content": {
                            "application/json": {
                                "example": {"download_url": "https://res.cloudinary.com/..."}
                            }
                        }
                    },
                    "404": {"description": "File record not found"}
                }
            }
        },
        "/api/prints": {
            "get": {
                "tags": ["Prints & Dashboard History"],
                "summary": "User Print History",
                "description": "Lists all documents printed by the user.",
                "parameters": [
                    {
                        "name": "email",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string", "format": "email"},
                        "example": "kaif@example.com"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "List of user prints",
                        "content": {
                            "application/json": {
                                "example": [
                                    {
                                        "_id": "648f1234",
                                        "user_email": "kaif@example.com",
                                        "id_number": "UK08AU0521",
                                        "name": "LALIT",
                                        "type": "RC",
                                        "file_url": "https://res.cloudinary.com/...",
                                        "status": "Printed"
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        },
        "/api/stats": {
            "get": {
                "tags": ["Prints & Dashboard History"],
                "summary": "Dashboard Statistics",
                "description": "Returns counts for today's user prints and total system prints.",
                "parameters": [
                    {
                        "name": "email",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string", "format": "email"},
                        "example": "kaif@example.com"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Dashboard statistics",
                        "content": {
                            "application/json": {
                                "example": {"userToday": 5, "systemTotal": 142}
                            }
                        }
                    }
                }
            }
        }
    }
}

SWAGGER_UI_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Smart ID Pro API - Swagger Documentation</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
    <link rel="icon" type="image/png" href="https://unpkg.com/swagger-ui-dist@5/favicon-32x32.png" sizes="32x32" />
    <style>
        html { box-sizing: border-box; overflow: -moz-scrollbars-vertical; overflow-y: scroll; }
        *, *:before, *:after { box-sizing: inherit; }
        body { margin: 0; background: #fafafa; }
        .swagger-ui .topbar { background-color: #1a252f; padding: 10px 0; }
        .swagger-ui .topbar .topbar-wrapper img { content: url('https://smart-id-pro.vercel.app/logo.png'); height: 40px; }
        .custom-header { background: #2c3e50; color: white; padding: 15px 30px; display: flex; align-items: center; justify-content: space-between; }
        .custom-header h1 { margin: 0; font-family: 'Segoe UI', sans-serif; font-size: 24px; font-weight: 600; }
        .custom-header span { background: #27ae60; padding: 5px 12px; border-radius: 20px; font-size: 13px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="custom-header">
        <h1>Smart ID Pro - OpenAPI Swagger Docs</h1>
        <span>v1.0.0 Live</span>
    </div>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js" charset="UTF-8"></script>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js" charset="UTF-8"></script>
    <script>
        window.onload = function() {
            window.ui = SwaggerUIBundle({
                url: "/swagger.json",
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "StandaloneLayout"
            });
        };
    </script>
</body>
</html>
"""

@swagger_bp.route('/swagger.json', methods=['GET'])
def get_swagger_json():
    return jsonify(OPENAPI_SPEC)

@swagger_bp.route('/docs', methods=['GET'])
@swagger_bp.route('/swagger', methods=['GET'])
@swagger_bp.route('/apidocs', methods=['GET'])
def render_swagger_ui():
    return render_template_string(SWAGGER_UI_HTML)
