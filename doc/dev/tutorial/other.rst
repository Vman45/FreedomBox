.. SPDX-License-Identifier: CC-BY-SA-4.0

Part 7: Other Changes
---------------------

Showing information about app clients
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It would be helpful to our users if we can show how they can use our app. If
there are desktop and mobile clients that can used to access our service, we
need to list them and present them. Let's add this information to
``manifest.py``.

.. code-block:: python3

  from plinth.clients import validate

  clients = validate([{
      'name': _('Transmission'),
      'platforms': [{
          'type': 'web',
          'url': '/transmission'
      }]
  }])

Since our app is a simple web application with no clients needed, we just list
that. We need to include this into the main app view. In ``__init__.py``, add:

.. code-block:: python3

   from .manifest import clients

   clients = clients

In ``views.py``, add:

.. code-block:: python3

  from plinth.modules import transmission

  class TransmissionAppView(views.AppView):
      ...
      clients = transmission.clients

Writing a manual page
^^^^^^^^^^^^^^^^^^^^^

The description of app should provide basic information on what the app is about
and how to use it. It is impractical, however, to explain everything about the
app in a few short paragraphs. So, we need to write a page about the app in the
FreedomBox manual. This page will be available to the users from within the
FreedomBox web interface. To make this happen, let us write a `manual page entry
<https://wiki.debian.org/FreedomBox/Manual/Transmission>`_ for our app in the
`FreedomBox Wiki <https://wiki.debian.org/FreedomBox/Manual>`_ and then provide
a link to it from app page. In ``__init__.py``, add:

.. code-block:: python3

  manual_page = 'Transmission'

Then, in ``views.py``, add:

.. code-block:: python3

  from plinth.modules import transmission

  class TransmissionAppView(views.AppView):
      ...
      manual_page = transmission.manual_page

Adding backup/restore functionality
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each app in FreedomBox needs to provide the ability to backup its configuration
and data. Apart from providing durability to users' data, this allows the user
to migrate from one machine to another. FreedomBox framework provides a simple
declarative mechanism to allow the app to be backed up and restored. In
``manifest.py``, add:

.. code-block:: python3

  from plinth.modules.backups.api import validate as validate_backup

  backup = validate_backup({
      'data': {
          'directories': ['/var/lib/transmission-daemon/.config']
      },
      'secrets': {
          'files': ['/etc/transmission-daemon/settings.json']
      },
      'services': ['transmission-daemon']
  })

The data and secrets information specifies which list of files and directories
FreedomBox framework needs to backup. The list of services specifies which
daemons should be stopped during the backup process. In ``__init__.py``, add:

.. code-block:: python3

  from .manifest import backup

Creating diagnostics
^^^^^^^^^^^^^^^^^^^^

When the app does not work as expected, the user should know what is happening
with the app. FreedomBox framework provides an API for running and showing
diagnostics results. Most of the common diagnostic tests are implemented by the
framework as part of the components used by an app. FreedomBox takes care of
calling the diagnostics method and displaying the list in a formatted manner.

To implement additional diagnostic tests on top of those provided by the
framework, the method :meth:`plinth.app.App.diagnose` has to be overridden or in
a component that belongs to the app, the method
:meth:`plinth.app.Component.diagnose` has to be overridden. The methods must
return a list in which each item is the result of a test performed. The item
itself is a two-tuple containing the display name of the test followed by the
result as ``passed``, ``failed`` or ``error``.

.. code-block:: python3

  class TransmissionAppView(views.AppView):
      ...
      def diagnose():
          """Run diagnostics and return the results."""
          results = super().diagnose()

          results.append(['Example test', 'passed'])

          return results

The user can trigger the diagnostics test by going to **System -> Diagnostics**
page. This runs diagnostics for all the applications. Users can also run
diagnostics specifically for this app from the app's page. A diagnostics menu
item is shown by the :class:`plinth.views.AppView` and `app.html` template
automatically when ``diagnose()`` method is overridden in the app or a
component.

Logging
^^^^^^^

Sometimes we may feel the need to write some debug messages to the console and
system logs. Doing this in FreedomBox is just like doing this any other Python
application.

.. code-block:: python3

  import logging

  logger = logging.getLogger(__name__)

  def example_method():
      logger.debug('A debug level message')

      logger.info('Showing application page - %s', request.method)

      try:
          something()
      except Exception as exception:
          # Print stack trace
          logger.exception('Encountered an exception - %s', exception)

For more information see Python :doc:`logging framework <howto/logging>`
documentation.

Internationalization
^^^^^^^^^^^^^^^^^^^^

Every string message that is visible to the user must be localized to user's
native language. For this to happen, our app needs to be internationalized. This
requires marking the user visible messages for translation. FreedomBox apps use
the Django's localization methods to make that happen.

.. code-block:: python3

  from django.utils.translation import ugettext_lazy as _

  name = _('Transmission')

  short_description = _('BitTorrent Web Client')

  description = [
      _('BitTorrent is a peer-to-peer file sharing protocol. '
        'Transmission daemon handles Bitorrent file sharing.  Note that '
        'BitTorrent is not anonymous.'),
      _('Access the web interface at <a href="/transmission">/transmission</a>.')
  ]

Notice that the app's name, description, etc. are wrapped in the ``_()`` method
call. This needs to be done for the rest of our app. We use the
:obj:`~django.utils.translation.ugettext_lazy` in some cases and we use the
regular :obj:`~django.utils.translation.ugettext` in other cases. This is
because in the second case the :obj:`~django.utils.translation.gettext` lookup
is made once and reused for every user looking at the interface. These users may
each have a different language set for their interface. Lookup made for one
language for a user should not be used for other users. The ``_lazy`` methods
provided by Django makes sure that the return value is an object that will
actually be converted to string at the final moment when the string is being
displayed. In the first case, the lookup is made and string is returned
immediately.

All of this is the usual way internationalization is done in Django. See
:doc:`Internationalization and localization <django:topics/i18n/index>`
documentation for more information.
