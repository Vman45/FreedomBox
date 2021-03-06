# SPDX-License-Identifier: AGPL-3.0-or-later
"""
FreedomBox app to configure sharing.
"""

import json

from django.utils.translation import ugettext_lazy as _

from plinth import actions
from plinth import app as app_module
from plinth import cfg, menu
from plinth.utils import format_lazy

from .manifest import backup  # noqa, pylint: disable=unused-import

version = 1

_description = [
    format_lazy(
        _('Sharing allows you to share files and folders on your {box_name} '
          'over the web with chosen groups of users.'),
        box_name=_(cfg.box_name))
]

app = None


class SharingApp(app_module.App):
    """FreedomBox app for sharing files."""

    app_id = 'sharing'

    def __init__(self):
        """Create components for the app."""
        super().__init__()
        info = app_module.Info(app_id=self.app_id, version=version,
                               name=_('Sharing'), icon_filename='sharing',
                               description=_description)
        self.add(info)

        menu_item = menu.Menu('menu-sharing', info.name, None,
                              info.icon_filename, 'sharing:index',
                              parent_url_name='apps')
        self.add(menu_item)


def list_shares():
    """Return a list of shares."""
    output = actions.superuser_run('sharing', ['list'])
    return json.loads(output)['shares']


def add_share(name, path, groups, is_public):
    """Add a new share by called the action script."""
    args = ['add', '--name', name, '--path', path, '--groups'] + groups
    if is_public:
        args.append('--is-public')
    actions.superuser_run('sharing', args)


def remove_share(name):
    """Remove a share by calling the action script."""
    actions.superuser_run('sharing', ['remove', '--name', name])
