from backend import redis_client

from datetime import datetime

def parse_key(cache_key):
    # Split the key into its components
    parts = cache_key.split("-")
    start_date, end_date = parts[0], parts[1]
    facilities = parts[2].split(",")
    return datetime.strptime(start_date, "%Y-%m-%d"), datetime.strptime(end_date, "%Y-%m-%d"), set(facilities)

def partial_match(new_key, existing_key):
    # Parse the keys
    new_start, new_end, new_facilities = parse_key(new_key)
    existing_start, existing_end, existing_facilities = parse_key(existing_key)

    # Check for date range overlap
    date_overlap = (new_start <= existing_end and new_end >= existing_start)

    # Check for facility overlap
    facility_overlap = bool(new_facilities & existing_facilities)  # Intersection of sets

    # Return True if either overlap
    return date_overlap and facility_overlap
    
def check_partial_overlap(cache_key):
    # Get all cached keys
    cached_keys = redis_client.keys("*")
    overlapping_results = []

    for key in cached_keys:
        key = key.decode("utf-8")  # Decode Redis byte string to Python string
        if partial_match(cache_key, key):
            cached_value = redis_client.get(key)
            overlapping_results.append(eval(cached_value))  # Convert cached value back to Python dict/list

    return overlapping_results