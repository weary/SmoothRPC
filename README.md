Here's a README for the SmoothRPC project:

# SmoothRPC

Decorator-based RPC library based on asyncio.

Works by replacing all decorated functions with remote function calls. Arguments and results are pickle'd. Host exceptions are re-thrown client-side.

> [!WARNING]
> SmoothRPC uses pickle to serialize objects. Do not use in untrusted environments.

## Installation

```bash
pip install --upgrade https://github.com/weary/SmoothRPC/tarball/master
```

## Quick Start

1. Define your RPC API class:

```python
from smooth_rpc import api

class APICommands:
    @api()
    async def say_hello(self, name:str) -> str:
        return f"Hello, {name}!"
```

2. Set up the host:

```python
from smooth_rpc import host_forever

# instance of your own API class. Instance stays in-memory, so can be used for context.
api_commands = APICommands()

# bind-address, start with 'ipc' for unix sockets or 'tcp'
address = "tcp://127.0.0.1:5000"

# SmoothRPC entrypoint:
# - Find 'rpc'-decorated functions for use as RPC-endpoints.
# - Listen on 'address', and keep handling RPC requests.
await host_forever(address, api_commands)  # listen and handle RPC requests
```

3. Create a client:

```python

# instance of your own API class. Instance stays in-memory.
api_commands = APICommands()

# connect-address, same as host address
address = "tcp://127.0.0.1:5000"

# SmoothRPC entrypoint:
# - Replace all 'rpc'-decorated functions in 'api_commands' with remote function calls.
# - Open connection to 'address'
await init_remote_rpc(address, api_commands)

# Call the 'hello' function on the host, and store the result.
out = await api_commands.hello("Alice")

# 'out' now has the value 'Hello Alice'
```

## Example

A full example is available in the 'example' folder on [github](https://github.com/weary/SmoothRPC/tree/main/example)

## License

SmoothRPC is released under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact

For any questions or support, please open an issue on the [GitHub repository](https://github.com/weary/SmoothRPC/issues).
