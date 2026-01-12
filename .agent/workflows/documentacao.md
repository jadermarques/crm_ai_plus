---
description: Sempre gerar e atualizar docstrings em Português do Brasil ao criar ou modificar código
---

# Regra de Documentação Automática

Ao criar ou modificar qualquer arquivo Python, SEMPRE:

1. **Adicionar/Atualizar Docstrings** em **Português do Brasil**
2. **Formato Google-Style** (compatível com Sphinx)

## Padrão de Docstrings

```python
def funcao_exemplo(param1: int, param2: str) -> bool:
    """Descrição breve da função.

    Descrição mais detalhada se necessário.

    Args:
        param1: Descrição do primeiro parâmetro.
        param2: Descrição do segundo parâmetro.

    Returns:
        Descrição do valor retornado.

    Raises:
        ValueError: Quando ocorre um erro de validação.
    """
```

## Docstring de Módulo

```python
"""Nome do Módulo - Descrição breve.

Descrição detalhada do propósito do módulo.

Attributes:
    CONSTANTE: Descrição da constante.

Functions:
    funcao: Descrição da função.

Example:
    >>> from modulo import funcao
    >>> funcao(1, "teste")
    True
"""
```

## Checklist

- [ ] Docstring de módulo no topo do arquivo
- [ ] Docstring em todas as funções públicas
- [ ] Docstring em todas as classes
- [ ] Args, Returns e Raises quando aplicável
- [ ] Tipagem estrita (Type Hints) nos argumentos e retorno
- [ ] Texto em Português do Brasil
