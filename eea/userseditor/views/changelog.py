from Products.Five import BrowserView
from eea.usersdb import factories
from zope.interface import Interface, Attribute, implements


class IActionDetails(Interface):
    """ A view that presents details about user changelog actions
    """

    action_title = Attribute("Human readable title for this action")
    author       = Attribute("Author of changes, in html format")
    details      = Attribute("Action details in html format")


class BaseActionDetails(BrowserView):
    """ Generic implementation of IActionDetails
    """

    implements(IActionDetails)

    @property
    def action_title(self):
        raise NotImplementedError

    def details(self, entry):
        self.entry = entry
        return self.index()

    def author(self, entry):
        if entry['author'] == 'unknown user':
            return entry['author']

        user_info = self._get_ldap_agent().user_info(entry['author'])
        return u"%s (%s)" % (user_info['full_name'], entry['author'])

    def _get_ldap_agent(self):
        return factories.agent_from_uf(self.context.restrictedTraverse("/acl_users"))

    def merge(self, roles):
        """ Merge the entries so that the only the leaf roles are displayed

        >>> roles = [
        ... 'eionet-nfp-mc-dk',
        ... 'eionet-nfp-mc',
        ... 'eionet-nfp',
        ... 'eionet',
        ... 'eionet-nfp-mc-se',
        ... 'eionet-nfp-mc',
        ... 'eionet-nfp',
        ... 'eionet',
        ... ]
        >>> print merge(roles)
        ['eionet-nfp-mc-dk', 'eionet-nfp-mc-se']
        """
        roles = sorted(roles)
        out = []
        last = len(roles) - 1
        for i, role in enumerate(roles):
            if i == last:
                out.append(role)
                break
            if role not in roles[i+1]:
                out.append(role)

        return out


class BaseRoleDetails(BaseActionDetails):

    def details(self, entry):
        roles = [x['role'] for x in entry['data']]
        self.roles = self.merge(roles)
        return self.index()


class BaseOrganisationDetails(object):

    @property
    def organisation(self):
        for entry in self.entry['data']:
            org = entry.get('organisation')
            if org:
                return self._get_ldap_agent().org_info(org)['name']

        return ""


class EnableAccount(BaseActionDetails):
    """ Details for action ENABLE_ACCOUNT
    """

    action_title = "Enabled account"


class DisableAccount(BaseActionDetails):
    """ Details for action DISABLE_ACCOUNT
    """

    action_title = "Disabled account"


class AddToOrg(BaseActionDetails, BaseOrganisationDetails):
    """ Details for action ADD_TO_ORG
    """

    action_title = "Added to organisation"


class RemovedFromOrg(BaseActionDetails, BaseOrganisationDetails):
    """ Details for action REMOVED_FROM_ORG
    """

    action_title = "Removed from organisation"


class AddPendingToOrg(BaseActionDetails, BaseOrganisationDetails):
    """ Details for action ADD_PENDING_TO_ORG
    """

    action_title = "Added pending to organisation"


class RemovedPendingFromOrg(BaseActionDetails, BaseOrganisationDetails):
    """ Details for action REMOVE_PENDING_TO_ORG
    """

    action_title = "Removed pending from organisation"


class AddedToRole(BaseRoleDetails):
    """ Details for action ADDED_TO_ROLE
    """

    action_title = "Added to role"


class RemovedFromRole(BaseRoleDetails):
    """ Details for action REMOVED_FROM_ROLE
    """

    action_title = "Removed from role"


class AddedAsRoleOwner(BaseActionDetails):
    """ Details for action ADDED_AS_ROLE_OWNER
    """

    action_title = "Added as role owner"


class RemovedAsRoleOwner(BaseActionDetails):
    """ Details for action REMOVED_AS_ROLE_OWNER
    """

    action_title = "Removed from role owner"


class AddedAsPermittedPerson(BaseActionDetails):
    """ Details for action ADDED_AS_PERMITTED_PERSON
    """

    action_title = "Added as permitted person"


class RemovedAsPermittedPerson(BaseActionDetails):
    """ Details for action REMOVED_AS_PERMITTED_PERSON
    """

    action_title = "Removed as permitted person"


class SetAsRoleLeader(BaseActionDetails):
    """ Details for action SET_AS_ROLE_LEADER
    """

    action_title = "Set as role leader"


class UnsetAsRoleLeader(BaseActionDetails):
    """ Details for action UNSET_AS_ROLE_LEADER
    """

    action_title = "Removed as role leader"


class SetAsAlternateRoleLeader(BaseActionDetails):
    """ Details for action SET_AS_ALTERNATE_ROLE_LEADER
    """

    action_title = "Added as alternate role leader"


class UnsetAsAlternateRoleLeader(BaseActionDetails):
    """ Details for action UNSET_AS_ALTERNATE_ROLE_LEADEg
    """

    action_title = "Removed as alternate role leader"
