# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Functional, browser based tests for ttrss app.
"""

from pytest_bdd import given, scenarios, then, when

from plinth.tests import functional

scenarios('ttrss.feature')


@given('I subscribe to a feed in ttrss')
def ttrss_subscribe(session_browser):
    _subscribe(session_browser)


@when('I unsubscribe from the feed in ttrss')
def ttrss_unsubscribe(session_browser):
    _unsubscribe(session_browser)


@then('I should be subscribed to the feed in ttrss')
def ttrss_assert_subscribed(session_browser):
    assert _is_subscribed(session_browser)


def _ttrss_load_main_interface(browser):
    """Load the TT-RSS interface."""
    functional.visit(browser, '/tt-rss/')
    overlay = browser.find_by_id('overlay')
    functional.eventually(lambda: not overlay.visible)


def _is_feed_shown(browser, invert=False):
    return browser.is_text_present('Planet Debian') != invert


def _click_main_menu_item(browser, text):
    """Select an item from the main actions menu."""
    burger_menu = browser.find_by_xpath('//*[contains(@title, "Actions...")]')
    if burger_menu:
        burger_menu.click()
    else:
        browser.find_by_text('Actions...').click()

    browser.find_by_text(text).click()


def _subscribe(browser):
    """Subscribe to a feed in TT-RSS."""
    _ttrss_load_main_interface(browser)

    _click_main_menu_item(browser, 'Subscribe to feed...')
    browser.find_by_id('feedDlg_feedUrl').fill(
        'https://planet.debian.org/atom.xml')
    browser.find_by_text('Subscribe').click()
    if browser.is_text_present('You are already subscribed to this feed.'):
        browser.find_by_text('Cancel').click()

    expand = browser.find_by_css('span.dijitTreeExpandoClosed')
    if expand:
        expand.first.click()

    assert functional.eventually(_is_feed_shown, [browser])


def _unsubscribe(browser):
    """Unsubscribe from a feed in TT-RSS."""
    _ttrss_load_main_interface(browser)
    expand = browser.find_by_css('span.dijitTreeExpandoClosed')
    if expand:
        expand.first.click()

    browser.find_by_text('Planet Debian').click()
    _click_main_menu_item(browser, 'Unsubscribe')

    prompt = browser.get_alert()
    prompt.accept()

    # Reload as sometimes the feed does not disappear immediately
    _ttrss_load_main_interface(browser)

    assert functional.eventually(_is_feed_shown, [browser, True])


def _is_subscribed(browser):
    """Return whether subscribed to a feed in TT-RSS."""
    _ttrss_load_main_interface(browser)
    return browser.is_text_present('Planet Debian')
