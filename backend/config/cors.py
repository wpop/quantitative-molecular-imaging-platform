"""Minimal CORS middleware for local frontend development."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse

if TYPE_CHECKING:
    from collections.abc import Callable


class DevelopmentCorsMiddleware:
    """Allow explicitly configured frontend origins to read API metadata."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method == "OPTIONS" and self._origin_allowed(request):
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)
        self._apply_headers(request, response)
        return response

    @staticmethod
    def _allowed_origins() -> set[str]:
        origins = getattr(settings, "CORS_ALLOWED_ORIGINS", [])
        return {str(origin).rstrip("/") for origin in origins}

    def _origin_allowed(self, request: HttpRequest) -> bool:
        origin = request.headers.get("Origin", "").rstrip("/")
        return bool(origin and origin in self._allowed_origins())

    def _apply_headers(self, request: HttpRequest, response: HttpResponse) -> None:
        origin = request.headers.get("Origin", "").rstrip("/")
        if not origin or origin not in self._allowed_origins():
            return
        response["Access-Control-Allow-Origin"] = origin
        response["Vary"] = self._append_vary(response.get("Vary"), "Origin")
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Accept, Content-Type"

    @staticmethod
    def _append_vary(current: Any, value: str) -> str:
        if not current:
            return value
        values = [item.strip() for item in str(current).split(",")]
        if value not in values:
            values.append(value)
        return ", ".join(values)
