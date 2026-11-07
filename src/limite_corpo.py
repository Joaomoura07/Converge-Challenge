"""Limite de tamanho do corpo das requisições (Fatia A, etapa 13; caso TC-098 "milhão de itens").

A API não confia no front: alguém pode chamar `POST /orcamentos` direto com um JSON gigante. Sem limite, o servidor lê
o corpo inteiro na memória antes de validar. Aqui a requisição acima do limite é recusada com 413 ANTES de ser lida
(pelo `Content-Length`) ou, se o tamanho não vier no cabeçalho, assim que os bytes recebidos passam do limite.
A Vercel já corta em ~4,5 MB; o limite local protege também o `uvicorn` e os testes.
"""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

LIMITE_CORPO_BYTES = 8 * 1024 * 1024
# Rotas que recebem listas de itens (as demais corpos são pequenos e já têm validação própria).
PREFIXOS_LIMITADOS = ("/orcamentos", "/revisao")

_RESPOSTA = json.dumps(
    {"detail": {"mensagem": "A lista é grande demais para um envio. Divida em partes menores.", "limite_bytes": LIMITE_CORPO_BYTES}}
).encode()


class CorpoGrandeDemais(Exception):
    pass


class LimiteDeCorpo:
    def __init__(self, app: ASGIApp, limite: int = LIMITE_CORPO_BYTES, prefixos: tuple[str, ...] = PREFIXOS_LIMITADOS):
        self.app, self.limite, self.prefixos = app, limite, prefixos

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH") or not scope["path"].startswith(self.prefixos):
            await self.app(scope, receive, send)
            return

        declarado = next((v for k, v in scope["headers"] if k == b"content-length"), None)
        if declarado is not None and declarado.isdigit() and int(declarado) > self.limite:
            await self._recusar(send)
            return

        recebidos = 0
        excedeu = False
        respondeu = False

        async def receive_limitado() -> Message:
            nonlocal recebidos, excedeu
            msg = await receive()
            if msg["type"] == "http.request":
                recebidos += len(msg.get("body", b""))
                if recebidos > self.limite:
                    excedeu = True
                    raise CorpoGrandeDemais
            return msg

        async def send_marcado(msg: Message) -> None:
            nonlocal respondeu
            if excedeu:
                # O FastAPI captura a exceção da leitura e responde 400; quem manda aqui é o limite: 413.
                if msg["type"] == "http.response.start" and not respondeu:
                    respondeu = True
                    await self._recusar(send)
                return
            if msg["type"] == "http.response.start":
                respondeu = True
            await send(msg)

        try:
            await self.app(scope, receive_limitado, send_marcado)
        except CorpoGrandeDemais:
            if not respondeu:
                respondeu = True
                await self._recusar(send)

    @staticmethod
    async def _recusar(send: Send) -> None:
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(_RESPOSTA)).encode())]})
        await send({"type": "http.response.body", "body": _RESPOSTA})
