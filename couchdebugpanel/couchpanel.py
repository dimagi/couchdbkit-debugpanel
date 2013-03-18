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





