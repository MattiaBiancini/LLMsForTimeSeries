import os
import subprocess

# Directory principale che contiene tutti i progetti
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_directory = os.path.join(script_dir, "..")
results_file = "results.csv"

# File per raccogliere tutte le dipendenze
output_requirements = "requirements.txt"

# Set per evitare duplicati
all_dependencies = set()

# Scorri tutte le sottocartelle
for root, dirs, files in os.walk(parent_directory):
    # Se contiene file Python, è una directory di progetto
    if any(file.endswith('.py') for file in files):
        print(f"Processing project in: {root}\n")
        try:
            # Esegui pipreqs per raccogliere le dipendenze senza generare un file
            result = subprocess.run(
                ['pipreqs', root, '--print'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            # Aggiungi le dipendenze al set
            dependencies = result.stdout.splitlines()
            all_dependencies.update(dependencies)
        except subprocess.CalledProcessError as e:
            print(f"Error processing {root}: {e.stderr}")

# Scrivi tutte le dipendenze uniche in un unico requirements.txt
with open(output_requirements, 'w') as f:
    f.write("\n".join(sorted(all_dependencies)))

print(f"Combined requirements saved to {output_requirements}")