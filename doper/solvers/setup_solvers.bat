if [%1]==[] (set solver_dir="../solvers/") else (set solver_dir=%1)

set cbc_repo="https://github.com/coin-or/Cbc/releases/download/releases%2F"
set cbc_version="2.10.8"

set solvers=(cbc)
cd $solver_dir

mkdir Windows64
cd Windows64
for %%x in %solvers% do (
	curl %cbc_repo%%cbc_version%/Cbc-releases.%cbc_version%-i686-w64-mingw32.zip -O -J -L
	tar -xf %%x-win64.zip
	del %%x-win64.zip
)
