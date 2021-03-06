.. SPDX-License-Identifier: CC-BY-SA-4.0

Part 4: Components
------------------

Each :class:`~plinth.app.App` contains various :class:`~plinth.app.Component`
components that each provide one small functionality needed by the app. Each of
these components are instantiated and added to the app as children.

Providing basic information about the app
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We need to provide some basic information about the application for the app to
function normally.

.. code-block:: python3

  from plinth import app as app_module

  class TransmissionApp(app_module.App):
      ...

      def __init__(self):
        ...

        info = app_module.Info(app_id=self.app_id, version=1,
                               name=_('Transmission'),
                               icon_filename='transmission',
                               short_description=_('BitTorrent Web Client'),
                               description=description,
                               manual_page='Transmission', clients=clients)
        self.add(info)

The first argument is app_id that is same as the ID for the app. The version is
the version number for this app that must be incremented whenever setup() method
needs to be called again. name, icon_filename, short_description, description,
manual_page and clients provide information that is shown on the app's main
page. More information the parameters is available in :class:`~plinth.app.Info`
class documentation.

Managing a daemon
^^^^^^^^^^^^^^^^^

Transmission, like many services in the FreedomBox, requires a daemon to be
running in the system to work. When the app is enabled, the daemon should be
enabled. When the app is disabled, the daemon should be disabled. We should also
show the status of whether the daemon is running in the app's view. All of these
concerns are automatically handled by the framework if a
:class:`~plinth.daemon.Daemon` component is added to the app. Let us do that in
our app's class.

.. code-block:: python3

  from plinth.daemon import Daemon

  managed_services = ['transmission-daemon']

  class TransmissionApp(app_module.App):
      ...

      def __init__(self):
        ...

        daemon = Daemon('daemon-transmission', managed_services[0],
                        listen_ports=[(9091, 'tcp4')])
        self.add(daemon)


The first argument to instantiate the :class:`~plinth.daemon.Daemon` class is a
unique ID. The second is the name of the `systemd
<https://www.freedesktop.org/wiki/Software/systemd/>`_ unit file which manages
the daemon. The final argument is the list of ports that this daemon listens on.
This information is used to check if the daemon is listening on the expected
ports when the user requests diagnostic tests on the app.

Managing web server configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Transmission provides a web interface to the user. This web interface needs to
be proxied through a web server for security and access control. We will need to
write a configuration snippet for Apache, the default web server on FreedomBox.
This configuration snippet needs to be activated when our app is enabled. The
configuration snippet needs to be deactivated when our app is disabled. All of
these concerns are automatically handled by the framework if a
:class:`~plinth.modules.apache.components.Webserver` component is added to the
app. Let us do that in our app's class.

.. code-block:: python3

  from plinth.modules.apache.components import Webserver

  class TransmissionApp(app_module.App):
      ...

      def __init__(self):
        ...

        webserver = Webserver('webserver-transmission', 'transmission-plinth'
                              urls=['https://{host}/transmission'])
        self.add(webserver)

The first argument to instantiate the
:class:`~plinth.modules.apache.components.Webserver` class is a unique ID. The
second is the name of the Apache2 web server configuration snippet that contains
the directives to proxy Transmission web interface via Apache2. We then need to
create the configuration file itself in ``tranmission-freedombox.conf``. The
final argument is the list of URLs that the app exposes to the users of the app.
This information is used to check if the URLs are accessible as expected when
the user requests diagnostic tests on the app.

.. code-block:: apache

  ## On all sites, provide Transmission on a default path: /transmission
  <Location /transmission>
      ProxyPass        http://localhost:9091/transmission
  </Location>

Managing the firewall
^^^^^^^^^^^^^^^^^^^^^

FreedomBox has a tight firewall that closes off all TCP/UDP ports by default. If
a service needs to available to users on a port, it needs to open the ports in
firewalld, the default firewall configuration manager in FreedomBox. When the
app is enabled, the ports need to opened and when the app is disabled, the ports
needs to be closed. The FreedomBox framework again provides a component for
handling these operations. In case of our app, there is no need to open a
special port since the web ports are always kept open. However, it is still good
to specify that we operate on http/https ports so that users can be provided
this information along with additional information on whether the service is
available over Internet. Create the
:class:`~plinth.modules.firewall.components.Firewall` component during app
initialization.

.. code-block:: python3

  from plinth.modules.firewall.components import Firewall

  class TransmissionApp(app_module.App):
      ...

      def __init__(self):
        ...

        firewall = Firewall('firewall-transmission', name,
                            ports=['http', 'https'], is_external=True)
        self.add(firewall)

The first parameter is a unique ID. Second one is the name of the app that as
shown to the user in the firewall status page. Third argument is the list of
services known to firewalld as listed in ``/usr/lib/firewalld/services/``.
Custom services can also be written. The final argument decides whether the
service should be made available by FreedomBox from external networks,
essentially the Internet.

User authentication and authorization
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We wish that only users of FreedomBox should access the web interface of our
app. Further, only users belonging to a specially created group are the only
ones who should be able access the app. Again, FreedomBox handles all of this
and we simply need to declare and use. First we need to register a user group
with the FreedomBox framework in ``__init.py__``.

.. code-block:: python3

  from plinth.modules.users.components import UsersAndGroups

  class TransmissionApp(app_module.App):
      ...

      def __init__(self):
          ...

          groups = { 'bit-torrent': _('Download files using BitTorrent applications') }
          users_and_groups = UsersAndGroups('users-and-groups-transmission',
                                            groups=groups)
          self.add(users_and_groups)


Then in the Apache configuration snippet, we can mandate that only users of this
group (and, of course, admin users) should be allowed to access our app. In the
file ``tranmission-freedombox.conf``, add the following.

.. code-block:: apache

  <Location /transmission>
      ...
      Include          includes/freedombox-single-sign-on.conf
      <IfModule mod_auth_pubtkt.c>
          TKTAuthToken "admin" "bit-torrent"
      </IfModule>
  </Location>

Showing a shortcut in the front page
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The app view we have created is only accessible by administrators of FreedomBox
since only they can configure the app. Other users who have access to this app
should have a way of discovering the app. This is done by providing a link in
the front page of FreedomBox web interface. This is the page that user's see
when they visit FreedomBox. To provide this shortcut, a
:class:`~plinth.frontpage.Shortcut` component can added to the app.

.. code-block:: python3

  from plinth import frontpage

  group = ('bit-torrent', 'Download files using BitTorrent applications')

  class TransmissionApp(app_module.App):
      ...

      def __init__(self):
          ...

          shortcut = frontpage.Shortcut(
              'shortcut-transmission', name, short_description=short_description,
              icon='transmission', url='/transmission', clients=clients,
              login_required=True, allowed_groups=[group[0]])
          self.add(shortcut)

The first parameter, as usual, is a unique ID. The next three parameters are
basic information about the app similar to the menu item. The URL parameter
specifies the URL that the user should be directed to when the shortcut is
clicked. This is the web interface provided by our app. The next parameter
provides a list of clients. This is useful for the FreedomBox mobile app when
the information is used to suggest installing mobile apps. This is described in
a later section of this tutorial. The next parameter specifies whether anonymous
users who are not logged into FreedomBox should be shown this shortcut. The
final parameter further restricts to which group of users this shortcut must be
shown.
