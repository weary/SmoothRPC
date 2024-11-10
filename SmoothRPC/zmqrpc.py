import logging
import types
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar, cast

from SmoothRPC.exceptions import RpcError
from SmoothRPC.network import AsyncNetwork, AsyncZmqNetwork

_log = logging.getLogger(__name__)


class AsyncRpc:
    def __init__(self, network: AsyncNetwork, is_server: bool) -> None:  # noqa: F821
        self.network = network
        if is_server:
            self.keep_serve_loop_running = True
        else:
            self._patch_client_calls()

    def shutdown(self) -> None:
        _log.info("Shutting down")
        self.keep_serve_loop_running = False
        self.network.shutdown()

    async def _call_command(self, func_name: str, *args, **kwargs) -> Any:
        _log.info("Received RPC call %s(args=%r, kwargs=%r)", func_name, args, kwargs)
        try:
            func = getattr(self, func_name)
        except AttributeError as exc:
            raise RpcError("No such rpc function", func_name) from exc
        if not getattr(func, "is_part_of_api", False):
            raise RpcError("Function not accessible", func_name)
        out = await func(*args, **kwargs)
        _log.info("Call %s returned %r", func_name, out)
        return out

    async def serve_forever(self) -> None:
        _log.info("Serving forever")
        while self.keep_serve_loop_running:
            try:
                try:
                    func_name, args, kwargs = cast(tuple, await self.network.recv_pyobj())
                except (TypeError, ValueError) as exc:
                    _log.warning("Received invalid RPC call", exc_info=exc)
                    raise RpcError("Invalid request") from exc
                out = await self._call_command(func_name, *args, **kwargs)
                await self.network.send_pyobj(out)
            except Exception as exc:
                _log.warning("Caught (and returning) exception", exc_info=exc)
                try:
                    await self.network.send_pyobj(exc)
                except Exception as exc2:
                    _log.error("Exception during sending exception", exc_info=exc2)
                    await self.network.send_pyobj(RpcError("Exception while returning exception"))

    def _patch_client_calls(self) -> None:
        for superclass in self.__class__.__mro__:
            for func_name, func in superclass.__dict__.items():
                if not getattr(func, "is_part_of_api", False):
                    continue

                def create_call_wrapper(func_name: str, func: Callable[Param, RetType]) -> Callable[Param, RetType]:
                    @wraps(func)
                    async def do_call(self, *args, **kwargs) -> RetType:
                        return await self._call_rpc_func(func_name, *args, **kwargs)

                    return types.MethodType(do_call, self)

                wrapper = create_call_wrapper(func_name, func)
                setattr(self, func_name, wrapper)

    async def _call_rpc_func(self, func_name: str, *args, **kwargs) -> Any:
        _log.info("Sending remote RPC call %s(args=%r, kwargs=%r)", func_name, args, kwargs)
        await self.network.send_pyobj((func_name, args, kwargs))
        out = await self.network.recv_pyobj()
        _log.info("Call %s returned %r", func_name, out)
        if isinstance(out, Exception):
            raise out  # re-raise received exception
        return out


class AsyncZmqRpc(AsyncRpc):
    def __init__(self, address: str, is_server: bool) -> None:
        super().__init__(AsyncZmqNetwork(address, is_server), is_server)


Param = ParamSpec("Param")
RetType = TypeVar("RetType")


def api(func: Callable[Param, RetType]) -> Callable[Param, RetType]:
    """Mark a function as part of the API, use as decorator."""
    func.is_part_of_api = True
    return func
