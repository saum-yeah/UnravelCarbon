from flask import Flask, request, jsonify
import redis
import json
import pandas as pd
from sort_dates import SORT_DATA_CSV
import re

# Initializing Flask app and Redis client
app = Flask(__name__)
app.config.from_object("env")

try:
    redis_client = redis.StrictRedis(host='127.0.0.1', port=6379, db=0, decode_responses=True)
    redis_client.ping()
except redis.ConnectionError as e:
    raise Exception(f"Redis connection failed: {e}")

# Load and sort the CSV file into memory
sorted_emissions_data = SORT_DATA_CSV()

def parse_date_formats(date_str):
    """Parse a date string with multiple potential formats."""
    for frmt in ("%d-%m-%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return pd.to_datetime(date_str, format=frmt)
        except ValueError:
            continue
    return pd.NaT

def filter_emissions_data(start_date, end_date, facilities):
    """Filter emissions data based on date range and facilities."""
    filtered_data = sorted_emissions_data[
        (sorted_emissions_data["TRANSACTION DATE"] >= start_date) &
        (sorted_emissions_data["TRANSACTION DATE"] <= end_date) &
        (sorted_emissions_data["Business Facility"].isin(facilities))
    ]
    filtered_data = filtered_data.sort_values(by="TRANSACTION DATE").reset_index(drop=True)
    emissions_summary = filtered_data.groupby("Business Facility")["CO2_ITEM"].sum().to_dict()
    return emissions_summary

def parse_cache_key(cache_key):
    """Parse a Redis cache key into its components."""
    try:
        start_date, end_date, facilities = cache_key.split("_")
        return pd.to_datetime(start_date), pd.to_datetime(end_date), facilities.split(",")
    except ValueError:
        raise ValueError(f"Malformed cache key: {cache_key}")

def is_partial_key_match(new_key, existing_key):
    """Check if a new cache key partially matches an existing key."""
    try:
        new_start, new_end, new_facilities = parse_cache_key(new_key)
        existing_start, existing_end, existing_facilities = parse_cache_key(existing_key)
    except ValueError:
        return False

    date_overlap = (new_start <= existing_end and new_end >= existing_start)
    facility_overlap = bool(set(new_facilities) & set(existing_facilities))
    return date_overlap and facility_overlap

@app.route("/api/emissions", methods=["POST"])
def get_emissions():
    """API endpoint to retrieve emissions data."""
    request_data = request.get_json()
    start_date = request_data.get("startDate")
    end_date = request_data.get("endDate")
    facilities = request_data.get("businessFacility", [])
    
    if not start_date or not end_date or not facilities:
        return jsonify({"error": "Missing required fields in request body"}), 400

    try:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
    except Exception:
        return jsonify({"error": "Invalid date format"}), 400

    cache_key = f"{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}_{','.join(sorted(facilities))}"
    cached_data = redis_client.get(cache_key)
    
    if cached_data:
        print("Returning cached result from Redis") 
        return jsonify({"source": "cached result from Redis", "data emission": json.loads(cached_data)})

    combined_emissions = {}
    partial_keys = []
    for existing_key in redis_client.scan_iter():
        if re.match(r'^\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}_.+$', existing_key):
            if is_partial_key_match(cache_key, existing_key):
                cached_data = redis_client.get(existing_key)
                if cached_data:
                    partial_emissions = json.loads(cached_data)
                    for facility, emission in partial_emissions.items():
                        combined_emissions[facility] = combined_emissions.get(facility, 0) + emission
                partial_keys.append(existing_key)

    total_covered_start = min(parse_cache_key(key)[0] for key in partial_keys) if partial_keys else None
    total_covered_end = max(parse_cache_key(key)[1] for key in partial_keys) if partial_keys else None

    if total_covered_start is None or total_covered_end is None or total_covered_start > start_date or total_covered_end < end_date:
        missing_start = max(start_date, total_covered_end + pd.Timedelta(days=1)) if total_covered_end else start_date
        missing_end = min(end_date, total_covered_start - pd.Timedelta(days=1)) if total_covered_start else end_date
        
        if missing_start <= missing_end:
            print(f"Querying missing range: {missing_start} to {missing_end}")
            new_data = filter_emissions_data(missing_start, missing_end, facilities)
            for facility, emission in new_data.items():
                combined_emissions[facility] = combined_emissions.get(facility, 0) + emission

            missing_cache_key = f"{missing_start.strftime('%Y-%m-%d')}_{missing_end.strftime('%Y-%m-%d')}_{','.join(sorted(facilities))}"
            redis_client.set(missing_cache_key, json.dumps(new_data), ex=3600)
    
    redis_client.set(cache_key, json.dumps(combined_emissions), ex=3600)

    print("Returning new result with combined and filled data")
    return jsonify({"source": "combined from cache and API call", "data emission": combined_emissions})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
