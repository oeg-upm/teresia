import json
import os
import pytest

from pattern_matching.pattern_matching import load_text_patterns, detect_patterns, highlight_patterns, highlight_term

BASE = os.path.dirname(__file__)

def load_fragments(file_name):
    """
    Carga fragments desde el directorio data.
    Lanza AssertionError si no existe el archivo.
    """
    path = os.path.join(BASE, os.pardir, "data", file_name)
    assert os.path.exists(path), (
        f"No existe {file_name}; ejecuta el script de conversión para generarlo en data/{file_name}"
    )
    with open(path, encoding="utf-8") as f:
        return json.load(f)

@pytest.mark.parametrize("file_name,pattern_label", [
    ("loan_fragments.json", "loan"),
    ("gloss_fragments.json", "gloss"),
])
def test_detect_patterns_with_fragments(file_name, pattern_label):
    """
    Para cada fragmento en los archivos generados, comprueba que detect_patterns devuelve booleano.
    Fallará si faltan archivos o patrones.
    """
    frags = load_fragments(file_name)
    # Directorio de patrones
    pattern_dir = os.path.join(BASE, os.pardir, "patterns")
    patterns_path = os.path.join(pattern_dir, f"{pattern_label}_patterns.json")
    assert os.path.exists(patterns_path), (
        f"No existe el fichero de patrones {patterns_path}. Comprueba la ruta y los nombres."
    )
    for entry in frags:
        term = entry.get("term") or entry.get("fragmento") or entry.get("fragment")
        fragment = entry.get("fragment") or entry.get("fragmento")
        # Carga los patrones para el término
        pats = load_text_patterns(patterns_path, term=term, pattern_label=pattern_label)
        # detect_patterns debe devolver un booleano y no lanzar excepción
        result = detect_patterns(fragment, pats)
        assert isinstance(result, bool), (
            f"detect_patterns no devolvió bool para {file_name} con término {term}"
        )


def test_highlight_patterns_and_term():
    """
    Prueba highlight_patterns y highlight_term con ejemplos simples.
    """
    pattern_dir = os.path.join(BASE, os.pardir, "patterns")
    gloss_file = os.path.join(pattern_dir, "gloss_patterns.json")
    assert os.path.exists(gloss_file), (
        f"No existe el fichero de patrones {gloss_file}. Comprueba la ruta."
    )
    term = "prueba"
    pats = load_text_patterns(gloss_file, term=term, pattern_label="gloss")
    text = "La prueba, es decir, un ejemplo claro."
    highlighted = highlight_patterns(text, pats)
    assert '<span class="highlight-term">prueba</span>' in highlighted
    # Prueba highlight_term
    out = highlight_term("Hola mundo", "mundo")
    assert '<span class="highlight-term">mundo</span>' in out
