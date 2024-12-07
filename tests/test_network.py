import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from smooth_rpc.exceptions import RpcMaxSizeExceededError
from smooth_rpc.network import AsyncNetworkConnection
from tests.conftest import data_to_msg


def _make_read_mock(data: bytes, cutoff: int | None = None) -> Callable:
    buffer = data_to_msg(data)
    if cutoff is not None:
        buffer = buffer[:cutoff]

    async def read_buffer_mock(read_size: int) -> bytes:
        nonlocal buffer
        buffer, out = buffer[read_size:], buffer[:read_size]
        if len(out) < read_size:
            raise asyncio.exceptions.IncompleteReadError(out, read_size)
        return out

    return read_buffer_mock


@pytest.mark.asyncio
async def test_send_message() -> None:
    mock_writer = AsyncMock()
    mock_writer.write = Mock()
    connection = AsyncNetworkConnection(reader=AsyncMock(), writer=mock_writer)

    data = b"test_message"

    # Send message should call writer.write and writer.drain
    await connection.send_message(data)

    # Assert the write and drain methods were called
    expected = data_to_msg(data)
    mock_writer.write.assert_called_once_with(expected)
    mock_writer.drain.assert_awaited_once()

    # Sending a message larger than the max allowed size should raise an RpcMaxSizeExceededError
    data = b"A" * (connection.MAX_MSG_SIZE + 1)
    with pytest.raises(RpcMaxSizeExceededError):
        await connection.send_message(data)

    # Sending a message exactly the max allowed should not raise an exception
    data = b"A" * (connection.MAX_MSG_SIZE)
    await connection.send_message(data)

    # Test connection reset
    mock_writer.drain.side_effect = ConnectionResetError
    with pytest.raises(ConnectionResetError):
        await connection.send_message(data)


@pytest.mark.asyncio
async def test_recv_message_success() -> None:
    test_message = b"test_message"
    mock_reader = AsyncMock()
    mock_reader.readexactly = AsyncMock(side_effect=_make_read_mock(test_message))
    connection = AsyncNetworkConnection(reader=mock_reader, writer=AsyncMock())

    result = await connection.recv_message()

    assert result == test_message

    # Receiving a message larger than the max allowed size should raise RpcMaxSizeExceededError
    too_large_msg = b"A" * (AsyncNetworkConnection.MAX_MSG_SIZE + 1)
    mock_reader.readexactly = AsyncMock(side_effect=_make_read_mock(too_large_msg))
    with pytest.raises(RpcMaxSizeExceededError):
        await connection.recv_message()

    # Receiving a message of the exact allowed amount should not throw
    just_right = b"A" * (AsyncNetworkConnection.MAX_MSG_SIZE)
    mock_reader.readexactly = AsyncMock(side_effect=_make_read_mock(just_right))
    result = await connection.recv_message()
    assert result == just_right


@pytest.mark.asyncio
async def test_recv_message_errors() -> None:
    # no bytes to read -> connection closed between calls
    mock_reader = AsyncMock()
    mock_reader.at_eof = Mock(return_value=True)
    mock_reader.readexactly = AsyncMock(side_effect=_make_read_mock(b"", cutoff=0))
    connection = AsyncNetworkConnection(reader=mock_reader, writer=MagicMock())

    # even though this is a normal close we still get an IncompleteReadError
    with pytest.raises(asyncio.exceptions.IncompleteReadError):
        await connection.recv_message()

    # partial length received
    mock_reader.readexactly = AsyncMock(side_effect=_make_read_mock(b"", cutoff=1))
    connection = AsyncNetworkConnection(reader=mock_reader, writer=MagicMock())

    with pytest.raises(asyncio.exceptions.IncompleteReadError):
        await connection.recv_message()

    # partial data received
    mock_reader.readexactly = AsyncMock(side_effect=_make_read_mock(b"some data", cutoff=9))
    connection = AsyncNetworkConnection(reader=mock_reader, writer=MagicMock())

    with pytest.raises(asyncio.exceptions.IncompleteReadError):
        await connection.recv_message()
