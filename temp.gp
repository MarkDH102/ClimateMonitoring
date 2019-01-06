set term png size 1920,1080
set output "file.png"
set title "".strftime("%A, %B %d, %Y", time(0) - (12*60*60))
set timefmt "%H%M"
set xdata time
plot "data.txt" using 0:1 with lines lw 2 title "Shed", "data.txt" using 0:2 with lines lw 2 title "Lounge" , "data.txt" using 0:6 with lines lw 2 title "Bed" , "data.txt" using 0:8 with lines lw 2 title "Garden", "data.txt" using 0:17 with lines lw 2 title "Attic", "data.txt" using 0:5 with lines lw 2 title "CPU"
exit
