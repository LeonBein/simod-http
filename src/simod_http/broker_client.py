import json
import logging
import os
import time
from typing import Union

import pika
import pika.exceptions
from pika.spec import PERSISTENT_DELIVERY_MODE

from simod_http.requests import JobRequest


class BrokerClient:
    def __init__(
            self,
            broker_url: str,
            exchange_name: str,
            routing_key: str,
            connection: Union[pika.BlockingConnection, None] = None,
            channel: Union[pika.adapters.blocking_connection.BlockingChannel, None] = None,
    ):
        self._broker_url = broker_url
        self._exchange_name = exchange_name
        self._routing_key = routing_key

        self._connection = connection
        self._channel = channel

        self._retries = 5
        self._retry_delay = 1

    def __repr__(self):
        return f'BrokerClient(_broker_url={self._broker_url}, ' \
               f'_exchange_name={self._exchange_name}, ' \
               f'_routing_key={self._routing_key})'

    def connect(self):
        logging.info(f'Connecting to the broker at {self._broker_url}')
        parameters = pika.URLParameters(self._broker_url)

        try:
            self._connection = pika.BlockingConnection(parameters)
            self._channel = self._connection.channel()
            self._channel.exchange_declare(exchange=self._exchange_name, exchange_type='topic', durable=True)

        except pika.exceptions.AMQPConnectionError:
            logging.warning(f'Failed to connect to the broker at {self._broker_url}. Retrying...')
            self._retries -= 1
            if self._retries > 0:
                time.sleep(self._retry_delay)
                self.connect()
            else:
                raise RuntimeError(f'Failed to connect to the broker at {self._broker_url}')

        self._retries = 5

    def publish_request(self, request_id: str):
        if self._connection is None or self._channel is None or self._connection.is_closed or self._channel.is_closed:
            self.connect()

        try:
            self._channel.basic_publish(
                exchange=self._exchange_name,
                routing_key=self._routing_key,
                body=request_id.encode(),
                properties=pika.BasicProperties(
                    delivery_mode=PERSISTENT_DELIVERY_MODE,
                ),
            )

            logging.info(f'Published request {request_id} to {self._routing_key}')

        except pika.exceptions.ConnectionClosed:
            logging.warning(f'Failed to publish request {request_id} to {self._routing_key} '
                            f'because the connection is closed. Reconnecting...')
            self.connect()
            self.publish_request(request_id)

        except pika.exceptions.ChannelClosed:
            logging.warning(f'Failed to publish request {request_id} to {self._routing_key} '
                            f'because the channel is closed. Reconnecting...')
            self.connect()
            self.publish_request(request_id)

        except pika.exceptions.StreamLostError:
            logging.warning(f'Failed to publish request {request_id} to {self._routing_key} '
                            f'because the stream is lost. Reconnecting...')
            self.connect()
            self.publish_request(request_id)

        except Exception as e:
            logging.error(f'Failed to publish request {request_id} to {self._routing_key} '
                          f'because of an unknown error: {e}')
            self.basic_publish_request(request_id)

    def basic_publish_request(self, request: JobRequest):
        parameters = pika.URLParameters(self._broker_url)
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.exchange_declare(exchange=self._exchange_name, exchange_type='topic', durable=True)

        request_id = request.get_id()

        body = json.dumps({
            'request_id': request_id,
            'configuration_path': request.configuration_path,
        })

        channel.basic_publish(
            exchange=self._exchange_name,
            routing_key=self._routing_key,
            body=body.encode(),
            properties=pika.BasicProperties(
                delivery_mode=PERSISTENT_DELIVERY_MODE,
                content_type='application/json',
            ),
        )
        connection.close()
        logging.info(f'Published request {request_id} to {self._routing_key}')


def make_broker_client(broker_url: str, exchange_name: str, routing_key: str) -> BrokerClient:
    fake_broker_client = os.environ.get('SIMOD_FAKE_BROKER_CLIENT', 'false').lower() == 'true'
    if fake_broker_client:
        from simod_http.broker_client_stub import stub_broker_client
        return stub_broker_client()
    else:
        return BrokerClient(
            broker_url=broker_url,
            exchange_name=exchange_name,
            routing_key=routing_key,
        )
