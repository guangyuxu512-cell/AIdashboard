from app.modules.access.contracts import HumanPrincipal
from app.modules.access.exceptions import HumanAuthenticationRequiredError


def get_human_principal() -> HumanPrincipal:
    """Fail-closed seam for the future Human Session authenticator.

    The current User model has no stable login identifier and the project has no
    Human Session contract. Tests and a future authentication adapter may
    override this dependency; request headers are deliberately not accepted as
    user identity.
    """

    raise HumanAuthenticationRequiredError()
