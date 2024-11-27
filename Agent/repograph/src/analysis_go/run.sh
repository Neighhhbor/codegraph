REPO_PATH="/home/sxj/Desktop/Workspace/Development/RepoRepresentation/examples/Go/aixgo-clear"
OUTPUT_DIR="./output"

# python repo_parser.py $REPO_PATH --output_dir $OUTPUT_DIR
# python golsp.py $REPO_PATH --output_dir $OUTPUT_DIR
# python defid_parser.py $REPO_PATH --output_dir $OUTPUT_DIR
# #     语言无关
# # ------------------------------------------------
# #     语言有关
# python funcid.py $REPO_PATH --output_dir $OUTPUT_DIR
# python relation_parser.py $REPO_PATH --output_dir $OUTPUT_DIR
python extract.py $REPO_PATH --output_dir $OUTPUT_DIR