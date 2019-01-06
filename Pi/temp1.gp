set term png size 1920,1080
set output "file1.png"
set title "".strftime("%A, %B %d, %Y", time(0) - (12*60*60))
set timefmt "%H%M"
set xdata time
plot "data.txt" using 0:3 with lines lw 2 title "Lounge" , "data.txt" using 0:7 with lines lw 2 title "Bed" , "data.txt" using 0:9 with lines lw 2 title "Garden"
exit
