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


class EnableAccount(BaseActionDetails):
    """ Details for action ENABLE_ACCOUNT
    """

    action_title = "Enabled account"


class DisableAccount(BaseActionDetails):
    """ Details for action DISABLE_ACCOUNT
    """

    action_title = "Disabled account"


class AddToOrg(BaseActionDetails):
    """ Details for action DISABLE_ACCOUNT
    """

    action_title = "Added to organisation"


class RemovedFromOrg(BaseActionDetails):
    """ Details for action DISABLE_ACCOUNT
    """

    action_title = "Removed from organisation"


class AddPendingToOrg(BaseActionDetails):
    """ Details for action ADD_PENDING_TO_ORG
    """

    action_title = "Added pending to organisation"


class RemovedPendingFromOrg(BaseActionDetails):
    """ Details for action REMOVE_PENDING_TO_ORG
    """

    action_title = "Removed pending from organisation"



class AddedToRole(BaseActionDetails):
    """ Details for action DISABLE_ACCOUNT
    """

    action_title = "Added to role"


class RemovedFromRole(BaseActionDetails):
    """ Details for action DISABLE_ACCOUNT
    """

    action_title = "Removed from role"


class AddedAsRoleOwner(BaseActionDetails):
    """ Details for action DISABLE_ACCOUNT
    """

    action_title = "Added as role owner"


class RemovedAsRoleOwner(BaseActionDetails):
    """ Details for action DISABLE_ACCOUNT
    """

    action_title = "Removed from role owner"


class AddedAsPermittedPerson(BaseActionDetails):
    """ Details for action DISABLE_ACCOUNT
    """

    action_title = "Added as permitted person"


class RemovedAsPermittedPerson(BaseActionDetails):
    """ Details for action DISABLE_ACCOUNT
    """

    action_title = "Removed as permitted person"


class SetAsRoleLeader(BaseActionDetails):
    """ Details for action DISABLE_ACCOUNT
    """

    action_title = "Set as role leader"


class UnsetAsRoleLeader(BaseActionDetails):
    """ Details for action DISABLE_ACCOUNT
    """

    action_title = "Removed as role leader"


class SetAsAlternateRoleLeader(BaseActionDetails):
    """ Details for action DISABLE_ACCOUNT
    """

    action_title = "Added as alternate role leader"


class UnsetAsAlternateRoleLeader(BaseActionDetails):
    """ Details for action DISABLE_ACCOUNT
    """

    action_title = "Removed as alternate role leader"
