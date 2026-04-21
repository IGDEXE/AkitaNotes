# AkitaNotes

Script para exportar as postagens da seção `Akitando` do blog do Akita para arquivos Markdown.

## Quem é o Akita

Fabio Akita, conhecido como Akita, é um desenvolvedor de software, empreendedor e criador de conteúdo brasileiro bastante conhecido na comunidade de tecnologia. Ele ficou popular por compartilhar opiniões técnicas diretas, análises de carreira, arquitetura de software, cultura de engenharia e fundamentos de computação, tanto no blog `AkitaOnRails` quanto no canal `Akitando`.

Neste projeto, a ideia é transformar os posts dessa série em arquivos Markdown para facilitar consumo posterior, indexação, busca e processos de destilação de informação.

## Uso

```powershell
py scripts/export_akita_akitando.py
```

Dependências de runtime:

- nenhuma dependência externa; o script usa apenas a biblioteca padrão do Python
- o arquivo `requirements.txt` existe para ferramentas de SCA reconhecerem o projeto como Python

Arquivos de saída:

- `output/akitando/*.md`
- `output/akitando/manifest.json`

Opções úteis:

```powershell
py scripts/export_akita_akitando.py --max-posts 3
py scripts/export_akita_akitando.py --out-dir data/akitando --overwrite
```

## GitHub Actions

O workflow [publish-akitando-zip.yml](/c:/LocalGit/AkitaNotes/.github/workflows/publish-akitando-zip.yml) primeiro executa as validações de segurança da Veracode e só então gera a estrutura em `dist/akitando/`, empacota em `.zip` e publica o arquivo como artifact do GitHub Actions.

Você pode rodar de dois jeitos:

- manualmente, em `Actions > Publish Akitando Zip > Run workflow`
- automaticamente em push para `main` quando o script ou o workflow forem alterados

O artifact publicado se chama `akitando-export-zip`.

Validações de segurança adicionadas no mesmo workflow:

- `Veracode SCA` opcional para projetos sem dependências externas suportadas
- `Veracode Upload and Scan`
- `Veracode Pipeline Scan`

Ordem dos estágios:

- `veracode-package`: monta o zip que a Veracode vai analisar
- `veracode-sca` opcional, não bloqueia a publicação do artefato
- `veracode-upload-and-scan`
- `veracode-pipeline-scan`
- `package`: só executa se todas as validações anteriores passarem

Secrets esperados no repositório:

- `SCA`
- `VeracodeID`
- `VeracodeKey`
