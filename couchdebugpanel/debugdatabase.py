# -*- coding: utf-8 -
from datetime import  datetime
from couchdbkit.client import Database, ViewResults
from django.utils.hashcompat import sha_constructor


COUCH_WARNING_THRESHOLD = getattr(settings, 'DEBUG_TOOLBAR_CONFIG', {}).get('COUCH_WARNING_THRESHOLD', 500)

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
                'is_slow': (duration > COUCH_WARNING_THRESHOLD),
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
    def real_fetch(self):
        """ Original fetch function moved to here
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



    def fetch(self):
        """
        Overrided fetch with measurements
        """
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
            self.real_fetch()

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
                'is_slow': (duration > COUCH_WARNING_THRESHOLD),
		'total_rows': len(self._result_cache.get('rows', [])),
                #'is_cached': is_cached,
                #'is_reduce': sql.lower().strip().startswith('select'),
                #'template_info': template_info,
            })


couchdbkit.client.ViewResults = DebugViewResults


def ms_from_timedelta(td):
    """
    Given a timedelta object, returns a float representing milliseconds
    """
    return (td.seconds * 1000) + (td.microseconds / 1000.0)
