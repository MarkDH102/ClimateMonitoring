set term png size 1920,1080
set output "file1.png"
set title "".strftime("%A, %B %d, %Y", time(0) - (12*60*60))
set timefmt "%H%M"
set xdata time
set style line 5 lt rgb "black" lw 2
set style line 6 lt rgb "yellow" lw 2
set style line 7 lt rgb "red" lw 2
set style line 8 lt rgb "blue" lw 2
set style line 9 lt rgb "green" lw 2
set style line 10 lt rgb "cyan" lw 2
plot "data.txt" using 0:20 with lines ls 5 title "Shed", \
"data.txt" using 0:3 with lines ls 6 title "Lounge", \
"data.txt" using 0:7 with lines ls 7 title "Bed", \
"data.txt" using 0:9 with lines ls 8 title "Garden", \
"data.txt" using 0:19 with lines ls 9 title "Attic", \
"data.txt" using 0:23 with lines ls 10 title "Light"
exit
