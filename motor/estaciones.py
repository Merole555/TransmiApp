"""R1, R2 y R3: consultas de estaciones (miembro 1).

red.estaciones es una TablaHash nombre -> True (abierta) / False (cerrada).
red.abiertas es un ArbolAVL que solo tiene las estaciones abiertas.
"""


def estado(red, nombre):
    """R1. Devuelve "ABIERTA", "CERRADA" o "NO_EXISTE"."""
    abierta = red.estaciones.obtener(nombre)
    if abierta is None:
        return "NO_EXISTE"
    return "ABIERTA" if abierta else "CERRADA"


def autocompletar(red, prefijo, k):
    """R2. Hasta k estaciones abiertas que empiezan por el prefijo, en orden."""
    resultado = []
    if k <= 0:
        return resultado
    for nombre in red.abiertas.desde(prefijo):
        if not nombre.startswith(prefijo) or len(resultado) == k:
            break
        resultado.append(nombre)
    return resultado


def rango(red, desde, hasta):
    """R3. Estaciones abiertas entre desde y hasta, incluyendo los extremos."""
    resultado = []
    if desde > hasta:
        return resultado
    for nombre in red.abiertas.desde(desde):
        if nombre > hasta:
            break
        resultado.append(nombre)
    return resultado


# Operaciones para R8 (miembro 3): cambian la visibilidad de una estación.

def retirar_abierta(red, nombre):
    """Marca la estación como cerrada y la saca del árbol. True si cambió."""
    if red.estaciones.obtener(nombre) is not True:
        return False
    red.estaciones.asignar(nombre, False)
    red.abiertas.eliminar(nombre)
    red.indice_ranking.cambiar_apertura(nombre, False)
    return True


def reinsertar_abierta(red, nombre):
    """Marca la estación como abierta y la vuelve a meter al árbol. True si cambió."""
    if red.estaciones.obtener(nombre) is not False:
        return False
    red.estaciones.asignar(nombre, True)
    red.abiertas.insertar(nombre)
    red.indice_ranking.cambiar_apertura(nombre, True)
    return True
