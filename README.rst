This is a debug toolbar panel for adding couch trace/performance logging

Setting up:

Make sure ``debug_toolbar`` is already working.

In your settings.py, INSTALLED_APPS, add:
::
    'debug_toolbar', #the debug toolbar is required for this to work.
    'couchdebugpanel',
    'dimagi.utils', #this will be removed in a later update

In your DEBUG_TOOLBAR_PANELS, add:
::
    'couchdebugpanel.CouchDBLoggingPanel'

If this isn't already defined, you'll need to explicitly pass in the full list of panels you want.  I recommend copying from https://django-debug-toolbar.readthedocs.org/en/latest/configuration.html#debug-toolbar-panels

(You should also consider disabling the LoggingPanel because couchdbkit/restkit uses extensive logging by default.  Either suppress the logging level on couchdbkit or just disable this panel, or adjusting restkit and couchdbkit's debug levels manually so as to not overload the LoggingPanel.)
