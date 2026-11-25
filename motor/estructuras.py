"""Estructuras propias del motor (no se pueden usar dict, set ni sorted)."""


class TablaHash:
    """Tabla hash con encadenamiento.

    Cada cubo es una lista de pares [clave, valor]. Cuando hay más de
    0.75 elementos por cubo se duplica la cantidad de cubos.
    Las claves pueden ser cadenas o tuplas de cadenas.
    """

    def __init__(self, capacidad=16):
        self.cubos = []
        for _ in range(capacidad):
            self.cubos.append([])
        self.cantidad = 0

    def _hash(self, clave):
        # hash polinomial sobre los caracteres (base 31)
        if isinstance(clave, tuple):
            texto = ""
            for parte in clave:
                texto += str(parte) + "\x00"
        else:
            texto = str(clave)
        valor = 0
        for caracter in texto:
            valor = (valor * 31 + ord(caracter)) % 1000000007
        return valor

    def _cubo(self, clave):
        return self.cubos[self._hash(clave) % len(self.cubos)]

    def obtener(self, clave, defecto=None):
        for par in self._cubo(clave):
            if par[0] == clave:
                return par[1]
        return defecto

    def contiene(self, clave):
        for par in self._cubo(clave):
            if par[0] == clave:
                return True
        return False

    def asignar(self, clave, valor):
        cubo = self._cubo(clave)
        for par in cubo:
            if par[0] == clave:
                par[1] = valor
                return
        cubo.append([clave, valor])
        self.cantidad += 1
        if self.cantidad > 0.75 * len(self.cubos):
            self._redimensionar()

    def eliminar(self, clave):
        cubo = self._cubo(clave)
        for i in range(len(cubo)):
            if cubo[i][0] == clave:
                cubo.pop(i)
                self.cantidad -= 1
                return True
        return False

    def _redimensionar(self):
        viejos = self.cubos
        self.cubos = []
        for _ in range(len(viejos) * 2):
            self.cubos.append([])
        for cubo in viejos:
            for par in cubo:
                self._cubo(par[0]).append(par)

    def claves(self):
        resultado = []
        for cubo in self.cubos:
            for par in cubo:
                resultado.append(par[0])
        return resultado

    def __len__(self):
        return self.cantidad


class NodoAVL:
    def __init__(self, clave):
        self.clave = clave
        self.izquierdo = None
        self.derecho = None
        self.altura = 1


def _altura(nodo):
    return 0 if nodo is None else nodo.altura


def _actualizar(nodo):
    a = _altura(nodo.izquierdo)
    b = _altura(nodo.derecho)
    nodo.altura = (a if a > b else b) + 1


def _rotar_derecha(y):
    x = y.izquierdo
    y.izquierdo = x.derecho
    x.derecho = y
    _actualizar(y)
    _actualizar(x)
    return x


def _rotar_izquierda(x):
    y = x.derecho
    x.derecho = y.izquierdo
    y.izquierdo = x
    _actualizar(x)
    _actualizar(y)
    return y


def _balancear(nodo):
    _actualizar(nodo)
    balance = _altura(nodo.izquierdo) - _altura(nodo.derecho)
    if balance > 1:
        if _altura(nodo.izquierdo.izquierdo) < _altura(nodo.izquierdo.derecho):
            nodo.izquierdo = _rotar_izquierda(nodo.izquierdo)  # caso izquierda-derecha
        return _rotar_derecha(nodo)
    if balance < -1:
        if _altura(nodo.derecho.derecho) < _altura(nodo.derecho.izquierdo):
            nodo.derecho = _rotar_derecha(nodo.derecho)  # caso derecha-izquierda
        return _rotar_izquierda(nodo)
    return nodo


class ArbolAVL:
    """Árbol AVL de cadenas, usado para las estaciones abiertas (R2 y R3)."""

    def __init__(self):
        self.raiz = None
        self.cantidad = 0

    def __len__(self):
        return self.cantidad

    def insertar(self, clave):
        """Devuelve True si la clave no estaba y se insertó."""
        antes = self.cantidad
        self.raiz = self._insertar(self.raiz, clave)
        return self.cantidad > antes

    def _insertar(self, nodo, clave):
        if nodo is None:
            self.cantidad += 1
            return NodoAVL(clave)
        if clave < nodo.clave:
            nodo.izquierdo = self._insertar(nodo.izquierdo, clave)
        elif clave > nodo.clave:
            nodo.derecho = self._insertar(nodo.derecho, clave)
        else:
            return nodo  # ya estaba
        return _balancear(nodo)

    def eliminar(self, clave):
        """Devuelve True si la clave estaba y se eliminó."""
        antes = self.cantidad
        self.raiz = self._eliminar(self.raiz, clave)
        return self.cantidad < antes

    def _eliminar(self, nodo, clave):
        if nodo is None:
            return None
        if clave < nodo.clave:
            nodo.izquierdo = self._eliminar(nodo.izquierdo, clave)
        elif clave > nodo.clave:
            nodo.derecho = self._eliminar(nodo.derecho, clave)
        else:
            if nodo.izquierdo is None or nodo.derecho is None:
                self.cantidad -= 1
                return nodo.izquierdo if nodo.izquierdo is not None else nodo.derecho
            # dos hijos: se reemplaza por el menor del subárbol derecho
            sucesor = nodo.derecho
            while sucesor.izquierdo is not None:
                sucesor = sucesor.izquierdo
            nodo.clave = sucesor.clave
            nodo.derecho = self._eliminar(nodo.derecho, sucesor.clave)
        return _balancear(nodo)

    def contiene(self, clave):
        nodo = self.raiz
        while nodo is not None:
            if clave == nodo.clave:
                return True
            nodo = nodo.izquierdo if clave < nodo.clave else nodo.derecho
        return False

    def desde(self, clave):
        """Recorre en orden ascendente las claves >= clave.

        Primero baja buscando el límite inferior y guarda en una pila los
        ancestros que todavía faltan por visitar; luego sigue el recorrido
        en orden normal con esa pila.
        """
        pila = []
        nodo = self.raiz
        while nodo is not None:
            if nodo.clave >= clave:
                pila.append(nodo)
                nodo = nodo.izquierdo
            else:
                nodo = nodo.derecho
        while len(pila) > 0:
            nodo = pila.pop()
            yield nodo.clave
            hijo = nodo.derecho
            while hijo is not None:
                pila.append(hijo)
                hijo = hijo.izquierdo

    def en_orden(self):
        return self.desde("")


class Nodo:
    """Parada de una ruta (lista doblemente enlazada)."""

    def __init__(self, estacion):
        self.estacion = estacion
        self.anterior = None
        self.siguiente = None

class Pila:
    """Pila sobre un arreglo: apilar y desapilar al final, O(1) amortizado."""

    def __init__(self):
        self.datos = []

    def __len__(self):
        return len(self.datos)

    def apilar(self, valor):
        self.datos.append(valor)

    def desapilar(self):
        return self.datos.pop()

    def vaciar(self):
        # Se desapila una a una: cada entrada se apiló una vez y se descarta
        # una vez, así que el costo es O(1) amortizado por mutación.
        while len(self.datos) > 0:
            self.datos.pop()

