PATH	:=	$(PATH):/Applications/calibre.app/Contents/console.app/Contents/MacOS/:/Applications/calibre.app/Contents/MacOS/
SHELL	:=	env PATH=$(PATH) /bin/bash

.PHONY: debug dist requirements

debug:
	calibre-customize -b .
	calibre-debug -g

requirements:
	(cd packages; rm -rvf *)
	pip3 download -r requirements.txt -d packages
	(cd packages; for f in `ls *.whl`; do unzip -oq $$f ; done)
	(cd packages; for f in `ls *.tar.gz`; do tar -xzf $$f; done)
	(cd packages; rm  -rfv SQLAlchemy-*)
	(cd packages; for i in `cat ../requirements.txt | grep -v  ^# | grep -v sqlalc`; do j=`echo $$i | tr -s "=" | tr "=" "-"`; rm -rfv $$j* ; done)
	

dist:
	mkdir -p dist
	if [ -f dist/Apple_iBookX355355s.zip ]; then rm dist/Apple_iBooks.zip; fi
	zip -r dist/Apple_iBooks.zip . -x@.zipignore
