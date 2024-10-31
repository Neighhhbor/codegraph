import json
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_prompt_for_namespace(element):
    """
    Generate a prompt for the given element based solely on the input_code.
    """
    if not isinstance(element, dict):
        logging.debug(f"Invalid element format, expected a dictionary but got: {type(element)}")
        return None

    input_code = element.get('input_code', '')

    if not input_code:
        logging.debug("No input code found in the element.")
        return None

    # Construct the prompt containing only the input code
    prompt = (
        f"The code to be completed is:\n```Python\n{input_code}\n```\n\n"    
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
    output_file_path = "/home/shixianjie/codegraph/codegraph/Agent/tools/experiments/gpt-4o/baseline_prompt.jsonl"
    generate_prompts_from_data(input_file_path, output_file_path)
