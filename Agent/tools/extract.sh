

python post_process.py --input_file gpt-4o-mini.jsonl --output_file processed_code.jsonl

python process_completion.py --model_type gpt --completion_file processed_code.jsonl --output_file ./gpt-4o-mini/completion.jsonl  --data_file /home/sxj/Desktop/Workspace/CodeQl/gptgraph/DevEval/data.jsonl

