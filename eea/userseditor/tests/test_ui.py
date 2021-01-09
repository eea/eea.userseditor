''' tests for ui '''
# encoding: utf-8
# pylint: disable=super-init-not-called
import unittest
from datetime import datetime
import re

from mock import Mock, patch
from lxml.html.soupparser import fromstring
from Products.statusmessages.interfaces import IStatusMessage
from Products.MailHost.interfaces import IMailHost
from plone.registry.interfaces import IRegistry
from plone.app.testing import (PLONE_FIXTURE,
                               IntegrationTesting, PloneSandboxLayer)
from zope.component import getUtility

from eea.userseditor.users_editor import UsersEditor
from eea.userseditor.userdetails import TemplateRenderer, CommonTemplateLogic


class Fixture(PloneSandboxLayer):
    """ Fixture """

    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        """ Set up Zope """
        # Load ZCML
        import eea.ldapadmin
        import eea.userseditor
        import plone.dexterity
        import plone.app.textfield

        # needed for Dexterity FTI
        self.loadZCML(package=plone.dexterity)

        # needed for DublinCore behavior
        self.loadZCML(package=plone.app.dexterity)

        # needed to support RichText in testpage
        self.loadZCML(package=plone.app.textfield)

        self.loadZCML(package=eea.ldapadmin)
        self.loadZCML(package=eea.userseditor)


FIXTURE = Fixture()
INTEGRATION_TESTING = IntegrationTesting(
    bases=(FIXTURE,),
    name='eea.userseditor:Integration',
)


NETWORK_NAME = 'Eionet'


def base_setup(context, user):
    """ create request based on the PloneSandboxLayer """
#    context.mock_agent._encoding = 'utf-8'
#    context.mock_agent.role_leaders = Mock(return_value=([], []))
#    context.mock_agent.role_infos_in_role.return_value = {}
#    context.ui.can_delete_role = Mock(return_value=True)
#    context.ui.can_edit_members = Mock(return_value=True)
#    context.ui.can_edit_organisations = Mock(return_value=True)
#    context.ui.getPhysicalRoot = Mock(return_value=context.layer['app'])

    context.request = context.REQUEST = context.ui.REQUEST = context.layer[
        'portal'].REQUEST
    context.request.method = 'POST'
    context.request.RESPONSE.redirect = Mock()
    context.request.RESPONSE.setStatus = Mock()
    context.REQUEST.AUTHENTICATED_USER = user
    context.mailhost = getUtility(IMailHost)
    registry = getUtility(IRegistry)
    registry["plone.email_from_address"] = "user-directory@plone.org"
    registry["plone.email_from_name"] = u"Plone test site"
    context.mock_agent = MockLdapAgent()
    context.mock_agent.filter_roles.return_value = []
    context.ui._get_ldap_agent = Mock(return_value=context.mock_agent)


def parse_html(html):
    """parse_html.

    :param html:
    """
    return fromstring(re.sub(r'\s+', ' ', html))
    # return fromstring(html)


def status_messages(request):
    """status_messages.

    :param request:
    """
    messages = {}
    for message in IStatusMessage(request).show():
        messages[message.type] = message.message
    return messages


def plaintext(element):
    """plaintext.

    :param element:
    """
    return re.sub(r'\s\s+', ' ', element.text_content()).strip()


# pylint: disable=invalid-encoded-data
user_data_fixture = {
    'first_name': "Joe",
    'last_name': "Smith",
    'full_name_native': "Joe Șmith",
    'search_helper': "Joe Smith Șmith",
    'job_title': "Lab rat",
    'email': "jsmith@example.com",
    'mobile': "+40 21 555 4321",
    'url': "http://example.com/~jsmith",
    'postal_address': "13 Smithsonian Way, Copenhagen, DK",
    'phone': "+40 21 555 4322",
    'fax': "+40 21 555 4323",
    'organisation': "bridge_club",
    'department': "My department",
    'reasonToCreate': "Account created before this field was introduced",
}

org_data_fixture = {
    'country': "eu",
}


def stubbed_renderer():
    """stubbed_renderer."""
    renderer = TemplateRenderer(CommonTemplateLogic)
    renderer.wrap = lambda html: "<html>%s</html>" % html
    return renderer


class MockLdapAgent(Mock):
    """MockLdapAgent."""

    def __init__(self, *args, **kwargs):
        super(MockLdapAgent, self).__init__(*args, **kwargs)
        self._user_info = dict(user_data_fixture)
        self.new_action = Mock
        self.new_action.__enter__ = Mock(return_value=self.new_action)
        self.new_action.__exit__ = Mock(return_value=None)

    def user_info(self, user_id):
        """user_info.

        :param user_id:
        """
        return self._user_info

    def all_organisations(self):
        """all_organisations."""
        return {}


class StubbedUsersEditor(UsersEditor):
    """StubbedUsersEditor."""

    def __init__(self):
        # self._render_template = stubbed_renderer()
        pass

    def _render_template(self, name, **options):
        """_render_template.

        :param name:
        :param options:
        """
        from eea.userseditor.users_editor import load_template
        options.update({'network_name': NETWORK_NAME})
        return "<html>%s</html>" % load_template(name)(**options)

    def absolute_url(self):
        """absolute_url."""
        return "URL"


def mock_user(user_id, user_pw):
    """mock_user.

    :param user_id:
    :param user_pw:
    """
    user = Mock()
    user.getId.return_value = user_id
    user.__ = user_pw
    return user


class AccountUITest(unittest.TestCase):
    """AccountUITest."""

    layer = INTEGRATION_TESTING

    def setUp(self):
        self.ui = StubbedUsersEditor()
        user = mock_user('jsmith', 'asdf')  # get_current()
        base_setup(self, user)
        self.mock_agent.user_organisations = Mock(return_value=[
            {'id': user_data_fixture['organisation'],
             'text': user_data_fixture['organisation'],
             'text_native': '', 'ldap': False}
        ])
        self.mock_agent.org_info = Mock(return_value=org_data_fixture)
        self.mock_agent.filter_roles.return_value = []
        self.ui._get_ldap_agent = Mock(return_value=self.mock_agent)
        user.getRoles = Mock(return_value=['Authenticated'])

    def test_edit_form(self):
        """test_edit_form."""
        page = parse_html(self.ui.edit_account_html(self.request))

        txt = lambda xp: plaintext(page.xpath(xp)[0])
        val = lambda xp: page.xpath(xp)[0].attrib['value']
        self.assertEqual(txt('//h1'), "Eionet account Edit information")
        self.assertEqual(val('//form//input[@name="first_name:utf8:ustring"]'),
                         user_data_fixture['first_name'])
        self.assertEqual(val('//form//input[@name="last_name:utf8:ustring"]'),
                         user_data_fixture['last_name'])
        self.assertEqual(val('//form//input[@name="job_title:utf8:ustring"]'),
                         user_data_fixture['job_title'])
        self.assertEqual(val('//form//input[@name="email:utf8:ustring"]'),
                         user_data_fixture['email'])
        self.assertEqual(val('//form//input[@name="url:utf8:ustring"]'),
                         user_data_fixture['url'])
        self.assertEqual(txt('//form//textarea'
                             '[@name="postal_address:utf8:ustring"]'),
                         "13 Smithsonian Way, Copenhagen, DK")
        self.assertEqual(val('//form//input[@name="phone:utf8:ustring"]'),
                         user_data_fixture['phone'])
        self.assertEqual(val('//form//input[@name="mobile:utf8:ustring"]'),
                         user_data_fixture['mobile'])
        self.assertEqual(val('//form//input[@name="fax:utf8:ustring"]'),
                         user_data_fixture['fax'])

    @patch('eea.userseditor.users_editor.datetime')
    def test_submit_edit(self, mock_datetime):
        """test_submit_edit.

        :param mock_datetime:
        """
        mock_datetime.now.return_value = datetime(2010, 12, 16, 13, 45, 21)
        self.request.form = dict(user_data_fixture)
        self.request.method = 'POST'

        self.ui.edit_account(self.request)

        self.request.RESPONSE.redirect.assert_called_with(
            'URL/edit_account_html')
        self.mock_agent.set_user_info.assert_called_with('jsmith',
                                                         user_data_fixture)

        self.assertEqual(status_messages(self.request),
                         {'info': 'Profile saved (2010-12-16 13:45:21)'})

    def test_password_form(self):
        """test_password_form."""
        page = parse_html(self.ui.change_password_html(self.request))

        txt = lambda xp: plaintext(page.xpath(xp)[0])
        exists = lambda xp: len(page.xpath(xp)) > 0
        self.assertEqual(txt('//h1'), "Eionet account Change password")
        self.assertEqual(txt('//p/tt'), "jsmith")
        self.assertTrue(exists('//form//input[@type="password"]'
                               '[@name="old_password"]'))
        self.assertTrue(exists('//form//input[@type="password"]'
                               '[@name="new_password"]'))
        self.assertTrue(exists('//form//input[@type="password"]'
                               '[@name="new_password_confirm"]'))

    def test_submit_new_password(self):
        """test_submit_new_password."""
        self.request.form = {
            'old_password': "asdf",
            'new_password': "zxcv",
            'new_password_confirm': "zxcv",
        }

        self.ui.change_password(self.request)

        self.mock_agent.bind_user.assert_called_with('jsmith', 'asdf')
        self.mock_agent.set_user_password.assert_called_with('jsmith',
                                                             "asdf", "zxcv")
        self.request.RESPONSE.redirect.assert_called_with(
            'URL/password_changed_html')

        page = parse_html(self.ui.password_changed_html(self.request))

        txt = lambda xp: page.xpath(xp)[0].text.strip()
        self.assertEqual(
            txt('//div[@class="system-msg"]'),
            "Password changed successfully. You must log in again.")

    def test_submit_new_password_bad_old_password(self):
        """test_submit_new_password_bad_old_password."""
        self.request.form = {
            'old_password': "qwer",
            'new_password': "zxcv",
            'new_password_confirm': "zxcv",
        }
        self.mock_agent.bind_user.side_effect = ValueError

        self.ui.change_password(self.request)

        self.mock_agent.bind_user.assert_called_with('jsmith', 'qwer')
        assert self.mock_agent.set_user_password.call_count == 0
        self.request.RESPONSE.redirect.assert_called_with(
            'URL/change_password_html')

        self.assertEqual(status_messages(self.request),
                         {'error': 'Old password is wrong'})

    def test_submit_new_password_mismatch(self):
        """test_submit_new_password_mismatch."""
        self.request.form = {
            'old_password': "asdf",
            'new_password': "zxcv",
            'new_password_confirm': "not quite zxcv",
        }

        self.ui.change_password(self.request)

        assert self.mock_agent.set_user_password.call_count == 0
        self.request.RESPONSE.redirect.assert_called_with(
            'URL/change_password_html')

        self.assertEqual(status_messages(self.request),
                         {'error': 'New passwords do not match'})


class NotLoggedInTest(unittest.TestCase):
    """NotLoggedInTest."""

    layer = INTEGRATION_TESTING

    def setUp(self):
        self.ui = StubbedUsersEditor()
        user = mock_user(None, '')  # get_current()
        base_setup(self, user)
        self.mock_agent.user_organisations = Mock(return_value=[
            {'id': user_data_fixture['organisation'],
             'text': user_data_fixture['organisation'],
             'text_native': '', 'ldap': False}
        ])
        self.mock_agent.org_info = Mock(return_value=org_data_fixture)
        user.getRoles = Mock(return_value=['Anonymous'])

    def _assert_error_msg_on_index(self):
        """_assert_error_msg_on_index."""
        page = parse_html(self.ui.index_html(self.request))
        txt = lambda xp: page.xpath(xp)[0].text_content().strip()
        self.assertEqual(txt('//p[@class="not-logged-in"]'),
                         "You must be authenticated to edit your profile. "
                         "Please log in.")

    def test_main_page(self):
        """test_main_page."""
        page = parse_html(self.ui.index_html(self.request))

        txt = lambda xp: page.xpath(xp)[0].text_content().strip()
        self.assertEqual(txt('//p[@class="not-logged-in"]'),
                         "You must be authenticated to edit your profile. "
                         "Please log in.")

    @patch('eea.ldapadmin.nfp_nrc.get_nrc_roles')
    def test_edit_form(self, mock_nrc_roles):
        """test_edit_form."""
        mock_nrc_roles.return_value = []
        self.ui.edit_account_html(self.request)
        self.request.RESPONSE.redirect.assert_called_with('URL/')
        self._assert_error_msg_on_index()

    def test_password_form(self):
        """test_password_form."""
        self.ui.change_password_html(self.request)
        self.request.RESPONSE.redirect.assert_called_with('URL/')
        self._assert_error_msg_on_index()


class EditOrganisationTest(unittest.TestCase):
    """EditOrganisationTest."""

    layer = INTEGRATION_TESTING

    def setUp(self):
        self.ui = StubbedUsersEditor()
        user = mock_user('jsmith', 'asdf')  # get_current()
        base_setup(self, user)
        self.mock_agent.user_organisations = Mock(return_value=[
            {'id': user_data_fixture['organisation'],
             'text': user_data_fixture['organisation'],
             'text_native': '', 'ldap': False}
        ])
        self.mock_agent.org_info = Mock(return_value=org_data_fixture)
        self.mock_agent.filter_roles.return_value = []
        self.ui._get_ldap_agent = Mock(return_value=self.mock_agent)
        all_orgs = {
            'bridge_club': {'name': 'Bridge club',
                            'name_native': 'Bridge club', 'country': 'eu'},
            'poker_club': {'name': 'Poker club',
                           'name_native': 'Poker club', 'country': 'eu'}}
        self.mock_agent.all_organisations = Mock(return_value=all_orgs)
        user.getRoles = Mock(return_value=['Authenticated'])

    def test_show_by_id(self):
        """test_show_by_id."""
        self.mock_agent._org_id.return_value = 'bridge_club'

        page = parse_html(self.ui.edit_account_html(self.request))

        select_by_id = page.xpath(
            '//form//select[@name="organisation:utf8:ustring"]')[0]
        options = select_by_id.xpath('option')
        self.assertEqual(len(options), 3)
        self.assertEqual(options[0].text, u"-")
        self.assertEqual(options[1].text,
                         "Bridge club (Bridge club, bridge_club)")
        self.assertEqual(options[1].attrib['value'], 'bridge_club')
        self.assertEqual(options[1].attrib['selected'], 'selected')
        self.assertEqual(options[2].text,
                         "Poker club (Poker club, poker_club)")
        self.assertEqual(options[2].attrib['value'], 'poker_club')
        self.assertTrue('selected' not in options[2].attrib)

    def test_submit_literal(self):
        """test_submit_literal."""
        user_info = dict(user_data_fixture, organisation=u"My own little club")
        self.request.form = dict(user_info)

        self.ui.edit_account(self.request)

        self.mock_agent.set_user_info.assert_called_with('jsmith', user_info)
