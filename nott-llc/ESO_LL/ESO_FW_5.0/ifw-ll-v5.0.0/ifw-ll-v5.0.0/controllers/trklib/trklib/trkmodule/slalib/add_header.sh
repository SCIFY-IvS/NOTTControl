header="#include \"../TcPch.h\"\n#pragma hdrstop\n"

for file in "$@"
do
    sed -i -e "1i\
$header" $file
done
