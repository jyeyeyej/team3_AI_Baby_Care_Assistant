"""Memory is an internal Agent layer and intentionally has no public API."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/memories", tags=["Agent Memory"])
