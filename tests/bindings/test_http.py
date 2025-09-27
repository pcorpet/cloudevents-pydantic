# ==============================================================================
#  Copyright (c) 2024 Federico Busetti                                         =
#  <729029+febus982@users.noreply.github.com>                                  =
#                                                                              =
#  Permission is hereby granted, free of charge, to any person obtaining a     =
#  copy of this software and associated documentation files (the "Software"),  =
#  to deal in the Software without restriction, including without limitation   =
#  the rights to use, copy, modify, merge, publish, distribute, sublicense,    =
#  and/or sell copies of the Software, and to permit persons to whom the       =
#  Software is furnished to do so, subject to the following conditions:        =
#                                                                              =
#  The above copyright notice and this permission notice shall be included in  =
#  all copies or substantial portions of the Software.                         =
#                                                                              =
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR  =
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,    =
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL     =
#  THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER  =
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING     =
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER         =
#  DEALINGS IN THE SOFTWARE.                                                   =
# ==============================================================================
from typing import List
from unittest.mock import MagicMock, call, patch

import pytest
from pydantic import Field, TypeAdapter

from cloudevents_pydantic.bindings.http import HTTPComponents, HTTPHandler
from cloudevents_pydantic.events import CloudEvent

minimal_attributes = {
    "type": "com.example.string",
    "source": "https://example.com/event-producer",
    "id": "b96267e2-87be-4f7a-b87c-82f64360d954",
    "specversion": "1.0",
}
test_attributes = {
    "type": "com.example.string",
    "source": "https://example.com/event-producer",
    "id": "b96267e2-87be-4f7a-b87c-82f64360d954",
    "time": "2022-07-16T12:03:20.519216+04:00",
    "specversion": "1.0",
}
valid_json = '{"data":null,"source":"https://example.com/event-producer","id":"b96267e2-87be-4f7a-b87c-82f64360d954","type":"com.example.string","specversion":"1.0","time":"2022-07-16T12:03:20.519216+04:00","subject":null,"datacontenttype":null,"dataschema":null}'
valid_json_batch = '[{"data":null,"source":"https://example.com/event-producer","id":"b96267e2-87be-4f7a-b87c-82f64360d954","type":"com.example.string","specversion":"1.0","time":"2022-07-16T12:03:20.519216+04:00","subject":null,"datacontenttype":null,"dataschema":null}]'


class SomeEvent(CloudEvent):
    some_attr: str = Field(default="some_value")


SomeAdapter = TypeAdapter(List[SomeEvent])

some_event_json = '{"data":null,"source":"https://example.com/event-producer","id":"b96267e2-87be-4f7a-b87c-82f64360d954","type":"com.example.string","specversion":"1.0","time":"2022-07-16T12:03:20.519216+04:00","subject":null,"datacontenttype":null,"dataschema":null,"some_attr":"some_value"}'
some_event_json_batch = '[{"data":null,"source":"https://example.com/event-producer","id":"b96267e2-87be-4f7a-b87c-82f64360d954","type":"com.example.string","specversion":"1.0","time":"2022-07-16T12:03:20.519216+04:00","subject":null,"datacontenttype":null,"dataschema":null,"some_attr":"some_value"}]'


@pytest.fixture
def type_adapter_init_mock():
    with patch.object(TypeAdapter, "__init__", return_value=None) as mocked_function:
        yield mocked_function


def test_initialization_defaults_to_cloudevents(type_adapter_init_mock: MagicMock):
    HTTPHandler()
    type_adapter_init_mock.assert_has_calls(
        [
            call(CloudEvent),
            call(List[CloudEvent]),
        ]
    )


def test_initialization_uses_provided_event_class(type_adapter_init_mock: MagicMock):
    HTTPHandler(event_class=SomeEvent)
    type_adapter_init_mock.assert_has_calls(
        [
            call(SomeEvent),
            call(List[SomeEvent]),
        ]
    )


@pytest.mark.parametrize(
    "event, expected_output",
    [
        (CloudEvent(**test_attributes), valid_json),
        (SomeEvent(**test_attributes), some_event_json),
    ],
)
def test_to_json(event, expected_output, json_serialize_spy):
    handler = HTTPHandler()

    _, json_repr = handler.to_json(event)
    json_serialize_spy.assert_called_once_with(event)
    assert json_repr == expected_output


@pytest.mark.parametrize(
    "event, expected_output",
    [
        (CloudEvent(**test_attributes), valid_json_batch),
        (SomeEvent(**test_attributes), some_event_json_batch),
    ],
)
def test_to_json_batch(event, expected_output, json_serialize_batch_spy):
    handler = HTTPHandler()

    _, json_repr = handler.to_json_batch([event])
    json_serialize_batch_spy.assert_called_once_with([event], handler.batch_adapter)
    assert json_repr == expected_output


def test_from_json(json_deserialize_spy):
    handler = HTTPHandler(event_class=SomeEvent)
    event = handler.from_json(valid_json)

    json_deserialize_spy.assert_called_once_with(valid_json, handler.event_adapter)
    assert event == SomeEvent(**test_attributes)
    assert event != CloudEvent(**test_attributes)
    assert isinstance(event, SomeEvent)


def test_from_json_batch(json_deserialize_batch_spy):
    handler = HTTPHandler(event_class=SomeEvent)
    events = handler.from_json_batch(valid_json_batch)
    event = events[0]

    assert len(events) == 1
    json_deserialize_batch_spy.assert_called_once_with(
        valid_json_batch, handler.batch_adapter
    )
    assert event == SomeEvent(**test_attributes)
    assert event != CloudEvent(**test_attributes)
    assert isinstance(event, SomeEvent)


@pytest.mark.parametrize(
    ["raw_value", "expected_value"],
    [
        ("Euro € 😀", "Euro%20%E2%82%AC%20%F0%9F%98%80"),
        ('"', "%22"),
        (" ", "%20"),
        ("%", "%25"),
        ("clean", "clean"),
    ],
)
def test_header_encoder(raw_value, expected_value):
    assert HTTPHandler()._header_encode(raw_value) == expected_value


@pytest.mark.parametrize(
    ["expected_value", "raw_value"],
    [
        ("Euro € 😀", "Euro%20%E2%82%AC%20%F0%9F%98%80"),
        ('"', "%22"),
        (" ", "%20"),
        ("%", "%25"),
        ("clean", "clean"),
    ],
)
def test_header_decoder(expected_value, raw_value):
    assert HTTPHandler()._header_decode(raw_value) == expected_value


@pytest.mark.parametrize(
    ["value"],
    [
        ("%C0%A0",),
    ],
)
def test_header_decoder_fails_with_invalid_values(value):
    with pytest.raises(UnicodeDecodeError):
        HTTPHandler()._header_decode(value)


@pytest.mark.parametrize(
    "event, expected_output",
    [
        (
            CloudEvent(**test_attributes, datacontenttype="text/plain"),
            HTTPComponents(
                headers={
                    "ce-source": "https://example.com/event-producer",
                    "ce-id": "b96267e2-87be-4f7a-b87c-82f64360d954",
                    "ce-specversion": "1.0",
                    "ce-time": "2022-07-16T12:03:20.519216+04:00",
                    "ce-type": "com.example.string",
                    "content-type": "text/plain",
                },
                body=None,
            ),
        ),
        (
            SomeEvent(**test_attributes, datacontenttype="text/plain"),
            HTTPComponents(
                headers={
                    "ce-source": "https://example.com/event-producer",
                    "ce-id": "b96267e2-87be-4f7a-b87c-82f64360d954",
                    "ce-specversion": "1.0",
                    "ce-time": "2022-07-16T12:03:20.519216+04:00",
                    "ce-some_attr": "some_value",
                    "ce-type": "com.example.string",
                    "content-type": "text/plain",
                },
                body=None,
            ),
        ),
    ],
)
def test_to_binary(event, expected_output, canonical_serialize_spy):
    handler = HTTPHandler()

    result = handler.to_binary(event)
    assert result == expected_output
    canonical_serialize_spy.assert_called_once_with(event)


def test_to_binary_fails_without_datacontenttype():
    event = CloudEvent(**test_attributes, datacontenttype=None)
    handler = HTTPHandler()

    with pytest.raises(ValueError):
        handler.to_binary(event)


def test_from_binary(canonical_deserialize_spy):
    handler = HTTPHandler()

    headers = {
        "ce-source": "https://example.com/event-producer",
        "ce-id": "b96267e2-87be-4f7a-b87c-82f64360d954",
        "ce-specversion": "1.0",
        "ce-time": "2022-07-16T12:03:20.519216+04:00",
        "ce-type": "com.example.string",
        "content-type": "text/plain",
        "x-ignored-header": "value",
    }
    body = None

    result = handler.from_binary(headers, body)
    assert result == CloudEvent(**test_attributes, datacontenttype="text/plain")

    #
    canonical_deserialize_spy.assert_called_once_with(
        {
            "source": "https://example.com/event-producer",
            "id": "b96267e2-87be-4f7a-b87c-82f64360d954",
            "specversion": "1.0",
            "time": "2022-07-16T12:03:20.519216+04:00",
            "type": "com.example.string",
            "datacontenttype": "text/plain",
            "data": None,
        },
        handler.event_adapter,
    )


def test_from_binary_fails_without_content_type():
    handler = HTTPHandler()

    headers = {
        "ce-source": "https://example.com/event-producer",
        "ce-id": "b96267e2-87be-4f7a-b87c-82f64360d954",
        "ce-specversion": "1.0",
        "ce-time": "2022-07-16T12:03:20.519216+04:00",
        "ce-type": "com.example.string",
    }
    body = None

    with pytest.raises(ValueError):
        handler.from_binary(headers, body)
