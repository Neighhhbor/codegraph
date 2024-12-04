REPO_PATH="/home/shixianjie/codegraph/codegraph/DevEval/Source_Code/Utilities/stellar"
# REPO_PATH="/home/shixianjie/codegraph/codegraph/DevEval/Source_Code/Software-Development/Django"
RESULTDIR="./testout"
PORT="4000 4001 4002 4003"

# python repo_parser.py $REPO_PATH --output_dir $RESULTDIR
# python pylsp.py $REPO_PATH --output_dir $RESULTDIR --ports $PORT
# python newdef.py $REPO_PATH --output_dir $RESULTDIR
# #     语言无关
# # ------------------------------------------------
# #     语言有关
# python funcid.py $REPO_PATH --output_dir $RESULTDIR
# python relation_parser.py $REPO_PATH --output_dir $RESULTDIR
# python extract.py $REPO_PATH --output_dir $RESULTDIR

python pipetest.py $REPO_PATH --output_dir $RESULTDIR --ports $PORT
