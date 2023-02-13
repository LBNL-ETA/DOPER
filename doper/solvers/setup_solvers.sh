if [ "$1" ]; then
    solver_dir=$1
else
    solver_dir="../solvers/"
fi

cbc_repo="https://github.com/coin-or/Cbc/releases/download/releases%2F"
cbc_version="2.10.8"

solvers="cbc"
cd $solver_dir

mkdir Linux64
cd Linux64
for s in $solvers
do
    fname=Cbc-releases.${cbc_version}-x86_64-ubuntu18-gcc750-static.tar.gz
	wget ${cbc_repo}${cbc_version}/${fname}
    tar -xvzf ${fname}
    rm ${fname}
	mv bin/* .
done
cd ..