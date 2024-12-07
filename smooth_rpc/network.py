"""Carrier network for SmoothRPC."""

import asyncio
import logging

from smooth_rpc.exceptions import RpcMaxSizeExceededError

_log = logging.getLogger(__name__)


class AsyncNetworkConnection:
    """
    Client network implementation.

    Converts the unix/tcp stream into messages by injecting length fields.
    """

    # arbitrary maximum message size, adjust if needed
    MAX_MSG_SIZE = 10 * 1024 * 1024  # 10MB

    # used to construct the friendly name
    connection_counter = 0

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Create a network instance and connect to address."""
        self.reader = reader
        self.writer = writer

        # friendly name used in logging
        AsyncNetworkConnection.connection_counter += 1
        self.friendly_name = f"connection {AsyncNetworkConnection.connection_counter}"

    async def send_message(self, data: bytes) -> None:
        """
        Send a blob to remote.

        Insert an 8-byte big-endian length before the data blob.
        """
        if len(data) > self.MAX_MSG_SIZE:
            raise RpcMaxSizeExceededError(
                "Trying to send message larger than allowed size on %s",
                len(data),
                self.MAX_MSG_SIZE,
                self.friendly_name,
            )
        try:
            self.writer.write(len(data).to_bytes(8) + data)
            await self.writer.drain()
        except ConnectionError:
            _log.debug("Connection error on %s", self.friendly_name)
            raise

    async def recv_message(self) -> bytes:
        """
        Receive an object from remote.

        Assume an 8-byte big-endian length before a data blob.
        """
        try:
            len_bytes = await self.reader.readexactly(8)
            data_len = int.from_bytes(len_bytes)
        except asyncio.exceptions.IncompleteReadError as exc:
            if self.reader.at_eof() and len(exc.partial) == 0:
                _log.debug("Connection closed normally")
                raise

            # if we did not read a 8-byte length header our protocol is broken, re-raise exception will close connection
            _log.debug("Partial read of %d bytes on %s", len(exc.partial), self.friendly_name)
            raise

        if data_len > self.MAX_MSG_SIZE:
            raise RpcMaxSizeExceededError(
                "Trying to receive message larger than allowed size", data_len, self.MAX_MSG_SIZE
            )

        try:
            data = await self.reader.readexactly(data_len)
        except asyncio.exceptions.IncompleteReadError as exc:
            _log.debug("Did not receive enough data, expected %d, got %d", data_len, len(exc.partial))
            raise

        _log.debug("Received message of %d bytes", len(data))
        return data
