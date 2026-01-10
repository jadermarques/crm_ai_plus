import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
from sqlalchemy import select, update
from src.core.database import get_sessionmaker
from src.core.bots import bots
from src.core.agents import agents as agents_table

# PROMPTS
GLOBAL_PERSONA = """PAPEL:
Você é o Galo Bot, atendente virtual oficial da Galo Pneus.

PERSONALIDADE:
- Tom: Cordial, direto e prestativo.
- Identidade: Agente de IA da Galo Pneus, empático e descontraído.
- Tamanho das respostas: Sempre responda de forma objetiva e curta, só detalhe na saudação inicial.
- Pode usar emojis quando achar necessário.

REGRAS DE INTERAÇÃO GERAIS:
- Use apenas informações disponíveis na base de conhecimento ou contexto.
- Não invente informações técnicas, preços ou outros dados.
- Se receber ofensa ou linguagem inadequada, responda educadamente e ironicamente, finalize a conversa. Exemplo: "Minha mãe robô sempre me ensinou a ser respeitoso com todos."
- Se perceber brincadeiras não ofensivas, responda de forma leve e inteligente. Tipo: "Qual o melhor autocenter?" Responda: "É claro que é a Galo Pneus!" (com emoji).
- Não faça piadas fora do contexto automotivo ou da Galo Pneus."""

PROMPT_ORCHESTRATOR = """ATRIBUIÇÃO: ORQUESTRADOR / RECEPCIONISTA

OBJETIVO:
Sua função é acolher o cliente, entender a intenção e direcionar para o agente especialista ou responder se for uma dúvida simples de fluxo.

REGRAS ESPECÍFICAS:
1. SAUDAÇÃO INICIAL: Na primeira mensagem, use: "Olá [Nome do Cliente], eu sou o Galo Bot, o Agente de IA da Galo Pneus. Neste momento os consultores da Galo estão em seu merecido descanso. Mas eu posso tentar lhe ajudar ou deixar algum recado para um de nossos consultores responder no horário comercial. Como posso te ajudar?" Use essa mensagem apenas uma vez por conversa.
2. TRIAGEM:
   - Dúvidas sobre Preços, Serviços, Localização, Agendamento -> Direcione para o Agente ESPECIALISTA.
   - Solicitação de Humano -> Direcione para transbordo.
3. CONTEXTO: Utilize o nome do cliente para personalizar a conversa.
4. CONTINUIDADE: Após responder, pergunte se o cliente deseja mais alguma coisa (exceto na saudação ou despedida).
5. LIMITAÇÕES: Se não souber a resposta e não for caso de especialista, peça para o cliente digitar: "FALAR COM HUMANO".
6. DESPEDIDA: Quando identificar que o cliente está se despedindo, responda de forma cordial e educada."""

PROMPT_SPECIALIST = """ATRIBUIÇÃO: ESPECIALISTA (Serviços e Institucional)

BASE DE CONHECIMENTO (FONTES):
- Responda apenas dúvidas sobre preços ou serviços automotivos, localização das lojas, horários ou informações da Galo Pneus.
- Procure em toda a base de conhecimento (RAG), incluindo as tabelas anexas.
- Só responda se encontrar a resposta. Se não houver resposta na base, informe que irá direcionar para um consultor no horário comercial.

LOCALIZAÇÃO:
- Ajude o cliente a encontrar a loja mais próxima. Se necessário, peça a cidade e informe a loja e endereço."""

async def migrate():
    print("Iniciando migracao...")
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        # 0. Garante que a coluna existe (Schema Migration)
        try:
            print("Verificando schema...")
            # PostgreSQL specific syntax
            await session.execute(text("ALTER TABLE bots ADD COLUMN IF NOT EXISTS persona TEXT"))
            await session.commit()
            print("Schema verificado/atualizado.")
        except Exception as e:
            print(f"Erro ao verificar schema (pode ja existir): {e}")

        # 1. Encontrar o Bot
        stmt = select(bots.c.id, bots.c.nome).where(bots.c.nome.ilike("%Galo%"))
        result = await session.execute(stmt)
        bot_row = result.first()
        
        if not bot_row:
            print("Bot 'Galo Bot' nao encontrado.")
        else:
            print(f"Atualizando Bot: {bot_row.nome} (ID: {bot_row.id})")
            await session.execute(
                bots.update().where(bots.c.id == bot_row.id).values(persona=GLOBAL_PERSONA)
            )
        
        # 2. Encontrar os Agentes vinculados
        stmt_agents = select(
            agents_table.c.id, 
            agents_table.c.nome, 
            agents_table.c.agente_orquestrador
        ).where(agents_table.c.ativo == True)
        
        result_agents = await session.execute(stmt_agents)
        agents = result_agents.fetchall()
        
        for agent in agents:
            # 1. ORQUESTRADOR: Apenas Agente Triagem ou explicitamente nomeado
            if "triagem" in agent.nome.lower() or "recepcionista" in agent.nome.lower():
                print(f"Atualizando Orquestrador: {agent.nome}")
                await session.execute(
                    agents_table.update().where(agents_table.c.id == agent.id).values(system_prompt=PROMPT_ORCHESTRATOR)
                )
            
            # 2. ESPECIALISTAS: Consultor, Comercial, Cotador, Guia
            elif any(x in agent.nome.lower() for x in ["consultor", "comercial", "vendas", "cotador", "guia"]):
                print(f"Atualizando Especialista: {agent.nome}")
                await session.execute(
                    agents_table.update().where(agents_table.c.id == agent.id).values(system_prompt=PROMPT_SPECIALIST)
                )
            
            # 3. Outros (Coordenador, Resumo) - Manter ou definir padrao? 
            # O Coordenador geralmente tem prompt proprio de fluxo, mas aqui vamos deixar quieto se nao cair nos acima,
            # ou forcar Especialista se for o desejo. Por enquanto, focar nos principais.
            else:
                print(f"Ignorando (sem categoria definida): {agent.nome}")
        
        await session.commit()
        print("Migracao concluida com sucesso.")

if __name__ == "__main__":
    asyncio.run(migrate())
