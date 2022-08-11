if [ "$1" ]; then
    solver_dir=$1
else
    solver_dir="../solvers/"
fi

solvers="cbc ipopt couenne"
cd $solver_dir

mkdir Linux64
cd Linux64
for s in $solvers
do
    wget https://ampl.com/dl/open/$s/$s-linux64.zip
    unzip -u $s-linux64.zip
    rm $s-linux64.zip
done
cd ..

#mkdir Windows64
#cd Windows64
#for s in $solvers
#do
#    wget https://ampl.com/dl/open/$s/$s-win64.zip
#    unzip -u $s-win64.zip
#    rm $s-win64.zip
#done
