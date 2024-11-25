import os
import subprocess
import pandas as pd


def initialize_csv(results_file):
    if not os.path.exists(results_file):
        # Create an empty DataFrame with the required columns
        df = pd.DataFrame(columns=["Method", "Script Name", "Predicate Length", "MAE", "MSE"])
        # Save it to a CSV file
        df.to_csv(results_file, index=False)
        print(f"Created {results_file} with header.")


# Define the base directory for your project
script_dir = os.path.dirname(os.path.abspath(__file__))
results_file = "results.csv"

initialize_csv(results_file)

# Loop through subdirectories to find and execute .sh files
for root, dirs, files in os.walk(script_dir):
    for file in files:
        if file.endswith(".sh"):
            sh_file_path = os.path.join(root, file)
            script_dir = os.path.dirname(sh_file_path)
            while "script" in script_dir:
                script_dir = os.path.dirname(script_dir)# Get the directory of the script
            print(f"Executing: {os.path.normpath(sh_file_path)} from {script_dir}")

            try:
                # Run the shell script with its directory as the working directory
                subprocess.run(["bash", sh_file_path.replace("C:", "/mnt/c").replace("\\", "/")], cwd=script_dir, check=True)
            except subprocess.CalledProcessError as e:
                print(f"Error while executing {sh_file_path}: {e}")
