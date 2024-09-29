import json

# Function to divide data into standalone and dependence sets
def divide_data(input_file, standalone_output, dependence_output):
    standalone = []
    dependence = []

    # Read the original jsonl file
    with open(input_file, 'r', encoding='utf-8') as file:
        for line in file:
            data = json.loads(line.strip())
            # Check if the data point has any dependencies
            if data["dependency"]["intra_class"] or data["dependency"]["intra_file"] or data["dependency"]["cross_file"]:
                dependence.append(data)
            else:
                standalone.append(data)

    # Write the standalone data into a jsonl file
    with open(standalone_output, 'w', encoding='utf-8') as standalone_file:
        for item in standalone:
            standalone_file.write(json.dumps(item, ensure_ascii=False) + '\n')

    # Write the dependence data into a jsonl file
    with open(dependence_output, 'w', encoding='utf-8') as dependence_file:
        for item in dependence:
            dependence_file.write(json.dumps(item, ensure_ascii=False) + '\n')

# Example usage
input_file = '/home/sxj/Desktop/Workspace/CodeQl/gptgraph/DevEval/data.jsonl'  # Replace with the path to your input jsonl file
standalone_output = './standalone_data.jsonl'  # Output file for standalone data
dependence_output = './dependence_data.jsonl'  # Output file for dependence data

divide_data(input_file, standalone_output, dependence_output)
