#!/usr/bin/python
# -*- coding=utf-8 -*-

from pprint import pprint
from ibooks_api import IbooksApi
import datetime

ibooks = IbooksApi()

for book in ibooks.catalog['Books']:
    pprint(book)

print ("Colections:")
for collection in ibooks.list_collection():
    print(collection.ZCOLLECTIONID, collection.ZTITLE, collection.ZDELETEDFLAG, str(collection.ZLASTMODIFICATION))

print ("Current Books:")
for book in ibooks.list_books():
    print (book.ZASSETID, book.ZTITLE, book.ZAUTHOR)


# ibooks.AddCollection(u"Ficção Científica2")
#
# for collection in ibooks.ListCollection():
#     print(collection.ZCOLLECTIONID, collection.ZTITLE, collection.ZDELETEDFLAG, str(collection.ZLASTMODIFICATION))


#result = ibooks.add_book(
#    title=u"Quick Start Guide",
#    author=u"John Schember",
#    input_path=u"~/Calibre Library/John Schember/Quick Start Guide (1)/Quick Start Guide - John Schember.epub",
#    collection=u"Ficção Científica",
#     genre=u"Fiction"
# )
#
# result = ibooks.add_book(
#     title=u"Pride and prejudice 1",
#     author=u"Jane Austen",
#     input_path=u"~/Downloads/1342-pdf.pdf",
#     collection=u"Literatura",
#     genre=u"Fiction",
#     series_name=u'Orgulho',
#     series_number=1
# )

result = ibooks.add_book(
    title=u"Pride and prejudice 2",
    author=u"Jane Austen",
    input_path=u"~/Downloads/33283-pdf.pdf",
    collection=u"Literatura",
    genre=u"Fiction",
    series_name=u'Orgulho',
    series_number=2
)

print ("Add new book result:")
print (result)

print ("Deleting allbooks from calibre")
result = ibooks.del_all_books_from_calibre()
print ("Delete all books result:", result)