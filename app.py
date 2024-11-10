import os
from fastapi import FastAPI, Request, Form
from instamojo_wrapper import Instamojo
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Initialize Instamojo API
api = Instamojo(api_key=os.getenv("API_KEY"), auth_token=os.getenv("AUTH_TOKEN"))

# Initialize FastAPI app
app = FastAPI()

# Initialize MongoDB async client
class DataBase:
    def __init__(self):
        username = os.getenv("DB_USERNAME")
        password = os.getenv("DB_PASSWORD")
        self.client = AsyncIOMotorClient(
            f"mongodb+srv://{username}:{password}@cluster0.rg4pbtc.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
        )
        self.db = self.client["ApnaDB"]
        self.collection = self.db["UserData"]

    async def upload_data(self, data: dict):
        query = {'UniqueCode': data.get('UniqueCode')}
        update = {'$set': data}
        result = await self.collection.find_one_and_update(query, update, return_document=True)
        if not result:
            await self.collection.insert_one(data)

    async def close(self):
        self.client.close()

# Initialize single instance of the database class to reuse connections
db = DataBase()

# Create a new Payment
async def create_new_payment() -> str:
    response = api.payment_request_create(
        amount=os.getenv("AMOUNT"),
        purpose=os.getenv("PURPOSE"),
        webhook=os.getenv("WEBHOOK"),
        allow_repeated_payments=False
    )
    if response['success']:
        return response['payment_request']['id']

async def get_payment_status(payment_request_id: str):
    return api.payment_request_status(payment_request_id)

@app.get("/")
async def home():
    return {"message": "Welcome to the Home Page!"}

@app.post("/Apna-Browser/Initialize-Payment")
async def initialize_payment(request: Request):
    data = await request.json()
    payment_request_id = await create_new_payment()
    data.update({"payment_request_id": payment_request_id})
    await db.upload_data(data)

    response_data = await get_payment_status(payment_request_id)
    if response_data['success']:
        webhook_data = {
            'shorturl': response_data['payment_request']['shorturl'],
            "payment_request_id": response_data['payment_request']["id"]
        }
    else:
        webhook_data = {"error": "Payment request creation failed"}

    return {"success": True, "message": webhook_data}

@app.post("/Apna-Browser/Complete-Payment")
async def complete_payment(payment_id: str = Form(...), payment_request_id: str = Form(...), status: str = Form(...)):
    try:
        if status == 'Credit':
            query = {'payment_request_id': payment_request_id}
            update = {'$set': {"status": status, "payment_id": payment_id}}
            await db.collection.find_one_and_update(query, update)
        else:
            print(f"Payment {payment_id} failed or is pending.")

        return {"status": "received"}

    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return {"status": "error", "message": str(e)}
