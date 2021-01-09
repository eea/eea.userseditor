''' userdetails view '''
import json

from zope.component import getMultiAdapter

from DateTime import DateTime
from Products.Five.browser import BrowserView
from zExceptions import NotFound
from eea.ldapadmin.ui_common import get_role_name
from eea.userseditor.permissions import EIONET_EDIT_USERS
from eea.userseditor.userdetails import CommonTemplateLogic


# pylint: disable=too-many-statements,too-many-branches,too-many-locals
class UserDetailsView(BrowserView):
    """UserDetailsView."""

    def __call__(self):
        REQUEST = self.request
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
            user, roles = self.context._prepare_user_page(uid)

        is_auth = ('Authenticated' in REQUEST.AUTHENTICATED_USER.getRoles())
        # we can only connect to ldap with bind=True if we have an
        # authenticated user
        agent = self.context._get_ldap_agent(bind=is_auth)

        user_dn = agent._user_dn(uid)
        log_entries = list(reversed(agent._get_metadata(user_dn)))
        VIEWS = {}
        filtered_roles = set([info[0] for info in roles])   # + owner_roles)

        if date_for_roles:
            filter_date = DateTime(date_for_roles).toZone("CET").asdatetime()
        else:
            filter_date = DateTime().toZone("CET").asdatetime()

        for entry in log_entries:
            date = DateTime(entry['timestamp']).toZone("CET")
            entry['timestamp'] = date.ISO()
            view = VIEWS.get(entry['action'])

            if not view:
                view = getMultiAdapter((self.context, self.request),
                                       name="details_" + entry['action'])
                VIEWS[entry['action']] = view
            entry['view'] = view

            _roles = entry.get('data', {}).get('roles')
            _role = entry.get('data', {}).get('role')

            if date.asdatetime() >= filter_date:
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
            auth_user = REQUEST.AUTHENTICATED_USER

            if not bool(
                auth_user.has_permission(EIONET_EDIT_USERS, self.context) or
                    self.context.nfp_for_country()):
                raise NotFound("User '%s' does not exist" % uid)
            # process log entries to list the roles the user had before
            # being disabled

            for entry in log_entries:
                if entry['action'] == 'DISABLE_ACCOUNT':
                    for role in entry['data'][0]['roles']:
                        try:
                            role_description = agent.role_info(role)[
                                'description']
                        except Exception:
                            role_description = ("This role doesn't exist "
                                                "anymore")
                        removed_roles.append((role, role_description))

                    break

        self.filtered_roles = [(role, get_role_name(agent, role))
                               for role in filtered_roles]
        self.user = user
        self.roles = roles
        self.removed_roles = removed_roles
        self.multi = multi
        self.log_entries = output
        self.common = CommonTemplateLogic(self.context)

        return self.index()
