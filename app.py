from quart import Quart, request, jsonify
from instamojo_wrapper import Instamojo
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

# Initialize the Instamojo API client
api = Instamojo(api_key=os.getenv("API_KEY"), auth_token=os.getenv("AUTH_TOKEN"))
app = Quart(__name__)

# Database connection pooling
class DataBase:
    def __init__(self):
        username = os.getenv("DB_USERNAME")
        password = os.getenv("DB_PASSWORD")
        uri = f"mongodb+srv://{username}:{password}@cluster0.rg4pbtc.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
        self.client = MongoClient(uri)
        self.user_db = self.client["ApnaDB"]["UserData"]

    async def upload_data(self, data: dict):
        query = {'UniqueCode': data.get('UniqueCode')}
        update = {'$set': data}
        result = await self.user_db.find_one_and_update(query, update, upsert=True)
        return result

db_instance = DataBase()

# Create a new Payment
async def create_new_payment() -> str:
    response = await asyncio.to_thread(api.payment_request_create,
                                       amount=os.getenv("AMOUNT"),
                                       purpose=os.getenv("PURPOSE"),
                                       webhook=os.getenv("WEBHOOK"),
                                       allow_repeated_payments=False)
    if response['success']:
        return response['payment_request']['id']

async def get_payment_status(payment_request_id):
    response = await asyncio.to_thread(api.payment_request_status, payment_request_id)
    return response

@app.route('/')
async def home():
    return "Welcome to the Home Page!"

@app.route('/Apna-Browser/Initialize-Payment', methods=['POST'])
async def initialize_payment():
    data = await request.get_json()
    payment_request_id = await create_new_payment()

    if payment_request_id:
        data.update({"payment_request_id": payment_request_id})
        await db_instance.upload_data(data)
        response_data = await get_payment_status(payment_request_id)

        if response_data['success']:
            webhook_data = {'shorturl': response_data['payment_request']['shorturl'], 
                            "payment_request_id": response_data['payment_request']["id"]}
            return jsonify({"success": True, "message": webhook_data}), 200

    return jsonify({"success": False, "message": "Payment initialization failed"}), 500

@app.route('/Apna-Browser/Complete-Payment', methods=['POST'])
async def complete_payment():
    try:
        data = await request.form.to_dict()
        payment_id = data.get('payment_id')
        payment_request_id = data.get('payment_request_id')
        status = data.get('status')

        if status == 'Credit':
            await db_instance.upload_data(data)
        else:
            print(f"Payment {payment_id} failed or is pending.")

        return jsonify({'status': 'received'}), 200

    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=False)
