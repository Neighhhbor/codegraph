import json
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_prompt_for_namespace(element):
    """
    Generate a prompt for the given element based on its context, imports, and most similar function.
    """
    if not isinstance(element, dict):
        logging.debug(f"Invalid element format, expected a dictionary but got: {type(element)}")
        return None

    namespace = element.get('namespace', 'unknown')
    contexts_above = element.get('contexts_above', '')
    contexts_below = element.get('contexts_below', '')
    input_code = element.get('input_code', '')
    contexts_import = element.get('contexts_import', [])
    most_similar_function = element.get('most_similar_function', {})

    # Ensure contexts_import is a list
    if not isinstance(contexts_import, list):
        logging.debug(f"Invalid contexts_import format for namespace {namespace}, expected list but got {type(contexts_import)}")
        contexts_import = []

    # Handle most_similar_function which could be either a dict or a str
    if isinstance(most_similar_function, str):
        if most_similar_function.lower() == "no similar function found.":
            logging.debug(f"most_similar_function for namespace {namespace} is 'No similar function found.', treating as empty.")
            most_similar_function = {}
        else:
            logging.debug(f"Unexpected string value for most_similar_function in namespace {namespace}, treating as empty.")
            most_similar_function = {}
    elif not isinstance(most_similar_function, dict):
        logging.debug(f"Invalid most_similar_function format for namespace {namespace}, expected dict but got {type(most_similar_function)}")
        most_similar_function = {}

    # Prepare the import context
    import_contexts = "\n".join([
        f"{imp.get('import_statement', '')}{'\n' + imp.get('code', '') if imp.get('code') else ''}"
        for imp in contexts_import if isinstance(imp, dict)
    ])

    # Prepare the most similar function context
    similar_function_code = most_similar_function.get('code', '')
    similarity_score = most_similar_function.get('similarity', '')
    most_similar_context = f"Most similar function (similarity score: {similarity_score}):\n{similar_function_code}" if similar_function_code else ""

    # Construct the prompt
    prompt = (
        f"Please complete the function in the middle of a file for namespace: {namespace}.\n\n"
        f"The contexts above the function are:\n```Python\n{contexts_above}\n```\n\n"
        f"The contexts below the function are:\n```Python\n{contexts_below}\n```\n\n"
        f"The imports in the file are:\n```Python\n{import_contexts}\n```\n\n"
        f"The code to be completed is:\n```Python\n{input_code}\n```\n\n"
        f"{most_similar_context}\n\n"
        f"Completed code:"
    )
    return prompt

def generate_prompts_from_data(input_file, output_file):
    """
    Read the input JSONL file, generate prompts for each element, and write them to the output file.
    """
    with open(input_file, 'r', encoding='utf-8') as in_f, open(output_file, 'w', encoding='utf-8') as out_f:
        for line_number, line in enumerate(in_f, start=1):
            try:
                # Load and validate the JSON line
                element = json.loads(line.strip())
                if not isinstance(element, dict):
                    logging.debug(f"Line {line_number}: Expected a JSON object, but got {type(element)}. Skipping this line.")
                    continue

                # Generate prompt for the element
                prompt = generate_prompt_for_namespace(element)
                if prompt is None:
                    logging.debug(f"Line {line_number}: Failed to generate a prompt. Skipping this line.")
                    continue

                # Prepare the output data
                output_data = {
                    "namespace": element.get('namespace', 'unknown'),
                    "prompt": prompt
                }

                # Write to output file
                json.dump(output_data, out_f, ensure_ascii=False)
                out_f.write('\n')

            except json.JSONDecodeError as e:
                logging.debug(f"Line {line_number}: Error decoding JSON: {e}")
            except Exception as e:
                logging.debug(f"Line {line_number}: Unexpected error: {e}")

if __name__ == "__main__":
    input_file_path = "/home/shixianjie/codegraph/codegraph/Agent/tools/LM_prompt_elements_with_contexts.jsonl"
    output_file_path = "/home/shixianjie/codegraph/codegraph/Agent/tools/experiments/gpt-4o/Prompt_exper1.jsonl"
    generate_prompts_from_data(input_file_path, output_file_path)
