REPO_PATH="/home/shixianjie/codegraph/codegraph/DevEval/Source_Code/Communications/Telethon"
RESULTDIR="./output"
PORT="3000 3001 3002 3003"

python repo_parser.py $REPO_PATH --output_dir $RESULTDIR
python pylsp.py $REPO_PATH --output_dir $RESULTDIR --ports $PORT
python defid_parser.py $REPO_PATH --output_dir $RESULTDIR
#     语言无关
# ------------------------------------------------
#     语言有关
python funcid.py $REPO_PATH --output_dir $RESULTDIR
python relation_parser.py $REPO_PATH --output_dir $RESULTDIR
python extract.py $REPO_PATH --output_dir $RESULTDIR