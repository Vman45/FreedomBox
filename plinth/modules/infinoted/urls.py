# SPDX-License-Identifier: AGPL-3.0-or-later
"""
URLs for the infinoted module.
"""

from django.conf.urls import url

from .views import InfinotedAppView

urlpatterns = [
    url(r'^apps/infinoted/$', InfinotedAppView.as_view(), name='index'),
]
