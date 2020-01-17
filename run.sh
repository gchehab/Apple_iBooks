#!/bin/bash
PATH=/Applications/calibre.app/Contents/console.app/Contents/MacOS/:$PATH

while [ `ps -ef | grep calibre-debug | grep -v grep | wc -l ` != "0" ]; do
	calibre-debug -s
	sleep 1
done

find . -type l -delete
calibre-customize -b `pwd`
for i in `echo ../calibre-src/src/*` ; do ln -s $i ;done
#open /Applications/calibre.app
clear
echo ----- Restarting Calibre -----
/Applications/calibre.app/Contents/calibre-debug.app/Contents/MacOS/calibre-debug -g &
sleep 2

while [ 1 ] ; do
	fswatch -v -0 -1 ./*.py ./ibooks_api/*.py
	while [ `ps -ef | grep calibre-debug | grep -v grep | wc -l ` != "0" ]; do
		calibre-debug -s 
		sleep 1
	done
	find . -type l -delete
	calibre-customize -b `pwd`
	for i in `echo ../calibre-src/src/*` ; do ln -s $i ;done
	#open /Applications/calibre.app
	clear
	echo ----- Restarting Calibre -----
	/Applications/calibre.app/Contents/calibre-debug.app/Contents/MacOS/calibre-debug -g &
	sleep 1
done

