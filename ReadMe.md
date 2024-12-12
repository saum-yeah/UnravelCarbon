#UC Backend Engineer Assignment

## Description
Part 1: Flask webFrame work based API Development
Here a web server that exposes a single API endpoint. This API will accept two parameters:
a. A date range defined by startDate and endDate in the format YYYY-MM-DD.

b. A list of business facilities, e.g., ["GreenEat Changi", "GreenEat Orchard"].

c. The API will respond with a JSON payload containing:
The total emissions of all transactions within the specified date range, grouped by the different business facilities.
Example of Request body and Response Format:
Request body for a post request:
json
{
    "startDate": "2021-01-01",
    "endDate": "2021-12-31",
    "businessFacilities": ["GreenEat Changi", "GreenEat Orchard"]
}

Response:
json
{
    "emissions": {
        "GreenEat Changi": 1500,
        "GreenEat Orchard": 1200
    }
}

Part 2: Intelligent Caching using redis
Here, we implemented an intelligent caching mechanism using Redis to improve performance and reduce database load. Here’s what is done in the assignment:
a. Exact Match Caching: If a request matches a previous request (same date range and facilities), the cached result is returned directly from Redis.
b. Partial Date Range Overlap: If the requested date range overlaps with cached ranges, we combine the partial data from Redis.
c. Partial Facility Overlap: If the requested business facilities overlap with cached data, the relevant cached data is aggregated.

## Installation
1. Clone the repository: `git clone https://github.com/SOUGUR/unravelCarbon` and navigate inside using "cd unravelCarbon"

2. Create a virtual environment in the project directory with " python -m venv virtE"

3. Activate the virtual environment with "virtE\Scripts\activate"

4. Navigate to the directory: `cd backend`

5. Install dependencies: `pip install -r requirements.txt`

6. Install Redis on Windows via WSL2
    6.1 Open PowerShell as an administrator and run the following command to install WSL with "wsl --install"
    6.2 After restarting, launch the installed Ubuntu from the Start menu. It will prompt you to create a    username and password for your Linux environment. Set your username & password
    6.3 Once you are in the Ubuntu terminal, update your package lists and install Redis:
        "sudo apt update"
        "sudo apt install redis-server"
    6.4 After installation, start the Redis server with:
        "sudo service redis-server start"
    6.5 check if Redis is running by using the Redis CLI like "redis-cli ping" , If Redis is running correctly, it should respond with PONG.

7. Run the Flask application, so make sure you are in backend package and there run "python main.py"



### Conclusion
1. Sorted Transaction Dates:

    1.1 The CSV file containing transaction data is sorted by transaction dates.
    This sorting allows for faster searching and scanning since we can leverage efficient range queries instead of scanning the entire file.

    1.2 By knowing the start and end dates of existing data, we can quickly identify which portions of the data are already available and which portions are missing.

    1.3 This strategy significantly reduces the time complexity of data lookups from O(n) (scanning the entire dataset) to something closer to O(log n) when combined with range-based lookups.

2. Redis Caching:

    2.1 Redis is used as an in-memory cache to store previously requested data.
    Whenever a request is made, the system first checks if the required data exists in the Redis cache.

    2.2 If a partial match is found (for date ranges and business facilities), the system retrieves only the missing portions instead of reloading the entire dataset.

    2.3 If the data is not fully available, a background task (using Celery) is triggered to fetch the missing data while still returning the available portions to the user.
    
    2.4 This approach reduces database or file system reads, enhances response times, and allows the system to serve repeated or similar requests instantly from Redis.

3. By sorting transaction dates and leveraging Redis caching, the code provides a solution that efficiently handles large datasets (even with over 1 million rows). This approach tries to ensure a fast, and provides near-instant response times for repeated or overlapping requests.
