export GOPROXY=https://goproxy.cn,direct
# gopls serve -rpc.trace -logfile=gopls.log --debug=localhost:6060 -listen=localhost:8080
gopls serve -rpc.trace --debug=localhost:6060 -listen=localhost:8080
