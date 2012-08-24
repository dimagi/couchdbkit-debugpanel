#taken from the django debug toolbar sql panel
import SocketServer
import logging
import traceback
from debug_toolbar.panels.sql import reformat_sql, reformat_sql
import django
from django.conf import settings #your django settings
from django.utils.translation import ugettext_lazy as _
import os

from debug_toolbar.panels import DebugPanel
import threading
from django.template.loader import render_to_string
from django.views.debug import linebreak_iter
import couchdbkit
from couchdbkit import resource

# Figure out some paths
django_path = os.path.realpath(os.path.dirname(django.__file__))
socketserver_path = os.path.realpath(os.path.dirname(SocketServer.__file__))
class CouchThreadTrackingHandler(logging.Handler):
    def __init__(self):
        if threading is None:
            raise NotImplementedError("threading module is not available, \
                the logging panel cannot be used without it")
        logging.Handler.__init__(self)
        self.records = {} # a dictionary that maps threads to log records

    def emit(self, record):
        self.get_records().append(record)

    def get_records(self, thread=None):
        """
        Returns a list of records for the provided thread, of if none is provided,
        returns a list for the current thread.
        """
        if thread is None:
            thread = threading.currentThread()
        if thread not in self.records:
            self.records[thread] = []
        return self.records[thread]

    def clear_records(self, thread=None):
        if thread is None:
            thread = threading.currentThread()
        if thread in self.records:
            del self.records[thread]


def tidy_stacktrace(strace):
    """
    Clean up stacktrace and remove all entries that:
    1. Are part of Django (except contrib apps)
    2. Are part of SocketServer (used by Django's dev server)
    3. Are the last entry (which is part of our stacktracing code)
    """
    trace = []
    for s in strace[:-1]:
        s_path = os.path.realpath(s[0])
        if getattr(settings, 'DEBUG_TOOLBAR_CONFIG', {}).get('HIDE_DJANGO_SQL', True) \
            and django_path in s_path and not 'django/contrib' in s_path:
            continue
        if socketserver_path in s_path:
            continue
        trace.append((s[0], s[1], s[2], s[3]))
    return trace



handler = CouchThreadTrackingHandler()
logging.root.setLevel(logging.NOTSET)
logging.root.addHandler(handler)

class CouchDBLoggingPanel(DebugPanel):
    """adapted from the django debug toolbar's LoggingPanel.  Instead, intercept the couchdbkit restkit logging calls to make a tidier display of couchdb calls being made."""
    name = 'CouchDB'
    has_content = True

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self._offset = len(couchdbkit.client.Database._queries)
        self._couch_time = 0
        self._key_queries = []

    def title(self):
        return _("CouchDB")

    def nav_title(self):
        return _("CouchDB")

    def nav_subtitle(self):
        self._key_queries = couchdbkit.client.Database._queries[self._offset:]
        self._couch_time = sum([q['duration'] for q in self._key_queries])
        num_queries = len(self._key_queries)
        ## TODO l10n: use ngettext
        return "%d %s in %.2fms" % (
            num_queries,
            (num_queries == 1) and 'request' or 'requests',
            self._couch_time
        )

    def process_request(self, request):
        handler.clear_records()

    def get_and_delete(self):
        records = handler.get_records()
        handler.clear_records()
        return records

    def url(self):
        return ''


    def content(self):
        width_ratio_tally = 0
        for query in self._key_queries:
            query['view_params'] = query['params']
            try:
                query['width_ratio'] = (query['duration'] / self._couch_time) * 100
            except ZeroDivisionError:
                query['width_ratio'] = 0
            query['start_offset'] = width_ratio_tally
            width_ratio_tally += query['width_ratio']

        context = self.context.copy()
        context.update({
            'queries': self._key_queries,
            'couch_time': self._couch_time,
        })
        return render_to_string('couchdebugpanel/couch.html', context)





# -*- coding: utf-8 -
from datetime import  datetime
from couchdbkit.client import Database, ViewResults
from django.utils.hashcompat import sha_constructor


SQL_WARNING_THRESHOLD = getattr(settings, 'DEBUG_TOOLBAR_CONFIG', {}) \
                            .get('SQL_WARNING_THRESHOLD', 500)

UNKOWN_INFO = {}

DEFAULT_UUID_BATCH_COUNT = 1000

couch_view_queries = []

def process_key(key_obj):
   if isinstance(key_obj, list):
       key_obj = [unicode(x).encode('utf-8') for x in key_obj]
   else:
       key_obj = key_obj.encode('utf-8')
   return key_obj

class DebugDatabase(Database):
    _queries = []
    def debug_open_doc(self, docid, **params):
        """Get document from database

        Args:
        @param docid: str, document id to retrieve
        @param wrapper: callable. function that takes dict as a param.
        Used to wrap an object.
        @param **params: See doc api for parameters to use:
        http://wiki.apache.org/couchdb/HTTP_Document_API

        @return: dict, representation of CouchDB document as
         a dict.
        """
        #debug panel
        start = datetime.now()
        newparams = params.copy()
        #end debug panel


        ############################
        #Start Database.open_doc
        wrapper = None
        if "wrapper" in params:
            wrapper = params.pop("wrapper")
        elif "schema" in params:
            schema = params.pop("schema")
            if not hasattr(schema, "wrap"):
                raise TypeError("invalid schema")
            wrapper = schema.wrap

        docid = resource.escape_docid(docid)
        doc = self.res.get(docid, **params).json_body
        #End Database.open_doc
        #############################

        #############################
        #Debug Panel data collection
        stop = datetime.now()
        duration = ms_from_timedelta(stop - start)
        stacktrace = tidy_stacktrace(traceback.extract_stack())

        if wrapper is not None:
            view_path_display = "GET %s" % wrapper.im_self._doc_type
        else:
            view_path_display = "Raw GET"

        self._queries.append({
                'view_path': 'get',
                'view_path_safe': 'get',
                'view_path_display': view_path_display,
                'duration': duration,
                'params': {'docid' : docid},
                'hash': sha_constructor(settings.SECRET_KEY + str(newparams) + docid).hexdigest(),
                'stacktrace': stacktrace,
                'start_time': start,
                'stop_time': stop,
                'is_slow': (duration > SQL_WARNING_THRESHOLD),
		'total_rows': 1,
                #'is_cached': is_cached,
                #'is_reduce': sql.lower().strip().startswith('select'),
                #'template_info': template_info,
            })

        #end debug panel data collection
        ################################



        ##################################
        #Resume original Database.open_doc
        if wrapper is not None:
            if not callable(wrapper):
                raise TypeError("wrapper isn't a callable")

            return wrapper(doc)

        return doc
    get = debug_open_doc
couchdbkit.client.Database = DebugDatabase


class DebugViewResults(ViewResults):
    def fetch(self):
        """ Overrided 
        fetch results and cache them 
        """
        # reset dynamic keys
        for key in  self._dynamic_keys:
            try:
                delattr(self, key)
            except:
                pass
        self._dynamic_keys = []

        self._result_cache = self.fetch_raw().json_body
        self._total_rows = self._result_cache.get('total_rows')
        self._offset = self._result_cache.get('offset', 0)

        # add key in view results that could be added by an external
        # like couchdb-lucene
        for key in self._result_cache.keys():
            if key not in ["total_rows", "offset", "rows"]:
                self._dynamic_keys.append(key)
                setattr(self, key, self._result_cache[key])



    def foo_fetch_if_needed(self):
        #todo: hacky way of making sure unicode is not in the keys
        newparams = self.params.copy()
        if newparams.has_key('key'):
            newparams['key'] = process_key(newparams['key'])
        if newparams.has_key('startkey'):
            newparams['startkey'] = process_key(newparams['startkey'])
        if newparams.has_key('endkey'):
            newparams['endkey'] = process_key(newparams['endkey'])
        if newparams.has_key('keys'):
            newparams['keys'] = process_key(newparams['keys'])
        start = datetime.now()

        if not self._result_cache:
            self.fetch()

        stop = datetime.now()
        duration = ms_from_timedelta(stop - start)
        stacktrace = tidy_stacktrace(traceback.extract_stack())

        view_path_arr = self.view.view_path.split('/')
        view_path_arr.pop(0) #pop out the leading _design
        view_path_arr.pop(1) #pop out the middle _view
        view_path_display = '/'.join(view_path_arr)

        self.view._db._queries.append({
                'view_path': self.view.view_path,
                'view_path_safe': self.view.view_path.replace('/','|'),
                'view_path_display': view_path_display,
                'duration': duration,
                'params': newparams,
                'hash': sha_constructor(settings.SECRET_KEY + str(newparams) + str(self.view.view_path)).hexdigest(),
                'stacktrace': stacktrace,
                'start_time': start,
                'stop_time': stop,
                'is_slow': (duration > SQL_WARNING_THRESHOLD),
		'total_rows': len(self._result_cache.get('rows', [])),
                #'is_cached': is_cached,
                #'is_reduce': sql.lower().strip().startswith('select'),
                #'template_info': template_info,
            })


couchdbkit.client.ViewResults = DebugViewResults


def get_template_info(source, context_lines=3):
    line = 0
    upto = 0
    source_lines = []
    before = during = after = ""

    origin, (start, end) = source
    template_source = origin.reload()

    for num, next in enumerate(linebreak_iter(template_source)):
        if start >= upto and end <= next:
            line = num
            before = template_source[upto:start]
            during = template_source[start:end]
            after = template_source[end:next]
        source_lines.append((num, template_source[upto:next]))
        upto = next

    top = max(1, line - context_lines)
    bottom = min(len(source_lines), line + 1 + context_lines)

    context = []
    for num, content in source_lines[top:bottom]:
        context.append({
            'num': num,
            'content': content,
            'highlight': (num == line),
        })

    return {
        'name': origin.name,
        'context': context,
    }


def ms_from_timedelta(td):
    """
    Given a timedelta object, returns a float representing milliseconds
    """
    return (td.seconds * 1000) + (td.microseconds / 1000.0)
