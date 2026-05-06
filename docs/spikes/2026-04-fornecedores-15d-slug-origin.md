# Spike: origem dos slugs malformados `/fornecedores/{15d}` e `/fornecedores/{11d}`

Data: 2026-04-27
Story: `STORY-DISC-001`
Fonte local: `gsc-404-urls.txt`

## Escopo executado

- Task 1: extracao local e analise de padrao dos slugs `/fornecedores/[0-9]{15}` e `/fornecedores/[0-9]{11}`.
- Task 3: greps locais em frontend/backend/sitemap para evidencias das hipoteses.
- Task 6, parte local: sintese e recomendacao com base nas evidencias disponiveis sem acesso externo.
- Fora de escopo nesta execucao: Sentry, GSC Performance e `curl` de endpoint remoto, por exigirem acesso externo/credenciais ou ambiente publicado.

## Resultado da extracao

| Metrica | Valor |
| --- | ---: |
| URLs totais extraidas de `gsc-404-urls.txt` | 1000 |
| URLs em `/fornecedores/{digits}` | 454 |
| URLs `/fornecedores/{15d}` | 268 |
| URLs `/fornecedores/{11d}` | 18 |
| URLs `/fornecedores/{14d}` presentes na lista bruta | 168 |
| Bases de 14 digitos unicas ao remover o ultimo digito das 15d | 268 |

Distribuicao do 15o digito nas URLs de 15 digitos:

| Digito final | Ocorrencias |
| --- | ---: |
| 2 | 268 |

Conclusao do padrao: o digito extra esta sempre na posicao final e e sempre `2` nas 268 URLs de 15 digitos. Isso e compativel com uma concatenacao deterministica de sufixo `2`, nao com erro aleatorio de crawler.

As 18 URLs de 11 digitos parecem CPFs ou identificadores de pessoa fisica, nao CNPJs truncados: todas tem 11 digitos e nenhuma compartilha prefixo evidente com a lista de 15 digitos.

## Lista completa filtrada

### `/fornecedores/{15d}` (268 URLs)

- https://smartlic.tech/fornecedores/007352600001052
- https://smartlic.tech/fornecedores/055467960001042
- https://smartlic.tech/fornecedores/500372600001002
- https://smartlic.tech/fornecedores/152851530001082
- https://smartlic.tech/fornecedores/249736270001972
- https://smartlic.tech/fornecedores/444213390001372
- https://smartlic.tech/fornecedores/061405320001002
- https://smartlic.tech/fornecedores/212866320001332
- https://smartlic.tech/fornecedores/251883880001272
- https://smartlic.tech/fornecedores/019249960001942
- https://smartlic.tech/fornecedores/166388340001672
- https://smartlic.tech/fornecedores/654882800001742
- https://smartlic.tech/fornecedores/394593400001102
- https://smartlic.tech/fornecedores/532175370001742
- https://smartlic.tech/fornecedores/291270590001272
- https://smartlic.tech/fornecedores/567292920001522
- https://smartlic.tech/fornecedores/092618080001052
- https://smartlic.tech/fornecedores/397579340001082
- https://smartlic.tech/fornecedores/186044760001052
- https://smartlic.tech/fornecedores/116095330001912
- https://smartlic.tech/fornecedores/202501900001022
- https://smartlic.tech/fornecedores/172809650001882
- https://smartlic.tech/fornecedores/343187290001222
- https://smartlic.tech/fornecedores/110442720001002
- https://smartlic.tech/fornecedores/375935550001022
- https://smartlic.tech/fornecedores/517845790001612
- https://smartlic.tech/fornecedores/009009300001002
- https://smartlic.tech/fornecedores/131808570001822
- https://smartlic.tech/fornecedores/321268930001022
- https://smartlic.tech/fornecedores/006754680001862
- https://smartlic.tech/fornecedores/445708430001072
- https://smartlic.tech/fornecedores/576509190001482
- https://smartlic.tech/fornecedores/187845660001172
- https://smartlic.tech/fornecedores/306765200001802
- https://smartlic.tech/fornecedores/224603120001102
- https://smartlic.tech/fornecedores/071878270001032
- https://smartlic.tech/fornecedores/060485390001052
- https://smartlic.tech/fornecedores/070096800001532
- https://smartlic.tech/fornecedores/778301560001242
- https://smartlic.tech/fornecedores/510822590001602
- https://smartlic.tech/fornecedores/330124050001072
- https://smartlic.tech/fornecedores/453609130001572
- https://smartlic.tech/fornecedores/469087700001382
- https://smartlic.tech/fornecedores/334534280001492
- https://smartlic.tech/fornecedores/298898080001532
- https://smartlic.tech/fornecedores/108680680001402
- https://smartlic.tech/fornecedores/057637850001782
- https://smartlic.tech/fornecedores/263373950001062
- https://smartlic.tech/fornecedores/157802020001702
- https://smartlic.tech/fornecedores/147174390001442
- https://smartlic.tech/fornecedores/728348150001872
- https://smartlic.tech/fornecedores/525517290001502
- https://smartlic.tech/fornecedores/106243840001772
- https://smartlic.tech/fornecedores/190690450001402
- https://smartlic.tech/fornecedores/113045900001622
- https://smartlic.tech/fornecedores/941320240001482
- https://smartlic.tech/fornecedores/172733480001552
- https://smartlic.tech/fornecedores/028428370001032
- https://smartlic.tech/fornecedores/285464700001742
- https://smartlic.tech/fornecedores/466038620001002
- https://smartlic.tech/fornecedores/331523850001612
- https://smartlic.tech/fornecedores/321799730001262
- https://smartlic.tech/fornecedores/103624430001862
- https://smartlic.tech/fornecedores/082037990001252
- https://smartlic.tech/fornecedores/449273490001492
- https://smartlic.tech/fornecedores/525749670001802
- https://smartlic.tech/fornecedores/281849510001872
- https://smartlic.tech/fornecedores/472183350001442
- https://smartlic.tech/fornecedores/395873390001712
- https://smartlic.tech/fornecedores/502524820001452
- https://smartlic.tech/fornecedores/546095690001882
- https://smartlic.tech/fornecedores/051662410001292
- https://smartlic.tech/fornecedores/219216450006412
- https://smartlic.tech/fornecedores/178562390001602
- https://smartlic.tech/fornecedores/111358320001312
- https://smartlic.tech/fornecedores/546864430001072
- https://smartlic.tech/fornecedores/042251530001982
- https://smartlic.tech/fornecedores/295434830002332
- https://smartlic.tech/fornecedores/464307410001032
- https://smartlic.tech/fornecedores/440340250001812
- https://smartlic.tech/fornecedores/491924280001722
- https://smartlic.tech/fornecedores/054555090001422
- https://smartlic.tech/fornecedores/488769630001802
- https://smartlic.tech/fornecedores/222533850002122
- https://smartlic.tech/fornecedores/399876830001582
- https://smartlic.tech/fornecedores/610495950001642
- https://smartlic.tech/fornecedores/018985450001202
- https://smartlic.tech/fornecedores/081794960001142
- https://smartlic.tech/fornecedores/172573440001832
- https://smartlic.tech/fornecedores/034317160001312
- https://smartlic.tech/fornecedores/357216250001272
- https://smartlic.tech/fornecedores/005120110001502
- https://smartlic.tech/fornecedores/107608360001482
- https://smartlic.tech/fornecedores/375081340001282
- https://smartlic.tech/fornecedores/150581440001762
- https://smartlic.tech/fornecedores/288133250001022
- https://smartlic.tech/fornecedores/253628090001942
- https://smartlic.tech/fornecedores/347431420001602
- https://smartlic.tech/fornecedores/038090740001612
- https://smartlic.tech/fornecedores/182369790001672
- https://smartlic.tech/fornecedores/134466420001602
- https://smartlic.tech/fornecedores/106321540001502
- https://smartlic.tech/fornecedores/329510080001202
- https://smartlic.tech/fornecedores/001592910001652
- https://smartlic.tech/fornecedores/373408100001052
- https://smartlic.tech/fornecedores/400648060001682
- https://smartlic.tech/fornecedores/035662170001512
- https://smartlic.tech/fornecedores/268663630001062
- https://smartlic.tech/fornecedores/074198420001212
- https://smartlic.tech/fornecedores/031326390001192
- https://smartlic.tech/fornecedores/817712480001582
- https://smartlic.tech/fornecedores/267427860001062
- https://smartlic.tech/fornecedores/502843850001342
- https://smartlic.tech/fornecedores/131777750001892
- https://smartlic.tech/fornecedores/144591580001392
- https://smartlic.tech/fornecedores/172322020001612
- https://smartlic.tech/fornecedores/071929290001092
- https://smartlic.tech/fornecedores/107644320001222
- https://smartlic.tech/fornecedores/010038690001522
- https://smartlic.tech/fornecedores/385515110001742
- https://smartlic.tech/fornecedores/048892200001792
- https://smartlic.tech/fornecedores/203351480001942
- https://smartlic.tech/fornecedores/133886910001942
- https://smartlic.tech/fornecedores/289176030001712
- https://smartlic.tech/fornecedores/391852690001252
- https://smartlic.tech/fornecedores/263221820001002
- https://smartlic.tech/fornecedores/102301700001162
- https://smartlic.tech/fornecedores/301748460001092
- https://smartlic.tech/fornecedores/094433270001022
- https://smartlic.tech/fornecedores/237299000001702
- https://smartlic.tech/fornecedores/288030640001402
- https://smartlic.tech/fornecedores/119965170001072
- https://smartlic.tech/fornecedores/502238230001542
- https://smartlic.tech/fornecedores/322471480001112
- https://smartlic.tech/fornecedores/127713610001102
- https://smartlic.tech/fornecedores/319668630001412
- https://smartlic.tech/fornecedores/075528510001962
- https://smartlic.tech/fornecedores/536303300001272
- https://smartlic.tech/fornecedores/205018540001692
- https://smartlic.tech/fornecedores/219337700001672
- https://smartlic.tech/fornecedores/802437690001702
- https://smartlic.tech/fornecedores/014664310001002
- https://smartlic.tech/fornecedores/575430010009572
- https://smartlic.tech/fornecedores/129043120001092
- https://smartlic.tech/fornecedores/480578790001342
- https://smartlic.tech/fornecedores/087607630001422
- https://smartlic.tech/fornecedores/392668710001972
- https://smartlic.tech/fornecedores/175586110001522
- https://smartlic.tech/fornecedores/025393840001402
- https://smartlic.tech/fornecedores/090827050001702
- https://smartlic.tech/fornecedores/061888780001892
- https://smartlic.tech/fornecedores/549713090001582
- https://smartlic.tech/fornecedores/233978650001392
- https://smartlic.tech/fornecedores/217095780001912
- https://smartlic.tech/fornecedores/020696290001132
- https://smartlic.tech/fornecedores/072429920001022
- https://smartlic.tech/fornecedores/281148930001152
- https://smartlic.tech/fornecedores/320405290001252
- https://smartlic.tech/fornecedores/039182380001992
- https://smartlic.tech/fornecedores/078669380001382
- https://smartlic.tech/fornecedores/363105430001522
- https://smartlic.tech/fornecedores/184924540001922
- https://smartlic.tech/fornecedores/224916770001022
- https://smartlic.tech/fornecedores/089586280002972
- https://smartlic.tech/fornecedores/578171670001672
- https://smartlic.tech/fornecedores/043843490001252
- https://smartlic.tech/fornecedores/489779210001352
- https://smartlic.tech/fornecedores/394203760001902
- https://smartlic.tech/fornecedores/136785370001572
- https://smartlic.tech/fornecedores/216120640001132
- https://smartlic.tech/fornecedores/581686190001902
- https://smartlic.tech/fornecedores/015702930001052
- https://smartlic.tech/fornecedores/417411340001402
- https://smartlic.tech/fornecedores/585215540001142
- https://smartlic.tech/fornecedores/393648330001772
- https://smartlic.tech/fornecedores/328995800001972
- https://smartlic.tech/fornecedores/182555330001802
- https://smartlic.tech/fornecedores/167256700001052
- https://smartlic.tech/fornecedores/066983000001722
- https://smartlic.tech/fornecedores/440429250001702
- https://smartlic.tech/fornecedores/324077150001502
- https://smartlic.tech/fornecedores/248380520001082
- https://smartlic.tech/fornecedores/095512470001702
- https://smartlic.tech/fornecedores/210982500001862
- https://smartlic.tech/fornecedores/038446980001102
- https://smartlic.tech/fornecedores/596886940001442
- https://smartlic.tech/fornecedores/396792450001222
- https://smartlic.tech/fornecedores/130248270001872
- https://smartlic.tech/fornecedores/108181130001522
- https://smartlic.tech/fornecedores/300889230001082
- https://smartlic.tech/fornecedores/240117410001362
- https://smartlic.tech/fornecedores/197142050001672
- https://smartlic.tech/fornecedores/259895930001912
- https://smartlic.tech/fornecedores/049510330001782
- https://smartlic.tech/fornecedores/765034320001872
- https://smartlic.tech/fornecedores/958038390001742
- https://smartlic.tech/fornecedores/026405770001932
- https://smartlic.tech/fornecedores/197511740001142
- https://smartlic.tech/fornecedores/073844930001502
- https://smartlic.tech/fornecedores/354199360001362
- https://smartlic.tech/fornecedores/392817720001842
- https://smartlic.tech/fornecedores/111063050001072
- https://smartlic.tech/fornecedores/335796800001072
- https://smartlic.tech/fornecedores/035623400001022
- https://smartlic.tech/fornecedores/235725040001812
- https://smartlic.tech/fornecedores/042472520001702
- https://smartlic.tech/fornecedores/045890980001152
- https://smartlic.tech/fornecedores/261938860001202
- https://smartlic.tech/fornecedores/050355320020402
- https://smartlic.tech/fornecedores/231114810001082
- https://smartlic.tech/fornecedores/150657860113072
- https://smartlic.tech/fornecedores/244084720001462
- https://smartlic.tech/fornecedores/059581980001342
- https://smartlic.tech/fornecedores/144516360001642
- https://smartlic.tech/fornecedores/089977560002402
- https://smartlic.tech/fornecedores/223361520001002
- https://smartlic.tech/fornecedores/260388790001542
- https://smartlic.tech/fornecedores/418587200001702
- https://smartlic.tech/fornecedores/306529720001212
- https://smartlic.tech/fornecedores/763961590001392
- https://smartlic.tech/fornecedores/202294320001862
- https://smartlic.tech/fornecedores/185290640001402
- https://smartlic.tech/fornecedores/411673470001002
- https://smartlic.tech/fornecedores/275493620001922
- https://smartlic.tech/fornecedores/360402730001072
- https://smartlic.tech/fornecedores/178514470001772
- https://smartlic.tech/fornecedores/212680220001072
- https://smartlic.tech/fornecedores/515311200001562
- https://smartlic.tech/fornecedores/370568960001302
- https://smartlic.tech/fornecedores/088559570001212
- https://smartlic.tech/fornecedores/231091420001972
- https://smartlic.tech/fornecedores/105483790001222
- https://smartlic.tech/fornecedores/070045110001202
- https://smartlic.tech/fornecedores/332588570001652
- https://smartlic.tech/fornecedores/004169730001062
- https://smartlic.tech/fornecedores/864480570001732
- https://smartlic.tech/fornecedores/297422430001872
- https://smartlic.tech/fornecedores/272720750001882
- https://smartlic.tech/fornecedores/031770790001192
- https://smartlic.tech/fornecedores/350750160001482
- https://smartlic.tech/fornecedores/852603540001282
- https://smartlic.tech/fornecedores/987488090001092
- https://smartlic.tech/fornecedores/898865430001612
- https://smartlic.tech/fornecedores/338435440001742
- https://smartlic.tech/fornecedores/557978700001252
- https://smartlic.tech/fornecedores/837548200001042
- https://smartlic.tech/fornecedores/251380930001462
- https://smartlic.tech/fornecedores/086249970001622
- https://smartlic.tech/fornecedores/713767840001032
- https://smartlic.tech/fornecedores/417221120001332
- https://smartlic.tech/fornecedores/913604200002152
- https://smartlic.tech/fornecedores/204152950017312
- https://smartlic.tech/fornecedores/598761190001752
- https://smartlic.tech/fornecedores/095025530001172
- https://smartlic.tech/fornecedores/383307850001332
- https://smartlic.tech/fornecedores/269662150001552
- https://smartlic.tech/fornecedores/122180830001792
- https://smartlic.tech/fornecedores/830735360001642
- https://smartlic.tech/fornecedores/008208540001142
- https://smartlic.tech/fornecedores/340283160028232
- https://smartlic.tech/fornecedores/153558190001492
- https://smartlic.tech/fornecedores/038235780001362
- https://smartlic.tech/fornecedores/319472740001162
- https://smartlic.tech/fornecedores/263085010001232
- https://smartlic.tech/fornecedores/061213250001092
- https://smartlic.tech/fornecedores/180279620001082
- https://smartlic.tech/fornecedores/375888780001082
- https://smartlic.tech/fornecedores/323310770001302

### `/fornecedores/{11d}` (18 URLs)

- https://smartlic.tech/fornecedores/02810984336
- https://smartlic.tech/fornecedores/01415448990
- https://smartlic.tech/fornecedores/09847698970
- https://smartlic.tech/fornecedores/10861038908
- https://smartlic.tech/fornecedores/02864381354
- https://smartlic.tech/fornecedores/07337813309
- https://smartlic.tech/fornecedores/01256209341
- https://smartlic.tech/fornecedores/59209836391
- https://smartlic.tech/fornecedores/03570103374
- https://smartlic.tech/fornecedores/08324076310
- https://smartlic.tech/fornecedores/89764706304
- https://smartlic.tech/fornecedores/06247413629
- https://smartlic.tech/fornecedores/04749023906
- https://smartlic.tech/fornecedores/01043291903
- https://smartlic.tech/fornecedores/86023420559
- https://smartlic.tech/fornecedores/08722218572
- https://smartlic.tech/fornecedores/44492707468
- https://smartlic.tech/fornecedores/03661240480

## Evidencias locais por hipotese

### H1: Backend retorna CNPJ + digito extra

Evidencia local contra a hipotese no codigo atual:

- `backend/routes/sitemap_cnpjs.py:332-335`: `_fetch_top_fornecedores_cnpjs()` le `ni_fornecedor`, aplica `.strip()` e aceita apenas `len(cnpj) == 14 and cnpj.isdigit()` antes de incluir no sitemap.
- `backend/routes/contratos_publicos.py:656-667`: `fornecedor_profile(cnpj)` limpa com `strip()` e rejeita qualquer slug que nao casa `_CNPJ_RE` de 14 digitos, retornando `400` no backend.
- Grep local por `fornecedores-cnpj`, `ni_fornecedor`, `concat`, `substring`, `cnpj +`, `+ 2`, `+ '2'`, `dvVerificador` e `digitoExtra` nao encontrou concatenacao de sufixo no endpoint de sitemap.

Limite da evidencia: sem consultar o banco/producao, nao foi possivel provar que dados antigos, cache CDN, shard legado ou deploy anterior nao emitiram os slugs malformados.

### H2: Link interno bug

Evidencias locais:

- `frontend/app/sitemap.ts:889-891`: o sitemap monta `/fornecedores/${cnpj}` diretamente a partir de `fetchSitemapFornecedoresCnpj()`, sem adicionar sufixo.
- `frontend/components/blog/ContractsPanoramaBlock.tsx:277-282`: link interno para fornecedor usa `href={`/fornecedores/${forn.cnpj}`}`.
- `frontend/app/orgaos/[slug]/OrgaoPerfilClient.tsx:363-367`: link de top fornecedores usa `href={`/fornecedores/${f.cnpj}`}`.
- `frontend/app/compliance/[cnpj]/page.tsx:301`: link relacionado usa `href={`/fornecedores/${cnpj}`}`.
- Grep local por `href` com `/fornecedores/`, `${cnpj}`, `cnpj +`, `padStart`, `dvVerificador` e `digitoExtra` nao encontrou codigo adicionando `2` ao CNPJ para rota `/fornecedores/{cnpj}`.

Conclusao local: nao ha evidencia de bug de link interno no codigo atual. Ainda e possivel que um deploy anterior tenha gerado essas URLs.

### H3: External backlink antigo

Nao verificavel com arquivos locais. Seria necessario acesso ao GSC Links ou ferramenta externa de backlinks. O padrao uniforme de sufixo `2` sugere origem sistemica, mas nao distingue sitemap legado, link interno antigo ou backlink externo que replicou URLs ja publicadas.

### H4: Bot scraping inserindo string corrompida

Nao ha evidencia local que sustente crawler externo inventando o sufixo. O fato de 268/268 URLs de 15 digitos terminarem em `2` aponta mais para uma fonte deterministica. Sem logs de referer/user-agent, a hipotese segue indeterminada.

### H5: Sitemap legacy

Evidencias locais relevantes:

- `frontend/app/sitemap.ts:220-231`: `fetchSitemapFornecedoresCnpj()` busca `/v1/sitemap/fornecedores-cnpj` e retorna `data.cnpjs` sem validacao de tamanho no frontend.
- `frontend/app/sitemap.ts:889-891`: qualquer valor retornado por esse endpoint vira URL `/fornecedores/${cnpj}`.
- `backend/routes/sitemap_cnpjs.py:332-335`: no codigo atual, o backend filtra para 14 digitos antes de responder.

Conclusao local: sitemap legacy/deploy antigo segue sendo a hipotese mais plausivel entre as que dependem de origem interna, porque o frontend atual confia no payload do backend e uma versao anterior do endpoint poderia ter emitido `ni_fornecedor + 2`. O codigo atual do backend, entretanto, contem filtro que impediria emissao nova desses slugs.

## Checks bloqueados ou nao executados

- Backend remoto (`curl https://api.smartlic.tech/v1/sitemap/fornecedores-cnpj`): bloqueado nesta execucao por escopo sem acesso externo. Check recomendado: contar itens cujo tamanho seja diferente de 14 e salvar amostra.
- Sentry: bloqueado por falta de acesso/credenciais nesta sessao. Query recomendada: `path ~ '/fornecedores/[0-9]{15}'` nos ultimos 30 dias, capturando `referer`, release e user-agent.
- GSC Performance/Search Analytics: bloqueado por falta de acesso externo nesta sessao. Filtro recomendado: Page contendo regex equivalente a `/fornecedores/[0-9]{15}`; exportar queries, paginas de entrada e datas de descoberta.
- Backlinks externos: bloqueado por depender de GSC Links ou ferramenta externa. Verificar se dominios externos apontam diretamente para slugs com sufixo `2`.

## Conclusao

A raiz exata permanece indeterminada com evidencia apenas local. O padrao extraido e forte: todas as 268 URLs de 15 digitos sao um CNPJ-like de 14 digitos seguido por `2`. No codigo atual, o backend de sitemap filtra `ni_fornecedor` para exatamente 14 digitos, e os links internos encontrados apenas interpolam o CNPJ recebido, sem concatenar sufixo.

A explicacao mais provavel e uma origem interna historica ou externa derivada de uma origem interna historica: sitemap antigo/deploy anterior/cache que publicou `ni_fornecedor + 2`, depois descoberto e retido pelo Google. As URLs de 11 digitos formam um subcluster separado, provavelmente CPFs/identificadores de pessoa fisica enviados para rota de CNPJ.

## Recomendacao

1. Antes de qualquer fix, executar os checks externos bloqueados para confirmar se ainda ha emissao viva: endpoint remoto de sitemap, Sentry com referer e GSC Performance.
2. Se o endpoint remoto atual nao emitir 15d, tratar como legado indexado: abrir story de mitigacao SEO para redirecionar `/fornecedores/{15d ending 2}` para `/fornecedores/{first14}` quando o primeiro 14d existir, com `301`, canonical e metricas.
3. Se Sentry/GSC mostrar referer interno atual, abrir story de bug no componente/endpoint apontado pelo referer.
4. Para o cluster 11d, nao redirecionar automaticamente para CNPJ. Manter `404/noindex` ou criar regra separada apenas se logs provarem rota legada valida.

## Comandos locais usados

```bash
node - <<'NODE' # extrai URLs de gsc-404-urls.txt e calcula distribuicoes/listas
rg -n "fornecedores-cnpj|fornecedores/|supplier_cnpj|fornecedor_cnpj|cnpj_fornecedor|cnpj.{0,20}fornecedor|fornecedor.{0,20}cnpj|substr|substring|concat|\|\||'2'|\+ '2'|\+ 2" backend/routes backend/services backend -g '!**/__pycache__/**'
rg -n 'fornecedores/\$\{|/fornecedores/|href=.*fornecedores|cnpj \+|padStart|dvVerificador|digitoExtra' frontend/app frontend/components frontend/lib -g '!**/.next/**'
rg -n '\$\{cnpj\}|cnpj \+|padStart|dvVerificador|digitoExtra' frontend/app/fornecedores frontend/app/orgaos frontend/components/blog backend/routes/sitemap_cnpjs.py backend/routes/contratos_publicos.py
```
