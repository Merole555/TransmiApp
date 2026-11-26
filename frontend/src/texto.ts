/** Misma normalización que hace el backend: mayúsculas, sin tildes y un solo espacio. */
export function normalizar(texto: string): string {
  return texto
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .split(/\s+/)
    .join(' ')
    .toUpperCase()
}
