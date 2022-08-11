if [%1]==[] (set solver_dir="../solvers/") else (set solver_dir=%1)

set solvers=(cbc,ipopt,couenne)
cd $solver_dir

mkdir Windows64
cd Windows64
for %%x in %solvers% do (
	curl https://ampl.com/dl/open/%%x/%%x-win64.zip -O -J -L
	tar -xf %%x-win64.zip
	del %%x-win64.zip
)
