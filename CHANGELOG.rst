1.1.32 (unreleased)
------------------

1.1.31 (2016-11-22)
------------------
* add os environ to zope environment [dumitval]

1.1.30 (2016-11-21)
------------------
* bugfix for users changint Organisation [dumitval]

1.1.29 (2016-10-10)
------------------
* show roles at the time a user was disabled [dumitval]

1.1.28 (2016-10-03)
------------------
* add organisation title in national language to the organisation
  selection list [dumitval]
* add Organisation title (if valid link available)
  and Department to the user details page [dumitval]

1.1.27 (2015-11-24)
------------------
* fix crash in user details when organisation from user's history was
  deleted [dumitval]

1.1.26 (2015-06-08)
------------------
* Bug fix: fixed user profile editor for missing organisation field
  [tiberich #26247]

1.1.25 (2015-05-19)
------------------
* Bug fix: call agent._get_metadata with userdn, not user id
  [tiberich]

1.1.24 (2015-04-14)
------------------
* is_manager replaced by can_edit_users, bound to permission, not role
  [dumitval]

1.1.23 (2015-03-30)
------------------
* Change: use bind=True in operations to allow retrieving the email address
  [tiberich #24362]

1.1.22 (2015-01-15)
------------------
* Bug fix: lineup arrows indicators in changelog with the rest of the text
  [tiberich #20422]
* Bug fix: don't show a user as disabled if he's not really disabled
  [tiberich #22487]

1.1.21 (2014-10-10)
------------------
* Bug fix: removed the visual icon ids, replaced them with some simple arrows
  [tiberich #20422]

1.1.20 (2014-09-24)
------------------
* Feature: added RESET_ACCOUNT view for the changelog
  [tiberich #9164]

1.1.19 (2014-09-19)
------------------
* Added method to retrieve user organisation membership
  [tiberich #20832]

1.1.18 (2014-07-15)
------------------
* Bug fix: fix case when editing user profile and an Organisation Editor was
  not found
  [tiberich #19143]

1.1.17 (2014-07-03)
------------------
* Bug fix: remove all organisations for a user before changing his organisation
  [tiberich #19143]

1.1.16 (2014-07-02)
------------------
* Bug fix: use the organisation membership for a member when showing his organisation
  in the edit form, instead of the 'o' field
  [tiberich #19143]

1.1.15 (2014-07-02)
------------------
* Bug fix: use the groupware standard_template when Zope is a Naaya groupware
  application
  [tiberich #19143]

1.1.14 (2014-07-01)
------------------
* Bug fix: don't fail when removing user from org if user is not in org
  [tiberich #19143]

1.1.13 (2014-07-01)
------------------
* Bug fix: use alternate agent to avoid insufficient permissions to perform
  LDAP operations
  [tiberich #19143]

1.1.12 (2014-07-01)
------------------
* Bug fix: remove user from old org when changing his organisation
  [tiberich #19143]

1.1.11 (2014-06-30)
------------------
* Feature: allow users to select their organisation from a list
  [tiberich #19143]

1.1.10 (2014-06-16)
------------------
* Bug fix: use the proper author name based on logged in user in changelog
  for user operations
  [tiberich #20081]

1.1.9 (2014-06-16)
------------------
* Bug fix: display the proper organisation name in changelog
  [tiberich #20081]

1.1.8 (2014-06-16)
------------------
* Bug fix: added views for the ADD_PENDING_TO_ORG changelog action
  [tiberich #20081]

1.1.7 (2014-06-10)
------------------
* Bugfix related to the encoding of role descriptions [dumitval]

1.1.6 (2014-05-12)
------------------
* Bug fix: don't take into consideration "owner of role" when 
  displaying history of roles
  [tiberich #19565]


1.1.5 (2014-05-9)
--------------------
* Bug fix: don't fail on user details page - history when encountering 
  roles that are not in the filtered roles list
  [tiberich]

1.1.4 (2014-03-07)
--------------------
* added edit link for managers on user index [dumitval]
* Feature: added support for pending membership to organisations
  [tiberich #15263]
* Feature: improved log entry views by compacting multiple entries
  to single table row
  [tiberich #16665]

1.1.3 (2014-01-10)
--------------------
* remove new password from confirmation mail [dumitval]

1.1.2 (2013-10-29)
--------------------
* wording in templates [dumitval]

1.1.1 (2013-09-05)
--------------------
* #15628; api change in eea.usersdb [simiamih]

1.1.0 (2013-02-21)
--------------------
* feature: compare userprofiles [simiamih]
* feature: object to display Eionet Member public page [simiamih]

1.0.3 (2012-10-29)
--------------------
* removed Circa encoding validation [simiamih]

1.0.2 (2012-07-19)
--------------------
* fixed circa agent _user_id call [simiamih]

1.0.1 (2012-07-19)
--------------------
* Send mail when changing password [bogdatan]

1.0.0 (2012-06-22)
--------------------
* "EIONET" string configurable by env "NETWORK_NAME" [simiamih]
* updating info in legacy ldap for nonexisting user fails silently [simiamih]

