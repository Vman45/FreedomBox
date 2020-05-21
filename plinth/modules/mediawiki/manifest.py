# SPDX-License-Identifier: AGPL-3.0-or-later

from django.utils.translation import ugettext_lazy as _

from plinth.clients import validate
from plinth.modules.backups.api import validate as validate_backup

clients = validate([{
    'name': _('MediaWiki'),
    'platforms': [{
        'type': 'web',
        'url': '/mediawiki'
    }]
}])

backup = validate_backup({
    'config': {
        'files': ['/etc/mediawiki/FreedomBoxSettings.php']
    },
    'data': {
        'directories': ['/var/lib/mediawiki-db/']
    },
    'services': ['mediawiki-jobrunner']
})
