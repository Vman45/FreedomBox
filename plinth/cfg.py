# SPDX-License-Identifier: AGPL-3.0-or-later

import configparser
import logging
import os

logger = logging.getLogger(__name__)

box_name = None
root = None
file_root = None
config_dir = None
data_dir = None
custom_static_dir = None
store_file = None
actions_dir = None
doc_dir = None
host = None
port = None
use_x_forwarded_for = False
use_x_forwarded_host = False
secure_proxy_ssl_header = None
develop = False
server_dir = '/'

config_file = None

DEFAULT_CONFIG_FILE = '/etc/plinth/plinth.config'
DEFAULT_ROOT = '/'


def get_fallback_config_paths():
    """Get config paths of the current source code folder"""
    root_directory = os.path.dirname(os.path.realpath(__file__))
    root_directory = os.path.join(root_directory, '..')
    root_directory = os.path.realpath(root_directory)
    config_path = os.path.join(root_directory, 'plinth.config')
    return config_path, root_directory


def get_config_paths():
    """Get default config paths."""
    return '/etc/plinth/plinth.config', '/'


def read(config_path=None, root_directory=None):
    """
    Read configuration.

    - config_path: path of plinth.config file
    - root_directory: path of plinth root folder
    """
    if not config_path and not root_directory:
        config_path, root_directory = get_config_paths()

    if not os.path.isfile(config_path):
        msg = 'No plinth.config file could be found on path: %s' % config_path
        raise FileNotFoundError(msg)

    global config_file  # pylint: disable-msg=invalid-name,global-statement
    config_file = config_path

    parser = configparser.ConfigParser(defaults={
        'root': os.path.realpath(root_directory),
    })
    parser.read(config_file)

    config_items = (
        ('Path', 'root', 'string'),
        ('Path', 'file_root', 'string'),
        ('Path', 'config_dir', 'string'),
        ('Path', 'data_dir', 'string'),
        ('Path', 'custom_static_dir', 'string'),
        ('Path', 'store_file', 'string'),
        ('Path', 'actions_dir', 'string'),
        ('Path', 'doc_dir', 'string'),
        ('Path', 'server_dir', 'string'),
        ('Network', 'host', 'string'),
        ('Network', 'port', 'int'),
        ('Network', 'secure_proxy_ssl_header', 'string'),
        ('Network', 'use_x_forwarded_for', 'bool'),
        ('Network', 'use_x_forwarded_host', 'bool'),
        ('Misc', 'box_name', 'string'),
    )

    for section, name, datatype in config_items:
        try:
            value = parser.get(section, name)
        except (configparser.NoSectionError, configparser.NoOptionError):
            logger.error('Configuration does not contain option: %s.%s',
                         section, name)
            raise
        else:
            if datatype == 'int':
                value = int(value)
            elif datatype == 'bool':
                value = (value.lower() == 'true')

            globals()[name] = value
