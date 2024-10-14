#!/bin/bash

# 退出时输出错误信息
set -e

# 定义文件夹路径（可修改）
WORKSPACE_PATH="/home/sxj/Desktop/Workspace/CodeQl/gptgraph/Agent/tools/experiments/gpt-4o-mini/tool"
DATA_PATH="/home/sxj/Desktop/Workspace/CodeQl/gptgraph/DevEval"

# 定义文件路径（可修改）
INPUT_FILE="$WORKSPACE_PATH/completions.jsonl"
PROCESSED_CODE_FILE="$WORKSPACE_PATH/processed_completion.jsonl"
COMPLETION_OUTPUT_FILE="$WORKSPACE_PATH/codebody.jsonl"
FINAL_OUTPUT_FILE="$WORKSPACE_PATH/output.jsonl"
DATA_FILE="$DATA_PATH/data.jsonl"


# # Step 1: 运行 post_process.py，提取代码部分
# echo "Step 1: Extracting code from completions..."
# python post_process.py --input_file "$INPUT_FILE" --output_file "$PROCESSED_CODE_FILE"
# echo "Code extraction completed. Output saved to $PROCESSED_CODE_FILE"

# Step 2: 运行 process_completion.py，进一步处理提取的代码
python process_completion.py --model_type gpt --completion_file "$INPUT_FILE" --output_file "$COMPLETION_OUTPUT_FILE" --data_file "$DATA_FILE"


# Step 3: 运行 get_completion.py，生成最终的测试输出

python get_completion.py --input_file "$COMPLETION_OUTPUT_FILE" --output_file "$FINAL_OUTPUT_FILE"


