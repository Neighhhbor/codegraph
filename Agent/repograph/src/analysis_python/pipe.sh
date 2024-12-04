DevEval_PATH="/home/shixianjie/codegraph/codegraph/DevEval/Source_Code/"
# DevEval_PATH="/home/shixianjie/codegraph/codegraph/DevEval/Source_Code/Software-Development/Django"
RESULTDIR="/home/shixianjie/codegraph/codegraph/data_process/repograph"

python exper.py $DevEval_PATH $RESULTDIR --max_workers 4 --ports_per_repo 4
