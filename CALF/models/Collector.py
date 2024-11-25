import pandas as pd
import os

results_file = "results.csv"

def append_to_csv(method, script_name, pred_length, mae, mse):
    # Create a DataFrame with the new row
    absolute_path = os.path.abspath(results_file)
    print(f"The absolute path of the CSV file is: {absolute_path}")
    new_row = pd.DataFrame([{
        "Method": method,
        "Script Name": script_name,
        "Predicate Length": pred_length,
        "MAE": mae,
        "MSE": mse
    }])
    # Append the row to the CSV without overwriting
    new_row.to_csv(results_file, mode="a", header=False, index=False)
    print(f"Appended results for {script_name} to {results_file}.")