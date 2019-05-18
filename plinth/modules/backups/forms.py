#
# This file is part of FreedomBox.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Forms for backups module.
"""

import logging

import paramiko
from django import forms
from django.core.validators import FileExtensionValidator
from django.utils.translation import ugettext
from django.utils.translation import ugettext_lazy as _

from plinth.utils import format_lazy

from . import ROOT_REPOSITORY_NAME, api, network_storage
from .errors import BorgRepositoryDoesNotExistError
from .repository import SshBorgRepository

logger = logging.getLogger(__name__)


def _get_app_choices(apps):
    """Return a list of check box multiple choices from list of apps."""
    choices = []
    for app in apps:
        name = app.app.name
        if not app.has_data:
            name = ugettext('{app} (No data to backup)').format(
                app=app.app.name)

        choices.append((app.name, name))

    return choices


def _get_repository_choices():
    """Return the list of available repositories."""
    choices = [('root', ROOT_REPOSITORY_NAME)]
    storages = network_storage.get_storages()
    for storage in storages.values():
        choices += [(storage['uuid'], storage['path'])]
    return choices


class CreateArchiveForm(forms.Form):
    repository = forms.ChoiceField()
    selected_apps = forms.MultipleChoiceField(
        label=_('Included apps'), help_text=_('Apps to include in the backup'),
        widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, **kwargs):
        """Initialize the form with selectable apps."""
        super().__init__(*args, **kwargs)
        apps = api.get_all_apps_for_backup()
        self.fields['selected_apps'].choices = _get_app_choices(apps)
        self.fields['selected_apps'].initial = [app.name for app in apps]
        self.fields['repository'].choices = _get_repository_choices()


class RestoreForm(forms.Form):
    selected_apps = forms.MultipleChoiceField(
        label=_('Select the apps you want to restore'),
        widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, **kwargs):
        """Initialize the form with selectable apps."""
        apps = kwargs.pop('apps')
        super().__init__(*args, **kwargs)
        self.fields['selected_apps'].choices = _get_app_choices(apps)
        self.fields['selected_apps'].initial = [app.name for app in apps]


class UploadForm(forms.Form):
    file = forms.FileField(
        label=_('Upload File'), required=True, validators=[
            FileExtensionValidator(
                ['gz'], _('Backup files have to be in .tar.gz format'))
        ], help_text=_('Select the backup file you want to upload'))


class AddRepositoryForm(forms.Form):
    repository = forms.CharField(
        label=_('SSH Repository Path'), strip=True,
        help_text=_('Path of a new or existing repository. Example: '
                    '<i>user@host:~/path/to/repo/</i>'))
    ssh_password = forms.CharField(
        label=_('SSH server password'), strip=True,
        help_text=_('Password of the SSH Server.<br />'
                    'SSH key-based authentication is not yet possible.'),
        widget=forms.PasswordInput(), required=False)
    encryption = forms.ChoiceField(
        label=_('Encryption'), help_text=format_lazy(
            _('"Key in Repository" means that a '
              'password-protected key is stored with the backup.')),
        choices=[('repokey', 'Key in Repository'), ('none', 'None')])
    encryption_passphrase = forms.CharField(
        label=_('Passphrase'),
        help_text=_('Passphrase; Only needed when using encryption.'),
        widget=forms.PasswordInput(), required=False)
    confirm_encryption_passphrase = forms.CharField(
        label=_('Confirm Passphrase'), help_text=_('Repeat the passphrase.'),
        widget=forms.PasswordInput(), required=False)

    def get_credentials(self):
        credentials = {}
        for field_name in ["ssh_password", "encryption_passphrase"]:
            field_value = self.cleaned_data.get(field_name, None)
            if field_value:
                credentials[field_name] = field_value

        return credentials

    def _check_if_duplicate_remote(self, path):
        for storage in network_storage.get_storages().values():
            if storage['path'] == path:
                raise forms.ValidationError(
                    _('Remote backup repository already exists.'))

    def _validate_remote_repository(self, path, credentials):
        """
        Validation of SSH remote

          * Create empty directory if not exists
          * Check if the directory is empty
            - if not empty, check if it's an existing backup repository
            - else throw an error
        """
        user_at_host, dir_path = path.split(':')
        username, hostname = user_at_host.split('@')
        dir_path = dir_path.replace('~', f'/home/{username}')
        password = credentials['ssh_password']
        ssh_client = paramiko.SSHClient()
        # TODO Prompt to accept fingerprint of the server
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh_client.connect(hostname, username=username, password=password)
        except Exception as err:
            msg = _('Accessing the remote repository failed. Details: %(err)s')
            raise forms.ValidationError(msg, params={'err': str(err)})
        else:
            sftp_client = ssh_client.open_sftp()
            try:
                dir_contents = sftp_client.listdir(dir_path)
            except FileNotFoundError:
                logger.info(
                    _(f"Directory {dir_path} doesn't exist. Creating ..."))
                sftp_client.mkdir(dir_path)
                self.repository = SshBorgRepository(path=path,
                                                    credentials=credentials)
            else:
                if dir_contents:
                    try:
                        self.repository = SshBorgRepository(
                            path=path, credentials=credentials)
                        self.repository.get_info()
                    except BorgRepositoryDoesNotExistError:
                        msg = _(f'Directory {path.split(":")[-1]} is '
                                'neither empty nor is an existing '
                                'backups repository.')
                        raise forms.ValidationError(msg)
            finally:
                sftp_client.close()
        finally:
            ssh_client.close()

    def clean(self):
        cleaned_data = super(AddRepositoryForm, self).clean()
        passphrase = cleaned_data.get("encryption_passphrase")
        confirm_passphrase = cleaned_data.get("confirm_encryption_passphrase")

        if passphrase != confirm_passphrase:
            raise forms.ValidationError(
                _("The entered encryption passphrases do not match"))

        path = cleaned_data.get("repository")
        credentials = self.get_credentials()

        # Avoid creation of duplicate ssh remotes
        self._check_if_duplicate_remote(path)

        self._validate_remote_repository(path, credentials)
