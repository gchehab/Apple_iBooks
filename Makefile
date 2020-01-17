.PHONY: debug dist

debug:
	calibre-customize -b .
	calibre-debug -g

dist:
	mkdir -p dist
	if [ -f dist/Apple_iBooks.zip ]; then rm dist/Apple_iBooks.zip; fi
	zip -r dist/Apple_iBooks.zip . -x@.zipignore
