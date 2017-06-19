from AccessControl import ClassSecurityInfo
from AccessControl.Permissions import view
from AccessControl.SecurityManagement import getSecurityManager
from App.class_init import InitializeClass
from App.config import getConfiguration
from OFS.PropertyManager import PropertyManager
from OFS.SimpleItem import SimpleItem
from Products.LDAPUserFolder.LDAPUser import LDAPUser
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from datetime import datetime
from eea import usersdb
from eea.ldapadmin.nfp_nrc import get_nrc_roles, get_nfps_for_country
from eea.ldapadmin.roles_editor import role_members
from email.mime.text import MIMEText
from image_processor import scale_to
from ldap import INSUFFICIENT_ACCESS
from ldap import CONSTRAINT_VIOLATION, NO_SUCH_OBJECT, SCOPE_BASE
from persistent.mapping import PersistentMapping
from zope.component import getUtility
from zope.component.interfaces import ComponentLookupError
from zope.sendmail.interfaces import IMailDelivery
import deform
import ldap
import logging
import os


cfg = getConfiguration()
cfg.environment.update(os.environ)
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


def _is_authenticated(request):
    return ('Authenticated' in request.AUTHENTICATED_USER.getRoles())


def logged_in_user(request):
    user_id = ''
    if _is_authenticated(request):
        user = request.get('AUTHENTICATED_USER', '')
        user_id = user.id

    return user_id

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
        {'label': 'View', 'action': ''},
    ) + SimpleItem.manage_options
    _properties = (
        {'id': 'title', 'type': 'string', 'mode': 'w', 'label': 'Title'},
        {'id': 'ldap_server', 'type': 'string', 'mode': 'w',
         'label': 'LDAP Server'},
    )
    security = ClassSecurityInfo()

    legacy_ldap_server = ""
    _properties += (
        {'id': 'legacy_ldap_server', 'type': 'string', 'mode': 'w',
         'label': 'Legacy LDAP Server (CIRCA)'},
    )

    def __init__(self, title, ldap_server):
        self.title = title
        self.ldap_server = ldap_server

    def _get_ldap_agent(self, bind=False, write=False):

        # temporary fix while CIRCA is still online
        current_agent = usersdb.UsersDB(ldap_server=self.ldap_server)
        if write and self.legacy_ldap_server != "":
            legacy_agent = CircaUsersDB(ldap_server=self.legacy_ldap_server,
                                        users_dn=CIRCA_USERS_DN_SUFFIX,
                                        encoding="ISO-8859-1")
            agent = DualLDAPProxy(current_agent, legacy_agent)
        else:
            agent = current_agent
        agent._author = logged_in_user(self.REQUEST)
        if bind is True:
            user = getSecurityManager().getUser()
            if isinstance(user, LDAPUser):
                user_dn = user.getUserDN()
                user_pwd = user._getPassword()
                if not user_pwd or user_pwd == 'undef':
                    # This user object did not result from a login
                    user_dn = user_pwd = ''
                else:
                    agent.perform_bind(user_dn, user_pwd)

        return agent

    _zope2_wrapper = PageTemplateFile('zpt/zope2_wrapper.zpt', globals())

    def _render_template(self, name, **options):
        tmpl = load_template(name)
        # Naaya groupware integration. If present, use the standard template
        # of the current site
        macro = self.aq_parent.restrictedTraverse('/').get('gw_macro')
        if macro:
            try:
                layout = self.aq_parent.getLayoutTool().getCurrentSkin()
                main_template = layout.getTemplateById('standard_template')
            except:
                main_template = self.aq_parent.restrictedTraverse(
                    'standard_template.pt')
        else:
            main_template = self.aq_parent.restrictedTraverse(
                'standard_template.pt')
        main_page_macro = main_template.macros['page']
        options.update({'network_name': NETWORK_NAME})
        return self._zope2_wrapper(main_page_macro=main_page_macro,
                                   body_html=tmpl(**options))

    security.declareProtected(view, 'index_html')

    def index_html(self, REQUEST):
        """ view """
        options = {
            'base_url': self.absolute_url(),
        }
        if _is_logged_in(REQUEST):
            agent = self._get_ldap_agent(bind=True)
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

        agent = self._get_ldap_agent(bind=True)
        user_id = _get_user_id(REQUEST)

        errors = _session_pop(REQUEST, SESSION_FORM_ERRORS, {})
        form_data = _session_pop(REQUEST, SESSION_FORM_DATA, None)
        if form_data is None:
            form_data = agent.user_info(user_id)

        orgs = agent.all_organisations()
        orgs = [{'id': k, 'text': v['name'], 'text_native': v['name_native'],
                 'ldap': True} for k, v in orgs.items()]

        user_orgs = list(agent.user_organisations(user_id))
        if not user_orgs:
            org = form_data.get('organisation')
            if org:
                orgs.append({'id': org, 'text': org, 'text_native': '',
                             'ldap': False})
        else:
            org = user_orgs[0]
            org_id = agent._org_id(org)
            form_data['organisation'] = org_id
        orgs.sort(lambda x, y: cmp(x['text'], y['text']))

        choices = [('-', '-')]
        for org in orgs:
            if org['ldap']:
                if org['text_native']:
                    label = u"%s (%s, %s)" % (org['text'], org['text_native'],
                                              org['id'])
                else:
                    label = u"%s (%s)" % (org['text'], org['id'])
            else:
                label = org['text']
            choices.append((org['id'], label))

        schema = user_info_schema.clone()
        widget = deform.widget.SelectWidget(values=choices)
        schema['organisation'].widget = widget

        invalid_nrcs = []

        org_info = None
        country_code = object()
        try:
            org_info = agent.org_info(form_data['organisation'])
        except:
            pass
        else:
            country_code = org_info['country']

        nrc_roles = get_nrc_roles(agent, user_id)
        for nrc_role in nrc_roles:
            nrc_role_info = agent.role_info(nrc_role)
            country_code = nrc_role.split('-')[-1]
            if not org_info or org_info.get('country') != country_code:
                invalid_nrcs.append(nrc_role_info)

        options = {
            'base_url': self.absolute_url(),
            'form_data': form_data,
            'errors': errors,
            'schema': schema,
            'invalid_nrcs': invalid_nrcs,
        }
        options.update(_get_session_messages(REQUEST))

        return self._render_template('zpt/edit_account.zpt', **options)

    security.declareProtected(view, 'edit_account')

    def edit_account(self, REQUEST):
        """ view """
        user_id = _get_user_id(REQUEST)

        user_form = deform.Form(user_info_schema)

        try:
            new_info = user_form.validate(REQUEST.form.items())
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
            agent = self._get_ldap_agent(bind=True, write=True)
            agent.bind_user(user_id, _get_user_password(REQUEST))

            with agent.new_action():
                # make a check if user is changing the organisation
                old_info = agent.user_info(user_id)

                new_org_id = new_info['organisation']
                old_org_id = old_info['organisation']

                new_org_id_valid = agent.org_exists(new_org_id)

                if new_org_id != old_org_id:
                    self._remove_from_all_orgs(agent, user_id)
                    if new_org_id_valid:
                        self._add_to_org(agent, new_org_id, user_id)
                        org_info = agent.org_info(new_org_id)
                    else:
                        org_info = None

                    nrc_roles = get_nrc_roles(agent, user_id)
                    for nrc_role in nrc_roles:
                        nrc_role_info = agent.role_info(nrc_role)
                        country_code = nrc_role.split('-')[-1]
                        # if the organisation is not proper for the nrc,
                        # send an email to all nfps for that country
                        if (not org_info or
                                org_info.get('country') != country_code):
                            nfp_roles = get_nfps_for_country(agent,
                                                             country_code)
                            for nfp_role in nfp_roles:
                                nfps = role_members(agent,
                                                    nfp_role)['users'].keys()
                                for nfp_id in nfps:
                                    nfp_info = agent.user_info(nfp_id)
                                    self._send_nfp_nrc_email(
                                        nrc_role_info, new_info, nfp_info)

                agent.set_user_info(user_id, new_info)

            when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _set_session_message(REQUEST, 'message',
                                 "Profile saved (%s)" % when)

        REQUEST.RESPONSE.redirect(self.absolute_url() + '/edit_account_html')

    def _add_to_org(self, agent, org_id, user_id):
        try:
            agent.add_to_org(org_id, [user_id])
        except ldap.INSUFFICIENT_ACCESS:
            ids = self.aq_parent.objectIds(["Eionet Organisations Editor"])
            if ids:
                obj = self.aq_parent[ids[0]]
                org_agent = obj._get_ldap_agent(bind=True)
                org_agent.add_to_org(org_id, [user_id])
            else:
                raise

    def _remove_from_all_orgs(self, agent, user_id):
        orgs = agent.user_organisations(user_id)
        for org_dn in orgs:
            org_id = agent._org_id(org_dn)
            try:
                agent.remove_from_org(org_id, [user_id])
            except ldap.NO_SUCH_ATTRIBUTE:  # user is not in org
                pass
            except ldap.INSUFFICIENT_ACCESS:
                ids = self.aq_parent.objectIds(["Eionet Organisations Editor"])
                if ids:
                    obj = self.aq_parent[ids[0]]
                    org_agent = obj._get_ldap_agent(bind=True)
                    try:
                        org_agent.remove_from_org(org_id, [user_id])
                    except ldap.NO_SUCH_ATTRIBUTE:    # user is not in org
                        pass
                else:
                    raise

    def _send_nfp_nrc_email(self, nrc_role_info, user_info, nfp_info):
        options = {'nrc_role_info': nrc_role_info,
                   'user_info': user_info,
                   'nfp_info': nfp_info}
        email_template = load_template('zpt/nfp_nrc_change_organisation.zpt')
        email_password_body = email_template.pt_render(options)
        addr_from = "no-reply@eea.europa.eu"
        addr_to = nfp_info['email']

        message = MIMEText(email_password_body.encode('utf-8'))
        message['From'] = addr_from
        message['To'] = addr_to
        message['Subject'] = "%s %s no longer valid member of %s NRC" % \
            (user_info['first_name'], user_info['last_name'],
             nrc_role_info['description'])

        try:
            mailer = getUtility(IMailDelivery, name="naaya-mail-delivery")
            mailer.send(addr_from, [addr_to], message)
        except TypeError:
            mailer = getUtility(IMailDelivery, name="naaya-mail-delivery")
            mailer.send(addr_from, [addr_to], message.as_string())
        except ComponentLookupError:
            mailer = getUtility(IMailDelivery, name="Mail")
            mailer.send(addr_from, [addr_to], message.as_string())

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
        agent = self._get_ldap_agent(bind=True, write=True)
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
        except CONSTRAINT_VIOLATION, e:
            if e.message['info'] in [
                    'Password fails quality checking policy']:
                try:
                    defaultppolicy = agent.conn.search_s(
                        'cn=defaultppolicy,ou=pwpolicies,o=EIONET,'
                        'l=Europe',
                        SCOPE_BASE)
                    p_length = defaultppolicy[0][1]['pwdMinLength'][0]
                    message = '%s (min. %s characters)' % (
                        e.message['info'], p_length)
                except NO_SUCH_OBJECT:
                    message = e.message['info']
            else:
                message = e.message['info']
            _set_session_message(REQUEST, 'error', message)
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
        agent = self._get_ldap_agent(bind=True)

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
            agent = self._get_ldap_agent(bind=True, write=True)
            try:
                password = _get_user_password(REQUEST)
                agent.bind_user(user_id, password)
                color = (255, 255, 255)
                picture_data = scale_to(picture_data, WIDTH, HEIGHT, color)
                success = agent.set_user_picture(user_id, picture_data)
            except ValueError:
                _set_session_message(REQUEST, 'error',
                                     "Error updating picture")
                return REQUEST.RESPONSE.redirect(self.absolute_url() +
                                                 '/profile_picture_html')
            if success:
                success_text = "That's a beautiful picture."
                _set_session_message(REQUEST, 'message', success_text)
            else:
                _set_session_message(REQUEST, 'error',
                                     "Error updating picture.")
        else:
            _set_session_message(REQUEST, 'error',
                                 "You must provide a JPG file.")
        return REQUEST.RESPONSE.redirect(self.absolute_url() +
                                         '/profile_picture_html')

    security.declareProtected(view, 'profile_picture_jpg')

    def profile_picture_jpg(self, REQUEST):
        """
        Returns jpeg picture data for logged-in user.
        Assumes picture is available in LDAP.

        """
        user_id = _get_user_id(REQUEST)
        agent = self._get_ldap_agent(bind=True)
        photo = agent.get_profile_picture(user_id)
        REQUEST.RESPONSE.setHeader('Content-Type', 'image/jpeg')
        return photo

    security.declareProtected(view, 'remove_picture')

    def remove_picture(self, REQUEST):
        """ Removes existing profile picture for loggedin user """
        user_id = _get_user_id(REQUEST)
        agent = self._get_ldap_agent(bind=True, write=True)
        try:
            password = _get_user_password(REQUEST)
            agent.bind_user(user_id, password)
            agent.set_user_picture(user_id, None)
        except Exception:
            _set_session_message(REQUEST, 'error', "Something went wrong.")
        else:
            _set_session_message(REQUEST, 'message', "No image for you.")
        return REQUEST.RESPONSE.redirect(self.absolute_url() +
                                         '/profile_picture_html')

InitializeClass(UsersEditor)
