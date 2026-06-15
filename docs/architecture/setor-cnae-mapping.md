# Mapeamento Setor-CNAE

## 20 Setores do SmartLic

Cada licitacao e classificada em um dos 20 setores abaixo, definidos em
`backend/sectors_data.yaml`. A classificacao usa um pipeline de 3 niveis:
keyword density, contexto (context_required_keywords), e zero-match LLM.

| ID | Nome | max_contract_value | keywords principais |
|----|------|--------------------|--------------------|
| `vestuario` | Vestuario e Uniformes | R$ 5M | uniforme, fardamento, jaleco, vestuario, farda, EPI |
| `alimentos` | Alimentos e Merenda | R$ 10M | merenda, genero alimenticio, refeicao, cesta basica, carnes |
| `informatica` | Hardware e Equipamentos de TI | R$ 20M | computador, notebook, impressora, servidor, monitor, switch |
| `mobiliario` | Mobiliario | R$ 8M | mobiliario, cadeira, mesa, armario, estante |
| `papelaria` | Papelaria e Material de Escritorio | R$ 5M | papelaria, papel A4, caneta, material de escritorio |
| `engenharia` | Engenharia, Projetos e Obras | sem limite | construcao civil, pavimentacao, reforma, obra, concreto |
| `software_desenvolvimento` | Desenvolvimento de Software e Consultoria de TI | R$ 20M | desenvolvimento de software, SaaS, sistema, plataforma digital |
| `software_licencas` | Licenciamento de Software Comercial | R$ 10M | licenca de software, Microsoft 365, antivirus, Autodesk |
| `servicos_prediais` | Servicos Prediais e Facilities | R$ 30M | servico de limpeza, portaria, zeladoria, jardinagem |
| `produtos_limpeza` | Produtos de Limpeza e Higienizacao | R$ 2M | material de limpeza, detergente, papel higienico, sabao |
| `medicamentos` | Medicamentos e Produtos Farmaceuticos | R$ 20M | medicamento, farmacia, vacina, comprimido |
| `equipamentos_medicos` | Equipamentos Medico-Hospitalares | R$ 30M | equipamento medico, tomografo, ultrassom, OPME, protese |
| `insumos_hospitalares` | Insumos e Materiais Hospitalares | R$ 10M | insumo hospitalar, seringa, cateter, gaze, luva cirurgica |
| `vigilancia` | Vigilancia e Seguranca Patrimonial | R$ 40M | vigilancia, seguranca patrimonial, CFTV, alarme |
| `transporte_servicos` | Transporte de Pessoas e Cargas | R$ 50M | transporte escolar, fretamento, locomotorista |
| `frota_veicular` | Frota e Veiculos | R$ 100M | veiculo, combustivel, pneu, manutencao veicular |
| `manutencao_predial` | Manutencao e Conservacao Predial | R$ 30M | manutencao predial, ar condicionado, elevador, pintura predial |
| `engenharia_rodoviaria` | Engenharia Rodoviaria e Infraestrutura Viaria | sem limite | pavimentacao asfaltica, rodovia, ponte, sinalizacao viaria |
| `materiais_eletricos` | Materiais Eletricos e Instalacoes | R$ 20M | material eletrico, cabo, disjuntor, luminaria, transformador |
| `materiais_hidraulicos` | Materiais Hidraulicos e Saneamento | R$ 30M | material hidraulico, tubo PVC, bomba d'agua, saneamento |

Para detalhes completos de keywords, exclusions, context_required_keywords e
co_occurrence_rules, veja `backend/sectors_data.yaml`.

## Mapeamento CNAE para Setor

O mapeamento CNAE (Classificacao Nacional de Atividades Economicas) para
setores SmartLic esta em `backend/utils/cnae_mapping.py`.

### Cobertura atual

70 CNAEs mapeados em 12 setores SmartLic (de 1300 subclasses ativas do IBGE
CNAE 2.3 = ~5,4% de cobertura).

### Fontes de verdade

1. **Banco de dados** (`public.cnae_setor_mapping` no Supabase) — fonte
   primaria, editavel em runtime por admins.
2. **Dict hardcoded** (`CNAE_TO_SETOR` em `cnae_mapping.py`) — fallback de
   resiliencia quando o banco esta indisponivel.

### Tabela de mapeamento

```
CNAE  | Setor SmartLic        | Descricao
------|-----------------------|-----------------------------------------------
4120  | engenharia            | Construcao de edificios
4211  | engenharia            | Construcao de rodovias e ferrovias
4212  | engenharia            | Construcao de obras de arte especiais
4213  | engenharia            | Obras de urbanizacao
4221  | engenharia            | Construcao de redes de abastecimento de agua
4222  | engenharia            | Redes de abastecimento de agua e saneamento
4291  | engenharia            | Obras portuarias, maritimas e fluviais
4292  | engenharia            | Montagem de instalacoes industriais
4311  | engenharia            | Demolicao e preparacao de canteiros
4312  | engenharia            | Perfuracoes e sondagens
4313  | engenharia            | Obras de terraplenagem
4321  | engenharia            | Instalacoes eletricas
4322  | engenharia            | Instalacoes hidraulicas, ventilacao e refrigeracao
4391  | engenharia            | Obras de fundacoes
7111  | engenharia            | Servicos de arquitetura
7112  | engenharia            | Servicos de engenharia
8411  | engenharia            | Administracao publica em geral
1412  | vestuario             | Confeccao de pecas de vestuario
1413  | vestuario             | Confeccao de roupas intimas
1421  | vestuario             | Fabricacao de meias
1422  | vestuario             | Fabricacao de artigos do vestuario
4753  | vestuario             | Comercio varejista de cama, mesa e banho
4781  | vestuario             | Comercio varejista de artigos de vestuario
8121  | servicos_prediais     | Limpeza em predios e domicilios
8122  | servicos_prediais     | Imunizacao e controle de pragas
8129  | servicos_prediais     | Limpeza e conservacao de logradouros
8130  | servicos_prediais     | Atividades paisagisticas
3811  | servicos_prediais     | Coleta de residuos nao-perigosos
8230  | servicos_prediais     | Organizacao de eventos
8011  | vigilancia            | Vigilancia e seguranca privada
8012  | vigilancia            | Transporte de valores
8020  | vigilancia            | Monitoramento de sistemas de seguranca
1011  | alimentos             | Abate de reses
1091  | alimentos             | Produtos de panificacao e confeitaria
4639  | alimentos             | Comercio atacadista de produtos alimenticios
4711  | alimentos             | Comercio varejista de produtos alimenticios
6201  | informatica           | Desenvolvimento de software sob encomenda
6202  | informatica           | Desenvolvimento e licenciamento de software
6209  | informatica           | Suporte tecnico em TI
6311  | informatica           | Tratamento de dados, provedores de aplicacao
6319  | informatica           | Portais, provedores de conteudo
6422  | informatica           | Bancos multiplos (TI intensiva)
3250  | *saude *              | Fabricacao de instrumentos para uso medico
4644  | *saude *              | Comercio atacadista de instrumentos medicos
8610  | *saude *              | Atividades de atendimento hospitalar
8630  | *saude *              | Atividades de atencao ambulatorial
8650  | *saude *              | Atividades de apoio a gestao de saude
2710  | *equipamentos *       | Fabricacao de geradores, transformadores
2759  | *equipamentos *       | Fabricacao de aparelhos eletrodomesticos
2861  | *equipamentos *       | Fabricacao de ferramentas
4921  | *transporte *         | Transporte rodoviario coletivo municipal
4922  | *transporte *         | Transporte rodoviario coletivo intermunicipal
4924  | *transporte *         | Transporte escolar
4930  | *transporte *         | Transporte rodoviario de carga
4731  | frota_veicular        | Comercio varejista de combustiveis
4744  | engenharia            | Comercio varejista de materiais de construcao
4742  | mobiliario            | Comercio varejista de moveis
4789  | papelaria             | Comercio varejista de outros produtos NEC
6911  | servicos_prediais     | Atividades juridicas
```

Legenda: `* asteriscos *` indicam setores que usam IDs mais genericos no
CNAE mapping do que os setores reais do `sectors_data.yaml`. Ex: CNAE mapeia
para "saude", mas o pipeline usa `medicamentos`, `equipamentos_medicos`,
`insumos_hospitalares` como setores distintos.

### Resolucao de CNAE (ordem)

```
lookup_cnae_setor(cnae_code):
  1. Extrai prefixo de 4 digitos de qualquer formato
     ("4781-4/00", "47814", "4781" -> "4781")
  2. Consulta DB `cnae_setor_mapping` (primario)
  3. Se falhar, consulta dict `CNAE_TO_SETOR` (fallback)
  4. Se ambos falharem, retorna "geral"
```

A funcao `map_cnae_to_setor(cnae)` em `cnae_mapping.py` e o ponto de entrada
publico. Resultados sao cacheados via `functools.lru_cache(maxsize=1024)`.

### Nota sobre nomenclatura

O `SETOR_NAMES` no `cnae_mapping.py` contem nomes mais genericos que as
descricoes do `sectors_data.yaml` por razoes historicas. Os setores "saude"
e "equipamentos" no CNAE mapping sao agregadores que antecedem a
granularizacao do pipeline de classificacao.

## Como Funciona a Classificacao por Keywords

O pipeline de classificacao (`backend/filter/pipeline.py`) segue esta ordem
de processamento (fail-fast):

1. **UF check** — verifica se a UF da licitacao esta no conjunto selecionado
2. **Value range** — verifica se o valor estimado esta dentro do range
3. **Keyword matching** — calcula densidade de keywords do setor no texto
   da licitacao (objeto/titulo)
4. **LLM zero-match** — para licitacoes com 0% de densidade de keywords,
   usa GPT-4.1-nano para classificar
5. **Status/date validation**
6. **Viability assessment** (pos-filtro)

### Niveis de classificacao por keyword

| Densidade | Fonte | Descricao |
|-----------|-------|-----------|
| >5% | `keyword` | Match direto por keyword de alta precisao |
| 2-5% | `llm_standard` | Keyword baixa densidade + confirmacao LLM |
| 1-2% | `llm_conservative` | Keyword muito baixa + confirmacao LLM |
| 0% | `llm_zero_match` | Zero keywords + classificacao GPT-4.1-nano pura |

### Estrutura de cada setor no YAML

Cada setor em `backend/sectors_data.yaml` contem:

- **`keywords`** — lista de termos de alta precisao que disparam match direto
- **`negative_keywords`** — termos que, se presentes como assunto principal,
  devem rejeitar a classificacao
- **`exclusions`** — frases completas que anulam o match mesmo com keyword
  presente (ex: "servidor publico" anula match de "servidor" em informatica)
- **`context_required_keywords`** — para termos ambiguos: exige que pelo
  menos um termo do contexto esteja presente no texto (ex: "mesa" so classifica
  como mobiliario se "escritorio" ou "reuniao" tambem estiver presente)
- **`co_occurrence_rules`** — regras de co-ocorrencia: trigger + contexto
  negativo (rejeita) + sinal positivo (resgata)
- **`domain_signals`** — sinais de dominio para inspecao em nivel de item:
  prefixos NCM, padroes de unidade, padroes de tamanho
- **`signature_terms`** — termos caracteristicos do setor
- **`viability_value_range`** — faixa de valor ideal para analise de
  viabilidade (D-04)
- **`max_contract_value`** — valor maximo de contrato (pode ser null)

## Como Adicionar um Novo Setor

### 1. Adicionar definicao em `backend/sectors_data.yaml`

Siga o formato existente, com todos os campos obrigatorios:

```yaml
meu_novo_setor:
  name: "Meu Novo Setor"
  description: "Descricao do setor"
  max_contract_value: 10000000
  viability_value_range: [50000, 5000000]
  keywords:
    - "termo1"
    - "termo2 composto"
  negative_keywords:
    - "falso_positivo"
  exclusions: []
  context_required_keywords: {}
  co_occurrence_rules: []
  domain_signals:
    ncm_prefixes: []
    unit_patterns: []
    size_patterns: []
  signature_terms: []
```

### 2. Adicionar mapeamento CNAE (opcional)

Em `backend/utils/cnae_mapping.py`, adicione entradas no dict
`CNAE_TO_SETOR`:

```python
"XXXX": "meu_novo_setor",  # Descricao do CNAE
```

### 3. Adicionar mapping no banco (opcional)

Execute migration no Supabase para inserir na tabela
`public.cnae_setor_mapping`:

```sql
INSERT INTO cnae_setor_mapping (cnae_code, setor_id, description)
VALUES ('XXXX', 'meu_novo_setor', 'Descricao do CNAE');
```

### 4. Atualizar frontend fallback (se necessario)

Rode `node scripts/sync-setores-fallback.js` para manter a lista de setores
no frontend sincronizada.

### 5. Adicionar testes

Atualize `backend/tests/test_filter*.py` com novos casos de teste:
- Match positivo com as keywords do novo setor
- Rejeicao de falsos positivos com `negative_keywords`/`exclusions`
- Validacao de `context_required_keywords` para termos ambíguos
- Benchmark de precisao >=85% e recall >=70%

### 6. Verificar pipeline

Rode `pytest -k test_filter` para garantir que nao houve regressao nos
outros setores.

## Referencias

- `backend/sectors_data.yaml` — definicao completa dos 20 setores
- `backend/utils/cnae_mapping.py` — mapeamento CNAE->setor com fallback
- `backend/filter/pipeline.py` — pipeline de classificacao
- `backend/sectors.py` — carregamento do YAML em runtime
- `supabase/migrations/20260511120000_cnae_setor_mapping.sql` — seed do
  mapeamento CNAE no banco
- `scripts/sync-setores-fallback.js` — sincronizacao com frontend
