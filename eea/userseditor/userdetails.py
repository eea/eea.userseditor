#from AccessControl.Permissions import view  #, view_management_screens
#from App.class_init import InitializeClass
#from eea import usersdb
from AccessControl import ClassSecurityInfo # , Unauthorized
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
        return zope2_tmpl(body_html=body_html)

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

    def is_manager(self):
        return ('Manager' in
                self._get_request().AUTHENTICATED_USER.getRoles())

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

    def _get_ldap_agent(self):
        return factories.agent_from_uf(self.restrictedTraverse("/acl_users"))

    def _prepare_user_page(self, uid):
        """Shared by index_html and simple_profile"""
        agent = self._get_ldap_agent()
        ldap_roles = sorted(agent.member_roles_info('user', uid, ('description',)))
        roles = []
        for (role_id, attrs) in ldap_roles:
            roles.append((role_id, attrs.get('description', ('', ))[0]))
        user = agent.user_info(uid)
        user['jpegPhoto'] = agent.get_profile_picture(uid)
        user['certificate'] = agent.get_certificate(uid)
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

        agent          = self._get_ldap_agent()
        log_entries    = list(reversed(agent._get_metadata(uid)))
        VIEWS          = {}
        filtered_roles = set([info[0] for info in roles])
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

            if date.asdatetime().date() >= filter_date:

                if entry['action'] == 'ENABLE_ACCOUNT':
                    roles = entry.get('data', {}).get('roles')
                    for role in roles:
                        if role in filtered_roles:
                            filtered_roles.remove(role)
                if entry['action'] == "DISABLE_ACCOUNT":
                    roles = entry.get('data', {}).get('roles')
                    for role in roles:
                        filtered_roles.add(role)

                if entry['action'] in ["ADDED_TO_ROLE", 'ADDED_AS_ROLE_OWNER']:
                    role = entry.get('data', {}).get('role')
                    if role and role in filtered_roles:
                        filtered_roles.remove(role)
                if entry['action'] in ["REMOVED_FROM_ROLE",
                                       "REMOVED_AS_ROLE_OWNER"]:
                    role = entry.get('data', {}).get('role')
                    if role:
                        filtered_roles.add(role)

        output = []
        for entry in log_entries:
            if output:
                last_entry = output[-1]
                check = ['author', 'action', 'timestamp']
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

        return self._render_template("zpt/userdetails/index.zpt",
                                     context=self, filtered_roles=filtered_roles,
                                     user=user, roles=roles, multi=multi,
                                     log_entries=output)

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
