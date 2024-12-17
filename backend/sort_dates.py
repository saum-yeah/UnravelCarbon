import pandas as pd

def SORT_DATA_CSV():
    emission_data = pd.read_csv("emission_data.csv")

    emission_data["TRANSACTION DATE"] = pd.to_datetime(emission_data["TRANSACTION DATE"], errors='coerce')
    
    emission_data = emission_data.sort_values(by="TRANSACTION DATE").reset_index(drop=True)

    return emission_data
