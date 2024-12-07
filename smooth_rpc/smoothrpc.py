"""Main SmoothRPC implementations."""

import asyncio
import inspect
import logging
import pickle
import types
from collections.abc import Callable, Generator
from dataclasses import dataclass
from functools import partial, wraps
from typing import NamedTuple, ParamSpec, TypeVar, cast

from smooth_rpc.exceptions import (
    RpcApiVersionMismatchError,
    RpcDecoratorError,
    RpcInternalError,
    RpcInvalidVersionError,
    RpcNoSuchApiError,
    RpcProtocolError,
    RpcSerializationError,
)
from smooth_rpc.network import AsyncNetworkConnection

_log = logging.getLogger(__name__)


class VersionRange(NamedTuple):
    """A closed range."""

    min_version: int | None
    max_version: int | None

    def __contains__(self, version: object) -> bool:
        """Return if the given version is in [min_version, max_version]."""
        if not isinstance(version, int):
            raise RpcInternalError("Can only compare int's")
        return (self.min_version is None or self.min_version <= version) and (
            self.max_version is None or version <= self.max_version
        )


@dataclass
class ApiFunctionSpec:
    """Function attributes, as stored by 'rpc' decorator."""

    name: str | None
    version_range: VersionRange


@dataclass
class ApiCall:
    """Network object sent from client to host."""

    func_name: str
    api_version: int
    args: tuple
    kwargs: dict

    def __str__(self) -> str:
        """Represent this call object as string. Used by tests."""
        return f"{self.func_name}(args={self.args!r}, kwargs={self.kwargs!r}, api_version={self.api_version})"


Param = ParamSpec("Param")
RetType = TypeVar("RetType")


def _create_call_wrapper(
    connection: AsyncNetworkConnection,
    func_name: str,
    api_version: int,
    method_self: object,
    func: Callable[Param, RetType],
) -> Callable[Param, RetType]:
    @wraps(func)
    async def do_call(_self: object, *args: tuple, **kwargs: dict) -> RetType:
        # Construct call object, pickle and send
        call_obj = ApiCall(func_name, api_version, args, kwargs)
        _log.info("Sending RPC call %s", call_obj)
        in_data = pickle.dumps(call_obj)
        await connection.send_message(in_data)

        # Receive response and unpickle
        out_data = await connection.recv_message()
        try:
            out = pickle.loads(out_data)  # noqa: S301, use pickle anyway, for lack of a safe alternative
        except (pickle.UnpicklingError, IndexError, AttributeError) as exc:
            # server should never send us something that we cannot unpickle
            raise RpcProtocolError("Received response that could not be unpickled") from exc
        _log.info("Call %s returned %r", func_name, out)

        if isinstance(out, Exception):
            raise out  # re-raise received exception
        return cast(RetType, out)

    return types.MethodType(do_call, method_self)


def _create_exception_wrapper(method_self: object, func: Callable[Param, RetType]) -> Callable[Param, RetType]:
    @wraps(func)
    async def do_throw(_self: object, *_args: tuple, **_kwargs: dict) -> RetType:
        raise RpcApiVersionMismatchError("Client API disabled due to api version restriction.")

    return types.MethodType(do_throw, method_self)


def _iterate_functions(command_object: object) -> Generator[tuple[str, str, VersionRange, Callable]]:
    for superclass in command_object.__class__.__mro__:
        for func_object_name, func in superclass.__dict__.items():
            api_spec = getattr(func, "__is_part_of_smooth_api", None)
            if api_spec is None:
                continue
            if not inspect.iscoroutinefunction(func):
                raise RpcDecoratorError("Not an async function")
            if not isinstance(api_spec, ApiFunctionSpec):
                raise RpcDecoratorError("Decorator malfunction")

            func_name = api_spec.name or func_object_name
            yield (func_object_name, func_name, api_spec.version_range, func)


def instrument_client_commands(connection: AsyncNetworkConnection, api_version: int, *command_objects: object) -> None:
    """Replace all functions in command_object that are marked with the api decorator with remote calls."""
    for command_object in command_objects:
        for org_func_name, func_name, version_range, func in _iterate_functions(command_object):
            if api_version in version_range:
                wrapper = _create_call_wrapper(connection, func_name, api_version, command_object, func)
            else:
                wrapper = _create_exception_wrapper(command_object, func)
            setattr(command_object, org_func_name, wrapper)


class SmoothRPCHost:
    """Host for the RPC API."""

    def __init__(self) -> None:
        """
        Create a RPC Host.

        Actually, just a dict of all registered commands and a connection-acceptor function.
        """
        self.commands: dict[str, list[tuple[VersionRange, Callable]]] = {}

    def register_commands(self, command_object: object) -> None:
        """Add all rpc-decorator marked functions in command_object to host command list."""
        count = 0
        for _org_func_name, func_name, version_range, func in _iterate_functions(command_object):
            func_bound = partial(func, command_object)
            self.commands.setdefault(func_name, []).append((version_range, func_bound))
            count += 1
        if count == 0:
            raise RpcDecoratorError("No decorated functions found")
        _log.info("Registered %d API endpoints", count)

    async def _call_command(self, call_obj: ApiCall) -> object:
        _log.info("Received RPC call %s", call_obj)

        try:
            version_list = self.commands[call_obj.func_name]
        except KeyError as err:
            raise RpcNoSuchApiError("No such api", call_obj.func_name) from err

        # find the first api that supports the requested api version
        matching_func: Callable
        for version_range, func in version_list:
            if call_obj.api_version in version_range:
                matching_func = func
                break
        else:
            raise RpcInvalidVersionError("Api endpoint does not support api version", call_obj.api_version)

        out = await matching_func(*call_obj.args, **call_obj.kwargs)
        _log.info("Call %s returned %r", call_obj.func_name, out)
        return out

    def _pack_result(self, obj: object) -> bytes:
        """Return the object pickled, or a pickled exception that it cannot be pickled."""
        try:
            return pickle.dumps(obj)
        except (pickle.PicklingError, AttributeError) as exc:
            return pickle.dumps(RpcSerializationError("Could not pickle object", exc))

    def _unpack_call(self, data: bytes) -> ApiCall:
        """Unpickle a received object and check the type."""
        try:
            call_obj = pickle.loads(data)  # noqa: S301, use pickle anyway, for lack of a safe alternative
        except (pickle.UnpicklingError, IndexError, AttributeError) as exc:
            raise RpcProtocolError("Failed to unpickle received data") from exc
        if not isinstance(call_obj, ApiCall):
            raise RpcProtocolError("Invalid object received")
        return call_obj

    async def _handle_one_command(self, connection: AsyncNetworkConnection) -> None:
        """Handle exactly one RPC call, receive/call/send."""
        in_data = await connection.recv_message()  # network exceptions propagate upwards
        call_obj = self._unpack_call(in_data)  # protocol errors propagate upwards

        try:
            out = await self._call_command(call_obj)
        except Exception as exc:  # noqa: BLE001, blind-catch exception
            _log.warning("Caught exception in call, returning to client: %r", exc)
            out = exc

        data = self._pack_result(out)
        await connection.send_message(data)  # network exceptions propagate upwards

    async def accept_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Use an existing connection for answering requests. Formatted for use with asyncio.Server."""
        connection = AsyncNetworkConnection(reader, writer)
        _log.info("Hosting client %s", connection.friendly_name)
        try:
            while True:
                await self._handle_one_command(connection)
        except asyncio.exceptions.IncompleteReadError as exc:
            # suppress exception on normal close
            if not reader.at_eof() or len(exc.partial) > 0:
                raise
        finally:
            _log.info("Hosting client %s closed", connection.friendly_name)


def api(*, func_name: str | None = None, min_version: int | None = None, max_version: int | None = None) -> Callable:
    """
    Mark a function as part of the API, use as decorator.

    Arguments are:
    - func_name, override the api name (defaults to function name).
    - min_version, first api version that supports this call.
    - max_version, last api version that supports this call.
    """

    def api_decorator(func: Callable[Param, RetType]) -> Callable[Param, RetType]:
        # Set a marker on the function so it can be instrumented later.
        # Neither mypy nor flake8 like us accessing a private non-existing  member
        spec = ApiFunctionSpec(func_name, VersionRange(min_version, max_version))
        func.__is_part_of_smooth_api = spec  # type: ignore[attr-defined]  # noqa: SLF001
        return func

    return api_decorator
