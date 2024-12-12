from flask import Flask, request, jsonify
import redis
import json
import pandas as pd
from sortdates import sortdatacsv
import re  


# Initializing Flask app and Redis client
app = Flask(__name__)
app.config.from_object("settings")
try:
    redis_client = redis.StrictRedis(host='127.0.0.1', port=6379, db=0, decode_responses=True)
    redis_client.ping()
except redis.ConnectionError as e:
    raise Exception(f"Redis connection failed: {e}")

# we load csv file which is sorted according to transaction dates into our RAM memory 
emissions_data = sortdatacsv()

# A function to parse dates with multiple formats
def parse_dates(date_str):
    for fmt in ("%d-%m-%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return pd.to_datetime(date_str, format=fmt)
        except ValueError:
            continue
    return pd.NaT

# A function to filter data based on start and end dates and facilities provided
def get_filtered_data(start_date, end_date, facilities):
    data = emissions_data.copy()
    #apply filter conditions
    filtered = data[
        (data["TRANSACTION DATE"] >= start_date) & 
        (data["TRANSACTION DATE"] <= end_date) & 
        (data["Business Facility"].isin(facilities))
    ]
    filtered = filtered.sort_values(by="TRANSACTION DATE").reset_index(drop=True)
    emissions = filtered.groupby("Business Facility")["CO2_ITEM"].sum().to_dict()
    return emissions

# A function to parse cache keys
def parse_key(cache_key):
    try:
        start_date, end_date, facilities = cache_key.split("_")
        return pd.to_datetime(start_date), pd.to_datetime(end_date), facilities.split(",")
    except ValueError:
        raise ValueError(f"Incorrectly formed cache key: {cache_key}")

# A function to check partial key match
def partial_match(new_key, existing_key):
    try:
        new_start, new_end, new_facilities = parse_key(new_key)
        existing_start, existing_end, existing_facilities = parse_key(existing_key)
    except ValueError:
        return False
    #checking for any overlaps of dates for new key with existing key
    date_overlap = (new_start <= existing_end and new_end >= existing_start)
    #checking for facility overlaps
    facility_overlap = bool(set(new_facilities) & set(existing_facilities))
    return date_overlap and facility_overlap #returns true only if dates and facilities overlap

# API route to get emissions data
@app.route("/api/emissions", methods=["POST"])
def get_emissions():
    data1 = request.get_json()
    start_date = data1.get("startDate")
    end_date = data1.get("endDate")
    facilities = data1.get("businessFacility", [])
    
    if not start_date or not end_date or not facilities:
        return jsonify({"error": "few fields missing from body"}), 400

    try:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
    except Exception:
        return jsonify({"error": "Invalid date format"}), 400

    #form a cache key 
    cache_key = f"{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}_{','.join(sorted(facilities))}"
    cached_result = redis_client.get(cache_key)
    
    if cached_result:
        print("Returning cached result from Redis") 
        return jsonify({"source": "cached result from Redis", "data": json.loads(cached_result)})

    # Collect and combine multiple partial matches if they exist
    combined_emissions = {}
    partial_keys = []
    for existing_key in redis_client.scan_iter():
        if re.match(r'^\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}_.+$', existing_key):
            if partial_match(cache_key, existing_key):
                cached_result = redis_client.get(existing_key)
                if cached_result:
                    partial_emissions = json.loads(cached_result)
                    for facility, emission in partial_emissions.items():
                        combined_emissions[facility] = combined_emissions.get(facility, 0) + emission
                partial_keys.append(existing_key)
    
    #Check for gaps in date range
    total_covered_start = min(parse_key(key)[0] for key in partial_keys) if partial_keys else None
    total_covered_end = max(parse_key(key)[1] for key in partial_keys) if partial_keys else None

    if total_covered_start is None or total_covered_end is None or total_covered_start > start_date or total_covered_end < end_date:
        # Get missing range and query the source
        missing_start = max(start_date, total_covered_end + pd.Timedelta(days=1)) if total_covered_end else start_date
        missing_end = min(end_date, total_covered_start - pd.Timedelta(days=1)) if total_covered_start else end_date
        
        if missing_start <= missing_end:  # Check if there is a range to query
            print(f"Querying missing range: {missing_start} to {missing_end}")
            new_data = get_filtered_data(missing_start, missing_end, facilities)
            for facility, emission in new_data.items():
                combined_emissions[facility] = combined_emissions.get(facility, 0) + emission
            
            # Cache the new result to avoid future gaps
            missing_key = f"{missing_start.strftime('%Y-%m-%d')}_{missing_end.strftime('%Y-%m-%d')}_{','.join(sorted(facilities))}"
            redis_client.set(missing_key, json.dumps(new_data), ex=3600)  # Cache for 1 hour
    
    # Cache the final result for the requested range
    redis_client.set(cache_key, json.dumps(combined_emissions), ex=3600)  # Cache for 1 hour

    print("Returning new result with combined and filled data")
    return jsonify({"source": "combined", "data": combined_emissions})

# Running the Flask app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
