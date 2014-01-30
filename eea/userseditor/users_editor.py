from datetime import datetime
import logging
from ldap import INSUFFICIENT_ACCESS

from AccessControl import ClassSecurityInfo
from App.class_init import InitializeClass
from App.config import getConfiguration
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from OFS.SimpleItem import SimpleItem
from OFS.PropertyManager import PropertyManager
from AccessControl.Permissions import view

from persistent.list import PersistentList
from persistent.mapping import PersistentMapping
import deform

from zope.component import getUtility
from zope.component.interfaces import ComponentLookupError
from zope.sendmail.interfaces import IMailDelivery
from email.mime.text import MIMEText

from eea import usersdb

from image_processor import scale_to

cfg = getConfiguration()
# constant defined in env
NETWORK_NAME = getattr(cfg, 'environment', {}).get('NETWORK_NAME', 'Eionet')

user_info_schema = usersdb.user_info_schema.clone()
user_info_schema['postal_address'].widget = deform.widget.TextAreaWidget()

SESSION_MESSAGES = 'eea.userseditor.messages'
SESSION_FORM_DATA = 'eea.userseditor.form_data'
SESSION_FORM_ERRORS = 'eea.userseditor.form_errors'
log = logging.getLogger(__name__)

WIDTH = 128
HEIGHT = 192

manage_addUsersEditor_html = PageTemplateFile('zpt/add', globals())
def manage_addUsersEditor(parent, id, title="", ldap_server="", REQUEST=None):
    """ Adds a new Eionet Users Editor object """
    ob = UsersEditor(title, ldap_server)
    ob._setId(id)
    parent._setObject(id, ob)
    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(parent.absolute_url() + '/manage_workspace')

def _get_session_messages(request):
    session = request.SESSION
    if SESSION_MESSAGES in session.keys():
        msgs = dict(session[SESSION_MESSAGES])
        del session[SESSION_MESSAGES]
    else:
        msgs = {}
    return msgs

def _set_session_message(request, msg_type, msg):
    session = request.SESSION
    if SESSION_MESSAGES not in session.keys():
        session[SESSION_MESSAGES] = PersistentMapping()
    # TODO: allow for more than one message of each type
    session[SESSION_MESSAGES][msg_type] = msg

def _session_pop(request, name, default):
    session = request.SESSION
    if name in session.keys():
        value = session[name]
        del session[name]
        return value
    else:
        return default

def _get_user_password(request):
    return request.AUTHENTICATED_USER.__

def _get_user_id(request):
    return request.AUTHENTICATED_USER.getId()

def _is_logged_in(request):
    if _get_user_id(request) is None:
        return False
    else:
        return True

def load_template(name, _memo={}):
    if name not in _memo:
        from zope.pagetemplate.pagetemplatefile import PageTemplateFile
        _memo[name] = PageTemplateFile(name, globals())
    return _memo[name]

CIRCA_USER_SCHEMA = dict(usersdb.db_agent.EIONET_USER_SCHEMA, fax='fax')
CIRCA_USERS_DN_SUFFIX = 'ou=Users,ou=DATA,ou=eea,o=IRCusers,l=CIRCA'

class DualLDAPProxy(object):
    """
    while CIRCA is still online, we need to write stuff to both LDAP
    servers. CIRCA first.
    """

    def __init__(self, current_ldap, legacy_ldap):
        self._current_ldap = current_ldap
        self._legacy_ldap = legacy_ldap

    def bind_user(self, user_id, user_pw):
        self._current_ldap.bind_user(user_id, user_pw)
        try:
            self._legacy_ldap.bind_user(user_id, user_pw)
        except (ValueError, INSUFFICIENT_ACCESS):
            log.info("User %r could not bind on CIRCA legacy LDAP", user_id)

    def set_user_info(self, user_id, new_info):
        self._current_ldap.set_user_info(user_id, new_info)
        try:
            self._legacy_ldap.set_user_info(user_id, new_info)
        except (usersdb.UserNotFound, INSUFFICIENT_ACCESS):
            log.info("User %r doesn't exist in CIRCA legacy LDAP", user_id)

    def set_user_password(self, user_id, old_pw, new_pw):
        self._current_ldap.set_user_password(user_id, old_pw, new_pw)
        try:
            self._legacy_ldap.set_user_password(user_id, old_pw, new_pw)
        except (usersdb.UserNotFound, INSUFFICIENT_ACCESS):
            log.info("User %r doesn't exist in CIRCA legacy LDAP", user_id)

    def __getattr__(self, name):
        # patch all other methods straight to front-end ldap
        return getattr(self._current_ldap, name)


class CircaUsersDB(usersdb.UsersDB):
    user_schema = CIRCA_USER_SCHEMA

    def _user_dn(self, user_id):
        return super(CircaUsersDB, self)._user_dn('%s@circa' % user_id)

    def _user_id(self, user_dn, attr={}):
        circa_user_id = super(CircaUsersDB, self)._user_id(user_dn)
        assert '@' in circa_user_id
        return circa_user_id.split('@')[0]

    def _search_user_in_orgs(self, user_id):
        return []


class UsersEditor(SimpleItem, PropertyManager):
    meta_type = 'Eionet Users Editor'
    icon = '++resource++eea.userseditor-www/users_editor.gif'
    manage_options = PropertyManager.manage_options + (
        {'label':'View', 'action':''},
    ) + SimpleItem.manage_options
    _properties = (
        {'id':'title', 'type': 'string', 'mode':'w', 'label': 'Title'},
        {'id':'ldap_server', 'type': 'string', 'mode':'w',
         'label': 'LDAP Server'},
    )
    security = ClassSecurityInfo()

    legacy_ldap_server = ""
    _properties += (
        {'id':'legacy_ldap_server', 'type': 'string', 'mode':'w',
         'label': 'Legacy LDAP Server (CIRCA)'},
    )

    def __init__(self, title, ldap_server):
        self.title = title
        self.ldap_server = ldap_server

    def _get_ldap_agent(self, write=False):
        #return usersdb.UsersDB(ldap_server=self.ldap_server)

        # temporary fix while CIRCA is still online
        current_agent = usersdb.UsersDB(ldap_server=self.ldap_server)
        if write and self.legacy_ldap_server != "":
            legacy_agent = CircaUsersDB(ldap_server=self.legacy_ldap_server,
                                        users_dn=CIRCA_USERS_DN_SUFFIX,
                                        encoding="ISO-8859-1")
            return DualLDAPProxy(current_agent, legacy_agent)
        else:
            return current_agent

    _zope2_wrapper = PageTemplateFile('zpt/zope2_wrapper.zpt', globals())

    def _render_template(self, name, **options):
        tmpl = load_template(name)
        options.update({'network_name': NETWORK_NAME})
        return self._zope2_wrapper(body_html=tmpl(**options))

    security.declareProtected(view, 'index_html')
    def index_html(self, REQUEST):
        """ view """
        options = {
            'base_url': self.absolute_url(),
        }
        if _is_logged_in(REQUEST):
            agent = self._get_ldap_agent()
            user_id = _get_user_id(REQUEST)
            options['user_info'] = agent.user_info(user_id)
        else:
            options['user_info'] = None
        options.update(_get_session_messages(REQUEST))
        return self._render_template('zpt/index.zpt', **options)

    security.declareProtected(view, 'edit_account_html')
    def edit_account_html(self, REQUEST):
        """ view """
        if not _is_logged_in(REQUEST):
            return REQUEST.RESPONSE.redirect(self.absolute_url() + '/')

        agent = self._get_ldap_agent()
        user_id = _get_user_id(REQUEST)

        errors = _session_pop(REQUEST, SESSION_FORM_ERRORS, {})
        form_data = _session_pop(REQUEST, SESSION_FORM_DATA, None)
        if form_data is None:
            form_data = agent.user_info(user_id)

        options = {
            'base_url': self.absolute_url(),
            'form_data': form_data,
            'errors': errors,
            'schema': user_info_schema,
        }
        options.update(_get_session_messages(REQUEST))
        return self._render_template('zpt/edit_account.zpt', **options)

    security.declareProtected(view, 'edit_account')
    def edit_account(self, REQUEST):
        """ view """
        user_id = _get_user_id(REQUEST)

        user_form = deform.Form(user_info_schema)

        try:
            user_data = user_form.validate(REQUEST.form.items())
        except deform.ValidationFailure, e:
            session = REQUEST.SESSION
            errors = {}
            for field_error in e.error.children:
                errors[field_error.node.name] = field_error.msg
            session[SESSION_FORM_ERRORS] = errors
            session[SESSION_FORM_DATA] = dict(REQUEST.form)
            msg = u"Please correct the errors below and try again."
            _set_session_message(REQUEST, 'error', msg)
        else:
            agent = self._get_ldap_agent(write=True)
            agent.bind_user(user_id, _get_user_password(REQUEST))
            agent.set_user_info(user_id, user_data)
            when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _set_session_message(REQUEST, 'message', "Profile saved (%s)" % when)

        REQUEST.RESPONSE.redirect(self.absolute_url() + '/edit_account_html')

    security.declareProtected(view, 'change_password_html')
    def change_password_html(self, REQUEST):
        """ view """
        if not _is_logged_in(REQUEST):
            return REQUEST.RESPONSE.redirect(self.absolute_url() + '/')

        return self._render_template('zpt/change_password.zpt',
                                     user_id=_get_user_id(REQUEST),
                                     base_url=self.absolute_url(),
                                     **_get_session_messages(REQUEST))

    security.declareProtected(view, 'change_password')
    def change_password(self, REQUEST):
        """ view """
        form = REQUEST.form
        user_id = _get_user_id(REQUEST)
        agent = self._get_ldap_agent(write=True)
        user_info = agent.user_info(user_id)

        if form['new_password'] != form['new_password_confirm']:
            _set_session_message(REQUEST, 'error',
                                 "New passwords do not match")
            return REQUEST.RESPONSE.redirect(self.absolute_url() +
                                             '/change_password_html')

        try:
            agent.bind_user(user_id, form['old_password'])
            agent.set_user_password(user_id, form['old_password'],
                                             form['new_password'])

            options = {
                'first_name': user_info['first_name'],
                'password': form['new_password'],
                'network_name': NETWORK_NAME,
            }

            email_template = load_template('zpt/email_change_password.zpt')
            email_password_body = email_template.pt_render(options)
            addr_from = "no-reply@eea.europa.eu"
            addr_to = user_info['email']

            message = MIMEText(email_password_body)
            message['From'] = addr_from
            message['To'] = addr_to
            message['Subject'] = "%s Account - New password" % NETWORK_NAME

            try:
                mailer = getUtility(IMailDelivery, name="Mail")
                mailer.send(addr_from, [addr_to], message.as_string())
            except ComponentLookupError:
                mailer = getUtility(IMailDelivery, name="naaya-mail-delivery")
                mailer.send(addr_from, [addr_to], message)

        except ValueError:
            _set_session_message(REQUEST, 'error', "Old password is wrong")
            return REQUEST.RESPONSE.redirect(self.absolute_url() +
                                             '/change_password_html')

        REQUEST.RESPONSE.redirect(self.absolute_url() +
                                  '/password_changed_html')

    security.declareProtected(view, 'password_changed_html')
    def password_changed_html(self, REQUEST):
        """ view """
        options = {
            'messages': [
                "Password changed successfully. You must log in again."],
            'base_url': self.absolute_url(),
        }
        return self._render_template('zpt/result_page.zpt', **options)

    security.declareProtected(view, 'profile_picture_html')
    def profile_picture_html(self, REQUEST):
        """ view """
        if not _is_logged_in(REQUEST):
            return REQUEST.RESPONSE.redirect(self.absolute_url() + '/')
        user_id = _get_user_id(REQUEST)
        agent = self._get_ldap_agent()

        if agent.get_profile_picture(user_id):
            has_image = True
        else:
            has_image = False
        return self._render_template('zpt/profile_picture.zpt',
                                     user_id=_get_user_id(REQUEST),
                                     base_url=self.absolute_url(),
                                     has_current_image=has_image,
                                     here=self,
                                     **_get_session_messages(REQUEST))

    security.declareProtected(view, 'profile_picture')
    def profile_picture(self, REQUEST):
        """ view """
        if not _is_logged_in(REQUEST):
            return REQUEST.RESPONSE.redirect(self.absolute_url() + '/')
        image_file = REQUEST.form.get('image_file', None)
        if image_file:
            picture_data = image_file.read()
            user_id = _get_user_id(REQUEST)
            agent = self._get_ldap_agent(write=True)
            try:
                password = _get_user_password(REQUEST)
                agent.bind_user(user_id, password)
                color = (255, 255, 255)
                picture_data = scale_to(picture_data, WIDTH, HEIGHT, color)
                success = agent.set_user_picture(user_id, picture_data)
            except ValueError:
                _set_session_message(REQUEST, 'error', "Error updating picture")
                return REQUEST.RESPONSE.redirect(self.absolute_url() +
                                                 '/profile_picture_html')
            if success:
                success_text = "That's a beautiful picture."
                _set_session_message(REQUEST, 'message', success_text)
            else:
                _set_session_message(REQUEST, 'error', "Error updating picture.")
        else:
            _set_session_message(REQUEST, 'error', "You must provide a JPG file.")
        return REQUEST.RESPONSE.redirect(self.absolute_url()
                                         + '/profile_picture_html')

    security.declareProtected(view, 'profile_picture_jpg')
    def profile_picture_jpg(self, REQUEST):
        """
        Returns jpeg picture data for logged-in user.
        Assumes picture is available in LDAP.

        """
        user_id = _get_user_id(REQUEST)
        agent = self._get_ldap_agent()
        photo = agent.get_profile_picture(user_id)
        REQUEST.RESPONSE.setHeader('Content-Type', 'image/jpeg')
        return photo

    security.declareProtected(view, 'remove_picture')
    def remove_picture(self, REQUEST):
        """ Removes existing profile picture for loggedin user """
        user_id = _get_user_id(REQUEST)
        agent = self._get_ldap_agent(write=True)
        try:
            password = _get_user_password(REQUEST)
            agent.bind_user(user_id, password)
            photo = agent.set_user_picture(user_id, None)
        except Exception:
            _set_session_message(REQUEST, 'error', "Something went wrong.")
        else:
            _set_session_message(REQUEST, 'message', "No image for you.")
        return REQUEST.RESPONSE.redirect(self.absolute_url()
                                         + '/profile_picture_html')

InitializeClass(UsersEditor)
