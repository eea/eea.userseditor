from AccessControl import ClassSecurityInfo  # , Unauthorized
from Acquisition import Implicit
from App.config import getConfiguration
from DateTime import DateTime
from OFS.SimpleItem import SimpleItem
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from eea.usersdb import factories
from zope.component import getMultiAdapter
from zope.pagetemplate.pagetemplatefile import PageTemplateFile as Z3Template
import json
import logging

cfg = getConfiguration()
NETWORK_NAME = getattr(cfg, 'environment', {}).get('NETWORK_NAME', 'EIONET')
eionet_edit_users = 'Eionet edit users'

log = logging.getLogger(__name__)

manage_add_userdetails_html = PageTemplateFile('zpt/userdetails/manage_add',
                                               globals())


def manage_add_userdetails(parent, id, REQUEST=None):
    """ Create a new UserDetails object """
    form = (REQUEST.form if REQUEST is not None else {})
    obj = UserDetails()
    obj.title = form.get('title', id)
    obj._setId(id)
    parent._setObject(id, obj)

    if REQUEST is not None:
        REQUEST.RESPONSE.redirect(parent.absolute_url() + '/manage_workspace')


def _is_authenticated(request):
    return ('Authenticated' in request.AUTHENTICATED_USER.getRoles())


def load_template(name, _memo={}):
    if name not in _memo:
        _memo[name] = Z3Template(name, globals())
    return _memo[name]

zope2_wrapper = PageTemplateFile('zpt/zope2_wrapper.zpt', globals())


class TemplateRenderer(Implicit):
    def __init__(self, common_factory=lambda ctx: {}):
        self.common_factory = common_factory

    def render(self, name, **options):
        context = self.aq_parent
        template = load_template(name)
        namespace = template.pt_getContext((), options)
        namespace['common'] = self.common_factory(context)
        return template.pt_render(namespace)

    def wrap(self, body_html):
        context = self.aq_parent
        zope2_tmpl = zope2_wrapper.__of__(context)

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
        return zope2_tmpl(main_page_macro=main_page_macro, body_html=body_html)

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
        user_id = str(user.id)

    return user_id


class UserDetails(SimpleItem):
    meta_type = 'Eionet User Details'
    security = ClassSecurityInfo()
    icon = '++resource++eea.userseditor-www/users_editor.gif'

    _render_template = TemplateRenderer(CommonTemplateLogic)

    def __init__(self):
        super(UserDetails, self).__init__()

    def _get_ldap_agent(self, bind=False):
        agent = factories.agent_from_uf(
            self.restrictedTraverse("/acl_users"),
            bind=bind
        )
        agent._author = logged_in_user(self.REQUEST)
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
            user['organisation_title'] = agent.org_info(
                user['organisation'])['name']
        else:
            user['organisation_title'] = ''
        return user, roles

    security.declarePublic("index_html")

    def index_html(self, REQUEST):
        """ """
        uid = REQUEST.form.get('uid')
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
