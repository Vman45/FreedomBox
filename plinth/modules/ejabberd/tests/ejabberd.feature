# SPDX-License-Identifier: AGPL-3.0-or-later

# TODO Check service
# TODO Check domain name display

@apps @ejabberd
Feature: Ejabberd Chat Server
  Run ejabberd chat server.

Background:
  Given I'm a logged in user
  Given the ejabberd application is installed

Scenario: Enable ejabberd application
  Given the ejabberd application is disabled
  When I enable the ejabberd application
  Then the ejabberd service should be running

Scenario: Enable message archive management
  Given the ejabberd application is enabled
  When I enable message archive management
  Then the ejabberd service should be running

Scenario: Disable message archive management
  Given the ejabberd application is enabled
  When I disable message archive management
  Then the ejabberd service should be running

@backups
Scenario: Backup and restore ejabberd
  Given the ejabberd application is enabled
  And I have added a contact to my roster
  When I create a backup of the ejabberd app data with name test_ejabberd
  And I delete the contact from my roster
  And I restore the ejabberd app data backup with name test_ejabberd
  Then I should have a contact on my roster

Scenario: Disable ejabberd application
  Given the ejabberd application is enabled
  When I disable the ejabberd application
  Then the ejabberd service should not be running
