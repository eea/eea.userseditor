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

