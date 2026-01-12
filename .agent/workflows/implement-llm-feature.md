---
description: Guia para implementar novas funcionalidades que usam LLM, garantindo o padrão de logging.
---

# Workflow: Implementar Funcionalidade LLM

Este workflow serve como guia para adicionar qualquer nova funcionalidade que envolva chamadas a LLMs (OpenAI, etc.), garantindo que o padrão de logging seja respeitado.

## 1. Planejamento

- Defina qual modelo será usado.
- Defina o System Prompt.
- Determine onde o código será implementado no projeto.

## 2. Implementação

Ao escrever o código que chama o modelo (ex: via `pydantic_ai` ou cliente direto), você **DEVE** adicionar o log.

1.  Importe o logger:
    ```python
    from src.core.debug_logger import log_llm_interaction
    ```

    ```python
    try:
        # Chamada ao modelo
        response = call_llm_model(...) 
        
        # Log de Sucesso
        log_llm_interaction(
            agent_name="<Nome do Agente/Funcionalidade>",
            model="<Nome do Modelo>",
            system_prompt="<O Prompt do Sistema>",
            user_prompt="<O Prompt do Usuário>",
            response="<A Resposta Gerada>",
            usage={"input": 0, "output": 0, "total": 0} # Se disponível
        )
    except Exception as e:
        # Log de Erro (Essencial para Debug)
        log_llm_interaction(
            agent_name="<Nome do Agente/Funcionalidade>",
            model="<Nome do Modelo> (ERROR)",
            system_prompt="<O Prompt do Sistema>",
            user_prompt="<O Prompt do Usuário>",
            response=f"ERRO NA CHAMADA LLM: {str(e)}",
            usage=None
        )
        raise e # Re-raise para tratamento superior
    ```

## 3. Verificação

1.  Execute a nova funcionalidade.
2.  Verifique se o arquivo `logs/llm_history.log` foi atualizado.
    ```bash
    tail -n 20 logs/llm_history.log
    ```
3.  Certifique-se de que os campos (Agent, Model, Prompts, Response) estão corretos.
