from doctest import debug
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import psycopg2
import base64
import hashlib
import os
app = FastAPI(title="Mailbox API" , debug=True)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
def connect_db():
    try:
        conn = psycopg2.connect(
            host="localhost",
            port="5432",
            database="vmail",
            user="postgres",
            password="postgres"
        )
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
#{SSHA512}I/2KCYnU5Z7HPpecuRq90LcY6immzXFfnR2xP6Bdhs5wRQmHHEB7FTwUNntuLOMJ7a3zUGz1S8yurg/WxfcJ9dKakE4mNE53
def verify_ssha512(stored_hash, password):
    # Remove the {SSHA512} prefix
    print("stored_hash",stored_hash)
    if stored_hash.startswith("{SSHA512}"):
        stored_hash = stored_hash[len("{SSHA512}"):]

    # Decode from base64
    decoded = base64.b64decode(stored_hash)

    hash_part = decoded[:64]  # SHA-512 output
    salt = decoded[64:]       # The rest is the salt
    print("hash_part",hash_part)
    print("salt",salt)
    # Recompute hash with the provided password and extracted salt
    new_hash = hashlib.sha512(password.encode('utf-8') + salt).digest()

    # Compare
    print("new_hash",new_hash == hash_part)
    
    return new_hash == hash_part
def hash_ssha512(password):
    try:
        salt = os.urandom(8)  # 8 bytes salt مثل iRedMail
        print("Generated salt:", salt.hex())
        # Recompute hash with the provided password and extracted salt
        new_hash = hashlib.sha512(password.encode('utf-8') + salt).digest()
        # Encode to base64
        encoded = base64.b64encode(new_hash + salt).decode('utf-8')
        return '{SSHA512}'+f'{encoded}'
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/login')
async def login(username :str , password :str):
    # admain 
    # normal user
    #select * from mailbox where username= 'ahmadjallab@ajcloudsolutions.com'; 
    #if user ahmadjallab@ajcloudsolutions.com with password compare with password col 
    # if found send aproval flag to request
    # if not found send error message 
    conn = connect_db()
    cursor =conn.cursor()
    cursor.execute(f"SELECT * FROM mailbox WHERE username = '{username}'")
    user = cursor.fetchone()
    print("user",user)
    cursor.close()
    conn.close()
    if user:
        if verify_ssha512(user[1], password):
            return {"message": "Login successful", "user": user}
        else:
            return HTTPException(status_code=401, detail="Invalid credentials password not correct")
    else:
        return HTTPException(status_code=401, detail="Invalid credentials username not correct")


def data_validation(user_data: dict) -> tuple[bool, str]:
    """
    Validate user registration data against mailbox table schema.
    Returns (is_valid: bool, error_message: str)
    """
    # Required fields with their expected types
    required_fields = {
        'username': str,
        'password': str,
        'name': str,
        'domain': str,
        'quota': int,
        'isadmin': int,
        'isglobaladmin': int,
        'active': int
    }

    # Check for missing required fields
    for field, field_type in required_fields.items():
        if field not in user_data:
            return False, f"Missing required field: {field}"
        
        # Check field type
        if not isinstance(user_data[field], field_type):
            return False, f"Invalid type for {field}. Expected {field_type.__name__}"

    # Validate email format
    if '@' not in user_data['username']:
        return False, "Username must be a valid email address"

    # Validate domain matches username domain
    if not user_data['username'].endswith('@' + user_data['domain']):
        return False, "Username domain must match the provided domain"

    # Validate quota (in MB)
    if not (0 <= user_data['quota'] <= 102400):  # 100GB max quota
        return False, "Quota must be between 0 and 102400 MB"

    # Validate boolean flags (0 or 1)
    for flag in ['isadmin', 'isglobaladmin', 'active']:
        if user_data[flag] not in (0, 1):
            return False, f"{flag} must be 0 or 1"

    # Validate password strength
    if len(user_data['password']) < 8:
        return False, "Password must be at least 8 characters long"

    # Additional validations for optional fields if provided
    if 'language' in user_data and not isinstance(user_data['language'], str):
        return False, "Language must be a string"

    if 'mailboxformat' in user_data and user_data['mailboxformat'] not in ('maildir', 'mdbox'):
        return False, "Invalid mailbox format. Must be 'maildir' or 'mdbox'"

    # If all validations pass
    return True, "Validation successful"

@app.post('/register')
async def register(user_data: dict):
    # Validate input data
    is_valid, message = data_validation(user_data)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)

    # Check authorization
    # if user_data.get('isadmin') == 1 and user_data.get('username') != 'postmaster@ajcloudsolutions.com':
    #     raise HTTPException(status_code=403, detail="Only postmaster can create admin users")
    print("user_data",user_data)
    conn = None
    cursor = None
    try:
        conn = connect_db()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute("SELECT username FROM mailbox WHERE username = %s", (user_data['username'],))
        if cursor.fetchone():
    
            print("Username already exists")
            raise Exception("Username already exists")

        # Set default values for required fields if not provided
        defaults = {
            'language': 'en_US',
            'mailboxformat': 'maildir',
            'mailboxfolder': 'Maildir',
            'storagebasedirectory': '/var/vmail',
            'storagenode': 'vmail1',
            'maildir': f"{user_data['domain']}/{user_data['username'][0]}/{user_data['username'][2]}/{user_data['username'][3]}/{user_data['name']}_ajwebBase/",
            'created': 'NOW()',
            'modified': 'NOW()',
            'expired': '2099-12-31 00:00:00'
        }
        print("defaults",defaults)
        # Merge user data with defaults
        user_data = {**defaults, **user_data}
        # hash password
        user_data['password'] =hash_ssha512(user_data['password'])
        # Build and execute the insert query
        columns = ', '.join(user_data.keys())
        placeholders = ', '.join(['%s'] * len(user_data))
        query = f"INSERT INTO mailbox ({columns}) VALUES ({placeholders})"
        
        cursor.execute(query, list(user_data.values()))
        conn.commit()
        
        return {"message": "User registered successfully"}

    except Exception as e:
        if conn:
            conn.rollback()
            print("Exception",type(e))
            print("Exception",e.__str__())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.get('/logout')
async def logout():
    pass 

@app.get('/get_user')
async def get_user(username :str):
    conn = connect_db()
    cursor =conn.cursor()
    cursor.execute(f"SELECT * FROM mailbox WHERE username = '{username}'")
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        return {"message": "User found", "user": user}
    else:
        return HTTPException(status_code=401, detail="Invalid credentials username not correct")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Service is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, reload=True)
