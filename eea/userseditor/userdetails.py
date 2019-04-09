import json
import logging
import os
from datetime import datetime, timedelta

from zope.component import getMultiAdapter

from AccessControl import ClassSecurityInfo  # , Unauthorized
from AccessControl.Permissions import view_management_screens
from Acquisition import Implicit
from App.config import getConfiguration
from DateTime import DateTime
from eea.ldapadmin import ldap_config
from OFS.PropertyManager import PropertyManager
from OFS.SimpleItem import SimpleItem
from persistent.mapping import PersistentMapping
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from z3c.pt.pagetemplate import PageTemplateFile as ChameleonTemplate
from zExceptions import NotFound

cfg = getConfiguration()
cfg.environment.update(os.environ)
NETWORK_NAME = getattr(cfg, 'environment', {}).get('NETWORK_NAME', 'EIONET')
eionet_edit_users = 'Eionet edit users'

log = logging.getLogger(__name__)

manage_add_userdetails_html = PageTemplateFile(
    'zpt/userdetails/user_manage_add.zpt', globals())
manage_add_userdetails_html.ldap_config_edit_macro = ldap_config.edit_macro
manage_add_userdetails_html.config_defaults = lambda: ldap_config.defaults


def manage_add_userdetails(parent, id, REQUEST=None):
    """ Create a new UserDetails object """
    form = (REQUEST.form if REQUEST is not None else {})
    config = ldap_config.read_form(form)
    obj = UserDetails(config)
    obj.title = form.get('title', id)
    obj._setId(id)
    parent._setObject(id, obj)

    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(parent.absolute_url() + '/manage_workspace')


def _is_authenticated(request):
    return ('Authenticated' in request.AUTHENTICATED_USER.getRoles())


def load_template(name, context=None, _memo={}):
    if name not in _memo:
        tpl = ChameleonTemplate(name)

        if context is not None:
            bound = tpl.bind(context)
            _memo[name] = bound
        else:
            _memo[name] = tpl

    return _memo[name]


zope2_wrapper = PageTemplateFile('zpt/zope2_wrapper.zpt', globals())
plone5_wrapper = PageTemplateFile('zpt/plone5_wrapper.zpt', globals())


class TemplateRenderer(Implicit):
    def __init__(self, common_factory=lambda ctx: {}):
        self.common_factory = common_factory

    def render(self, name, **options):
        context = self.aq_parent
        template = load_template(name, context)

        try:
            namespace = template.pt_getContext((), options)
        except AttributeError:      # Plone5 compatibility
            namespace = template.im_self._pt_get_context(
                context, context.REQUEST, options)

        namespace['common'] = self.common_factory(context)
        namespace['browserview'] = self.browserview

        if hasattr(template, 'pt_render'):
            return template.pt_render(namespace)
        else:
            return template.im_self.render(**namespace)

    def browserview(self, context, name):
        return getMultiAdapter((context, self.aq_parent.REQUEST), name=name)

    def wrap(self, body_html):
        context = self.aq_parent
        plone = False
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
            main_page_macro = main_template.macros['page']
        else:
            main_template = self.aq_parent.restrictedTraverse(
                'main_template')
            plone = True
            main_page_macro = main_template.macros['master']

        if plone:
            tmpl = plone5_wrapper.__of__(context)
        else:
            tmpl = zope2_wrapper.__of__(context)

        return tmpl(main_page_macro=main_page_macro, body_html=body_html)

    def __call__(self, name, **options):
        return self.wrap(self.render(name, **options))


class CommonTemplateLogic(object):
    def __init__(self, context):
        self.context = context

    def _get_request(self):
        return self.context.REQUEST

    def base_url(self):
        return self.context.absolute_url()

    def portal_url(self):
        return self.context.restrictedTraverse("/").absolute_url()

    def is_authenticated(self):
        return _is_authenticated(self._get_request())

    def can_edit_users(self):
        user = self.context.REQUEST.AUTHENTICATED_USER

        return bool(user.has_permission(eionet_edit_users, self.context))

    @property
    def macros(self):
        return load_template('zpt/macros.zpt').macros

    @property
    def network_name(self):
        """ E.g. EIONET, SINAnet etc. """

        return NETWORK_NAME


def logged_in_user(request):
    user_id = ''

    if _is_authenticated(request):
        user = request.get('AUTHENTICATED_USER', '')

        if user:
            user_id = user.getId()

    return user_id


class UserDetails(SimpleItem):
    meta_type = 'Eionet User Details'
    security = ClassSecurityInfo()
    icon = '++resource++eea.userseditor-www/users_editor.gif'

    _render_template = TemplateRenderer(CommonTemplateLogic)

    manage_options = (
        {'label': 'Configure', 'action': 'manage_edit'},
        {'label': 'View', 'action': ''},
    ) + PropertyManager.manage_options + SimpleItem.manage_options

    security.declareProtected(view_management_screens, 'manage_edit')
    manage_edit = PageTemplateFile('zpt/userdetails/user_manage_edit.zpt',
                                   globals())
    manage_edit.ldap_config_edit_macro = ldap_config.edit_macro

    security.declareProtected(view_management_screens, 'get_config')

    def get_config(self):
        config = dict(getattr(self, '_config', {}))

        return config

    security.declareProtected(view_management_screens, 'manage_edit_save')

    def manage_edit_save(self, REQUEST):
        """ save changes to configuration """
        self._config.update(ldap_config.read_form(REQUEST.form, edit=True))
        REQUEST.RESPONSE.redirect(self.absolute_url() + '/manage_edit')

    def __init__(self, config={}):
        super(UserDetails, self).__init__()
        self._config = PersistentMapping(config)

    def _get_ldap_agent(self, bind=True, secondary=False):
        agent = ldap_config.ldap_agent_with_config(self._config, bind,
                                                   secondary=secondary)
        try:
            agent._author = logged_in_user(self.REQUEST)
        except AttributeError:
            agent._author = "System user"

        return agent

    def _prepare_user_page(self, uid):
        """Shared by index_html and simple_profile"""
        is_auth = _is_authenticated(self.REQUEST)
        agent = self._get_ldap_agent(bind=is_auth)
        ldap_roles = sorted(agent.member_roles_info('user',
                                                    uid,
                                                    ('description',)))
        roles = []

        for (role_id, attrs) in ldap_roles:
            roles.append((role_id,
                          attrs.get('description', ('', ))[0].decode('utf8')))
        user = agent.user_info(uid)
        user['jpegPhoto'] = agent.get_profile_picture(uid)
        user['certificate'] = agent.get_certificate(uid)

        if user['organisation']:
            if user['organisation'] == 'eea':
                user['organisation'] = 'eu_eea'
            org_info = agent.org_info(user['organisation'])
            org_id = org_info.get('id')

            if 'INVALID' in org_id:
                user['organisation'] = org_id.decode('utf8')
            user['organisation_title'] = org_info['name']
        else:
            user['organisation_title'] = ''
        pwdChangedTime = user['pwdChangedTime']

        if pwdChangedTime:
            pwdChangedTime = datetime.strptime(pwdChangedTime, '%Y%m%d%H%M%SZ')
            user['pwdChanged'] = pwdChangedTime.strftime('%Y-%m-%d %H:%M:%S')
            user['pwdExpired'] = datetime.now() - timedelta(
                days=365) > pwdChangedTime
        else:
            user['pwdChanged'] = ''
            user['pwdExpired'] = True

        return user, roles

    security.declarePublic("index_html")

    def index_html(self, REQUEST):
        """ """
        uid = REQUEST.form.get('uid')

        if not uid:
            # a missing uid can only mean this page is called by accident

            return
        date_for_roles = REQUEST.form.get('date_for_roles')

        if "," in uid:
            user = None
            roles = None
            multi = json.dumps({'users': uid.split(",")})
        else:
            multi = None
            user, roles = self._prepare_user_page(uid)

        is_auth = _is_authenticated(REQUEST)
        # we can only connect to ldap with bind=True if we have an
        # authenticated user
        agent = self._get_ldap_agent(bind=is_auth)

        user_dn = agent._user_dn(uid)
        log_entries = list(reversed(agent._get_metadata(user_dn)))
        VIEWS = {}
        filtered_roles = set([info[0] for info in roles])   # + owner_roles)

        if date_for_roles:
            filter_date = DateTime(date_for_roles).asdatetime().date()
        else:
            filter_date = DateTime().asdatetime().date()

        for entry in log_entries:
            date = DateTime(entry['timestamp']).toZone("CET")
            entry['timestamp'] = date.ISO()
            view = VIEWS.get(entry['action'])

            if not view:
                view = getMultiAdapter((self, self.REQUEST),
                                       name="details_" + entry['action'])
                VIEWS[entry['action']] = view
            entry['view'] = view

            _roles = entry.get('data', {}).get('roles')
            _role = entry.get('data', {}).get('role')

            if date.asdatetime().date() >= filter_date:
                if entry['action'] == 'ENABLE_ACCOUNT':
                    filtered_roles.difference_update(set(_roles))
                elif entry['action'] == "DISABLE_ACCOUNT":
                    filtered_roles.update(set(_roles))
                elif entry['action'] in ["ADDED_TO_ROLE"]:
                    if _role and _role in filtered_roles:
                        filtered_roles.remove(_role)
                elif entry['action'] in ["REMOVED_FROM_ROLE"]:
                    if _role:
                        filtered_roles.add(_role)

        output = []

        for entry in log_entries:
            if output:
                last_entry = output[-1]
                check = ['author', 'action']
                flag = True

                for k in check:
                    if last_entry[k] != entry[k]:
                        flag = False

                        break

                if flag:
                    last_entry['data'].append(entry['data'])
                else:
                    entry['data'] = [entry['data']]
                    output.append(entry)
            else:
                entry['data'] = [entry['data']]
                output.append(entry)

        removed_roles = []

        if user.get('status') == 'disabled':
            auth_user = self.REQUEST.AUTHENTICATED_USER

            if not bool(auth_user.has_permission(eionet_edit_users, self)):
                raise NotFound("User '%s' does not exist" % uid)
            # process log entries to list the roles the user had before
            # being disabled

            for entry in log_entries:
                if entry['action'] == 'DISABLE_ACCOUNT':
                    for role in entry['data'][0]['roles']:
                        try:
                            role_description = agent.role_info(role)[
                                'description']
                        except:
                            role_description = ("This role doesn't exist "
                                                "anymore")
                        removed_roles.append((role, role_description))

                    break

        return self._render_template(
            "zpt/userdetails/index.zpt", context=self,
            filtered_roles=filtered_roles, user=user, roles=roles,
            removed_roles=removed_roles, multi=multi, log_entries=output)

    security.declarePublic("simple_profile")

    def simple_profile(self, REQUEST):
        """ """
        uid = REQUEST.form.get('uid')
        user, roles = self._prepare_user_page(uid)
        tr = TemplateRenderer(CommonTemplateLogic)

        return tr.__of__(self).render("zpt/userdetails/simple.zpt",
                                      user=user, roles=roles)

    security.declarePublic("userphoto_jpeg")

    def userphoto_jpeg(self, REQUEST):
        """ """
        uid = REQUEST.form.get('uid')
        agent = self._get_ldap_agent()
        REQUEST.RESPONSE.setHeader('Content-Type', 'image/jpeg')

        return agent.get_profile_picture(uid)

    security.declarePublic("usercertificate")

    def usercertificate(self, REQUEST):
        """ """
        uid = REQUEST.form.get('uid')
        agent = self._get_ldap_agent()
        REQUEST.RESPONSE.setHeader('Content-Type', 'application/pkix-cert')

        return agent.get_certificate(uid)

    security.declarePublic("get_user_orgs")

    def get_user_orgs(self, user_id=None):
        """ Convenience method to be used in the /directory/ folder of EIONET
        """

        if user_id is None:
            user_id = self.REQUEST.form.get('uid')

        agent = self._get_ldap_agent()

        return agent.orgs_for_user(user_id)
