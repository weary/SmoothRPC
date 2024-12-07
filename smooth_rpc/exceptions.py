"""All exceptions throw from the SmoothRPC module."""


class RpcError(Exception):
    """Base SmoothRPC exception."""


class RpcApiVersionMismatchError(RpcError):
    """Client tried to call an API endpoint that is not supported by the current api-version."""


class RpcNoSuchApiError(RpcError):
    """Host could not find the named API endpoint."""


class RpcInvalidVersionError(RpcError):
    """Host found the API endpoint, but no acceptable version(range) was found."""


class RpcProtocolError(RpcError):
    """Host or client received something unexpected."""


class RpcSerializationError(RpcError):
    """Cannot serialize(pickle) object."""


class RpcInternalError(RpcError):
    """Library failure, should not happen."""


class RpcDecoratorError(RpcError):
    """The rpc decorator was used on something that is not an async function."""


class RpcAddressError(RpcError):
    """Unrecognized address."""


class RpcMaxSizeExceededError(RpcError):
    """Message size too big."""
