from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, Response, status

from app.schemas.server import ConnectionTestResponse, Server, ServerCreate, ServerUpdate
from app.services.server_service import server_service

router = APIRouter()


@router.get("", response_model=List[Server])
def list_servers() -> List[Server]:
    return server_service.list_servers()


@router.post("", response_model=Server, status_code=status.HTTP_201_CREATED)
def create_server(payload: ServerCreate) -> Server:
    try:
        return server_service.create_server(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{server_id}", response_model=Server)
def get_server(server_id: int) -> Server:
    server = server_service.get_server(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    return server


@router.put("/{server_id}", response_model=Server)
def update_server(server_id: int, payload: ServerUpdate) -> Server:
    try:
        server = server_service.update_server(server_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    return server


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_server(server_id: int) -> Response:
    deleted = server_service.delete_server(server_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{server_id}/test-connection", response_model=ConnectionTestResponse)
def test_connection(server_id: int) -> ConnectionTestResponse:
    server = server_service.get_server(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    return server_service.test_connection(server_id)


@router.post("/{server_id}/ping", response_model=ConnectionTestResponse)
def ping_server(server_id: int) -> ConnectionTestResponse:
    server = server_service.get_server(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    return server_service.ping_server(server_id)
