import json

# Define file paths
input_file = 'data.jsonl'
any_crossfile_file = 'any_crossfile.jsonl'
only_crossfile_file = 'only_crossfile.jsonl'

# Function to filter and save the data
def filter_and_save_jsonl(input_file, any_crossfile_file, only_crossfile_file):
    try:
        # Initialize lists to store filtered data
        any_crossfile_data = []
        only_crossfile_data = []

        # Read the input file and process each line
        with open(input_file, 'r') as file:
            for line in file:
                entry = json.loads(line)
                # Extract dependency components
                cross_file = entry.get('dependency', {}).get('cross_file', [])
                intra_class = entry.get('dependency', {}).get('intra_class', [])
                intra_file = entry.get('dependency', {}).get('intra_file', [])
                
                # Condition for any_crossfile
                if cross_file:
                    any_crossfile_data.append(entry)
                
                # Condition for only_crossfile
                if cross_file and not intra_class and not intra_file:
                    only_crossfile_data.append(entry)

        # Write the filtered data to respective output files
        with open(any_crossfile_file, 'w') as file:
            for entry in any_crossfile_data:
                file.write(json.dumps(entry) + '\n')

        with open(only_crossfile_file, 'w') as file:
            for entry in only_crossfile_data:
                file.write(json.dumps(entry) + '\n')

        print(f"Filtered data saved to {any_crossfile_file} and {only_crossfile_file}")

    except FileNotFoundError:
        print(f"File {input_file} not found. Please ensure the file exists.")
    except Exception as e:
        print(f"An error occurred: {e}")

# Call the function
filter_and_save_jsonl(input_file, any_crossfile_file, only_crossfile_file)
