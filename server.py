"""
	Steps to run the backend server:
	1. Activate the virtual environment: venv\Scripts\activate
	2. Run the server: uvicorn server:app --host 0.0.0.0 --port 8000 --reload
	3. Access the API endpoints: http://localhost:8000/docs
"""
from fastapi import FastAPI, HTTPException, status, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from pymongo import MongoClient
from pymongo.errors import PyMongoError, DuplicateKeyError
from bson import ObjectId
import os
from dotenv import load_dotenv

# from datetime import datetime

load_dotenv()

# --- MongoDB connection ---
client = MongoClient(os.environ["MONGODB_URI"]) # MongoDB user URI
db = client["cs3720db"] # Database name
collection = db["sculptures"] # Collection name

# --- FastAPI app setup ---
app = FastAPI()

# Optional: enable CORS if you’ll connect from React/React Native
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"], # or specify your frontend domain
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# --- Minimal Pydantic model ---
class Sculpture(BaseModel):
	name: str
	price: float
	description: str
	imageUrl: str

# --- Validated Pydantic model ---
class SculptureValidated(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid"
    )
    name: str = Field(min_length=1)
    price: float = Field(ge=0, allow_inf_nan=False)
    description: str = Field(min_length=1)
    imageUrl: HttpUrl


# --- Root endpoint ---
@app.get("/hello")
def read_root():
	return {"message": "Hello from FastAPI + MongoDB Atlas backend!"}


# --- Get all Sculptures ---
@app.get("/sculptures")
def get_sculptures():
	sculptures = list(collection.find())	# Try to retrieve all documents from MongoDB
	for r in sculptures:
		r["_id"] = str(r["_id"]) 	# Convert ObjectId to string for each sculpture
	return sculptures


# --- Post a new Sculpture ---
@app.post("/sculptures", status_code=status.HTTP_201_CREATED)
def add_sculpture(sculpture: Sculpture):
    collection.insert_one(sculpture.dict())
    return {"message": "Sculpture added successfully"}


# --- GET all with Error verification ---
@app.get("/sculpturese")
def get_sculpturese():
	try:
		if "sculptures" not in db.list_collection_names():
			raise HTTPException(status_code=404, detail="Collection 'sculptures' not found")
	
		# Try to retrieve all documents from MongoDB
		sculptures = list(collection.find())
		
		# Convert ObjectId to string for each sculpture
		for r in sculptures:
			r["_id"] = str(r["_id"])

			# Test Error code 500
			# r["_id"] = str(r[_id])
		return sculptures

	# If collection name is not found, raise a 404 error
	except HTTPException:
		raise # let FastAPI handle our own HTTP errors

	# If db_user name not found, raise a 503 error
	except PyMongoError as e:
		print("Database error:", e)
		raise HTTPException(status_code=503, detail="Database not reachable")
	
	# If any other unexpected error occurs, raise a 500 error
	except Exception as e:
		print("Unexpected error:", e)
		raise HTTPException(status_code=500, detail="Internal server error")


# --- Post a new sculpture with Error verification ---
@app.post("/sculpturese", status_code=status.HTTP_201_CREATED)
def add_sculpturee(sculpture: Sculpture):
    try:
        if "sculptures" not in db.list_collection_names():
            raise HTTPException(status_code=404, detail="Collection 'sculptures' not found")
        if collection.find_one({"name": sculpture.name}):
            raise HTTPException(status_code=409, detail="Sculpture already exists")
        result = collection.insert_one(sculpture.model_dump())
        return {"message": "Sculpture added successfully", "id": str(result.inserted_id)}
    except HTTPException:
        raise
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Sculpture already exists")
    except PyMongoError as e:
        print("Database error:", e)
        raise HTTPException(status_code=503, detail="Database not reachable")
    except Exception as e:
        print("Unexpected error:", e)
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Update a sculpture with Error verification ---
@app.put("/sculpturese/{name}")
def update_sculpture_with_errors(
    sculpture: SculptureValidated,
    name: str = Path(min_length=1)
):
    try:
        if not name.strip():
            raise HTTPException(status_code=422, detail="Sculpture name cannot be blank")

        if "sculptures" not in db.list_collection_names():
            raise HTTPException(status_code=404, detail="Collection 'sculptures' not found")

        # Find the sculpture using its current name.
        existing_sculpture = collection.find_one({"name": name})

        if existing_sculpture is None:
            raise HTTPException(status_code=404, detail=f"Sculpture '{name}' not found")

        # Prevent renaming it to another sculpture's name.
        duplicate = collection.find_one({
            "name": sculpture.name,
            "_id": {"$ne": existing_sculpture["_id"]}
        })

        if duplicate is not None:
            raise HTTPException(status_code=409, detail="Another sculpture already has that name")

        # JSON mode converts HttpUrl to a MongoDB-compatible string.
        updated_data = sculpture.model_dump(mode="json")

        result = collection.update_one(
            {"_id": existing_sculpture["_id"]},
            {"$set": updated_data}
        )

        # The sculpture might have been deleted after the lookup.
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Sculpture no longer exists")

        if result.modified_count == 0:
            return {
                "message": "No changes needed; sculpture already has these values",
                "id": str(existing_sculpture["_id"])
            }

        return {
            "message": "Sculpture updated successfully",
            "id": str(existing_sculpture["_id"])
        }

    except HTTPException:
        raise

    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Another sculpture already has that name")

    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database operation failed")

    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


# --- Delete a sculpture with Error verification ---
@app.delete("/sculpturese/{sculpture_id}")
def delete_sculpture(
    # Must be a 24-character hex string. Otherwise FastAPI returns 422 before the function runs.
    sculpture_id: str = Path(pattern=r"^[0-9a-fA-F]{24}$")
):
    try:
        if "sculptures" not in db.list_collection_names():
            raise HTTPException(status_code=404, detail="Collection 'sculptures' not found")

        object_id = ObjectId(sculpture_id)

        existing_sculpture = collection.find_one({"_id": object_id})
        if existing_sculpture is None:
            raise HTTPException(
                status_code=404,
                detail="Sculpture not found. It may have already been deleted"
            )

        result = collection.delete_one({"_id": object_id})

        # The sculpture might have been deleted by someone else after the lookup.
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Sculpture no longer exists")

        return {
            "message": f"Sculpture '{existing_sculpture.get('name', '')}' deleted successfully",
            "id": sculpture_id
        }

    except HTTPException:
        raise

    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database operation failed")


    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")
