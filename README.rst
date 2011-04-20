This is a debug toolbar panel for adding couch trace/performance logging


Setting up:

In your settings.py, INSTALLED_APPS, add:
    'debug_toolbar', #the debug toolbar is required for this to work.
    'couchdebugpanel',

In your DEBUG_TOOLBAR_PANELS, add:
   'couchdebugtoolbar.CouchDBLoggingPanel'
   #you should also consider disabling the LoggingPanel because couchdbkit/restkit uses extensive logging by default.  Either suppress the logging level on couchdbkit or just disable this panel, or adjusting restkit and couchdbkit's debug levels manually so as to not overload the LoggingPanel


In your settings_local, under LOCAL_APP_URLS, add this line:
    (r'', include('couchdebugpanel.urls')),

    This is because the debug toolbar doesn't scan for other panel URLs, though this may change.

Finally, this plugin has a bit of javascript to render itself prettily like the debug toolbar

