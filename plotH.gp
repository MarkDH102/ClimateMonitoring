set term gif size 960,540
set output "/home/pi/MarksStuff/plot.gif"
#set title "".strftime("%A, %B %d, %Y", time(0) - (12*60*60))
#set ylabel "Humidity"
#set yrange [-10 : 50]
set timefmt "%H%M"
set xdata time
set xlabel "Time in hours (from midnight)"
#set xrange [0 : 1500]
plot "/home/pi/MarksStuff/plot.txt" using 0:1 with lines lw 2 title "Lounge", "/home/pi/MarksStuff/plot.txt" using 0:2 with lines lw 2 title "Bed", "/home/pi/MarksStuff/plot.txt" using 0:3 with lines lw 2 title "Garden"
exit
