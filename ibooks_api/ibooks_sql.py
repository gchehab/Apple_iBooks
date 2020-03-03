#!/usr/bin/python
# -*- coding=utf-8 -*-
from os import path, remove
from shutil import copy2

import sys
import zlib
import hashlib

from datetime import datetime, timedelta
from uuid import uuid5, NAMESPACE_X500
# import re
from pprint import pprint

from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, MetaData, Table, Column, ForeignKey, types, \
    event, TypeDecorator, Unicode, or_, text, func
from sqlalchemy.inspection import inspect

from calibre_plugins.apple_ibooks.config import prefs

class CoerceUTF8(TypeDecorator):
    """Safely coerce Python bytestrings to Unicode
    before passing off to the database."""

    impl = Unicode

    def process_bind_param(self, value, dialect):
        if isinstance(value, str):
            value = value.decode('utf-8')
        return value


class MyEpochType(types.TypeDecorator):
    """ Fix for timestamps - decorator"""
    impl = types.Integer

    epoch = datetime(2001, 1, 1, 0, 0, 0)

    def process_bind_param(self, value, dialect):
        try:
            result = (value - self.epoch).total_seconds()
            return result
        except Exception:
            return value

    def process_result_value(self, value, dialect):
        try:
            result = self.epoch + timedelta(seconds=value)
            return result
        except Exception:
            return value


@event.listens_for(Table, "column_reflect")
def setup_epoch(inspector, table, column_info):
    """ Fix for timestamps - event listener when reflecting automap """
    if isinstance(column_info['type'], types.DateTime):
        column_info['type'] = MyEpochType()


def update_pks(session, base):
    try:
        session.flush()
        pks = session.query(base.classes.Z_PRIMARYKEY).all()
        if prefs['debug']:
            print (str(datetime.now()) + ": Update pks for " + str(len(pks)) + " tables")
        for pk in pks:
            z_name = pk.Z_NAME
            class_name = "Z" + str(z_name).upper()
            max_pk = session.query(func.max(base.classes[class_name].Z_PK)).limit(1).all()[0][0]
            pk.Z_MAX = max_pk if max_pk is not None else 0
            if prefs['debug']:
                print ("\tPk for " + z_name + " is " + str(max_pk))
            session.add(pk)
        session.flush()

    except Exception:
        print (sys.exc_info()[0])
        session.rollback()


class BkLibraryDb:
    """Create class to access BKLibrary DB"""

    def __init__(self):
        try:
            """ Todo: Create autodetection of BKLibrary sqlite file """
            #IBOOKS_BKLIBRARY_CATALOG = "BKLibrary/BKLibrary-1-091020131601.sqlite"
            #IBOOKS_BKLIBRARY_CATALOG_FILE = path.join(IBOOKS_BKLIBRARY_PATH, IBOOKS_BKLIBRARY_CATALOG)
            IBOOKS_BKLIBRARY_CATALOG_FILE = prefs['dbbookcatalog']

            self.__engine = create_engine("sqlite:///" + IBOOKS_BKLIBRARY_CATALOG_FILE) #, echo='debug')
            metadata = MetaData()
            metadata.reflect(self.__engine)

            self.__base = automap_base(metadata=metadata)
            self.__base.prepare()

            # """ Auto detect relationships """
            # fkeys = {}
            # for table in metadata.sorted_tables:
            #     for column in table.columns:
            #         if (re.match ('\S+ID$', column.name) is not None):
            #             if (column.name not in fkeys):
            #                 fkeys[column.name] = []
            #             fkeys[column.name].append(table.name)
            #             if (len(fkeys[column.name]) > 1):
            #                 print (table.name, column.name)
            # for column in fkeys:
            #     if (len(fkeys[column]) > 1):
            #         pprint(fkeys[column])

            # for mapped_class in self.base.classes:
            #     print (mapped_class)
            #     relations = inspect(mapped_class).relationships.items()
            #     print (relations)

            self.__session = Session(self.__engine)
            self.has_changed = 0
            self.has_backup = False
        except Exception:
            print (sys.exc_info()[0])
            raise


    def __del__(self):
        # self.commit()
        del self.__session
        del self.__base
        del self.__engine

    def rollback(self):
        try:
            self.__session.rollback()
            update_pks(self.__session, self.__base)
            self.has_changed = 0
            if prefs['backup'] and self.has_backup:
                for file in ['dbbookcatalog']:
                    if prefs['debug']:
                        print (str(datetime.now()) + ": Rolling back " + filename)
                    copy2(prefs[file] + ".bkp", prefs[file])
                    remove(prefs[file] + ".bkp")
                self.has_backup = False
        except Exception:
            print (sys.exc_info()[0])
            self.__session.rollback()
            self.has_changed = 0

    def commit(self):
        try:
            if self.has_changed:
                if prefs['backup'] and not self.has_backup:
                    for filename in ['dbbookcatalog']:
                        if prefs['debug']:
                            print (str(datetime.now()) + ": Backing up " + filename)
                        copy2(prefs[filename], prefs[filename] + ".bkp")
                    self.has_backup = True
                update_pks(self.__session, self.__base)
                self.__session.flush()
                self.__session.commit()
                self.has_changed = 0

        except Exception:
            print (sys.exc_info()[0])
            self.__session.rollback()
            self.has_changed=0

    def list_books(self):
        """List all books in iBooks"""
        try:
            return (self.__session.query(self.__base.classes.ZBKLIBRARYASSET)).all()
        except Exception:
            print (sys.exc_info()[0])
            raise


    def add_book(self, book_id=None, title=None, filepath=None, author=None, collection_name=None,
                 asset_id=None, size=None, series_name=None, series_id=None, series_number=None, genre=None):
        """Add or update a book to the asset list in iBooks"""
        try:

            # pk_bklibraryasset = self.__session.query(self.__base.classes.Z_PRIMARYKEY).filter(
            #     self.__base.classes.Z_PRIMARYKEY.Z_NAME == 'BKLibraryAsset'
            # ).limit(1).all()[0]
            #
            # pk_bkcollectionmember = self.__session.query(self.__base.classes.Z_PRIMARYKEY).filter(
            #     self.__base.classes.Z_PRIMARYKEY.Z_NAME == 'BKCollectionMember'
            # ).limit(1).all()[0]

            # Create collections for series and collection

            # Todo: add new collections for each tag or category

            new_collection = self.create_collection(collection_name=u"Calibre", collection_id=u'All_Calibre_ID')

            if series_name is not None:
                new_collection = self.create_collection(collection_name=series_name)
                self.__session.add(new_collection)
                self.__session.flush()

            if collection_name is not None:
                new_collection = self.create_collection(collection_name=collection_name)
                self.__session.add(new_collection)
                self.__session.flush()

            default_collection_id = u'Pdfs_Collection_ID' if ".pdf" in filepath.lower() else u'Books_Collection_ID'
            result = self.__session.query(self.__base.classes.ZBKCOLLECTION).filter(
                self.__base.classes.ZBKCOLLECTION.ZCOLLECTIONID == default_collection_id
            ).limit(1).all()

            if len(result):
                default_collection = result[0]

            collections = self.__session.query(self.__base.classes.ZBKCOLLECTION).filter(
                or_(
                    self.__base.classes.ZBKCOLLECTION.ZCOLLECTIONID == u'All_Collection_ID',
                    self.__base.classes.ZBKCOLLECTION.ZCOLLECTIONID == default_collection_id,
                    self.__base.classes.ZBKCOLLECTION.ZCOLLECTIONID == u'All_Calibre_ID',
                    self.__base.classes.ZBKCOLLECTION.ZTITLE == collection_name,
                    self.__base.classes.ZBKCOLLECTION.ZTITLE == series_name,
                )
            )

            # Check if file already on catalog, if so check if it is on the same collection
            result = self.__session.query(self.__base.classes.ZBKLIBRARYASSET).filter_by(
                ZASSETID=asset_id
            ).all()

            if len(result):
                if prefs['debug']:
                    print (str(datetime.now()) + ": Book already exists, updating database")
                new_book = result[0]
                new_book.ZAUTHOR = author
                new_book.ZSERIESID = series_id
                new_book.ZCOMMENTS = 'Calibre #' + str(book_id)
                new_book.ZSERIESSORTKEY = series_number

                self.__session.add(new_book)
                self.__session.flush()

            else:
                if prefs['debug']:
                    print (str(datetime.now()) + ": Book is new, adding to database")
                new_book = self.__base.classes.ZBKLIBRARYASSET(
                    Z_OPT=1,
                    Z_ENT=5,
                    # ZCANREDOWNLOAD=0,
                    ZCONTENTTYPE=1,
                    ZCOMMENTS='Calibre #' + str(book_id),
                    # ZDESKTOPSUPPORTLEVEL=0,
                    # ZDIDWARNABOUTDESKTOPSUPPORT=0,
                    ZTITLE=title,
                    ZSORTTITLE=title,
                    ZFILESIZE=size,
                    ZGENERATION=1,
                    # ZISDEVELOPMENT=0,
                    # ZISEPHEMERAL=0,
                    # ZISHIDDEN=0,
                    # ZISLOCKED=0,
                    # ZISPROOF=0,
                    # ZISSAMPLE=0,
                    ZISNEW=1,
                    # ZPAGECOUNT=0,
                    # ZRATING=0,
                    ZSERIESID=series_id,
                    ZSERIESSORTKEY=series_number,
                    ZSORTKEY=int(10000 + (0 if series_number is None else series_number)),
                    ZSTATE=1,
                    ZBOOKHIGHWATERMARKPROGRESS='0.0',
                    ZCREATIONDATE=datetime.fromtimestamp(path.getmtime(filepath)),
                    ZMODIFICATIONDATE=datetime.now(),
                    ZLASTOPENDATE=-63114076800,
                    ZVERSIONNUMBER='0.0',
                    ZASSETID=asset_id if asset_id is not None else str(
                        uuid5(NAMESPACE_X500, (title + author).encode('ascii', 'ignore'))).upper(),
                    ZGENRE=genre,
                    ZDATASOURCEIDENTIFIER='com.apple.ibooks.plugin.Bookshelf.platformDataSource.BookKit',
                    ZAUTHOR=author,
                    ZSORTAUTHOR=author,
                    ZPATH=filepath,
                    # ZCOVERURL='file:/tmp/cover.jpg'
                )

                if hasattr(self.__base.classes.ZBKLIBRARYASSET,'ZBOOKTYPE'):
                    new_book.ZBOOKTYPE=1

                if hasattr(self.__base.classes.ZBKLIBRARYASSET,'ZSERIESCONTAINER'):
                    new_book.ZSERIESCONTAINER=series_id

                # Seems to enable proper series grouping, however creates a lot of issues with book deletion
                if hasattr(self.__base.classes.ZBKLIBRARYASSET,'ZSTOREID'):
                    new_book.ZSTOREID=0 # asset_id

                if hasattr(self.__base.classes.ZBKLIBRARYASSET,'ZCOLLECTIONID'):
                    if collection_name is not None:
                        new_book.ZCOLLECTIONID = new_collection.ZCOLLECTIONID
                else:
                    new_book.ZCOLLECTIONID = default_collection.ZCOLLECTIONID

                self.__session.add(new_book)
                self.__session.flush()
                self.has_changed=1

                # pk_bklibraryasset.Z_MAX = new_book.Z_PK
                # self.__session.add(pk_bklibraryasset)
                # self.__session.flush()

            for collection in collections:
                if prefs['debug']:
                    print (str(datetime.now()) + ": Adding book to collection: " + collection.ZTITLE)
                collection_membership = self.__session.query(self.__base.classes.ZBKCOLLECTIONMEMBER).filter_by(
                    ZASSETID=asset_id,
                    ZCOLLECTION=collection.Z_PK
                ).all()
                if not len(collection_membership):
                    new_collection_member = self.__base.classes.ZBKCOLLECTIONMEMBER(
                        Z_OPT=1,
                        Z_ENT=3,
                        ZSORTKEY=int(10000 + (0 if series_number is None else series_number)),
                        ZCOLLECTION=collection.Z_PK,
                        ZASSETID=new_book.ZASSETID
                    )
                    if hasattr(self.__base.classes.ZBKCOLLECTIONMEMBER, 'ZASSET'):
                        new_collection_member.ZASSET = new_book.Z_PK

                    self.__session.add(new_collection_member)
                    self.__session.flush()
                    self.has_changed=1
                    #
                    # pk_bkcollectionmember.Z_MAX = new_collection_member.Z_PK
                    # self.__session.add(pk_bkcollectionmember)
                    # self.__session.flush()

            # self.__session.commit()
            return new_book
        except Exception:
            self.__session.rollback()
            print (sys.exc_info()[0])
            raise

    def del_all_books_from_calibre(self):
        try:
            books = self.__session.query(self.__base.classes.ZBKLIBRARYASSET).filter(
                self.__base.classes.ZBKLIBRARYASSET.ZCOMMENTS.like("Calibre #%")
            )

            asset_ids = [book.ZASSETID for book in books]
            series_ids = [book.ZSERIESID for book in books] if\
                hasattr(self.__base.classes.ZBKLIBRARYASSET,'ZSERIESID') else []
            collection_ids = [book.ZCOLLECTIONID for book in books] if\
                hasattr(self.__base.classes.ZBKLIBRARYASSET, 'ZCOLLECTIONID') else []

            count=0
            for book in books:
                self.__session.delete(book)
                count+=1

            for asset_id in asset_ids:
                books = self.__session.query(self.__base.classes.ZBKCOLLECTIONMEMBER).filter_by(
                    ZASSETID=asset_id
                )
                for book in books:
                    collections = self.__session.query(self.__base.classes.ZBKCOLLECTION).filter_by(
                        Z_PK=book.ZCOLLECTION,
                        Z_ENT=1
                    )

                    self.__session.delete(book)
                    self.has_changed = 1

                    # Delete empty collections
                    for collection in collections:
                        book_count = self.__session.query(self.__base.classes.ZBKCOLLECTIONMEMBER).filter_by(
                            ZCOLLECTION=collection.Z_PK
                        ).count()

                        if book_count == 0:
                            if prefs['debug']:
                                print (str(datetime.now()) + ": Delete Empty collection " + collection.ZTITLE)
                            self.__session.delete(collection)

            # Delete empty collections
            for collection_id in collection_ids:
                collections = self.__session.query(self.__base.classes.ZBKCOLLECTION).filter_by(
                    ZCOLLECTIONID=collection_id,
                    Z_ENT=1
                )

                for collection in collections:
                    book_count = self.__session.query(self.__base.classes.ZBKCOLLECTIONMEMBER).filter_by(
                        ZCOLLECTION=collection.Z_PK,
                    ).count()

                    if book_count==0:
                        if prefs['debug']:
                            print (str(datetime.now()) + ": Delete Empty collection " + collection.ZTITLE)
                        self.__session.delete(collection)
                        self.has_changed = 1

            # Todo: reset primary keys to max of remaining itens

            self.__session.flush()
            if prefs['debug']:
                print str(datetime.now()) + ": Books in library assets table: " + str(count)
                print str(datetime.now()) + ": Books in collection member table: " + str(len(asset_ids))
            return len(asset_ids)

        except Exception:
            self.__session.rollback()
            print (sys.exc_info()[0])
            raise


    def list_colections(self):
        """List all collections in iBooks"""
        try:
            return (self.__session.query(self.__base.classes.ZBKCOLLECTION)).all()
        except Exception:
            print (sys.exc_info()[0])
            raise

    def create_collection(self, collection_name=None, collection_id=None):
        try:
            if (collection_name == None):
                raise ("Cannot create collection without name")

            result = self.__session.query(self.__base.classes.ZBKCOLLECTION).filter_by(
                ZTITLE=collection_name
            ).all()

            if (len(result)):
                if (result[0].ZDELETEDFLAG == 1):
                    result[0].ZDELETEDFLAG = 0
                    self.__session.commit()
                return result[0]
            else:
                new = self.__base.classes.ZBKCOLLECTION(
                    Z_OPT=1,
                    Z_ENT=1,
                    ZTITLE=collection_name,
                    ZCOLLECTIONID=collection_id if collection_id is not None else
                        str(uuid5(NAMESPACE_X500, collection_name.encode('ascii', 'ignore'))).upper(),
                    ZLASTMODIFICATION=datetime.now(),
                    ZDELETEDFLAG=0,
                    ZSORTKEY=10000,
                )
                self.__session.add(new)
                self.__session.flush()

                pk_bkcollection = self.__session.query(self.__base.classes.Z_PRIMARYKEY).filter(
                    self.__base.classes.Z_PRIMARYKEY.Z_NAME == 'BKCollection'
                ).limit(1).all()[0]

                pk_bkcollection.Z_MAX = new.Z_PK
                self.__session.add(pk_bkcollection)
                self.__session.flush()
                self.has_changed=1

                return new

        except Exception:
            self.__session.rollback()
            print (sys.exc_info()[0])
            raise

    def delete_collection(self, title=None):
        try:
            if title == None:
                raise ("Cannot delete collection without name")

            result = self.__session.query(self.__base.classes.ZBKCOLLECTION).filter_by(
                ZTITLE=title
            ).all()

            if len(result):
                #self.__session.begin_nested()

                # Update all books from collection returning them to the default collection

                # Delete logically the collection
                if result[0].ZDELETEDFLAG == 0:
                    result[0].ZDELETEDFLAG = 1
                    self.__session.add(result[0])
                    self.__session.flush()
                    self.has_changed=1
                    return 0
                else:
                    raise ("No collection named " + title + " to delete")

            # Todo: reset primary keys to max of remaining itens

        except Exception:
            self.__session.rollback()
            print (sys.exc_info()[0])
            raise


class BkSeriesDb:
    """Create class to access BKSeries DB"""

    def __init__(self):
        try:
            """ Todo: Create autodetection of BKSeries sqlite file """
            #IBOOKS_BKSERIES_CATALOG = "BKSeriesDatabase/BKSeries-1-012820141020.sqlite"
            #IBOOKS_BKSERIES_CATALOG_FILE = path.join(IBOOKS_BKLIBRARY_PATH, IBOOKS_BKSERIES_CATALOG)
            IBOOKS_BKSERIES_CATALOG_FILE = prefs['dbseriescatalog']

            self.__engine = create_engine("sqlite:///" + IBOOKS_BKSERIES_CATALOG_FILE) #, echo='debug')
            metadata = MetaData()
            metadata.reflect(self.__engine)

            self.__base = automap_base(metadata=metadata)
            self.__base.prepare()

            # """ Auto detect relationships """
            # fkeys = {}
            # for table in metadata.sorted_tables:
            #     for column in table.columns:
            #         if (re.match ('\S+ID$', column.name) is not None):
            #             if (column.name not in fkeys):
            #                 fkeys[column.name] = []
            #             fkeys[column.name].append(table.name)
            #             if (len(fkeys[column.name]) > 1):
            #                 print (table.name, column.name)
            # for column in fkeys:
            #     if (len(fkeys[column]) > 1):
            #         pprint(fkeys[column])

            # for mapped_class in self.base.classes:
            #     print (mapped_class)
            #     relations = inspect(mapped_class).relationships.items()
            #     print (relations)

            self.__session = Session(self.__engine)
            self.has_changed = 0
            self.has_backup = False
        except Exception:
            print (sys.exc_info()[0])
            raise

    def __del__(self):
        # self.commit()
        del self.__session
        del self.__base
        del self.__engine

    def rollback(self):
        try:
            self.__session.rollback()
            update_pks(self.__session, self.__base)
            self.has_changed = 0
            if prefs['backup'] and self.has_backup:
                for filename in ['dbbookcatalog']:
                    if prefs['debug']:
                        print (str(datetime.now()) + ": Rolling back " + filename)
                    copy2(prefs[filename] + ".bkp", prefs[filename])
                    remove(prefs[filename] + ".bkp")
                self.has_backup = False
        except Exception:
            print (sys.exc_info()[0])
            self.__session.rollback()
            self.has_changed = 0

    def commit(self):
        try:
            if self.has_changed:
                if prefs['backup'] and not self.has_backup:
                    for filename in ['dbseriescatalog']:
                        if prefs['debug']:
                            print (str(datetime.now()) + ": Backing up " + filename)
                        copy2(prefs[filename], prefs[filename] + ".bkp")
                    self.has_backup = True
                update_pks(self.__session, self.__base)
                self.__session.flush()
                self.__session.commit()
                self.has_changed=0

        except Exception:
            print (sys.exc_info()[0])
            self.has_changed=0
            self.__session.rollback()

    def list_series_items(self):
        """List all series in iBooks"""
        try:
            return (self.__session.query(self.__base.classes.ZBKSERIESITEM)).all()
        except Exception:
            print (sys.exc_info()[0])
            raise

    def add_book_to_series(self, series_name=None, series_id=None, series_number=None,
                           is_explicit=None, popularity=None, adam_id=None, author=None,
                           genre=None, sequence_display_name=None, title=None):
        """Add or update a book to a series in iBooks"""
        try:
            sequence_display_name = series_name
            parent_id = series_id
            is_container = 1

            for name in [series_name, series_name + str(series_number)]:
                # Add or update series metadata
                result = self.__session.query(self.__base.classes.ZBKSERIESCHECK).filter_by(
                    ZADAMID=series_id
                ).all()
                if len(result):
                    new_series_checked = result[0]
                    new_series_checked.ZDATECHECKED = datetime.now()
                else:
                    new_series_checked = self.__base.classes.ZBKSERIESCHECK(
                        Z_OPT=1 if is_container == 0 else 3,
                        Z_ENT=1,
                        ZDATECHECKED=datetime.now(),
                        ZADAMID=series_id,
                    )

                result = self.__session.query(self.__base.classes.ZBKSERIESITEM).filter_by(
                    ZADAMID=series_id,
                    ZISCONTAINER=is_container,
                    ZSERIESADAMID=parent_id
                ).all()
                if len(result):
                    new_series_item = result[0]
                    new_series_item.ZISCONTAINER = is_container
                    new_series_item.ZISEXPLICIT = is_explicit
                    new_series_item.ZPOSITION = 0 if is_container == 1 else series_number
                    new_series_item.ZPOPULARITY = popularity
                    new_series_item.ZADAMID = series_id
                    new_series_item.ZAUTHOR = author
                    new_series_item.ZGENRE = genre
                    new_series_item.ZSEQUENCEDISPLAYNAME = None if is_container == 1 else sequence_display_name
                    new_series_item.ZSERIESADAMID = parent_id
                    new_series_item.ZSERIESTITLE = series_name
                    new_series_item.ZSORTAUTHOR = author
                    new_series_item.ZSORTTITLE = series_name if is_container == 1 else title
                    new_series_item.ZTITLE = series_name if is_container == 1 else title
                else:
                    new_series_item = self.__base.classes.ZBKSERIESITEM(
                        Z_OPT=1,
                        Z_ENT=2,
                        ZISCONTAINER=is_container,
                        ZISEXPLICIT=is_explicit,
                        ZPOSITION=0 if is_container == 1 else series_number,
                        ZPOPULARITY=popularity,
                        ZADAMID=series_id,
                        ZAUTHOR=author,
                        ZGENRE=genre,
                        ZSEQUENCEDISPLAYNAME=None if is_container == 1 else sequence_display_name,
                        ZSERIESADAMID=parent_id,
                        ZSERIESTITLE=series_name,
                        ZSORTAUTHOR=author,
                        ZSORTTITLE=series_name if is_container == 1 else title,
                        ZTITLE=series_name if is_container == 1 else title
                    )

                self.__session.add(new_series_checked)
                self.__session.add(new_series_item)
                self.__session.flush()
                self.has_changed = 1

                # Update indices
                # pk_bkseriescheck = self.__session.query(self.__base.classes.Z_PRIMARYKEY).filter(
                #     self.__base.classes.Z_PRIMARYKEY.Z_NAME == 'BKSeriesCheck'
                # ).limit(1).all()[0]
                #
                # pk_bkseriescheck.Z_MAX = new_series_checked.Z_PK
                # self.__session.add(pk_bkseriescheck)

                # pk_bkseriesitem = self.__session.query(self.__base.classes.Z_PRIMARYKEY).filter(
                #     self.__base.classes.Z_PRIMARYKEY.Z_NAME == 'BKSeriesItem'
                # ).limit(1).all()[0]
                #
                # pk_bkseriesitem.Z_MAX = new_series_item.Z_PK
                # self.__session.add(pk_bkseriesitem)

                # self.__session.flush()

                is_container = 0
                parent_id = series_id
                series_id = adam_id
                sequence_display_name = series_name + ' - ' + str(series_number + 1)

            return None
        except Exception:
            self.__session.rollback()
            print (sys.exc_info()[0])
            raise

    def del_book_from_series(self, adam_id=None):
        """Delete a book from a series in iBooks"""
        try:
            if (adam_id is None):
                return None
            else:
                books = self.__session.query(self.__base.classes.ZBKSERIESITEM).filter_by(
                    ZADAMID=adam_id
                )
                series_ids = [book.ZSERIESADAMID for book in books]

                for book in books:
                    self.__session.delete(book)

                books = self.__session.query(self.__base.classes.ZBKSERIESCHECK).filter_by(
                    ZADAMID=adam_id
                )
                for book in books:
                    if prefs['debug']:
                        print(str(datetime.now()) + ": Deleting book " + book.ZADAMID + " from series DB")
                    self.__session.delete(book)
                    self.has_changed=1

                # Delete empty series
                for series_id in series_ids:
                    series_itens = self.__session.query(self.__base.classes.ZBKSERIESITEM).filter_by(
                        ZSERIESADAMID=series_id,
                    ).all()
                    if len (series_itens) == 1:
                        for series_item in series_itens:
                            series_checks = self.__session.query(self.__base.classes.ZBKSERIESCHECK).filter_by(
                                ZADAMID = series_id
                            ).all()
                            for series_check in series_checks:
                                self.__session.delete(series_check)
                            self.__session.delete(series_item)

                # Todo: reset primary keys to max of remaining itens / checks

                self.__session.flush()
        except Exception:
            self.__session.rollback()
            print (sys.exc_info()[0])
            raise

