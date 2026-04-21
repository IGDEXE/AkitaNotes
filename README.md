# AkitaNotes

Script para exportar as postagens da seção `Akitando` do blog do Akita para arquivos Markdown.

## Uso

```powershell
py scripts/export_akita_akitando.py
```

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

- `Veracode SCA`
- `Veracode Upload and Scan`
- `Veracode Pipeline Scan`

Ordem dos estágios:

- `veracode-package`: monta o zip que a Veracode vai analisar
- `veracode-sca`
- `veracode-upload-and-scan`
- `veracode-pipeline-scan`
- `package`: só executa se todas as validações anteriores passarem

Secrets esperados no repositório:

- `SCA`
- `VeracodeID`
- `VeracodeKey`
