"""Errores de negocio. La capa de API los convierte en códigos HTTP."""


class RecursoDesconocido(Exception):
    """El nombre del recurso no existe (404)."""


class NoEncontrado(Exception):
    """El registro pedido no existe (404)."""


class Invalido(Exception):
    """Los datos no cumplen las reglas (422)."""


class Conflicto(Exception):
    """La acción choca con otros datos, por ejemplo borrar algo en uso (409)."""


class ArchivoInvalido(Exception):
    def __init__(self, mensaje: str, estado: int = 422):
        super().__init__(mensaje)
        self.estado = estado
