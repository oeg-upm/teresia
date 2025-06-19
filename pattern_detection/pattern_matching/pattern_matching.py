import json
from typing import List, Dict, Union, List
from pathlib import Path
import re

def load_text_patterns(file_path: str, term: str, pattern_label: str = None) -> List[str]:
    """
    Carga patrones desde un archivo JSON y los adapta al término especificado.
    
    Args:
        file_path: Ruta al archivo JSON que contiene los patrones
        term: Término que se usará para reemplazar __TERM__ en los patrones
        pattern_label: Nombre de patrón a cargar (opcional si el archivo solo tiene un tipo)
    
    Returns:
        Lista de patrones adaptados al término
        
    Raises:
        FileNotFoundError: Si el archivo no existe
        ValueError: Si el pattern_label no existe en el archivo
        json.JSONDecodeError: Si el archivo no es un JSON válido
    """
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"El archivo de patrones no existe: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            patterns_data = json.load(f)
        
        # Si no se especifica pattern_label y solo hay un tipo en el archivo, usarlo
        if pattern_label is None:
            if len(patterns_data) == 1:
                pattern_label = next(iter(patterns_data.keys()))
            else:
                raise ValueError("Debe especificar pattern_label cuando el archivo contiene múltiples tipos")
        
        if pattern_label not in patterns_data:
            available_types = list(patterns_data.keys())
            raise ValueError(
                f"Tipo de patrón '{pattern_label}' no encontrado. "
                f"Tipos disponibles: {', '.join(available_types)}"
            )
        
        return [pattern.replace("__TERM__", term) for pattern in patterns_data[pattern_label]]
    
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Error al decodificar JSON en {file_path}: {e.msg}", e.doc, e.pos)


def detect_patterns(text: str, patterns: List[str]) -> bool:
    """
    Detecta si alguno de los patrones se encuentra en el texto.
    Args:
        text (str): El texto en el que buscar los patrones.
        patterns (list): Lista de patrones a buscar.
    Returns:
        bool: True si se encuentra al menos un patrón, False en caso contrario.
    """
    compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    found = False
    processed_text = text

    for pattern in compiled_patterns:
        match = pattern.search(processed_text)
        if match and match.group(0).strip() != "":
            found = True
    return found


def highlight_patterns(text: str, patterns: list) -> str:
    """
    Resalta el término y los patrones de contexto sin alterar el orden original.
    Args:
        text (str): El texto en el que buscar los patrones.
        patterns (list): Lista de patrones a resaltar, donde cada patrón puede contener grupos nombrados.
    Returns:
        str: El texto con los patrones resaltados, o None si no se encuentra ninguno.
    """
    regexes = [re.compile(p, re.IGNORECASE) for p in patterns]
    found = False
    highlighted_text = text

    for regex in regexes:
        def replacer(match):
            nonlocal found
            # Validar que la coincidencia no esté vacía
            if not match or match.group(0).strip() == "":
                return match.group(0)
            found = True
            result = match.group(0)
            replaced = result
            spans = []

            # Ordenar los grupos según su posición en el texto
            spans_data = []
            for name, value in match.groupdict().items():
                if value:
                    start = match.start(name) - match.start()
                    end = match.end(name) - match.start()
                    span_class = 'highlight-term' if name == 'term' else 'highlight-pattern'
                    spans_data.append((start, end, span_class, value))

            # Aplicar los span *desde el final hacia el inicio* para no romper los índices
            for start, end, cls, val in sorted(spans_data, reverse=True):
                replaced = replaced[:start] + f'<span class="{cls}">{val}</span>' + replaced[end:]

            return replaced

        highlighted_text = regex.sub(replacer, highlighted_text)

    return highlighted_text if found else None


def highlight_term(text: str, term: str) -> str:
    """
    Resalta un término específico en el texto, envolviéndolo en una etiqueta <span>.
    Si el término no se encuentra, devuelve el texto original.
    Args:
        text (str): El texto en el que buscar el término.
        term (str): El término a resaltar.
    Returns:
        str: El texto con el término resaltado, o el texto original si no se encuentra.
    """
    found = False
    pattern = re.compile(term, re.IGNORECASE)
    if pattern.search(text):
        found = True
        highlighted_text = pattern.sub(lambda match: f'<span class="highlight-term">{match.group(0)}</span>', text)

    return highlighted_text if found else text



