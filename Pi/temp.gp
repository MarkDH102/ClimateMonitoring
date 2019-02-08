set term png size 1920,1080
set output "file.png"
set title "".strftime("%A, %B %d, %Y", time(0) - (12*60*60))
set ytics nomirror
set y2tics nomirror
set timefmt "%H%M"
set xdata time
set xrange [0 : 1500]
set x2range[0 : 1500]
set y2range[0 : 100]
plot "data.txt" using 0:1 with lines lw 2 title "Shed" axes x1y1, "data.txt" using 0:2 with lines lw 2 title "Lounge" axes x1y1, "data.txt" using 0:6 with lines lw 2 title "Bed" axes x1y1, "data.txt" using 0:8 with lines lw 2 title "Garden" axes x1y1, "data.txt" using 0:17 with lines lw 2 title "Attic" axes x1y1, "data.txt" using 0:5 with lines lw 2 title "CPU" axes x1y1 
exit
