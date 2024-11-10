from flask import Flask, request, jsonify
from instamojo_wrapper import Instamojo
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import threading

load_dotenv()

# Initialize Instamojo API client
api = Instamojo(api_key=os.getenv("API_KEY"), auth_token=os.getenv("AUTH_TOKEN"))
app = Flask(__name__)

# Database connection initialized once and reused
client_read = MongoClient(
    f"mongodb+srv://{os.getenv('DB_USERNAME')}:{os.getenv('DB_PASSWORD')}@cluster0.rg4pbtc.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
)
user_db = client_read["ApnaDB"]["UserData"]

def close_db_connection():
    client_read.close()

class Database:
    @staticmethod
    def upload_data(data: dict):
        query = {'UniqueCode': data.get('UniqueCode')}
        update = {'$set': data}
        result = user_db.find_one_and_update(query, update, return_document=True)
        
        if not result:
            user_db.insert_one(data)

def create_new_payment():
    response = api.payment_request_create(
        amount=os.getenv("AMOUNT"),
        purpose=os.getenv("PURPOSE"),
        webhook=os.getenv("WEBHOOK"),
        allow_repeated_payments=False
    )
    if response['success']:
        return response['payment_request']['id']

def get_payment_status(payment_request_id):
    return api.payment_request_status(payment_request_id)

@app.route('/')
def home():
    return "Welcome to the Home Page!"

@app.route('/Apna-Browser/Initialize-Payment', methods=['POST'])
def initialize_payment():
    try:
        data = request.json
        payment_request_id = create_new_payment()
        
        if payment_request_id:
            data.update({"payment_request_id": payment_request_id})
            Database.upload_data(data)
            response_data = get_payment_status(payment_request_id)
            webhook = {
                'shorturl': response_data['payment_request']['shorturl'],
                "payment_request_id": response_data['payment_request']["id"]
            }
            return jsonify({"success": True, "message": webhook}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/Apna-Browser/Complete-Payment', methods=['POST'])
def complete_payment():
    try:
        data = request.form.to_dict()
        payment_request_id = data.get('payment_request_id')
        status = data.get('status')
        
        if status == 'Credit':
            query = {'payment_request_id': payment_request_id}
            update = {'$set': data}
            user_db.find_one_and_update(query, update)

        return jsonify({'status': 'received'}), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

# Ensure the database connection is closed properly on Vercel's function timeout
threading.Thread(target=close_db_connection).start()
