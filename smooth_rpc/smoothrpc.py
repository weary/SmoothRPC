"""Main SmoothRPC implementations."""

import inspect
import logging
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
)
from smooth_rpc.network import AsyncNetwork

_log = logging.getLogger(__name__)


class VersionRange(NamedTuple):
    """A closed range."""

    min_version: int | None
    max_version: int | None

    def __contains__(self, version: int) -> bool:
        """Return if the given version is in [min_version, max_version]."""
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
    network: AsyncNetwork, func_name: str, api_version: int, method_self: object, func: Callable[Param, RetType]
) -> Callable[Param, RetType]:
    @wraps(func)
    async def do_call(_self: object, *args: tuple, **kwargs: dict) -> RetType:
        call_obj = ApiCall(func_name, api_version, args, kwargs)
        _log.info("Sending RPC call %s", call_obj)

        await network.send_pyobj(call_obj)
        out = await network.recv_pyobj()
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
            api_spec = getattr(func, "is_part_of_smooth_api", None)
            if api_spec is None:
                continue
            if not inspect.iscoroutinefunction(func):
                raise RpcDecoratorError("Not an async function")
            if not isinstance(api_spec, ApiFunctionSpec):
                raise RpcDecoratorError("Decorator malfunction")

            func_name = api_spec.name or func_object_name
            yield (func_object_name, func_name, api_spec.version_range, func)


class SmoothRPCClient:
    """User of the RPC API."""

    def __init__(self, network: AsyncNetwork) -> None:
        """
        Create a RPC Client.

        'network' is the carrier network, typically an AsyncZmqNetworkClient.
        """
        self.network = network

    def instrument(self, command_object: object, api_version: int) -> None:
        """Replace all functions in command_object that are marked with the api decorator with remote calls."""
        for org_func_name, func_name, version_range, func in _iterate_functions(command_object):
            if api_version in version_range:
                wrapper = _create_call_wrapper(self.network, func_name, api_version, command_object, func)
            else:
                wrapper = _create_exception_wrapper(command_object, func)
            setattr(command_object, org_func_name, wrapper)


class SmoothRPCHost:
    """Host for the RPC API."""

    def __init__(self, network: AsyncNetwork) -> None:
        """
        Create a RPC Host.

        'network' is the carrier network, typically an AsyncZmqNetworkHost.
        """
        self.network = network
        self.keep_serve_loop_running = True

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

    def shutdown_after_call(self) -> None:
        """Stop processing commands, terminate 'serve_forever' after the next (or current, if any) call."""
        _log.info("Shutting down")
        self.keep_serve_loop_running = False

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

    async def _host_one(self) -> None:
        """Handle exactly one RPC call, receive/call/send."""
        try:
            call_obj = await self.network.recv_pyobj()
            if not isinstance(call_obj, ApiCall):
                raise RpcProtocolError("Invalid object received")  # noqa: TRY301

            out = await self._call_command(call_obj)
            await self.network.send_pyobj(out)
        except Exception as exc:  # noqa: BLE001, blind-catch exception
            _log.warning("Caught (and returning) exception", exc_info=exc)
            try:
                await self.network.send_pyobj(exc)
            except Exception as exc2:  # noqa: BLE001, blind-catch exception
                _log.error("Exception during sending exception", exc_info=exc2)
                await self.network.send_pyobj(RpcInternalError("Exception while returning exception"))

    async def host_forever(self) -> None:
        """Keep handling RPC calls until terminated."""
        _log.info("Serving forever")
        while self.keep_serve_loop_running and self.network is not None:
            await self._host_one()


Param = ParamSpec("Param")
RetType = TypeVar("RetType")


def api(*, func_name: str | None = None, min_version: int | None = None, max_version: int | None = None) -> Callable:
    """
    Mark a function as part of the API, use as decorator.

    Arguments are:
    - func_name, override the api name (defaults to function name).
    - min_version, first api version that supports this call.
    - max_version, last api version that supports this call.
    """

    def api_decorator(func: Callable[Param, RetType]) -> Callable[Param, RetType]:
        func.is_part_of_smooth_api = ApiFunctionSpec(func_name, VersionRange(min_version, max_version))
        return func

    return api_decorator
