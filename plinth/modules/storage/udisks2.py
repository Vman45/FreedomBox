# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Handle disk operations using UDisk2 DBus API.
"""

import logging
import threading

from plinth import actions
from plinth.errors import ActionError
from plinth.utils import import_from_gi

glib = import_from_gi('GLib', '2.0')
gio = import_from_gi('Gio', '2.0')

_DBUS_NAME = 'org.freedesktop.UDisks2'

_INTERFACES = {
    'Ata': 'org.freedesktop.UDisks2.Drive.Ata',
    'Block': 'org.freedesktop.UDisks2.Block',
    'Drive': 'org.freedesktop.UDisks2.Drive',
    'Filesystem': 'org.freedesktop.UDisks2.Filesystem',
    'Job': 'org.freedesktop.UDisks2.Job',
    'Manager': 'org.freedesktop.UDisks2.Manager',
    'ObjectManager': 'org.freedesktop.DBus.ObjectManager',
    'Partition': 'org.freedesktop.UDisks2.Partition',
    'Properties': 'org.freedesktop.DBus.Properties',
    'UDisks2': 'org.freedesktop.UDisks2',
}

_OBJECTS = {
    'drives': '/org/freedesktop/UDisks2/drives/',
    'jobs': '/org/freedesktop/UDisks2/jobs/',
    'Manager': '/org/freedesktop/UDisks2/Manager',
    'UDisks2': '/org/freedesktop/UDisks2',
}

_ERRORS = {
    'AlreadyMounted': 'org.freedesktop.UDisks2.Error.AlreadyMounted',
    'Failed': 'org.freedesktop.UDisks2.Error.Failed',
}

_jobs = {}

logger = logging.getLogger(__name__)


def _get_dbus_proxy(object_, interface):
    """Return a DBusProxy for a given UDisks2 object and interface."""
    connection = gio.bus_get_sync(gio.BusType.SYSTEM)
    return gio.DBusProxy.new_sync(connection, gio.DBusProxyFlags.NONE, None,
                                  _DBUS_NAME, object_, interface)


class Proxy:
    """Base methods for abstraction over UDisks2 DBus proxy objects."""
    interface = None
    properties = {}

    def __init__(self, object_path):
        """Return an object instance."""
        self.object_path = object_path
        self._proxy = _get_dbus_proxy(object_path, self.interface)

    def __getattr__(self, name):
        """Retrieve a property from underlying proxy or delegate."""
        if name not in self.properties:
            return getattr(self._proxy, name)

        signature, original_name = self.properties[name]
        value = self._proxy.get_cached_property(original_name)

        if value is None:
            return value

        if signature == 'ay':
            return bytes(value)[:-1].decode()

        if signature == 'aay':
            return [bytes(value_item).decode()[:-1] for value_item in value]

        if signature in ('s', 'b', 'o', 'u'):
            return glib.Variant.unpack(value)

        raise ValueError('Unhandled type')


class Drive(Proxy):
    """Abstraction for UDisks2 Drive."""
    interface = _INTERFACES['Drive']
    properties = {'id': ('s', 'Id')}


class BlockDevice(Proxy):
    """Abstraction for UDisks2 Block device."""
    interface = _INTERFACES['Block']
    properties = {
        'crypto_backing_device': ('o', 'CryptoBackingDevice'),
        'device': ('ay', 'Device'),
        'hint_ignore': ('b', 'HintIgnore'),
        'hint_system': ('b', 'HintSystem'),
        'id': ('s', 'Id'),
        'preferred_device': ('ay', 'PreferredDevice'),
        'symlinks': ('aay', 'Symlinks'),
    }


class Partition(Proxy):
    """Abstraction for UDisks2 Partition."""
    interface = _INTERFACES['Partition']
    properties = {
        'number': ('u', 'Number'),
    }


class Filesystem(Proxy):
    """Abstraction for UDisks2 Filesystem."""
    interface = _INTERFACES['Filesystem']
    properties = {'mount_points': ('aay', 'MountPoints')}


def _mount(object_path):
    """Start the mount operation on an block device.

    Runs in a separate thread from glib due to blocking operations.

    """
    filesystem = Filesystem(object_path)
    block_device = BlockDevice(object_path)
    if filesystem.mount_points:
        logger.info('Ignoring auto-mount on already mounted device: %s %s',
                    block_device.id, block_device.preferred_device)
        return

    logger.info('Auto-mounting device: %s %s', block_device.id,
                block_device.preferred_device)
    try:
        actions.superuser_run(
            'storage',
            ['mount', '--block-device', block_device.preferred_device],
            log_error=False)
    except ActionError as exception:
        parts = exception.args[2].split(':')
        if parts[1].strip() != 'GDBus.Error':
            raise

        if parts[2].strip() == _ERRORS['AlreadyMounted']:
            logger.warning('Device is already mounted: %s %s', block_device.id,
                           block_device.preferred_device)
        elif parts[2].strip() == _ERRORS['Failed']:
            logger.warning('Mount operation failed: %s %s: %s',
                           block_device.id, block_device.preferred_device,
                           exception)
        else:
            raise


def _on_job_created(object_path, interfaces_created):
    """Called when a job is created.

    Runs in glib thread. No blocking operations.

    """
    job = interfaces_created[_INTERFACES['Job']]
    if job['Operation'] == 'filesystem-mount':
        logger.info('Mounting operation started on disk: %s',
                    ', '.join(job['Objects']))
        _jobs[object_path] = job


def _on_job_removed(object_path):
    """Called when a job is completed.

    Runs in glib thread. No blocking operations.

    """
    if object_path in _jobs:
        logger.info('Mounting operation completed on disk: %s',
                    ', '.join(_jobs[object_path]['Objects']))


def _on_filesystem_added(object_path, _interfaces):
    """Called when a filesystem is added.

    Runs in glib thread. No blocking operations.

    """
    threading.Thread(target=_consider_for_mounting, args=[object_path]).start()


def _consider_for_mounting(object_path):
    """Check if the block device needs mounting and mount it."""
    block_device = BlockDevice(object_path)

    # Ignore non-block devices.
    if not block_device.device:
        logger.info('Ignoring non-block device, not auto-mounting %s',
                    object_path)
        return

    logger.info('New filesystem found: %s %s', block_device.id,
                block_device.preferred_device)

    # Ignore devices that are hinted by udev to ignore.
    if block_device.hint_ignore:
        logger.info(
            'Ignoring auto-mount of device due to udev ignore hint: %s %s',
            block_device.id, block_device.preferred_device)
        return

    # Ignore docker devices.
    for symlink in block_device.symlinks:
        if symlink.startswith('/dev/mapper/docker-') or \
           symlink.startswith('/dev/disk/by-id/dm-name-docker-'):
            logger.info('Ignoring auto-mount of docker device: %s %s',
                        block_device.id, block_device.preferred_device)
            return

    # Ignore non-external devices that don't have partition table (top-level
    # filesystem). If the device is backed by a crypto device, still handle it.
    # XXX: This rule is from udiskie. Should we keep it?
    partition = Partition(object_path)
    if block_device.hint_system and not partition.number and \
       block_device.crypto_backing_device == '/':
        logger.info('Ignoring auto-mount of top-level internal device: %s %s',
                    block_device.id, block_device.preferred_device)
        return

    _mount(object_path)


def _on_interfaces_added(_connection, _sender_name, _object_path,
                         _interface_name, _signal_name, parameters, _user_data,
                         _unknown):
    """Called when objects/interfaces have been added.

    Runs in glib thread. No blocking operations.

    """
    object_path, interfaces = parameters
    if object_path.startswith(_OBJECTS['jobs']):
        _on_job_created(object_path, interfaces)

    if _INTERFACES['Filesystem'] in interfaces:
        _on_filesystem_added(object_path, interfaces)


def _on_interfaces_removed(_connection, _sender_name, _object_path,
                           _interface_name, _signal_name, parameters,
                           _user_data, _unknown):
    """Called when objects/interfaces have been removed.

    Runs in glib thread. No blocking operations.

    """
    object_path, _interfaces = parameters
    if object_path.startswith(_OBJECTS['jobs']):
        _on_job_removed(object_path)


def _on_properties_changed(_connection, _sender_name, object_path,
                           _interface_name, _signal_name, parameters,
                           _user_data, _unknown):
    """Called when properties change on matching objects.

    Runs in glib thread. No blocking operations.

    """
    interface_changed, properties_changed, _properties_invalided = parameters
    if interface_changed == _INTERFACES['Ata'] and \
       'SmartFailing' in properties_changed:
        drive = Drive(object_path)
        thread = threading.Thread(
            target=_report_failing_drive,
            args=[drive.id, properties_changed['SmartFailing']])
        thread.start()


def _report_failing_drive(id_, is_failing):
    """Show or withdraw notification about failing drive."""
    if is_failing:
        logger.info('Drive %s is failing', id_)
    else:
        logger.info('Drive %s appears healthy', id_)

    from . import report_failing_drive
    report_failing_drive(id_, is_failing)


def _connect():
    """Connect to all necessary signals from UDisks2."""
    udisks = _get_dbus_proxy(_OBJECTS['UDisks2'], _INTERFACES['UDisks2'])
    connection = udisks.get_connection()

    connection.signal_subscribe(None, _INTERFACES['ObjectManager'],
                                'InterfacesAdded', _OBJECTS['UDisks2'], None,
                                gio.DBusSignalFlags.NONE, _on_interfaces_added,
                                None, None)
    connection.signal_subscribe(None, _INTERFACES['ObjectManager'],
                                'InterfacesRemoved', _OBJECTS['UDisks2'], None,
                                gio.DBusSignalFlags.NONE,
                                _on_interfaces_removed, None, None)
    connection.signal_subscribe(udisks.get_name(), _INTERFACES['Properties'],
                                'PropertiesChanged', None, None,
                                gio.DBusSignalFlags.NONE,
                                _on_properties_changed, None, None)


def _check_failing_drives():
    """Check if any of the drives are failing and report."""
    manager = _get_dbus_proxy(_OBJECTS['UDisks2'],
                              _INTERFACES['ObjectManager'])
    objects = manager.GetManagedObjects()
    for _, interface_and_properties in objects.items():
        if _INTERFACES['Drive'] in interface_and_properties and \
           _INTERFACES['Ata'] in interface_and_properties:
            _report_failing_drive(
                interface_and_properties[_INTERFACES['Drive']]['Id'],
                interface_and_properties[_INTERFACES['Ata']]['SmartFailing'])


def _mount_initial_devices():
    """Check if any of the block devices need mounting."""
    manager = _get_dbus_proxy(_OBJECTS['UDisks2'],
                              _INTERFACES['ObjectManager'])
    objects = manager.GetManagedObjects()
    for object_, interface_and_properties in objects.items():
        if _INTERFACES['Filesystem'] in interface_and_properties:
            _consider_for_mounting(object_)


def init(_data):
    """Subscribe to signals from UDisks2 and check for failing drives.

    Runs in a separate thread from glib thread due to blocking operations.

    """
    _connect()
    _check_failing_drives()
    _mount_initial_devices()
