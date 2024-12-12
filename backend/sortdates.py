import pandas as pd

def sortdatacsv():
    emissions_data = pd.read_csv("emission_data.csv")
    emissions_data["TRANSACTION DATE"] = pd.to_datetime(emissions_data["TRANSACTION DATE"], errors='coerce')
    
    emissions_data = emissions_data.sort_values(by="TRANSACTION DATE").reset_index(drop=True)
    
    # Print the processed DataFrame (optional)
    print("emissions_data changed and sorted according to transaction dates")
    return emissions_data

if __name__ == "__main__":
    sortdatacsv()
