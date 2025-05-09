#!/bin/bash
PATH=/Applications/calibre.app/Contents/console.app/Contents/MacOS/:/Applications/calibre.app/Contents/MacOS/:$PATH

while [ `ps -ef | grep calibre-debug | grep -v grep | wc -l ` != "0" ]; do
	calibre-debug -s
	sleep 1
	kill -9 `ps -ef  | grep calibre | grep -v grep| tr -s ' '| cut -f 3 -d ' '`
done

find . -type l -delete
calibre-customize -b `pwd`
if [ -d ../calibre-src/src ] ; then
	for i in `echo ../calibre-src/src/*` ; do ln -s $i ;done
fi

#open /Applications/calibre.app
clear
echo ----- Restarting Calibre -----
calibre-debug -g &
sleep 2

while [ 1 ] ; do
	fswatch -v -0 -1 ./*.py ./ibooks_api/*.py ./requirements.txt
	while [ `ps -ef | grep calibre-debug | grep -v grep | wc -l ` != "0" ]; do
		calibre-debug -s 
		sleep 1
		kill -9 `ps -ef  | grep calibre | grep -v grep| tr -s ' '| cut -f 3 -d ' '`
	done
	find . -type l -delete
	calibre-customize -b `pwd`
	for i in `echo ../calibre-src/src/*` ; do ln -s $i ;done
	#open /Applications/calibre.app
	clear
	echo ----- Restarting Calibre -----
	calibre-debug -g &
	sleep 1
done

