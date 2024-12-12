import pandas as pd

def load_csv_data():
    return pd.read_csv("emission_data/emission_data.csv") #function to load your csv file

def get_filtered_data(start_date, end_date, facilities):
    data = load_csv_data()
    #apply filters as per start and end dates for specific facilities only
    filtered = data[
        (data["TRANSACTION DATE"] >= start_date) &
        (data["TRANSACTION DATE"] <= end_date) &
        (data["Business Facility"].isin(facilities))
    ]
    # group filtered data based on Business Facility 
    emissions = filtered.groupby("Business Facility")["CO2_ITEM"].sum().to_dict()
    return emissions
