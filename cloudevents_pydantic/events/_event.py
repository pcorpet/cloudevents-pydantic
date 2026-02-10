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
import base64
import datetime
from typing import Annotated, Any, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_serializer,
    model_validator,
)
from pydantic.fields import FieldInfo
from pydantic_core.core_schema import ValidationInfo
from ulid import ULID

from .fields.metadata import (
    FieldData,
    FieldDataContentType,
    FieldDataSchema,
    FieldId,
    FieldSource,
    FieldSpecVersion,
    FieldSubject,
    FieldTime,
    FieldType,
)
from .fields.types import (
    URI,
    Binary,
    MimeType,
    SpecVersion,
    String,
    Timestamp,
    URIReference,
)

DEFAULT_SPECVERSION = SpecVersion.v1_0


_binary_field_metadata = FieldInfo.from_annotation(Binary).metadata


class CloudEvent(BaseModel):
    """
    A Python-friendly CloudEvent representation backed by Pydantic-modeled fields.
    """

    @classmethod
    def event_factory(
        cls,
        id: Optional[str] = None,
        specversion: Optional[SpecVersion] = None,
        time: Optional[Union[datetime.datetime, str]] = None,
        **kwargs,
    ) -> "CloudEvent":
        """
        Builds a new CloudEvent using sensible defaults.

        :param id: The event id, defaults to a ULID
        :type id: typing.Optional[str]
        :param specversion: The specversion of the event, defaults to 1.0
        :type specversion: typing.Optional[SpecVersion]
        :param time: The time the event occurred, defaults to now
        :type time: typing.Optional[Union[datetime.datetime, str]]
        :param kwargs: Other kwargs forwarded directly to the CloudEvent model.
        :return: A new CloudEvent model
        :rtype: CloudEvent
        """
        return cls(
            id=id or str(ULID()),
            specversion=specversion or DEFAULT_SPECVERSION,
            time=time or datetime.datetime.now(datetime.timezone.utc),
            **kwargs,
        )

    data: Annotated[Any, Field(default=None), FieldData]

    # Mandatory fields
    source: Annotated[URIReference, FieldSource]
    id: Annotated[String, FieldId]
    type: Annotated[String, FieldType]
    specversion: Annotated[SpecVersion, FieldSpecVersion]

    # Optional fields
    time: Annotated[Optional[Timestamp], Field(default=None), FieldTime]
    subject: Annotated[Optional[String], Field(default=None), FieldSubject]
    datacontenttype: Annotated[
        Optional[MimeType], Field(default=None), FieldDataContentType
    ]
    dataschema: Annotated[Optional[URI], Field(default=None), FieldDataSchema]

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "specversion": "1.0",
                "type": "com.github.pull_request.opened",
                "source": "https://github.com/cloudevents/spec/pull",
                "subject": "123",
                "id": "A234-1234-1234",
                "time": "2018-04-05T17:31:00Z",
                "comexampleextension1": "value",
                "comexampleothervalue": 5,
                "datacontenttype": "text/xml",
                "data": '<much wow="xml"/>',
            }
        },
    )

    """
    Having the JSON functionality here is a violation of the Single Responsibility
    Principle, however we want to get advantage of improved pydantic JSON performances.
    Using `orjson` could solve this, perhaps it could be a future improvement.
    """

    # Typing for return value here breaks `.model_json_schema(mode='serialization')`
    @model_serializer(when_used="json")
    def base64_json_serializer(self):
        """Takes care of handling binary data serialization into `data_base64`
        attribute.

        :param self: CloudEvent.

        :return: Event serialized as a standard CloudEvent dict with binary
                 data handled.
        """
        model_dict = self.model_dump()
        if _binary_field_metadata == self.__class__.model_fields["data"].metadata:
            model_dict["data_base64"] = model_dict["data"]
            del model_dict["data"]
        elif isinstance(model_dict["data"], (bytes, bytearray, memoryview)):
            model_dict["data_base64"] = base64.b64encode(model_dict["data"])
            del model_dict["data"]

        return model_dict

    @model_validator(mode="before")
    @classmethod
    def base64_json_validator(cls, data: dict, info: ValidationInfo) -> Any:
        """Takes care of handling binary data deserialization from `data_base64`
        attribute.

        :param data: Input data for validation
        :param info: Pydantic validation context
        :return: input data, after handling data_base64
        """
        if info.mode == "json" and isinstance(data, dict) and data.get("data_base64"):
            data["data"] = base64.b64decode(data["data_base64"])
            del data["data_base64"]
        return data
