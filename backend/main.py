from flask import Flask, request, jsonify
import redis
import json
import pandas as pd
import re  # For regex matching

# Initializing Flask app and Redis client
app = Flask(__name__)
app.config.from_object("settings")
try:
    redis_client = redis.StrictRedis(host='127.0.0.1', port=6379, db=0, decode_responses=True)
    redis_client.ping()
except redis.ConnectionError as e:
    raise Exception(f"Redis connection failed: {e}")

# Load CSV once and cache it
emissions_data = pd.read_csv("emission_data.csv")

# Function to parse dates with multiple formats
def parse_dates(date_str):
    for fmt in ("%d-%m-%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return pd.to_datetime(date_str, format=fmt)
        except ValueError:
            continue
    return pd.NaT

# Function to filter data based on start and end dates and facilities provided
def get_filtered_data(start_date, end_date, facilities):
    data = emissions_data.copy()
    data["TRANSACTION DATE"] = data["TRANSACTION DATE"].apply(parse_dates)
    data = data.dropna(subset=["TRANSACTION DATE"])
    
    filtered = data[
        (data["TRANSACTION DATE"] >= start_date) & 
        (data["TRANSACTION DATE"] <= end_date) & 
        (data["Business Facility"].isin(facilities))
    ]
    emissions = filtered.groupby("Business Facility")["CO2_ITEM"].sum().to_dict()
    return emissions

# Function to parse cache keys
def parse_key(cache_key):
    try:
        start_date, end_date, facilities = cache_key.split("_")
        return pd.to_datetime(start_date), pd.to_datetime(end_date), facilities.split(",")
    except ValueError:
        raise ValueError(f"Malformed cache key: {cache_key}")

# Function to check partial key match
def partial_match(new_key, existing_key):
    try:
        new_start, new_end, new_facilities = parse_key(new_key)
        existing_start, existing_end, existing_facilities = parse_key(existing_key)
    except ValueError:
        return False

    date_overlap = (new_start <= existing_end and new_end >= existing_start)
    facility_overlap = bool(set(new_facilities) & set(existing_facilities))
    return date_overlap or facility_overlap

# API route to get emissions data
@app.route("/api/emissions", methods=["POST"])
def get_emissions():
    data1 = request.get_json()
    start_date = data1.get("startDate")
    end_date = data1.get("endDate")
    facilities = data1.get("businessFacility", [])
    
    if not start_date or not end_date or not facilities:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
    except Exception:
        return jsonify({"error": "Invalid date format"}), 400

    cache_key = f"{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}_{','.join(sorted(facilities))}"
    cached_result = redis_client.get(cache_key)
    
    if cached_result:
        print("Returning cached result") 
        print(json.loads(cached_result))
        return jsonify({"source": "Memory", "data": json.loads(cached_result)})

    # Check for partial matches using regex
    for existing_key in redis_client.scan_iter():
        if re.match(r'^\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}_.+$', existing_key):
            if partial_match(cache_key, existing_key):
                cached_result = redis_client.get(existing_key)
                print("Returning partial match cached result") 
                print(json.loads(cached_result))
                return jsonify({"source": "Memory", "data": json.loads(cached_result)})

    result = get_filtered_data(start_date, end_date, facilities)
    redis_client.set(cache_key, json.dumps(result), ex=3600)  # Cache for 1 hour

    print("Returning new result from database")
    print(result)
    return jsonify({"source": "database", "data": result})

# Running the Flask app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
