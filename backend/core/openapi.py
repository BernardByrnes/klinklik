"""OpenAPI schema policy for APIViews with explicit request/response serializers."""

from rest_framework import serializers
from rest_framework.schemas.openapi import AutoSchema, is_list_view


class KlinKlikAutoSchema(AutoSchema):
    def map_field(self, field):
        custom_schema = getattr(field, "openapi_schema", None)
        if custom_schema is not None:
            return custom_schema.copy()
        return super().map_field(field)

    def get_operation_id(self, path, method):
        explicit = getattr(self.view, "operation_id", None)
        if explicit:
            return explicit
        return super().get_operation_id(path, method)

    def get_response_serializer(self, path, method):
        response_serializer_classes = getattr(self.view, "response_serializer_classes", None) or {}
        response_serializer_class = response_serializer_classes.get(
            method.upper(), getattr(self.view, "response_serializer_class", None)
        )
        if response_serializer_class is not None:
            return response_serializer_class()
        return super().get_response_serializer(path, method)

    def get_response_serializers_by_status(self, path, method):
        configured = getattr(self.view, "response_serializer_classes_by_status", None) or {}
        return configured.get(method.upper(), {})

    def get_components(self, path, method):
        components = super().get_components(path, method)
        for serializer_class in self.get_response_serializers_by_status(path, method).values():
            serializer = serializer_class() if isinstance(serializer_class, type) else serializer_class
            if isinstance(serializer, serializers.Serializer):
                component_name = self.get_component_name(serializer)
                components.setdefault(component_name, self.map_serializer(serializer))
        return components

    def _is_list_response(self, path, method):
        configured = getattr(self.view, "response_is_list", None)
        if isinstance(configured, dict):
            configured = configured.get(method.upper())
        if configured is not None:
            return bool(configured)
        return is_list_view(path, method, self.view)

    def get_responses(self, path, method):
        method = method.upper()
        if method == "DELETE":
            return {"204": {"description": ""}}

        self.response_media_types = self.map_renderers(path, method)
        configured = self.get_response_serializers_by_status(path, method)
        if not configured:
            configured = {"201" if method == "POST" else "200": self.get_response_serializer(path, method)}

        responses = {}
        for status_code, serializer_class in sorted(configured.items(), key=lambda item: str(item[0])):
            serializer = serializer_class() if isinstance(serializer_class, type) else serializer_class
            item_schema = self.get_reference(serializer) if isinstance(serializer, serializers.Serializer) else {}
            response_schema = item_schema
            if self._is_list_response(path, method):
                response_schema = {"type": "array", "items": item_schema}
                paginator = self.get_paginator()
                if paginator:
                    response_schema = paginator.get_paginated_response_schema(response_schema)
            responses[str(status_code)] = {
                "content": {
                    content_type: {"schema": response_schema}
                    for content_type in self.response_media_types
                },
                "description": "",
            }
        return responses

    def get_request_serializer(self, path, method):
        request_serializer_classes = getattr(self.view, "request_serializer_classes", None) or {}
        request_serializer_class = request_serializer_classes.get(
            method.upper(), getattr(self.view, "request_serializer_class", None)
        )
        if request_serializer_class is not None:
            return request_serializer_class()
        return super().get_request_serializer(path, method)
