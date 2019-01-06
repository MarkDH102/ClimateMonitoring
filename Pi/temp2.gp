set term png size 1920,1080
set output "file2.png"
set title "".strftime("%A, %B %d, %Y", time(0) - (12*60*60))
set ytics nomirror
set y2tics nomirror
set timefmt "%H%M"
set xdata time
set xrange [0 : 1500]
set x2range[0 : 1500]
set yrange[4 : 6.5]
plot "data.txt" using 0:13 with lines lw 2 title "Shed V" axes x1y1, "data.txt" using 0:14 with lines lw 2 title "Bed V" axes x1y1, "data.txt" using 0:15 with lines lw 2 title "Garden V" axes x1y1, "data.txt" using 0:16 with lines lw 2 title "Attic V" axes x1y1, "data.txt" using 0:4 with lines lw 2 title "House P" axes x2y2
exit
