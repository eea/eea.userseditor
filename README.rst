Eionet LDAP tools
=================

This package provides web forms for user interaction with the Eionet LDAP
account system. Users can modify personal information and change their
password. New accounts and password recovery are handled by another package.

https://svn.eionet.europa.eu/projects/Zope/ticket/1721
https://svn.eionet.europa.eu/projects/Zope/ticket/3967


Installation
------------
The EionetLDAP package needs to be installed in the Products folder of a Zope
instance. You can create an EionetLDAP object anywhere, with any name; it
should find acl_users and MailHost (see Dependencies below) by itself. You can
customize the noreply e-mail address and e-mail templates from the Properties
tab.

For Zope 2.8: make sure the ``eea`` folder is on the Python path, so that
``eea.userseditor`` can be imported. Copy or symlink the
``Products/EionetUsersEditor`` folder into a Zope product folder (e.g. the
``Products`` folder inside ``INSTANCE_HOME``).

For Zope 2.10 and newer: make sure ``eea.userseditor`` and
``Products.EionetUsersEditor`` can be imported. Zope will automatically find
and load the product at startup.

From ZMI you can now add an `Eionet Users Editor` object.

Page templates in this package expect the Eionet default layout at ``/styles``
and jQuery at ``/styles/jquery-1.4.4.min.js``; it also uses the macro at
``/standard_template.pt``.


Development
-----------
There are two components: an LDAP agent, and a user-interface Zope2 object
subclassed from ``SimpleItem``. Templates are rendered using the Zope3 template
engine, so be careful, they make no security checks.

Both modules are covered by unit tests in the ``tests`` folder. To run them you
need `mock`, `lxml` and `BeautifulSoup`; `nose` is highly recommended. In a
buildout environment you could set up a test runner like so::

    [nosetests]
    recipe = zc.recipe.egg
    scripts = nosetests
    eggs =
        nose
        mock
        lxml
        beautifulsoup4
        eea.userseditor
    extra-paths = ../zopes/2.10.12/lib/python
