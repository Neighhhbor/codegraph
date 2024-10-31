import json
import os


def merge_jsonl_files(lm_prompt_file, data_file, output_file):
    # Load LM prompt elements into a dictionary with namespace as the key
    lm_prompt_elements = {}
    with open(lm_prompt_file, 'r') as f:
        for line in f:
            if line.strip():
                element = json.loads(line)
                lm_prompt_elements[element['namespace']] = element

    # Load data elements and merge with LM prompt elements
    merged_elements = []
    with open(data_file, 'r') as f:
        for line in f:
            if line.strip():
                data_element = json.loads(line)
                namespace = data_element['namespace']

                if namespace in lm_prompt_elements:
                    lm_element = lm_prompt_elements[namespace]
                    # Merge lm_element and data_element, giving preference to lm_element values in case of conflicts
                    merged_element = {**data_element, **lm_element}
                    merged_elements.append(merged_element)
                else:
                    # If no corresponding LM prompt element, add the data element as it is
                    merged_elements.append(data_element)

    # Write merged elements to output file
    with open(output_file, 'w') as f:
        for element in merged_elements:
            json.dump(element, f)
            f.write('\n')


if __name__ == "__main__":
    lm_prompt_file_path = "/home/shixianjie/codegraph/codegraph/DevEval/Experiments/prompt/LM_prompt_elements.jsonl"
    data_file_path = "/home/shixianjie/codegraph/codegraph/DevEval/data.jsonl"
    output_file_path = "/home/shixianjie/codegraph/codegraph/Agent/tools/LM_prompt_elements_merged.jsonl"

    merge_jsonl_files(lm_prompt_file_path, data_file_path, output_file_path)
