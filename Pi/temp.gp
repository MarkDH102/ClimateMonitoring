set term png size 1920,1080
set output "file.png"
set title "".strftime("%A, %B %d, %Y", time(0) - (12*60*60))
set ytics nomirror
#set y2tics nomirror
set timefmt "%H%M"
set xdata time
set xrange [0 : 1500]
#set x2range[0 : 1500]
#set y2range[0 : 100]
set style line 5 lt rgb "black" lw 2
set style line 6 lt rgb "yellow" lw 2
set style line 7 lt rgb "red" lw 2
set style line 8 lt rgb "blue" lw 2
set style line 9 lt rgb "green" lw 2
set style line 10 lt rgb "cyan" lw 2
plot "data.txt" using 0:1 with lines ls 5 title "Shed" axes x1y1, \
"data.txt" using 0:2 with lines ls 6 title "Lounge" axes x1y1, \
"data.txt" using 0:6 with lines ls 7 title "Bed" axes x1y1, \
"data.txt" using 0:8 with lines ls 8 title "Garden" axes x1y1, \
"data.txt" using 0:17 with lines ls 9 title "Attic" axes x1y1, \
"data.txt" using 0:5 with lines ls 10 title "CPU" axes x1y1
exit
