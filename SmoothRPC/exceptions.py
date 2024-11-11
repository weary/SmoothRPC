class RpcError(Exception):
    """Base SmoothRPC exception."""


class RpcApiVersionMismatchError(RpcError):
    """Client tried to call an API endpoint that is not supported by the current api-version."""


class RpcNoSuchApiError(RpcError):
    """Host could not find the named API endpoint."""


class RpcInvalidVersionError(RpcError):
    """Host found the API endpoint, but no acceptable version(range) was found."""


class RpcProtocolError(RpcError):
    """Host received something unexpected."""


class RpcInternalError(RpcError):
    """Host caught an exception while serializing an exception."""


class RpcDecoratorError(RpcError):
    """An rpc decorator was used on something that is not an async function."""
